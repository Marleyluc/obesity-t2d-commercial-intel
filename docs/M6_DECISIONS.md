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
