"""Build the change log between two snapshots: the input to the weekly brief (M5).

Run from the repo root with the virtual environment active:
    python scripts/build_changes.py                               # each source's last two pulls
    python scripts/build_changes.py --old 2026-11-24 --new 2026-12-01

Needs at least two pulls of a source (e.g. run scripts/pull_ctgov.py on two different days).
Writes data/processed/changes/changes_<new date>.csv (and .parquet).
"""

import argparse

import pandas as pd

from obesity_ci.transform import changes

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--old")
parser.add_argument("--new")
args = parser.parse_args()

r = changes.run(args.old, args.new)
df = r["changes"]
for source, dates in r["skipped"].items():
    print(f"{source}: skipped, needs two snapshots (have: {', '.join(dates) or 'none'})")
if df.empty:
    print("No changes found." if not r["skipped"] or len(r["skipped"]) < 3 else "Nothing to compare yet.")
else:
    pd.set_option("display.width", 220)
    pd.set_option("display.max_colwidth", 50)
    print(f"\n{len(df)} changes:")
    print(df.groupby(["source", "change_type", "importance"]).size().to_string())
    top = df[df["importance"] == "high"]
    print(f"\nHigh-importance changes ({len(top)}):")
    print(top[["source", "change_type", "id", "molecules", "old", "new", "detail"]].to_string(index=False))
    print(f"\nSaved to {r['out']}")
