"""Health Canada Drug Product Database (DPD) puller: Canadian approvals.

The DPD API is keyed by `drug_code` (one per product, e.g. each strength/form a company
sells). So a pull is two stages:
1. Find drug codes: search by ingredient name (newer classes) and by brand name (all
   molecules with brands).
2. Look up each drug code: product details (brand, company, DIN), its status history
   (Approved / Marketed / Cancelled, with original market date) and its full list of
   active ingredients (to recognise combination products).

The original market date is what M3 compares with the FDA approval date to measure
Canada's approval/launch lag.

API docs: https://health-products.canada.ca/api/documentation/dpd-documentation-en.html
"""

from __future__ import annotations

import re
from datetime import date

from obesity_ci import config, snapshots
from obesity_ci.http import PoliteSession
from obesity_ci.sources.ctgov import slug

SOURCE = "hc_dpd"


def _as_list(payload) -> list[dict]:
    """The API returns a list for searches and sometimes a single object for id lookups."""
    if payload is None:
        return []
    return payload if isinstance(payload, list) else [payload]


def _ingredient_term(generic: str) -> str:
    """DPD ingredient search is a contains-match on one name. For combinations
    ('cagrilintide/semaglutide') we search the first component and keep only products
    that contain every component (filtered in M3 using the saved ingredient lists)."""
    name = re.sub(r"\(.*?\)", "", generic).strip()
    name = re.sub(r"^oral\s+", "", name)
    return name.split("/")[0].strip()


def build_searches() -> list[dict]:
    gens = set(config.settings()["sources"]["hc_dpd"]["ingredient_search_generations"])
    out = []
    for _, row in config.molecules().iterrows():
        s = {"name": slug(row["generic"]), "class_id": row["class_id"], "generic": row["generic"],
             "ingredient": _ingredient_term(row["generic"]) if row["generation"] in gens else None,
             "brands": list(row["brands"])}
        if s["ingredient"] or s["brands"]:
            out.append(s)
    return out


class DPD:
    def __init__(self, session):
        self.session = session
        self.base = config.settings()["sources"]["hc_dpd"]["base_url"]

    def get(self, endpoint: str, **params) -> list[dict]:
        payload = self.session.get_json(f"{self.base}/{endpoint}/",
                                        params={**params, "lang": "en", "type": "json"},
                                        none_on_404=True)
        return _as_list(payload)


def find_drug_codes(dpd: DPD, search: dict) -> dict[int, str]:
    """drug_code -> how we found it (kept so M3 can explain every match)."""
    codes: dict[int, str] = {}
    if search["ingredient"]:
        for r in dpd.get("activeingredient", ingredientname=search["ingredient"]):
            codes.setdefault(int(r["drug_code"]), f"ingredient:{search['ingredient']}")
    for brand in search["brands"]:
        for r in dpd.get("drugproduct", brandname=brand):
            if brand_matches(r.get("brand_name", ""), brand):
                codes.setdefault(int(r["drug_code"]), f"brand:{brand}")
    return codes


def brand_matches(product_brand: str, brand: str) -> bool:
    """The API's brand search is a contains-match, so 'Alli' also returns 'ALLIUM CEPA' and
    'PLUMBUM METALLICUM' (found 2026-11-24: 191 orlistat 'products', mostly homeopathics).
    Keep only the brand itself or the brand followed by a word ('MOUNJARO KWIKPEN')."""
    p, b = product_brand.upper().strip(), brand.upper().strip()
    return p == b or p.startswith(b + " ")


def pull(snapshot_date: date | None = None, only: str | None = None, session=None) -> dict:
    st = config.settings()["sources"]["hc_dpd"]
    dpd = DPD(session or PoliteSession(delay_s=st["request_delay_s"]))
    folder = snapshots.snapshot_dir(SOURCE, snapshot_date)
    searches = [s for s in build_searches() if not only or only.lower() in s["name"]]
    if not searches:
        raise ValueError(f"No molecule matches only={only!r}")
    if not only:
        for old in folder.glob("*.json"):
            old.unlink()

    entries = []
    for i, s in enumerate(searches, 1):
        codes = find_drug_codes(dpd, s)
        products = []
        for code, found_by in sorted(codes.items()):
            products.append({
                "drug_code": code,
                "found_by": found_by,
                "product": dpd.get("drugproduct", id=code),
                "status": dpd.get("status", id=code),
                "ingredients": dpd.get("activeingredient", id=code),
            })
        out = folder / f"{s['name']}.json"
        snapshots.write_json(out, {"search": s, "products": products})
        marketed = sum(any(x.get("status") == "Marketed" for x in p["status"]) for p in products)
        entries.append({**s, "file": out.name, "n_products": len(products), "n_marketed": marketed})
        note = ""
        if not products:
            note = "  <-- none found: not approved in Canada, or different name? check" if s["brands"] \
                else "  (none: expected for pipeline assets)"
        print(f"[{i:>2}/{len(searches)}] {s['name']:<40} {len(products):>4} products, {marketed:>3} marketed{note}")

    snapshots.write_manifest(folder, SOURCE, entries)
    print(f"\nSaved {len(entries)} files to {folder}\nProducts found: {sum(e['n_products'] for e in entries)}")
    return {"folder": str(folder), "files": entries}
