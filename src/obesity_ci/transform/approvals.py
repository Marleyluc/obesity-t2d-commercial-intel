"""Turn a raw openFDA snapshot into tidy US approval tables (M3, chunk 2).

fda_applications      one row per FDA application (NDA, BLA or ANDA): sponsor, brands,
                      first approval date, current marketing status, molecules
fda_app_molecules     one row per (application, molecule) link, with class
fda_events            one row per submission: original approval, tentative approval,
                      efficacy supplement (usually a new indication or population),
                      labelling or manufacturing change
fda_labels            current label per brand: indications text, "recent major changes",
                      boxed warning; is_primary marks the application holder's own label

Rules (see docs/M3_DECISIONS.md):
- Molecules come from each product's active ingredients, not from which search found it.
  A combination needs all its parts in the same product (Xultophy = degludec + liraglutide),
  and then absorbs them, as in the trials table.
- "oral semaglutide" vs "semaglutide" is decided by the product route (Rybelsus, oral
  Wegovy) because the ingredient name is the same.
- Approval status always comes from here, never from the config.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from obesity_ci import config, snapshots
from obesity_ci.sources.ctgov import slug
from obesity_ci.transform.trials import parts_of, term_pattern

SOURCE = "openfda"

EVENT_TYPES = {"EFFICACY": "Efficacy supplement", "LABELING": "Labeling change",
               "MANUF (CMC)": "Manufacturing change", "REMS": "REMS change"}
# Regulators' own names for human insulins, which share no word with our generic names
# (FDA: "INSULIN SUSP ISOPHANE RECOMBINANT HUMAN"; Health Canada: "INSULIN NPH HUMAN DNA ORIGIN").
# "insulin human" must not match NPH ("INSULIN SUSP ISOPHANE RECOMBINANT HUMAN"): the
# patterns require the words to be adjacent, so it doesn't.
FDA_INGREDIENT_ALIASES = {
    "insulin regular": ["insulin human", "insulin recombinant human"],
    "insulin isophane (nph)": ["insulin susp isophane", "isophane insulin", "insulin nph"],
}
# Label publishers that repackage someone else's drug (seen in the 2026-11-24 pull).
REPACKAGERS = r"repack|medication solutions|aphena|cardinal health|redpharm|bryant ranch|proficient rx|quality care|preferred pharmaceuticals|direct.?rx|henry schein"
# Best status wins when an application has several products.
STATUS_ORDER = ["Prescription", "Over-the-counter", "None (Tentative Approval)", "Discontinued"]


def fda_date(s: str | None):
    return pd.to_datetime(s, format="%Y%m%d", errors="coerce") if s else pd.NaT


def event_type(sub: dict) -> str:
    if sub.get("submission_type") == "ORIG":
        return "Tentative approval" if sub.get("submission_status") == "TA" else "Original approval"
    return EVENT_TYPES.get(sub.get("submission_class_code"), "Other supplement")


# ---------- molecule matching from ingredients ----------

def build_matchers(mols: pd.DataFrame) -> list[dict]:
    generics = set(mols["generic"])
    out = []
    for _, m in mols.iterrows():
        g = m["generic"]
        oral = g.startswith("oral ")
        base = g[len("oral "):] if oral else g
        parts = [p.strip() for p in re.sub(r"\(.*?\)", "", base).split("/")]
        alt = [term_pattern(a) for a in FDA_INGREDIENT_ALIASES.get(g, [])]
        out.append({"generic": g, "class_id": m["class_id"],
                    "part_patterns": [term_pattern(p) for p in parts], "alt_patterns": alt,
                    "needs_oral": oral,
                    # plain "semaglutide" yields to "oral semaglutide" for oral products
                    "not_oral": (f"oral {g}" in generics),
                    "absorbs": parts_of(g)})
    return out


def match_product(ingredients: list[str], route: str | None, matchers: list[dict]) -> set[str]:
    ings = [i.lower() for i in ingredients]
    is_oral = "oral" in (route or "").lower()
    hits = set()
    for m in matchers:
        if m["needs_oral"] and not is_oral or m["not_oral"] and is_oral:
            continue
        if (all(any(p.search(i) for i in ings) for p in m["part_patterns"])
                or any(p.search(i) for p in m["alt_patterns"] for i in ings)):
            hits.add(m["generic"])
    absorbed = set().union(*(m["absorbs"] for m in matchers if m["generic"] in hits)) if hits else set()
    return hits - absorbed


# ---------- snapshot ----------

def load(folder: Path) -> tuple[dict[str, dict], list[tuple[str, dict]]]:
    apps, labels = {}, []
    for f in sorted(folder.glob("*.json")):
        if f.name == "manifest.json":
            continue
        results = json.loads(f.read_text(encoding="utf-8")).get("results") or []
        if f.stem.startswith("approvals__"):
            for r in results:
                apps[r["application_number"]] = r
        elif f.stem.startswith("label__"):
            labels += [(f.stem[len("label__"):], r) for r in results]
    return apps, labels


def _first(lst):
    return lst[0] if isinstance(lst, list) and lst else None


def brand_applications(apps: dict[str, dict]) -> dict[str, dict[str, dict]]:
    """brand slug -> {application number: {sponsor, oral, n_rx}} for branded (non-ANDA) applications.

    One brand can sit on several applications (2026-11-24: Ozempic injection NDA209637 and
    Ozempic tablets NDA213051; Wegovy injection and tablets; two Levemir BLAs).
    """
    out: dict[str, dict[str, dict]] = {}
    for num, a in apps.items():
        if num.startswith("ANDA"):
            continue
        for p in a.get("products", []) or []:
            if not p.get("brand_name"):
                continue
            e = out.setdefault(slug(p["brand_name"]), {}).setdefault(
                num, {"sponsor": a.get("sponsor_name"), "oral": False, "n_rx": 0})
            e["oral"] |= "ORAL" in (p.get("route") or "").upper()
            e["n_rx"] += p.get("marketing_status") == "Prescription"
    return out


def guess_application(label: dict, known: dict[str, dict]) -> str | None:
    """For a label with no openFDA index: pick the brand's application by dosage form
    (more "tablet" than "inject" wording = oral application), then the one with most marketed products, then lowest number."""
    if not known:
        return None
    text = " ".join(" ".join(label.get(f) or []) for f in
                    ("spl_product_data_elements", "dosage_forms_and_strengths", "description",
                     "package_label_principal_display_panel"))
    oral = len(re.findall(r"\btablets?\b", text, flags=re.I)) > len(re.findall(r"\binject", text, flags=re.I))
    cands = [n for n, e in known.items() if e["oral"] == oral] or list(known)
    return sorted(cands, key=lambda n: (-known[n]["n_rx"], n))[0]


def label_rows(labels: list[tuple[str, dict]], apps: dict[str, dict] | None = None) -> pd.DataFrame:
    by_brand = brand_applications(apps or {})
    rows = []
    for brand_query, r in labels:
        o = r.get("openfda") or {}
        known = by_brand.get(brand_query, {})
        app, maker, source = _first(o.get("application_number")), _first(o.get("manufacturer_name")), "openFDA index"
        if not o:
            # Label not in openFDA's harmonised index: take the application from Drugs@FDA
            # (see guess_application) and its sponsor as the manufacturer. Repackagers are
            # still caught from the label's own package panel text.
            source = "Drugs@FDA (label not indexed)"
            app = guess_application(r, known)
            maker = known[app]["sponsor"] if app else None
            panel = " ".join(r.get("package_label_principal_display_panel") or [])
            if re.search(REPACKAGERS, panel, flags=re.I):
                maker = f"repackager (from package text): {maker or ''}".strip()
        rows.append({
            "brand_query": brand_query,
            "brand_names": "; ".join(o.get("brand_name", [])),
            "application_number": app,
            "manufacturer": maker,
            "manufacturer_source": source,
            # A label found under one brand but filed under another brand's application
            # (e.g. a Rybelsus label that also lists Ozempic) can't be that brand's primary label.
            "app_matches_brand": (not known) or app in known,
            "set_id": r.get("set_id"),
            "version": int(r["version"]) if str(r.get("version", "")).isdigit() else None,
            "effective_date": fda_date(r.get("effective_time")),
            "indications": _first(r.get("indications_and_usage")),
            "recent_major_changes": _first(r.get("recent_major_changes")),
            "has_boxed_warning": bool(r.get("boxed_warning")),
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    # Repackagers (pharmacies, distributors) publish copies of a label under their own
    # set_id. The primary label is the most recent label from a non-repackager, per
    # (brand, application). If only repackager copies came back, we keep the best one but
    # flag it: the manufacturer's own label is then missing from our pull.
    # A label from a repackager or under another brand's application is never primary unless nothing
    # better exists for that (brand, application); labels with no application at all are never primary.
    df["is_repackager"] = df["manufacturer"].fillna("").str.contains(REPACKAGERS, case=False, regex=True)
    # Newest effective date first: version numbers only count within one document (set_id), and
    # Novo keeps several Levemir documents (a 2022 one at version 30, a 2026 one at version 26).
    df = df.sort_values(["brand_query", "application_number", "is_repackager", "effective_date", "version"],
                        ascending=[True, True, True, False, False])
    df["is_primary"] = (~df.duplicated(["brand_query", "application_number"]) & df["app_matches_brand"]
                        & df["application_number"].notna())
    return df.reset_index(drop=True)


def build(folder: Path, mols: pd.DataFrame | None = None) -> dict[str, pd.DataFrame]:
    mols = config.molecules() if mols is None else mols
    matchers = build_matchers(mols)
    class_of = dict(zip(mols["generic"], mols["class_id"]))
    apps, labels = load(folder)

    app_rows, links, events = [], [], []
    for num, a in apps.items():
        products = a.get("products", []) or []
        hits = set()
        for p in products:
            hits |= match_product([i.get("name", "") for i in p.get("active_ingredients", []) or []],
                                  p.get("route"), matchers)
        statuses = {p.get("marketing_status") for p in products}
        subs = a.get("submissions", []) or []
        orig = [s for s in subs if s.get("submission_type") == "ORIG"]
        ap = [fda_date(s.get("submission_status_date")) for s in orig if s.get("submission_status") == "AP"]
        ta = [fda_date(s.get("submission_status_date")) for s in orig if s.get("submission_status") == "TA"]
        app_rows.append({
            "application_number": num,
            "app_type": re.match(r"[A-Z]+", num).group(0),
            "sponsor": a.get("sponsor_name"),
            "brands": "; ".join(sorted({p.get("brand_name", "") for p in products})),
            "ingredients": "; ".join(sorted({i.get("name", "") for p in products
                                             for i in p.get("active_ingredients", []) or []})),
            "routes": "; ".join(sorted({p.get("route") or "" for p in products} - {""})),
            "marketing_status": next((s for s in STATUS_ORDER if s in statuses), None),
            "first_approval_date": min(ap) if ap else pd.NaT,
            "tentative_approval_date": min(ta) if ta else pd.NaT,
            "molecules": "; ".join(sorted(hits)),
            "n_molecules": len(hits),
        })
        links += [{"application_number": num, "generic": g, "class_id": class_of[g]} for g in sorted(hits)]
        for s in subs:
            events.append({
                "application_number": num,
                "submission": f"{s.get('submission_type')}-{s.get('submission_number')}",
                "status": s.get("submission_status"),
                "date": fda_date(s.get("submission_status_date")),
                "event_type": event_type(s),
                "class_code": s.get("submission_class_code"),
                "review_priority": s.get("review_priority"),
                "letter_url": next((d.get("url") for d in s.get("application_docs", []) or []
                                    if d.get("type") == "Letter"), None),
            })

    applications = pd.DataFrame(app_rows).sort_values("application_number").reset_index(drop=True)
    return {
        "fda_applications": applications,
        "fda_app_molecules": pd.DataFrame(links, columns=["application_number", "generic", "class_id"]),
        "fda_events": pd.DataFrame(events).sort_values(["date", "application_number"],
                                                       ascending=[False, True]).reset_index(drop=True),
        "fda_labels": label_rows(labels, apps),
    }


def run(snapshot: str | None = None) -> dict:
    """Build tables for one snapshot (default: latest) into data/interim/openfda/<date>/."""
    snaps = snapshots.list_snapshots(SOURCE)
    if not snaps:
        raise RuntimeError("No openFDA snapshot found. Run scripts/pull_openfda.py first.")
    folder = next((p for p in snaps if p.name == snapshot), None) if snapshot else snaps[-1]
    if folder is None:
        raise RuntimeError(f"No snapshot {snapshot}. Available: {[p.name for p in snaps]}")
    tables = build(folder)
    out = config.path("interim") / SOURCE / folder.name
    out.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_parquet(out / f"{name}.parquet", index=False)
    return {"snapshot": folder.name, "out": out, **tables}
