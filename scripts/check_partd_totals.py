"""Compare our filtered Part D extract with CMS's published national totals.

Run from the repo root with the virtual environment active:
    python scripts/check_partd_totals.py

Saves next to the latest Part D snapshot:
    partd_national_drug_<year>.csv        CMS national rows for our drugs (the reference)
    partd_reconciliation_<year>.csv       ours vs national, per drug
    partd_reconciliation_<year>.json      the summary below
Exits with code 1 if any drug is OVER the national total or MISSING.
"""

import sys

import pandas as pd

from obesity_ci.sources import partd_check

result = partd_check.run()
s, df = result["summary"], result["table"]

pd.set_option("display.width", 140)
cols = ["generic_name", "brand_name", "our_claims", "national_claims", "captured_pct", "status"]
print("\nTop 15 drugs by national claims:")
print(df[cols].head(15).to_string(index=False, float_format=lambda x: f"{x:,.0f}" if x >= 1000 else f"{x:.1f}"))

print(f"\nDrugs compared: {s['drugs_compared']}")
print(f"Our claims:      {s['our_claims']:,}")
print(f"National claims: {s['national_claims']:,}")
print(f"Captured:        {s['captured_pct']}%  (the rest is CMS's <11-claim suppression)")
print(f"Status counts:   {s['status_counts']}")
if s["passed"]:
    print("\nPASSED: every drug is at or below the national total, and nothing large is missing.")
else:
    print("\nFAILED, check these:")
    for p in s["problems"]:
        print(f"  {p['status']:8} {p['generic_name']} / {p['brand_name']}")
    sys.exit(1)
