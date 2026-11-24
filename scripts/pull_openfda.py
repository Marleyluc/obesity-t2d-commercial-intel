"""Download US approvals and labels from openFDA into data/raw/openfda/<today>/

Run from the repo root with the virtual environment active:
    python scripts/pull_openfda.py                    # full pull (~2-5 minutes)
    python scripts/pull_openfda.py --only tirzepatide # quick test
    python scripts/pull_openfda.py --list             # show queries, download nothing
"""

import argparse

from obesity_ci.sources import openfda

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--only", help="run only queries whose name contains this text")
parser.add_argument("--list", action="store_true", help="print the queries and exit")
args = parser.parse_args()

if args.list:
    for q in openfda.build_queries():
        print(f"{q['name']:<45} {q['params']['search']}")
    print(f"\n{len(openfda.build_queries())} queries")
else:
    openfda.pull(only=args.only)
