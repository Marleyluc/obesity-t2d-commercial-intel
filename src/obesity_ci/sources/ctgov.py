"""ClinicalTrials.gov API v2 puller.

Two kinds of query, both saved raw:
1. Molecule queries: one per tracked molecule in drug_classes.yaml, searching the
   intervention field for its generic name, brand names and code names.
2. Condition sweeps: recent interventional Phase 2/3 trials for obesity and T2D,
   to catch new entrants whose names are not in our config yet.

The same trial can appear in several queries (e.g. a semaglutide vs tirzepatide
head-to-head). That is fine: de-duplication happens in M3, and keeping the query
that found each trial tells us WHY it is in our dataset.

API docs: https://clinicaltrials.gov/data-api/api
"""

from __future__ import annotations

import json
import re
from datetime import date

from obesity_ci import config, snapshots
from obesity_ci.http import PoliteSession

SOURCE = "ctgov"


def _clean_term(term: str) -> str:
    """Make one search term safe for the API's query syntax.

    Drops parenthetical notes ("insulin isophane (NPH)" -> "insulin isophane"),
    and wraps multi-word or punctuated terms in quotes so they are searched as a phrase.
    """
    term = re.sub(r"\(.*?\)", "", term).strip()
    if re.search(r"[\s/\-]", term):
        return f'"{term}"'
    return term


def molecule_search_terms(row) -> list[str]:
    terms = [row["generic"], *row["brands"], *row["aliases"]]
    seen, out = set(), []
    for t in terms:
        c = _clean_term(t)
        if c and c.lower() not in seen:
            seen.add(c.lower())
            out.append(c)
    return out


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def build_queries() -> list[dict]:
    """Every query we send, as plain data. Easy to inspect, test and log."""
    st = config.settings()["sources"]["ctgov"]
    queries = []
    mols = config.molecules()
    for _, row in mols[mols["track_trials"]].iterrows():
        queries.append(
            {
                "name": f"molecule__{slug(row['generic'])}",
                "kind": "molecule",
                "class_id": row["class_id"],
                "generic": row["generic"],
                "params": {"query.intr": " OR ".join(molecule_search_terms(row))},
            }
        )
    for cond in config.drug_config()["trial_conditions"]:
        queries.append(
            {
                "name": f"condition__{slug(cond)}",
                "kind": "condition",
                "params": {"query.cond": cond, "filter.advanced": st["condition_filter"]},
            }
        )
    return queries


def fetch_all_pages(session: PoliteSession, params: dict) -> tuple[list[dict], int | None]:
    """Follow nextPageToken until the API says there are no more pages."""
    st = config.settings()["sources"]["ctgov"]
    url = f"{st['base_url']}/studies"
    base = {
        **params,
        "pageSize": st["page_size"],
        "countTotal": "true",
        "fields": ",".join(st["fields"]),
        "format": "json",
    }
    studies, total, token = [], None, None
    while True:
        page = session.get_json(url, params={**base, **({"pageToken": token} if token else {})})
        if total is None:
            total = page.get("totalCount")
        studies.extend(page.get("studies", []))
        token = page.get("nextPageToken")
        if not token:
            return studies, total


def pull(snapshot_date: date | None = None, only: str | None = None, session=None) -> dict:
    """Run every query and save one raw JSON file per query plus a manifest.

    only: optional substring to run a subset, e.g. only="tirzepatide" for a quick test.
    Returns the manifest as a dict.
    """
    st = config.settings()["sources"]["ctgov"]
    session = session or PoliteSession(delay_s=st["request_delay_s"])
    folder = snapshots.snapshot_dir(SOURCE, snapshot_date)
    queries = [q for q in build_queries() if not only or only.lower() in q["name"]]
    if not queries:
        raise ValueError(f"No query matches only={only!r}")

    if not only:
        # A snapshot is one complete run. Re-running on the same day replaces that day's
        # files, so files from queries we have since removed can't linger in the folder.
        for old in folder.glob("*.json"):
            old.unlink()

    entries = []
    for i, q in enumerate(queries, 1):
        studies, total = fetch_all_pages(session, q["params"])
        out = folder / f"{q['name']}.json"
        snapshots.write_json(out, {"query": q, "studies": studies})
        complete = total is None or len(studies) == total
        entries.append({**q, "file": out.name, "n_studies": len(studies),
                        "api_total": total, "complete": complete})
        flag = "" if complete else f"  <-- WARNING: API reported {total}"
        print(f"[{i:>2}/{len(queries)}] {q['name']:<45} {len(studies):>5} studies{flag}")

    snapshots.write_manifest(folder, SOURCE, entries, extra={"fields": st["fields"]})
    unique = len({s["protocolSection"]["identificationModule"]["nctId"]
                  for e in entries for s in _load(folder / e["file"])})
    print(f"\nSaved {len(entries)} files to {folder}\nUnique trials across all queries: {unique}")
    return {"folder": str(folder), "files": entries, "unique_trials": unique}


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))["studies"]
