"""Tidy Medicare Part D prescribing table for the segmentation (M4, chunk 1).

claims      one row per (prescriber NPI, CMS drug name, brand), mapped to OUR molecule and class:
            claims, 30-day fills, days' supply, drug cost, beneficiaries (blank when CMS hides it)
excluded    the CMS names we dropped, with claim totals and the reason

Rules (see docs/M4_DECISIONS.md):
- Every CMS generic name is mapped by hand in config/partd_names.csv: CMS spells names its own
  way and truncates them ("Dapaglifloz Propaned/Metformin"), so guessing would be fragile.
  A name that isn't in the file stops the build, so a new data year can't slip in unmapped drugs.
- Excluded: drugs that are only a PART of an obesity combination and are mostly prescribed
  for something else (bupropion, topiramate, naltrexone alone), and insulin devices/supplies.
- A fixed-dose combination (Janumet = sitagliptin + metformin) counts once, under its
  newest-mechanism part, so class shares add up to 100%.
- Semaglutide is split by brand: Rybelsus = oral semaglutide; Ozempic and Wegovy = injectable.
- Prescriber names and cities are dropped: the portfolio shows segments, not named doctors.
"""

from __future__ import annotations

import json

import pandas as pd

from obesity_ci import config, snapshots

SOURCE = "cms_partd"
ORAL_SEMAGLUTIDE_BRANDS = {"rybelsus"}
NUMERIC = {"Tot_Clms": "claims", "Tot_30day_Fills": "fills_30d", "Tot_Day_Suply": "days_supply",
           "Tot_Drug_Cst": "drug_cost", "Tot_Benes": "beneficiaries"}
KEEP = {"Prscrbr_NPI": "npi", "Prscrbr_Type": "specialty", "Prscrbr_Type_Src": "specialty_source",
        "Prscrbr_State_Abrvtn": "state", "Prscrbr_State_FIPS": "state_fips",
        "Brnd_Name": "cms_brand", "Gnrc_Name": "cms_generic"}


def name_map() -> pd.DataFrame:
    df = pd.read_csv(config.CONFIG_DIR / "partd_names.csv", comment="#", dtype=str, keep_default_na=False)
    bad = df[(df["status"] == "in_scope") & ~df["generic"].isin(set(config.molecules()["generic"]))]
    if len(bad):
        raise ValueError(f"partd_names.csv maps to molecules not in drug_classes.yaml: {list(bad['generic'])}")
    return df


def build(raw: pd.DataFrame, names: pd.DataFrame, mols: pd.DataFrame) -> dict[str, pd.DataFrame]:
    unknown = sorted(set(raw["Gnrc_Name"]) - set(names["cms_generic_name"]))
    if unknown:
        raise ValueError(f"CMS names not in config/partd_names.csv (add them, mapped or excluded): {unknown}")

    df = raw[list(KEEP) + list(NUMERIC)].rename(columns={**KEEP, **NUMERIC})
    for c in NUMERIC.values():
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.merge(names.rename(columns={"cms_generic_name": "cms_generic"}), on="cms_generic", how="left")

    excluded = (df[df["status"] == "excluded"]
                .groupby(["cms_generic", "note"], as_index=False)
                .agg(claims=("claims", "sum"), prescribers=("npi", "nunique"))
                .sort_values("claims", ascending=False).reset_index(drop=True))

    df = df[df["status"] == "in_scope"].drop(columns=["status", "note"]).copy()
    oral = (df["generic"] == "semaglutide") & df["cms_brand"].str.lower().isin(ORAL_SEMAGLUTIDE_BRANDS)
    df.loc[oral, "generic"] = "oral semaglutide"

    info = mols.set_index("generic")[["class_id", "class_label", "generation", "sponsor"]]
    df = df.join(info, on="generic")
    # Beneficiary counts under 11 are hidden by CMS: keep them blank, never zero.
    df["beneficiaries_hidden"] = df["beneficiaries"].isna()
    df = df.astype({c: object for c in ["specialty", "specialty_source", "state", "state_fips", "cms_brand",
                                        "cms_generic", "generic", "class_id", "class_label", "generation",
                                        "sponsor"]})
    return {"claims": df.reset_index(drop=True), "excluded": excluded}


def run(snapshot: str | None = None) -> dict:
    snaps = snapshots.list_snapshots(SOURCE)
    if not snaps:
        raise RuntimeError("No Part D snapshot found. Run scripts/pull_partd.py first.")
    folder = next((p for p in snaps if p.name == snapshot), None) if snapshot else snaps[-1]
    if folder is None:
        raise RuntimeError(f"No Part D snapshot {snapshot}. Available: {[p.name for p in snaps]}")
    year = json.loads((folder / "manifest.json").read_text())["data_year"]
    raw = pd.read_parquet(folder / f"partd_prescriber_drug_{year}_in_scope.parquet")
    t = build(raw, name_map(), config.molecules())
    out = config.path("interim") / SOURCE / folder.name
    out.mkdir(parents=True, exist_ok=True)
    t["claims"].to_parquet(out / "claims.parquet", index=False)
    t["excluded"].to_csv(out / "excluded_names.csv", index=False)
    return {"snapshot": folder.name, "data_year": year, "out": out, "raw_rows": len(raw), **t}
