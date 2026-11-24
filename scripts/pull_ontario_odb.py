"""Download the Ontario Drug Benefit Formulary files into data/raw/ontario_odb/<today>/

Run from the repo root with the virtual environment active:
    python scripts/pull_ontario_odb.py
"""

from obesity_ci.sources import ontario_odb

ontario_odb.pull()
