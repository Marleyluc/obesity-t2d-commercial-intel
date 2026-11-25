"""Build the M4 tidy Part D table: every claim row mapped to our molecules and classes.

Run from the repo root with the virtual environment active:
    python scripts/build_prescriptions.py

Writes to data/interim/cms_partd/<snapshot>/:
    claims.parquet        one row per (prescriber, drug), mapped to molecule and class
    excluded_names.csv    the CMS names we dropped, with claims and the reason
"""

import pandas as pd

from obesity_ci.transform import prescriptions

r = prescriptions.run()
c, ex = r["claims"], r["excluded"]
pd.set_option("display.width", 200)
kept, dropped = c["claims"].sum(), ex["claims"].sum()
print(f"Part D data year {r['data_year']} (snapshot {r['snapshot']}): {r['raw_rows']:,} raw rows")
print(f"Kept {len(c):,} rows, {c['npi'].nunique():,} prescribers, {kept:,.0f} claims "
      f"({100 * kept / (kept + dropped):.1f}% of the extract's claims)\n")

print("Dropped (not counted in M4):")
print(ex.to_string(index=False))

print("\nClaims by class:")
by_class = (c.groupby("class_label").agg(claims=("claims", "sum"), prescribers=("npi", "nunique"),
                                          drug_cost_musd=("drug_cost", lambda x: round(x.sum() / 1e6)))
            .sort_values("claims", ascending=False))
by_class["share_pct"] = (100 * by_class["claims"] / by_class["claims"].sum()).round(1)
print(by_class.to_string())

print("\nGLP-1 family by brand (the analogue market for an oral GLP-1 launch):")
glp = c[c["class_id"].isin(["glp1_injectable", "glp1_oral", "gip_glp1"])]
print(glp.groupby(["class_id", "cms_brand"])["claims"].sum().sort_values(ascending=False).head(12).to_string())

print("\nTop specialties by in-scope claims:")
sp = c.groupby("specialty").agg(claims=("claims", "sum"), prescribers=("npi", "nunique"))
sp["share_pct"] = (100 * sp["claims"] / sp["claims"].sum()).round(1)
print(sp.sort_values("claims", ascending=False).head(10).to_string())
print(f"\nSaved to {r['out']}")
