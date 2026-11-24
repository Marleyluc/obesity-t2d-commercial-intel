"""Download trial data from ClinicalTrials.gov into data/raw/ctgov/<today>/

Run from the repo root with the virtual environment active:
    python scripts/pull_ctgov.py                     # full pull (~10-20 minutes)
    python scripts/pull_ctgov.py --only tirzepatide  # quick test: one molecule
    python scripts/pull_ctgov.py --list              # show the queries, download nothing
"""

import argparse

from obesity_ci.sources import ctgov

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--only", help="run only queries whose name contains this text")
parser.add_argument("--list", action="store_true", help="print the queries and exit")
args = parser.parse_args()

if args.list:
    for q in ctgov.build_queries():
        print(f"{q['name']:<45} {q['params']}")
    print(f"\n{len(ctgov.build_queries())} queries")
else:
    ctgov.pull(only=args.only)
