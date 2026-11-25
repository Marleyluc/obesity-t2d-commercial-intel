"""Download CMS Medicare Part D Prescriber data, filtered to our drugs, into
data/raw/cms_partd/<today>/

Run from the repo root with the virtual environment active:
    python scripts/pull_partd.py --list      # show available years, download nothing
    python scripts/pull_partd.py             # download latest year (several GB), filter, clean up
    python scripts/pull_partd.py --keep-csv  # same, but keep the full national CSV
"""

import argparse

from obesity_ci import config
from obesity_ci.http import PoliteSession
from obesity_ci.sources import partd

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--list", action="store_true", help="list available years and exit")
parser.add_argument("--keep-csv", action="store_true", help="keep the full national CSV")
args = parser.parse_args()

if args.list:
    st = config.settings()["sources"]["cms_partd"]
    session = PoliteSession()
    dists = partd.find_distributions(session.get_json(st["catalog_url"]), st["dataset_title"])
    for d in dists:
        size = session.content_length(d["url"])
        print(f"{d['year']}  {(size or 0) / 1e9:5.1f} GB  {d['title']}\n      {d['url']}")
    print(f"\nWould use: {partd.choose(dists, st['data_year'])['year']}")
else:
    partd.pull(keep_csv=args.keep_csv or None)
