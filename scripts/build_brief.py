"""Write the weekly "what changed" brief with Claude (M5, chunk 2).

Run from the repo root with the virtual environment active, AFTER scripts/build_brief_input.py:
    python scripts/build_brief.py
    python scripts/build_brief.py --date 2026-12-01

Needs ANTHROPIC_API_KEY in .env (not needed for a week with no changes).
Writes briefs/<date>.md next to its input, briefs/<date>.input.json, but only if the brief
passes the ID guardrail (one retry allowed). If it fails twice, the last draft goes to
briefs/<date>.rejected.md and nothing is saved as the brief.
"""

import argparse
import sys

from obesity_ci.brief import generate

ap = argparse.ArgumentParser()
ap.add_argument("--date", help="date of the brief input (default: latest)")
args = ap.parse_args()

try:
    r = generate.run(args.date)
except generate.BriefError as e:
    sys.exit(f"No brief saved.\n{e}")
print(r["brief"])
if r["model"]:
    print(f"Model: {r['model']}  |  tokens in {r['input_tokens']:,}, out {r['output_tokens']:,} "
          f"(out includes thinking)")
    print(f"ID guardrail: passed on attempt {r['guardrail']['attempts']}, "
          f"{r['guardrail']['citations']} distinct IDs cited")
else:
    print("No changes to send this week: brief written by code, no API call.")
print(f"Saved to {r['out']}")
