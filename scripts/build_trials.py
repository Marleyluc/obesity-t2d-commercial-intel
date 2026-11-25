"""Build the M3 trials tables from a ClinicalTrials.gov snapshot.

Run from the repo root with the virtual environment active:
    python scripts/build_trials.py                      # latest snapshot
    python scripts/build_trials.py --snapshot 2026-11-24

Writes to data/interim/ctgov/<snapshot>/:
    trials.parquet           one row per trial
    trial_molecules.parquet  one row per (trial, molecule) link
    trials_unmatched.csv     trials that match no configured molecule (new code names show up here)
"""

import argparse

from obesity_ci import config
from obesity_ci.transform import trials

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--snapshot", help="snapshot date folder, e.g. 2026-11-24 (default: latest)")
args = parser.parse_args()

r = trials.run(args.snapshot)
tr, links, un = r["trials"], r["trial_molecules"], r["unmatched"]
print(f"Snapshot {r['snapshot']}: {len(tr):,} unique trials, {len(links):,} trial-molecule links")
print(f"  matched to at least one molecule: {(tr['n_molecules'] > 0).sum():,}")
print(f"  matched to none (see trials_unmatched.csv): {len(un):,}")
print(f"  with a Canadian site: {tr['has_canada_site'].sum():,}")

print("\nTrials by phase:")
print(tr["phase"].value_counts().to_string())

labels = config.molecules().drop_duplicates("class_id").set_index("class_id")["class_label"]
per_class = (links.merge(tr[["nct_id", "phase"]], on="nct_id")
             .drop_duplicates(["nct_id", "class_id"])  # a trial counts once per class
             .groupby("class_id").agg(trials=("nct_id", "size"),
                                      phase3=("phase", lambda p: (p == "Phase 3").sum()))
             .sort_values("trials", ascending=False))
per_class.index = [labels.get(c, c) for c in per_class.index]
print("\nTrials per class (each trial counted once per class):")
print(per_class.to_string())
print(f"\nSaved to {r['out']}")
