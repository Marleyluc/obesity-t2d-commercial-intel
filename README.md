# Obesity & T2D Commercial Intelligence

> **Work in progress.** This README becomes the business-facing summary in Milestone 7. See [docs/ROADMAP.md](docs/ROADMAP.md) for status.

**The question:** In the fastest-moving market in pharma, what is changing in the competitive landscape this week, and which prescribers should a brand team prioritise?

This project combines two views a commercial team uses every day:

1. **Competitive landscape tracker.** Pipeline and trial data from ClinicalTrials.gov and approvals/labels from openFDA across GLP-1s (injectable and oral), GIP/GLP-1 and glucagon combinations, amylin analogues, SGLT2 and DPP-4 inhibitors, insulins and emerging mechanisms, with an LLM-generated weekly "what changed" brief.
2. **Prescriber segmentation.** CMS Medicare Part D Prescriber data, clustered by volume, class mix, specialty, geography and uptake of newer agents, translated into a targeting recommendation.

Output: a Streamlit dashboard combining both.

## Data sources and limits
| Source | What it gives | Key limitation |
|---|---|---|
| ClinicalTrials.gov API v2 | Trials, phases, status, completion dates | Sponsor-reported; results and readout dates lag or are missing |
| openFDA (Drugs@FDA, labels) | US approvals and label text | US only; no Health Canada data |
| CMS Medicare Part D Prescriber | Claims by prescriber x drug | US Medicare (mostly 65+) only, ~2-year lag, rows under 11 claims suppressed, anti-obesity use largely excluded by statute |

## Quick start
```bash
git clone https://github.com/<your-username>/obesity-t2d-commercial-intel.git
cd obesity-t2d-commercial-intel
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env             # Windows: copy .env.example .env
pytest
python scripts/check_setup.py
```

## Repo structure
```
config/            drug_classes.yaml (scope), settings.yaml (endpoints, paths)
src/obesity_ci/    the Python package: config, sources/, landscape/, segmentation/, brief/
scripts/           command-line entry points (pull data, build tables, generate brief)
app/               Streamlit dashboard
data/              raw/ interim/ processed/ (git-ignored, rebuilt by scripts)
briefs/            generated weekly briefs (committed, so the history is visible)
notebooks/         exploration only; anything reused moves into src/
tests/             pytest
docs/              roadmap, data notes, write-up
```
