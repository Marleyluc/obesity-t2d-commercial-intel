"""Export the small files the dashboard reads into app/data/ (M6, chunk 1).

Run from the repo root with the virtual environment active, after the M3, M4 and M5 builds
(build_landscape, build_targeting, build_changes, build_brief):
    python scripts/build_app_data.py

app/data/ is committed to git (data/processed/ is not), so the deployed app has its data.
Re-run this, then commit app/data/, whenever the pipeline output changes.
"""

from obesity_ci import app_data

r = app_data.run()
m = r["meta"]
print(f"Wrote {len(r['written'])} files to {r['out']} ({r['size_mb']:.1f} MB):")
for name, rows in r["written"].items():
    print(f"  {name:<34} {rows if isinstance(rows, str) else f'{rows:,} rows'}")
print(f"\nSources: landscape {m['landscape_snapshot']}, change log {m['change_log']}, brief {m['brief']}, "
      f"Part D {m['part_d_data_year']} (snapshot {m['part_d_snapshot']})")
print(f"Headline: {m['in_call_plan']:,} names in the call plan reach {m['plan_pct_incretin_claims']}% of "
      f"GLP-1 / GIP-GLP-1 claims (grid-based list: {m['baseline_pct_incretin_claims']}%); "
      f"{m['plan_pct_high_fit']}% are high launch fit (grid: {m['baseline_pct_high_fit']}%).")
