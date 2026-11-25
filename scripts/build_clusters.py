"""Build the M4 behavioural clusters, check their stability, and compare with the baseline grid.

Run from the repo root with the virtual environment active:
    python scripts/build_clusters.py           # k = 7, about 1 minute
    python scripts/build_clusters.py --scan    # also compare k = 3..10 (a few more minutes)

Writes to data/processed/segments/<snapshot>/:
    clusters.parquet       one row per prescriber: cluster name
    cluster_profile.csv    one row per cluster: size, share of value, prescribing mix
"""

import argparse

import numpy as np
import pandas as pd

from obesity_ci.segment import clusters as C

ap = argparse.ArgumentParser()
ap.add_argument("--scan", action="store_true", help="also compare k = 3..10")
args = ap.parse_args()

r = C.run(do_scan=args.scan)
pd.set_option("display.width", 250)
s = r["segments"]
e = s[s["eligible"]]

if r["scan"] is not None:
    print("Choosing k (silhouette: higher = better separated; stability: 1 = same groups every time):")
    print(r["scan"].to_string(index=False), "\n")

st = r["stability"]
print(f"k = {C.K} on {len(e):,} profiled prescribers (features: class-mix shares only)")
print(f"  silhouette {r['silhouette']:.3f}  (0.25-0.5 = real but overlapping groups, typical for behaviour data)")
print(f"  stability: mean adjusted Rand {np.mean(st):.3f}, min {min(st):.3f} over {len(st)} bootstrap refits "
      f"-> {'PASS' if np.mean(st) >= 0.8 else 'FAIL'} (exit criterion >= 0.8)")
print(f"  agreement with the baseline grid: adjusted Rand {r['ari_vs_baseline']:.3f} "
      "(low = the clusters carry information the grid doesn't)\n")

print("Cluster profiles (shares are averages across prescribers, %):")
print(r["by_cluster"].sort_values("pct_of_claims", ascending=False).to_string())

print("\nClusters vs baseline launch priority (prescribers):")
print(pd.crosstab(e["cluster"], e["priority"], margins=True).to_string())
print(f"\nSaved to {r['out']}")
