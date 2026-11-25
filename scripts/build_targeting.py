"""Build the M4 targeting recommendation for the orforglipron launch (runs chunks 1-4 first).

Run from the repo root with the virtual environment active:
    python scripts/build_targeting.py       # about 1-2 minutes

Writes to data/processed/segments/<snapshot>/:
    targeting.parquet      one row per prescriber: value tier, cluster, launch fit, tier, call plan (no names)
    segment_cards.csv      one row per segment: name, description, size, recommended action
"""

import numpy as np
import pandas as pd

from obesity_ci.segment import targeting as T

r = T.run()
t = r["targeting"]
pd.set_option("display.width", 250)
pd.set_option("display.max_colwidth", 120)
inc_total = t["incretin_claims"].sum()

print(f"Orforglipron launch targeting, Medicare Part D {r['data_year']} "
      f"(stability check: mean adjusted Rand {np.mean(r['stability']):.3f})\n")
print("TARGETING MATRIX: prescribers (rows = value, columns = launch fit)")
print(r["matrix_prescribers"].to_string())
print("\nSame matrix: share of all GLP-1 / GIP-GLP-1 claims (%)")
print((100 * r["matrix_incretin"] / inc_total).round(1).to_string())

print("\nTIERS")
tiers = t.groupby("target_tier").agg(prescribers=("npi", "size"), claims=("total_claims", "sum"),
                                     incretin=("incretin_claims", "sum"), in_call_plan=("in_call_plan", "sum"))
tiers["pct_of_incretin_claims"] = (100 * tiers["incretin"] / inc_total).round(1)
tiers["action"] = tiers.index.map(T.TIER_ACTION)
print(tiers.drop(columns=["claims", "incretin"]).to_string())

plan = t[t["in_call_plan"]]
print(f"\nCALL PLAN (capacity {T.CALL_CAPACITY:,} prescribers, an assumption: ~300 reps x ~150 targets)")
print(f"  {len(plan):,} prescribers reach {100 * plan['incretin_claims'].sum() / inc_total:.1f}% of GLP-1 claims "
      f"and {100 * plan['total_claims'].sum() / t['total_claims'].sum():.1f}% of all in-scope claims")
print(f"  by specialty: " + ", ".join(f"{k} {v:,}" for k, v in plan["specialty_group"].value_counts().items()))
v = r["vs_baseline"]
print(f"\nVS THE BASELINE GRID (same {T.CALL_CAPACITY:,} capacity, filled from priority A then B)")
print(f"  GLP-1 claims reached: clusters {v['cluster_reach']:.1f}% vs grid {v['baseline_reach']:.1f}%; "
      f"{v['overlap']:,} prescribers on both lists")
print(f"  already-in-class (High launch fit) share of the list: clusters {v['high_fit_pct']['cluster plan']:.0f}% "
      f"vs grid {v['high_fit_pct']['baseline plan']:.0f}%")
print("  swapped in by the clusters: " + ", ".join(f"{k} {n:,}" for k, n in v["added"].items()))
print("  swapped out:                " + ", ".join(f"{k} {n:,}" for k, n in v["dropped"].items()))
print("  -> similar list; the clusters mainly change WHAT to say to each group (segment cards below)")

print("\nSEGMENT CARDS")
for name, row in r["cards"].iterrows():
    print(f"\n{name}  [launch fit: {row['launch_fit'] or '-'}]")
    print(f"  {row['prescribers']:,} prescribers, {row['pct_of_claims']}% of claims, "
          f"{row['pct_of_incretin_claims']}% of GLP-1 claims; Tier 1: {row['tier_1']:,}, Tier 2: {row['tier_2']:,}, "
          f"in call plan: {row['in_call_plan']:,}")
    print(f"  Who: {row['description']}")
    print(f"  Action: {row['recommended_action']}")
print(f"\nSaved to {r['out']}")
