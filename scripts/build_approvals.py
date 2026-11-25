"""Build the M3 FDA approval tables from an openFDA snapshot.

Run from the repo root with the virtual environment active:
    python scripts/build_approvals.py                      # latest snapshot
    python scripts/build_approvals.py --snapshot 2026-11-24

Writes to data/interim/openfda/<snapshot>/:
    fda_applications.parquet   one row per application (NDA / BLA / ANDA)
    fda_app_molecules.parquet  one row per (application, molecule) link
    fda_events.parquet         one row per submission (approvals, supplements)
    fda_labels.parquet         current labels per brand (is_primary = manufacturer's own)
"""

import argparse

import pandas as pd

from obesity_ci.transform import approvals

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--snapshot", help="snapshot date folder, e.g. 2026-11-24 (default: latest)")
parser.add_argument("--since", default="2025-01-01", help="show key events on or after this date")
args = parser.parse_args()

r = approvals.run(args.snapshot)
ap, ev, lb = r["fda_applications"], r["fda_events"], r["fda_labels"]
print(f"Snapshot {r['snapshot']}: {len(ap)} applications, {len(ev):,} submissions, {len(lb)} label records")
print(f"  by type: {ap['app_type'].value_counts().to_dict()}")
print(f"  by status: {ap['marketing_status'].value_counts().to_dict()}")
print(f"  applications matching no molecule: {(ap['n_molecules'] == 0).sum()}")

key = (ev.merge(ap[["application_number", "app_type", "sponsor", "brands", "molecules"]], on="application_number")
       .query("app_type != 'ANDA' and event_type in ['Original approval', 'Tentative approval', 'Efficacy supplement']")
       .query("date >= @pd.Timestamp(@args.since)"))
pd.set_option("display.width", 200)
pd.set_option("display.max_colwidth", 40)
print(f"\nBranded approvals and efficacy supplements since {args.since} ({len(key)}):")
print(key[["date", "event_type", "application_number", "brands", "molecules"]].to_string(index=False))

gen = ev.merge(ap, on="application_number").query("app_type == 'ANDA' and event_type == 'Tentative approval'")
gen = gen[gen["molecules"].str.contains("semaglutide|tirzepatide|liraglutide|dulaglutide|empagliflozin|dapagliflozin")]
print(f"\nGeneric (ANDA) tentative approvals for key newer molecules ({len(gen)}):")
print(gen[["date", "application_number", "sponsor", "molecules"]].to_string(index=False))

primary = lb[lb["is_primary"]]
missing = primary[primary["is_repackager"]]
print(f"\nPrimary labels: {len(primary)}. Only a repackager copy found for: "
      f"{', '.join(sorted(missing['brand_query'] + ' (' + missing['application_number'] + ')')) or 'none'}")
print(f"\nSaved to {r['out']}")
