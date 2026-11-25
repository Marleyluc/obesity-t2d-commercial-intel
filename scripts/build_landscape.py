"""Build the M3 landscape views and print the hand check for three known assets.

Run from the repo root with the virtual environment active:
    python scripts/build_landscape.py

Writes to data/processed/landscape/<snapshot>/: class_phase, sponsor_share, upcoming, assets (.parquet)
"""

import pandas as pd

from obesity_ci.transform import landscape

CHECK = ["retatrutide", "orforglipron", "cagrilintide/semaglutide"]  # M3 exit criterion

r = landscape.run()
pd.set_option("display.width", 220)
pd.set_option("display.max_colwidth", 40)
print(f"Snapshot {r['snapshot']}. Pipeline = active, interventional, Phase 1-3, industry-sponsored.\n")
if r["canada_error"]:
    print(f"WARNING: Canada columns are empty because the Canada build failed: {r['canada_error']}\n")
print("Pipeline by class x phase (trials, each counted once per class):")
print(r["class_phase"].to_string())
print("\nWho runs the active late-stage trials (Phase 2/3 and 3):")
print(r["sponsor_share"].to_string())
up = r["upcoming"]
print(f"\nUpcoming primary completions, next {landscape.UPCOMING_MONTHS} months ({len(up)} trials; first 15):")
print(up[["primary_completion_date", "molecules", "lead_sponsor", "acronym", "phase", "nct_id"]]
      .head(15).to_string(index=False))
print("\nAssets (tracked newer molecules):")
print(r["assets"].to_string(index=False))

print("\n" + "=" * 80 + "\nHAND CHECK (M3 exit criterion): compare with what you know / company pipelines\n")
a = r["assets"].set_index("generic")
for g in CHECK:
    row = a.loc[g]
    print(f"{g}: highest active phase {row['highest_active_phase']}, {row['active_late_stage']} active "
          f"late-stage trials, next readout {row['next_readout'].date() if pd.notna(row['next_readout']) else 'n/a'}, "
          f"US approval {row['us_first_approval'].date() if pd.notna(row['us_first_approval']) else 'none'}, "
          f"Canada: {row['ca_status']}")
    print(landscape.late_stage_trials(r["trials"], r["links"], g).to_string(index=False))
    print()
print(f"Saved to {r['out']}")
