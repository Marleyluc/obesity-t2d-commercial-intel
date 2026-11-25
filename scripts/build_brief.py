"""Write the weekly "what changed" brief (M5).

Run from the repo root with the virtual environment active, AFTER scripts/build_brief_input.py.

Two ways to get the draft; both go through the same ID guardrail before anything is saved:
    python scripts/build_brief.py                                 # Claude API (needs ANTHROPIC_API_KEY in .env, costs cents)
    python scripts/build_brief.py --draft briefs/2026-11-25.draft.md   # a draft written elsewhere, e.g. in the Claude app (free)
Add --date 2026-12-01 to pick a week (default: latest input).

Writes briefs/<date>.md next to its input, briefs/<date>.input.json, but only if the brief passes
the guardrail. A failing draft goes to briefs/<date>.rejected.md and nothing is saved as the brief.
A week with no changes is written by code: no API call and no draft needed.
"""

import argparse
import sys
from pathlib import Path

from obesity_ci.brief import generate

ap = argparse.ArgumentParser()
ap.add_argument("--date", help="date of the brief input (default: latest)")
ap.add_argument("--draft", type=Path, help="a Markdown draft to check and save instead of calling the API")
args = ap.parse_args()

try:
    draft = args.draft.read_text(encoding="utf-8") if args.draft else None
    r = generate.run(args.date, draft=draft)
except (generate.BriefError, FileNotFoundError) as e:
    sys.exit(f"No brief saved.\n{e}")
print(r["brief"])
if "guardrail" in r:
    if "input_tokens" in r:
        print(f"Model: {r['model']}  |  tokens in {r['input_tokens']:,}, out {r['output_tokens']:,} "
              f"(out includes thinking)")
    print(f"ID guardrail: passed on attempt {r['guardrail']['attempts']}, "
          f"{r['guardrail']['citations']} distinct IDs cited")
else:
    print("No changes to send this week: brief written by code, no API call.")
print(f"Saved to {r['out']}")
