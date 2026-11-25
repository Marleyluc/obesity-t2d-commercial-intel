"""Build the M4 prescriber feature table (one row per prescriber) and print a profile of it.

Run from the repo root with the virtual environment active:
    python scripts/build_prescribers.py

Writes data/interim/cms_partd/<snapshot>/prescribers.parquet
"""

import pandas as pd

from obesity_ci.transform import prescribers as P

r = P.run()
f = r["prescribers"]
e = f[f["eligible"]]
pd.set_option("display.width", 200)
pct = lambda x: f"{100 * x:.1f}%"

print(f"Part D {r['data_year']}: {len(f):,} prescribers with any in-scope claims")
print(f"Eligible for segmentation (>= {P.MIN_CLAIMS} in-scope claims): {len(e):,} prescribers "
      f"({pct(len(e) / len(f))}), writing {pct(e['total_claims'].sum() / f['total_claims'].sum())} of claims\n")

print("Value concentration (eligible prescribers, by volume decile):")
dec = e.groupby("volume_decile").agg(prescribers=("npi", "size"), min_claims=("total_claims", "min"),
                                     claims=("total_claims", "sum"))
dec["share_of_claims"] = (100 * dec["claims"] / dec["claims"].sum()).round(1)
print(dec.to_string())

share_cols = [c for c in f.columns if c.startswith("share_")]
print("\nAverage prescribing mix by specialty group (eligible; shares of in-scope claims, %):")
sg = e.groupby("specialty_group")
prof = (100 * sg[share_cols + ["newer_share", "incretin_share"]].mean()).round(1)
prof.insert(0, "prescribers", sg.size())
prof.insert(1, "median_claims", sg["total_claims"].median())
print(prof.sort_values("prescribers", ascending=False).rename(columns=lambda c: c.replace("share_", "")).to_string())

print("\nLaunch analogues (eligible prescribers):")
print(f"  write any GLP-1 / GIP-GLP-1:       {e['writes_incretin'].sum():>7,} ({pct(e['writes_incretin'].mean())})")
print(f"  write Rybelsus (oral GLP-1):       {e['writes_oral_glp1'].sum():>7,} ({pct(e['writes_oral_glp1'].mean())})")
print(f"  of incretin users, median Lilly share: {pct(e['lilly_of_incretin'].median())}")
print(f"  of incretin users, median oral share:  {pct(e['oral_glp1_of_incretin'].median())}")
top = e[e["volume_decile"] == 10]
print(f"  top-decile prescribers writing no incretin at all: {(~top['writes_incretin']).sum():,} "
      f"of {len(top):,} (big volume, not yet on the class)")
print(f"\nSaved to {r['out'] / 'prescribers.parquet'}")
