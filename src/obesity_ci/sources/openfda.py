"""openFDA puller: US approvals (Drugs@FDA) and drug labels.

Two endpoints, both saved raw:
1. drug/drugsfda: one record per FDA application (NDA, BLA or ANDA), with every
   submission: the original approval and each later supplement (new indications,
   new doses, label changes). This is our approval history.
2. drug/label: the current prescribing information (indications, boxed warnings,
   dosing) for each brand. M3 diffs labels between snapshots to spot label changes.

Approval status is never hard-coded in the config: it comes from here, so the
dashboard can't go stale.

API docs: https://open.fda.gov/apis/drug/
"""

from __future__ import annotations

import re
from datetime import date

from obesity_ci import config, snapshots
from obesity_ci.http import PoliteSession
from obesity_ci.sources.ctgov import slug

SOURCE = "openfda"


def _fda_name(name: str) -> str:
    """openFDA writes combinations as 'A AND B' and has no parenthetical notes."""
    name = re.sub(r"\(.*?\)", "", name).strip()
    name = re.sub(r"^oral\s+", "", name)  # Rybelsus is listed under plain 'semaglutide'
    return name.replace("/", " and ")


def approvals_search(row) -> str:
    """Search string for drug/drugsfda. Space between clauses means OR in openFDA syntax.

    We search two places for each name. The `openfda.*` fields are a harmonised layer that
    is missing on some records (tested 2026-11-24: Ozempic and Wegovy were not found via
    openfda.brand_name), so we also search the application's own `products.*` fields.
    """
    name = _fda_name(row["generic"])
    clauses = [f'openfda.generic_name:"{name}"', f'products.active_ingredients.name:"{name}"']
    for b in row["brands"]:
        clauses += [f'openfda.brand_name:"{b}"', f'products.brand_name:"{b}"']
    return " ".join(clauses)


def label_search(brand: str) -> str:
    return f'openfda.brand_name:"{brand}"'


def build_queries() -> list[dict]:
    queries = []
    for _, row in config.molecules().iterrows():
        queries.append({"name": f"approvals__{slug(row['generic'])}", "endpoint": "drug/drugsfda",
                        "class_id": row["class_id"], "generic": row["generic"],
                        "params": {"search": approvals_search(row)}})
        for brand in row["brands"]:
            queries.append({"name": f"label__{slug(brand)}", "endpoint": "drug/label",
                            "class_id": row["class_id"], "generic": row["generic"], "brand": brand,
                            "params": {"search": label_search(brand)}})
    return queries


def fetch_all(session, endpoint: str, params: dict) -> tuple[list[dict], int]:
    """openFDA pages with limit/skip. A 404 means 'no matches', which is normal for pipeline assets."""
    st = config.settings()["sources"]["openfda"]
    url = f"{st['base_url']}/{endpoint}.json"
    key = config.secrets().openfda_api_key
    results, skip, total = [], 0, 0
    while True:
        p = {**params, "limit": st["page_limit"], "skip": skip, **({"api_key": key} if key else {})}
        page = session.get_json(url, params=p, none_on_404=True)
        if page is None:
            return results, total
        total = page["meta"]["results"]["total"]
        results.extend(page["results"])
        skip += st["page_limit"]
        if skip >= total:
            return results, total


def pull(snapshot_date: date | None = None, only: str | None = None, session=None) -> dict:
    st = config.settings()["sources"]["openfda"]
    session = session or PoliteSession(delay_s=st["request_delay_s"])
    folder = snapshots.snapshot_dir(SOURCE, snapshot_date)
    queries = [q for q in build_queries() if not only or only.lower() in q["name"]]
    if not queries:
        raise ValueError(f"No query matches only={only!r}")
    if not only:
        for old in folder.glob("*.json"):
            old.unlink()

    entries = []
    for i, q in enumerate(queries, 1):
        results, total = fetch_all(session, q["endpoint"], q["params"])
        out = folder / f"{q['name']}.json"
        snapshots.write_json(out, {"query": q, "results": results})
        entries.append({**q, "file": out.name, "n_results": len(results), "api_total": total,
                        "complete": len(results) == total})
        note = ""
        if not results:
            marketed = q["endpoint"] == "drug/label" or bool(config.molecules().set_index("generic").loc[q["generic"], "brands"])
            note = ("  <-- none found: brand discontinued, renamed, or not FDA-approved? check"
                    if marketed else "  (none: expected for pipeline assets)")
        if results and len(results) != total:
            note = f"  <-- WARNING: API reported {total}"
        print(f"[{i:>3}/{len(queries)}] {q['name']:<45} {len(results):>5}{note}")

    snapshots.write_manifest(folder, SOURCE, entries)
    n_apps = sum(e["n_results"] for e in entries if e["endpoint"] == "drug/drugsfda")
    print(f"\nSaved {len(entries)} files to {folder}\nApplications found: {n_apps}")
    return {"folder": str(folder), "files": entries}
