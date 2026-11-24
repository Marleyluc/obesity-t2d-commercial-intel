"""Download Canadian approvals from Health Canada's Drug Product Database into
data/raw/hc_dpd/<today>/

Run from the repo root with the virtual environment active:
    python scripts/pull_hc_dpd.py                    # full pull (~5-10 minutes)
    python scripts/pull_hc_dpd.py --only tirzepatide # quick test
    python scripts/pull_hc_dpd.py --list             # show the searches, download nothing
"""

import argparse

from obesity_ci.sources import hc_dpd

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--only", help="run only molecules whose name contains this text")
parser.add_argument("--list", action="store_true", help="print the searches and exit")
args = parser.parse_args()

if args.list:
    for s in hc_dpd.build_searches():
        print(f"{s['name']:<40} ingredient={s['ingredient']!s:<25} brands={s['brands']}")
    print(f"\n{len(hc_dpd.build_searches())} molecules")
else:
    hc_dpd.pull(only=args.only)
