# M6 decisions: the dashboard

**Objective.** One internal app a brand team opens on Monday morning: what the competitive
landscape looks like, what changed this week, and who the field force should call for the
orforglipron launch, and why. Exit check: a non-technical person answers "who should we target
and why?" in under 2 minutes, and pages load in under ~5 seconds.

## Chunk 1: the app data export (`src/obesity_ci/app_data.py`)

| Decision | Why | Cost |
|---|---|---|
| **The app reads only `app/data/`, a small export (about 2 MB) that is committed to git.** | `data/processed/` is git-ignored and large, but a deployed app is built from GitHub. A small, pre-computed export also keeps page loads fast and means the app never calls an API. | One extra step after each pipeline run: `python scripts/build_app_data.py`, then commit `app/data/`. |
| **Treated as an internal tool: the export includes a prescriber-level call list** (every Tier 1-3 prescriber: NPI, specialty group, state, segment, tier, claims, call-plan flag, action). | A call list is what a brand or sales-ops team actually uses. Everything in it is CMS public data. | The GitHub repo is public, so the list is too. Doctor names stay out (dropped since M4), and a test enforces it. |
| **Aggregates are computed once in the export, not in the app:** the value x fit matrix, a per-state summary, and the headline numbers in `meta.json`. | The app stays simple (read and draw), and the numbers on screen are the same ones the tests check. | None. |
| **Class ids become labels in the export** ("glp1_oral" becomes "GLP-1 receptor agonist (oral)"). | The app shouldn't need our config files to show readable names. | None. |
| **`meta.json` records where every page's data came from** (snapshot dates, Part D data year, build time). | The About page shows data freshness, so nobody mistakes 2024 Part D data for this year's. | None. |

**First export (2026-11-25):** 13 files, 2.2 MB. The call list has 168,281 Tier 1-3 prescribers; the
headline numbers match M4 (45,000 names reach 61.9% of GLP-1 / GIP-GLP-1 claims vs 60.5% for the
grid-based list; 65.9% vs 54.5% are high launch fit).

## Chunk 2: app skeleton and the Landscape page (`app/`)

| Decision | Why | Cost |
|---|---|---|
| **One entry file (`app/streamlit_app.py`) with `st.navigation`; each page is a file in `app/views/`; shared loading and colours in `app/common.py`.** | Pages stay short and readable, and adding a page is one line. Loading is cached (`st.cache_data`), so each file is read once per session. | Needs Streamlit 1.36+ (you have 1.67). |
| **The Overview page answers three questions in three boxes:** what the pipeline looks like, what changed, who to call. Each box links to its page. | A brand lead decides in seconds whether to click further. | Detail lives on the other pages. |
| **Landscape page: class x phase heatmap, sponsor share bar, key-asset table, readout timeline with filters and a trial table.** | Crowding (where competition is heaviest), ownership (who runs the late-stage work), and timing (when readouts land) are the three things CI teams track. | Counts are "class x trial": a trial testing two classes counts once in each, stated on the page. |
| **Colours: blue = Lilly, orange = Novo, grey = everyone else; Phase 3 blue vs Phase 2 orange; one blue ramp for counts.** | The palette was checked with a colour-blind simulator (worst pair still clearly apart). Every chart also has a table or labels, so colour is never the only clue. | None. |
| **Trial IDs link to ClinicalTrials.gov; the readout table downloads as CSV.** | Anyone can check a dot against the source in one click. | None. |
| **Smoke tests run every page with Streamlit's test runner** on the committed `app/data/`, and fail if a page errors or takes over 5 seconds. | Catches a broken page before you open the app. | They test that pages run, not that the charts look right; that's a look-and-check. |
