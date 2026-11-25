"""Build the M5 brief input from the latest change log, and show what the model will see.

Run from the repo root with the virtual environment active, AFTER scripts/build_changes.py:
    python scripts/build_brief_input.py
    python scripts/build_brief_input.py --date 2026-12-01

Writes briefs/<date>.input.json (kept next to the brief, so every brief has its evidence).
"""

import argparse

from obesity_ci.brief import inputs

ap = argparse.ArgumentParser()
ap.add_argument("--date", help="new-snapshot date of the change log (default: latest)")
args = ap.parse_args()

r = inputs.run(args.date)
d = r["input"]
print(f"Change log {r['log'].name}: {d['counts']['all_changes']} changes, "
      f"{d['period']['from']} -> {d['period']['to']}")
print(f"Sent to the model: {d['counts']['sent']} {d['counts']['by_importance_sent']}")
print(f"Left out: {d['omitted']}\n")
for c in d["changes"]:
    print(f"[{c['importance']:<6}] {c['source']:<28} {c['change_type']:<26} {c['id']:<12} "
          f"{c['molecules'][:30]:<30} {c['sponsors'][:25]}")
print(f"\nSaved to {r['out']}")
