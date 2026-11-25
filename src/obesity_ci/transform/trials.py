"""Turn a raw ClinicalTrials.gov snapshot into two tidy tables (M3, chunk 1).

trials           one row per trial (NCT ID): status, phase, dates, sponsor, countries...
trial_molecules  one row per (trial, molecule) link, with class and whether the lead
                 sponsor is the molecule's originator

Rules (see docs/M3_DECISIONS.md):
- We decide which molecule a trial is about by matching our own names (generic, brands,
  code names) against the trial's listed interventions. Which search returned the trial
  is kept for traceability but NOT trusted, because the API expands search terms.
- Only molecules with track_trials = true are linked. Legacy agents (metformin, insulin
  regular, ...) mostly appear as background or comparator therapy.
- A combination absorbs its parts: a CagriSema trial links to cagrilintide/semaglutide,
  not also to semaglutide and cagrilintide. Same for "oral semaglutide" vs semaglutide.
- Trials with no phase (observational, or "NA") are kept and labelled "Not applicable".
- Trials that match no molecule are written out separately: they are where new code
  names and new entrants show up.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from obesity_ci import config, snapshots

SOURCE = "ctgov"

PHASE_LABELS = {  # set of API phase codes -> label, rank (for "highest phase" sorting)
    frozenset({"EARLY_PHASE1"}): ("Phase 1", 1),
    frozenset({"PHASE1"}): ("Phase 1", 1),
    frozenset({"EARLY_PHASE1", "PHASE1"}): ("Phase 1", 1),
    frozenset({"PHASE1", "PHASE2"}): ("Phase 1/2", 1.5),
    frozenset({"PHASE2"}): ("Phase 2", 2),
    frozenset({"PHASE2", "PHASE3"}): ("Phase 2/3", 2.5),
    frozenset({"PHASE3"}): ("Phase 3", 3),
    frozenset({"PHASE4"}): ("Phase 4", 4),
}
# Intervention types that cannot be "the drug" of a trial.
NON_DRUG_TYPES = {"BEHAVIORAL", "PROCEDURE", "DEVICE", "DIAGNOSTIC_TEST", "RADIATION", "GENETIC"}


# ---------- one study -> one flat row ----------

def phase_label(phases: list[str] | None) -> tuple[str, float]:
    codes = frozenset(p for p in (phases or []) if p != "NA")
    return PHASE_LABELS.get(codes, ("Not applicable", 0) if not codes else ("Other", 0))


def flatten(study: dict) -> dict:
    ps = study.get("protocolSection", {})
    ident, status = ps.get("identificationModule", {}), ps.get("statusModule", {})
    spons, design = ps.get("sponsorCollaboratorsModule", {}), ps.get("designModule", {})
    interventions = ps.get("armsInterventionsModule", {}).get("interventions", []) or []
    countries = sorted({loc.get("country") for loc in
                        ps.get("contactsLocationsModule", {}).get("locations", []) or [] if loc.get("country")})
    phase, rank = phase_label(design.get("phases"))

    def d(key):
        return (status.get(key) or {}).get("date")

    return {
        "nct_id": ident.get("nctId"),
        "title": ident.get("briefTitle"),
        "acronym": ident.get("acronym"),
        "status": status.get("overallStatus"),
        "why_stopped": status.get("whyStopped"),
        "phase": phase,
        "phase_rank": rank,
        "phases_raw": "|".join(design.get("phases") or []),
        "study_type": design.get("studyType"),
        "start_date": d("startDateStruct"),
        "primary_completion_date": d("primaryCompletionDateStruct"),
        "completion_date": d("completionDateStruct"),
        "first_posted": d("studyFirstPostDateStruct"),
        "last_updated": d("lastUpdatePostDateStruct"),
        "lead_sponsor": (spons.get("leadSponsor") or {}).get("name"),
        "sponsor_class": (spons.get("leadSponsor") or {}).get("class"),
        "collaborators": "; ".join(c.get("name", "") for c in spons.get("collaborators", []) or []),
        "conditions": "; ".join(ps.get("conditionsModule", {}).get("conditions", []) or []),
        "interventions": "; ".join(i.get("name", "") for i in interventions),
        "drug_interventions": [i.get("name", "") for i in interventions
                               if (i.get("type") or "").upper() not in NON_DRUG_TYPES],
        "enrollment": (design.get("enrollmentInfo") or {}).get("count"),
        "countries": "; ".join(countries),
        "n_countries": len(countries),
        "has_canada_site": "Canada" in countries,
        "has_results": bool(study.get("hasResults")),
    }


# ---------- molecule matching ----------

def term_pattern(term: str) -> re.Pattern:
    """Regex for one name that tolerates spacing/hyphen differences.

    "BI 456906" matches "BI456906", "BI-456906" and "bi 456906";
    "semaglutide" matches inside "Cagrilintide/Semaglutide" but not inside "xsemaglutidey".
    """
    tokens = re.findall(r"[a-z]+|\d+", re.sub(r"\(.*?\)", "", term.lower()))
    return re.compile(r"(?<![a-z0-9])" + r"[\W_]*".join(tokens) + r"(?![a-z0-9])")


def parts_of(generic: str) -> set[str]:
    """Molecules a molecule 'contains': components of a combination, and X for 'oral X'."""
    g = re.sub(r"\(.*?\)", "", generic).strip()
    out = {p.strip() for p in g.split("/")} if "/" in g else set()
    if g.startswith("oral "):
        out.add(g[len("oral "):])
    return out


def build_matchers(mols: pd.DataFrame) -> list[dict]:
    out = []
    for _, m in mols[mols["track_trials"]].iterrows():
        names = [m["generic"], *m["brands"], *m["aliases"]]
        out.append({"generic": m["generic"], "class_id": m["class_id"], "sponsor": m["sponsor"],
                    "patterns": [term_pattern(n) for n in names if n.strip()],
                    "parts": parts_of(m["generic"])})
    return out


def match_molecules(intervention_names: list[str], matchers: list[dict]) -> list[str]:
    text = " ; ".join(intervention_names).lower()
    hits = {m["generic"] for m in matchers if any(p.search(text) for p in m["patterns"])}
    absorbed = set().union(*(m["parts"] for m in matchers if m["generic"] in hits)) if hits else set()
    return sorted(hits - absorbed)


def sponsor_is_originator(lead_sponsor: str | None, originator: str) -> bool:
    """'Eli Lilly and Company' vs config 'Eli Lilly' -> True. Config may list 'A / B'."""
    if not lead_sponsor:
        return False
    lead = lead_sponsor.lower()
    return any(p.strip().lower() and p.strip().lower() in lead
               for p in re.split(r"/", re.sub(r"\(.*?\)", "", originator)))


# ---------- whole snapshot ----------

def load_studies(folder: Path) -> tuple[dict[str, dict], dict[str, list[str]]]:
    """All unique studies in a snapshot, plus which queries found each one."""
    studies, found_by = {}, {}
    for f in sorted(folder.glob("*.json")):
        if f.name == "manifest.json":
            continue
        for s in json.loads(f.read_text(encoding="utf-8")).get("studies", []):
            nct = s["protocolSection"]["identificationModule"]["nctId"]
            studies[nct] = s
            found_by.setdefault(nct, []).append(f.stem)
    return studies, found_by


def build(folder: Path, mols: pd.DataFrame | None = None) -> dict[str, pd.DataFrame]:
    mols = config.molecules() if mols is None else mols
    matchers = build_matchers(mols)
    by_generic = {m["generic"]: m for m in matchers}
    studies, found_by = load_studies(folder)

    rows, links = [], []
    for nct, s in studies.items():
        r = flatten(s)
        r["found_by"] = "; ".join(sorted(found_by[nct]))
        hits = match_molecules(r.pop("drug_interventions"), matchers)
        r["molecules"] = "; ".join(hits)
        r["n_molecules"] = len(hits)
        rows.append(r)
        for g in hits:
            m = by_generic[g]
            links.append({"nct_id": nct, "generic": g, "class_id": m["class_id"],
                          "sponsor_is_originator": sponsor_is_originator(r["lead_sponsor"], m["sponsor"])})

    trials = pd.DataFrame(rows)
    for c in ["start_date", "primary_completion_date", "completion_date", "first_posted", "last_updated"]:
        # CT.gov dates can be "2026-02" (month only): parsed as the 1st of the month.
        trials[c] = pd.to_datetime(trials[c], format="ISO8601", errors="coerce")
    trials = trials.sort_values("nct_id").reset_index(drop=True)
    links_df = pd.DataFrame(links, columns=["nct_id", "generic", "class_id", "sponsor_is_originator"])
    unmatched = trials[(trials["n_molecules"] == 0)].sort_values(
        ["phase_rank", "start_date"], ascending=[False, False])
    return {"trials": trials, "trial_molecules": links_df, "unmatched": unmatched}


def run(snapshot: str | None = None) -> dict:
    """Build tables for one snapshot (default: latest) into data/interim/ctgov/<date>/."""
    snaps = snapshots.list_snapshots(SOURCE)
    if not snaps:
        raise RuntimeError("No ClinicalTrials.gov snapshot found. Run scripts/pull_ctgov.py first.")
    folder = next((p for p in snaps if p.name == snapshot), None) if snapshot else snaps[-1]
    if folder is None:
        raise RuntimeError(f"No snapshot {snapshot}. Available: {[p.name for p in snaps]}")
    tables = build(folder)
    out = config.path("interim") / SOURCE / folder.name
    out.mkdir(parents=True, exist_ok=True)
    tables["trials"].to_parquet(out / "trials.parquet", index=False)
    tables["trial_molecules"].to_parquet(out / "trial_molecules.parquet", index=False)
    cols = ["nct_id", "phase", "status", "lead_sponsor", "sponsor_class", "start_date",
            "title", "interventions", "found_by"]
    tables["unmatched"][cols].to_csv(out / "trials_unmatched.csv", index=False)
    return {"snapshot": folder.name, "out": out, **tables}
