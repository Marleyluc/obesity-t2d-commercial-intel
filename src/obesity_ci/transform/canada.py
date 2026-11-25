"""Canada market-access tables (M3, chunk 3): Health Canada approvals + Ontario coverage.

hc_products       one row per Canadian product (DIN): brand, company, current status,
                  first market date, molecules
odb_listings      one row per DIN on the Ontario Drug Benefit formulary: price, what the
                  ministry pays, listing date, Limited Use criteria, "not a benefit" flag
canada_molecules  one row per molecule: first US approval, first Canadian market date,
                  the lag between them, Canadian status and Ontario coverage

Definitions (see docs/M3_DECISIONS.md):
- Canada lag = first Canadian market date minus first US approval (NDA/BLA only).
  Negative means Canada was first. Health Canada only gives the current status, so
  for products that are marketed we know the market date but not the approval date.
  Lags are reliable only for "newer" molecules, which we searched by ingredient; legacy
  molecules were searched by US brand names only (lag_reliable = False).
- Only single-molecule products count towards a molecule's dates (Janumet does not move
  sitagliptin's dates); a combination counts for the combination molecule.
- Ontario coverage, best first: "General benefit" (listed, no criteria), "Limited Use"
  (listed with clinical criteria a prescriber must meet), "Listed, not a benefit",
  "Not listed". Other formulary flags (sec3, sec12, ...) are kept raw: their meaning is
  not documented in the schema, so we don't label them.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

from obesity_ci import config, snapshots
from obesity_ci.sources.hc_dpd import brand_matches
from obesity_ci.transform.approvals import build_matchers, match_product

ODB_STATUS_ORDER = ["General benefit", "Limited Use", "Listed, not a benefit", "Not listed"]
INJECTABLE_WORDS = ("PEN", "INJECT", "VIAL", "CARTRIDGE", "SYRINGE", "KWIKPEN", "FLEXTOUCH")


# ---------- Health Canada ----------

def route_guess(product: dict, ingredients: list[dict]) -> str:
    """DPD product records have no route, but injectables carry a per-mL strength or a pen/vial
    descriptor. Needed only to tell Rybelsus (oral) from Ozempic (injection)."""
    descriptor = (product.get("descriptor") or "").upper()
    per_ml = any((i.get("dosage_unit") or "").upper() == "ML" for i in ingredients)
    return "SUBCUTANEOUS" if per_ml or any(w in descriptor for w in INJECTABLE_WORDS) else "ORAL"


def brand_fallback(brand: str, mols: pd.DataFrame) -> set[str]:
    """For the few products whose ingredient name matches nothing (Canadian human insulins:
    "INSULIN SEMI SYNTHETIC HUMAN"), use the brand: Humulin R -> insulin regular."""
    return {m["generic"] for _, m in mols.iterrows() if any(brand_matches(brand or "", b) for b in m["brands"])}


def hc_products(folder: Path, mols: pd.DataFrame) -> pd.DataFrame:
    matchers = build_matchers(mols)
    seen, rows = set(), []
    for f in sorted(folder.glob("*.json")):
        if f.name == "manifest.json":
            continue
        for p in json.loads(f.read_text(encoding="utf-8")).get("products", []):
            if p["drug_code"] in seen or not p.get("product"):
                continue
            seen.add(p["drug_code"])
            prod, ings = p["product"][0], p.get("ingredients", []) or []
            st = (p.get("status") or [{}])[0]
            route = route_guess(prod, ings)
            hits = match_product([i.get("ingredient_name", "") for i in ings], route, matchers)
            matched_by = "ingredient" if hits else "brand"
            hits = hits or brand_fallback(prod.get("brand_name"), mols)
            rows.append({
                "drug_code": p["drug_code"],
                "din": prod.get("drug_identification_number"),
                "brand": prod.get("brand_name"),
                "descriptor": prod.get("descriptor"),
                "company": prod.get("company_name"),
                "ingredients": "; ".join(sorted({i.get("ingredient_name", "") for i in ings})),
                "route_guess": route,
                "status": st.get("status"),
                "status_date": pd.to_datetime(st.get("history_date"), errors="coerce"),
                "first_market_date": pd.to_datetime(st.get("original_market_date"), errors="coerce"),
                "molecules": "; ".join(sorted(hits)),
                "matched_by": matched_by if hits else None,
            })
    return pd.DataFrame(rows).sort_values(["molecules", "brand", "din"]).reset_index(drop=True)


# ---------- Ontario Drug Benefit ----------

def _num(text):
    try:
        return float(text) if text not in (None, "") else None
    except ValueError:
        return None


def odb_listings(xml_path: Path, mols: pd.DataFrame) -> pd.DataFrame:
    """Every drug on the formulary, with our molecules matched from Ontario's own generic name
    ("EMPAGLIFLOZIN & METFORMIN") and dosage form ("Tab" vs "Inj Sol...")."""
    matchers = build_matchers(mols)
    root = ET.parse(xml_path).getroot()
    formulary = root.find("formulary")
    edition_date = formulary.get("formularyDate") if formulary is not None else None
    rows = []
    for g in root.iter("genericName"):
        generic = g.findtext("name")
        for grp in g.findall("pcgGroup"):
            notes = grp.findall("lccNote")
            criteria = [n.text.strip() for n in notes if n.get("reasonForUseId") and n.text]
            for p9 in grp.findall("pcg9"):
                for d in p9.findall("drug"):
                    flags = {k: v for k, v in d.attrib.items() if k != "id"}
                    rows.append({
                        "din": d.get("id"),
                        "odb_name": d.findtext("name"),
                        "odb_generic": generic,
                        "strength": p9.findtext("strength"),
                        "dosage_form": p9.findtext("dosageForm"),
                        "list_price": _num(d.findtext("individualPrice")),
                        "ministry_pays": _num(d.findtext("amountMOHLTCPays")),
                        "listing_date": pd.to_datetime(d.findtext("listingDate"), errors="coerce"),
                        "not_a_benefit": flags.get("notABenefit") == "Y",
                        "limited_use": bool(criteria),
                        "lu_criteria": " | ".join(criteria) or None,
                        "raw_flags": "; ".join(f"{k}={v}" for k, v in sorted(flags.items())),
                        "edition_date": edition_date,
                    })
    df = pd.DataFrame(rows).astype({"odb_generic": "object", "dosage_form": "object"})
    df = df.where(df.notna(), None)
    df["molecules"] = [
        "; ".join(sorted(match_product([x.strip() for x in str(g or "").split("&")],
                                       "SUBCUTANEOUS" if "inj" in str(f or "").lower() else "ORAL", matchers)))
        for g, f in zip(df["odb_generic"], df["dosage_form"])]
    df["coverage"] = df.apply(lambda r: "Listed, not a benefit" if r.not_a_benefit
                              else "Limited Use" if r.limited_use else "General benefit", axis=1)
    return df


# ---------- per molecule ----------

def molecule_summary(mols: pd.DataFrame, hc: pd.DataFrame, odb: pd.DataFrame,
                     fda_apps: pd.DataFrame) -> pd.DataFrame:
    branded = fda_apps[fda_apps["app_type"] != "ANDA"]
    searched_by_ingredient = set(config.settings()["sources"]["hc_dpd"]["ingredient_search_generations"])
    rows = []
    for _, m in mols.iterrows():
        g = m["generic"]
        us = branded[branded["molecules"] == g]
        ca = hc[hc["molecules"] == g]
        on = odb[odb["molecules"] == g]
        full_search = m["generation"] in searched_by_ingredient
        marketed = ca[ca["first_market_date"].notna()]
        approved_only = ca[ca["status"] == "Approved"]
        us_date = us["first_approval_date"].min()
        ca_market = marketed["first_market_date"].min()
        rows.append({
            "generic": g, "class_id": m["class_id"], "generation": m["generation"],
            "is_pipeline": m["is_pipeline"],
            "us_first_approval": us_date,
            "us_first_brand": us.sort_values("first_approval_date")["brands"].iloc[0] if len(us) else None,
            "ca_status": ("Marketed" if (ca["status"] == "Marketed").any()
                          else "Approved, not marketed" if len(approved_only)
                          else "Previously marketed" if len(marketed)
                          else "Not in Canada" if full_search
                          else "Not found under US brand names"),
            "ca_first_market_date": ca_market,
            "ca_approval_date_if_unmarketed": approved_only["status_date"].min() if not len(marketed) else pd.NaT,
            "canada_lag_months": round((ca_market - us_date).days / 30.44, 1)
                                 if pd.notna(ca_market) and pd.notna(us_date) else None,
            # Legacy molecules were searched by US brand name only, so their first Canadian
            # date can be a later brand (NovoRapid is missed for insulin aspart).
            "lag_reliable": full_search,
            "ca_search": "ingredient + brand" if full_search else "US brand names only",
            "ca_products": len(ca),
            "ca_companies": "; ".join(sorted(ca["company"].dropna().unique())),
            "ontario_coverage": next((s for s in ODB_STATUS_ORDER if s in set(on["coverage"])), "Not listed"),
            "ontario_first_listing": on["listing_date"].min(),
            "ontario_brands": "; ".join(sorted(on["odb_name"].dropna().unique())),
        })
    return pd.DataFrame(rows)


def run(snapshot: str | None = None) -> dict:
    mols = config.molecules()
    hc_snap = _pick(snapshots.list_snapshots("hc_dpd"), snapshot, "hc_dpd")
    odb_snap = _pick(snapshots.list_snapshots("ontario_odb"), snapshot, "ontario_odb")
    fda_dirs = sorted((config.path("interim") / "openfda").glob("*/fda_applications.parquet"))
    if not fda_dirs:
        raise RuntimeError("No FDA tables yet. Run scripts/build_approvals.py first.")
    xml = next(odb_snap.glob("*.xml"))

    hc = hc_products(hc_snap, mols)
    odb = odb_listings(xml, mols)
    summary = molecule_summary(mols, hc, odb, pd.read_parquet(fda_dirs[-1]))
    out = config.path("interim") / "canada" / hc_snap.name
    out.mkdir(parents=True, exist_ok=True)
    hc.to_parquet(out / "hc_products.parquet", index=False)
    odb.to_parquet(out / "odb_listings.parquet", index=False)
    summary.to_parquet(out / "canada_molecules.parquet", index=False)
    return {"snapshot": hc_snap.name, "odb_edition": xml.name, "fda_from": fda_dirs[-1].parent.name,
            "out": out, "hc_products": hc, "odb_listings": odb, "canada_molecules": summary}


def _pick(snaps: list[Path], snapshot: str | None, source: str) -> Path:
    if not snaps:
        raise RuntimeError(f"No {source} snapshot found. Run its pull script first.")
    if not snapshot:
        return snaps[-1]
    match = [p for p in snaps if p.name == snapshot]
    if not match:
        raise RuntimeError(f"No {source} snapshot {snapshot}. Available: {[p.name for p in snaps]}")
    return match[0]
