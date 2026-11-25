"""Build the M4 rules-based baseline segments (value tier x GLP-1 adoption) and print their profiles.

Run from the repo root with the virtual environment active:
    python scripts/build_baseline_segments.py

Writes to data/processed/segments/<snapshot>/:
    baseline.parquet          one row per prescriber: tiers, segment, priority (no names)
    baseline_profile.csv      one row per segment: size, share of value, prescribing mix
"""

import pandas as pd

from obesity_ci.segment import baseline

r = baseline.run()
s = r["segments"]
pd.set_option("display.width", 250)
print(f"Part D {r['data_year']}: {len(s):,} prescribers, {s['eligible'].sum():,} profiled\n")

e = s[s["eligible"]]
print("Prescribers per cell (rows = value tier, columns = GLP-1 adoption tier):")
grid = pd.crosstab(e["value_tier"], e["adoption_tier"]).reindex(
    index=["High", "Medium", "Low"], columns=baseline.ADOPTION_TIERS)
print(grid.to_string())
print("\nShare of all GLP-1 / GIP-GLP-1 claims per cell (%):")
print((100 * pd.crosstab(e["value_tier"], e["adoption_tier"], values=e["incretin_claims"], aggfunc="sum")
       / s["incretin_claims"].sum()).reindex(index=["High", "Medium", "Low"],
                                              columns=baseline.ADOPTION_TIERS).round(1).to_string())

print("\nSegment profiles (shares are averages across prescribers, %):")
print(r["by_segment"].sort_values("pct_of_claims", ascending=False).to_string())

print("\nBy launch priority (A = first-wave rep calls, B = second wave, C = non-personal, - = not profiled):")
print(r["by_priority"].to_string())
print(f"\nSaved to {r['out']}")
