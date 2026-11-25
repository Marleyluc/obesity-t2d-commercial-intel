"""Build the M3 Canada tables: Health Canada approvals, Ontario coverage, lag vs the US.

Run from the repo root with the virtual environment active, AFTER build_approvals.py
(the US approval dates come from the FDA tables):
    python scripts/build_canada.py

Writes to data/interim/canada/<snapshot>/:
    hc_products.parquet       one row per Canadian product (DIN)
    odb_listings.parquet      every drug on the Ontario formulary, with our molecules matched
    canada_molecules.parquet  one row per molecule: US vs Canada dates, lag, Ontario coverage
"""

import pandas as pd

from obesity_ci.transform import canada

r = canada.run()
hc, odb, s = r["hc_products"], r["odb_listings"], r["canada_molecules"]
print(f"Health Canada snapshot {r['snapshot']}: {len(hc)} products, "
      f"{(hc['molecules'] != '').sum()} matched to a molecule ({(hc['matched_by'] == 'brand').sum()} by brand name)")
print(f"Ontario formulary {r['odb_edition'][:60]}...: {len(odb):,} listings, "
      f"{(odb['molecules'] != '').sum()} for our molecules")
print(f"US approval dates from FDA tables of {r['fda_from']}")

pd.set_option("display.width", 200)
fmt = {"us_first_approval": "US approval", "ca_first_market_date": "CA first market",
       "canada_lag_months": "lag (months)", "ca_status": "Canada status", "ontario_coverage": "Ontario"}
newer = s[(s["generation"] == "newer") & (s["us_first_approval"].notna() | (s["ca_status"] != "Not in Canada"))]
print("\nNewer agents: US approval vs Canada (negative lag = Canada first):")
print(newer[["generic", *fmt]].rename(columns=fmt).to_string(index=False))

legacy = s[(s["generation"] == "legacy") & s["canada_lag_months"].notna()]
print("\nLegacy agents (searched by US brand only, so lags are indicative):")
print(legacy[["generic", *fmt]].rename(columns=fmt).to_string(index=False))

newer_mols = set(s.loc[s["generation"] == "newer", "generic"])
detail = odb[odb["molecules"].isin(newer_mols)]
detail = (detail.groupby(["molecules", "odb_name", "coverage"], as_index=False)
          .agg(list_price=("list_price", "max"), ministry_pays=("ministry_pays", "max"),
               listed=("listing_date", "min"))
          .sort_values(["molecules", "listed"]))
print("\nOntario formulary detail, newer agents (max price per pack/unit across strengths):")
print(detail.to_string(index=False))
print(f"\nSaved to {r['out']}")
