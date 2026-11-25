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

## Chunk 3: the What changed page (`app/views/changes.py`)

| Decision | Why | Cost |
|---|---|---|
| **Two tabs: the brief first, then every change.** | The brand lead reads the memo; the analyst checks the rows behind it. | None. |
| **Every [ID] in the brief becomes a link** (NCT to ClinicalTrials.gov, NDA/BLA/ANDA to Drugs@FDA), and adjacent citations are shown as one list. | One click from a sentence to its source record is what makes a grounded brief checkable. | DINs stay plain text: Health Canada has no stable per-DIN link. |
| **"Evidence" expander shows the exact rows the model saw** (`brief.input.json`). | Shows the grounding, not just claims it. | None. |
| **Housekeeping rows ("Primary label source changed", "No longer returned") are hidden by default and counted in their own box.** | They describe our pipeline, not the market, and need a human check first (same rule as the brief). | One toggle to see them. |

## Chunk 4: Who to target and Call list (`app/views/segments.py`, `app/views/call_list.py`)

| Decision | Why | Cost |
|---|---|---|
| **The page opens with the answer in one paragraph**, then four numbers, then the evidence. | The exit test is "who should we target and why, in under 2 minutes". The answer has to be readable before any chart. | None. |
| **Targeting matrix coloured by tier, not by count.** Each box shows tier, prescribers and share of GLP-1 claims. | The tier is the decision; colour should point at it. Counts are printed, so nothing depends on reading shades. | None. |
| **One card per segment** with fit, size, share of GLP-1 claims, names in the plan, description and recommended action. | Matches the M4 exit criterion (name, description, size, action) and is what a brand team would brief reps with. | None. |
| **US map with a switch:** names in the call plan, or % of the state's GLP-1 claims reached. | Raw names mostly follow population; the % view shows where the plan is thin, which is a case for inside sales or digital rather than more reps. | Territories and unknown states are in the table only. The map shapes load from Plotly's CDN, so the map needs internet. |
| **Call list: filters (state, specialty, segment, tier, in-plan), NPI search, registry look-up link, full CSV download.** | It's the file sales operations would load into the CRM. Names stay out of our data; the NPI registry link shows who it is when needed. | The table shows the first 5,000 rows for speed; the download has all. |

## Chunk 5: About page, speed, deployment

| Decision | Why | Cost |
|---|---|---|
| **About page: sources with "as of" dates from `meta.json`, the method in three bullets, and the nine limits** a reader must know (from M4, plus trial-date caveats). | A dashboard without visible freshness and limits invites the wrong conclusion (e.g. treating 2024 Medicare data as this year's whole market). | None. |
| **Speed check:** each page renders in 0.2-0.8 s in Streamlit's test runner (cold, in the cloud sandbox), against the < 5 s target; the smoke tests fail if any page takes over 5 s. | The exit criterion, checked by a test rather than by eye. | The browser adds network time when deployed. |
| **`app/requirements.txt` lists only what the app needs** (streamlit, pandas, pyarrow, plotly), pinned to the versions tested. | Streamlit Community Cloud installs from the entry file's folder first; a short list builds faster and avoids installing the whole pipeline. | Update the pins when you upgrade locally. |
| **Deployed on Streamlit Community Cloud from `main`, entry file `app/streamlit_app.py`.** | Free and connected to GitHub: each push redeploys. | Free-tier apps sleep after inactivity and take ~30 s to wake. Treated as internal in the write-up; the link itself is public unless restricted in the app's sharing settings. |

## Design pass (2026-11-25)

| Decision | Why | Cost |
|---|---|---|
| **A theme in `.streamlit/config.toml`:** Inter font, navy sidebar, one blue accent shared with the charts, rounded bordered cards, softer table headers. | Reads as a product rather than a notebook; one accent colour keeps charts and UI consistent. | Inter loads from Google Fonts; without internet the app falls back to the system font. |
| **Navigation grouped (Market, Field force, Reference) with Material icons instead of emoji.** | Mirrors how a brand team thinks about the questions, and looks like enterprise software. | None. |
| **Every page opens with a section label, title and one-line purpose; headline numbers sit in bordered KPI cards.** | Consistent page anatomy: the reader always knows where they are and what the page answers. | None. |
| **One Plotly template for all charts** (font, muted axes, hover style). | Charts match the app instead of Plotly's defaults. | None. |
| **The developer "Deploy" menu is hidden from viewers** (`client.toolbarMode = "viewer"`). | Viewers of an internal tool shouldn't see developer controls. | Run locally with `--client.toolbarMode developer` if you need them. |

## Website-style redesign (2026-11-25)

| Decision | Why | Cost |
|---|---|---|
| **Top navigation bar with a logo (`app/assets/logo.svg`) and drop-down groups, instead of a sidebar.** | Reads like a web product; more room for content. | None. |
| **A gradient header band on every page** (section label, title, purpose, data-freshness chips), a centred 1,240 px content width, and a footer with methodology and source links. | Consistent page anatomy, and the reader always sees how fresh the data is. | Custom CSS (`common.CSS`) targets Streamlit's element ids; a future Streamlit release could change them, so re-check the look after upgrading. |
| **KPI tiles with an accent bar and soft shadow; cards (`st.container(key="card-...")`) lift on hover; links styled as pill buttons.** | Clear visual hierarchy: numbers, then cards, then detail. | None. |
| **Stayed in Streamlit rather than rebuilding as a custom website (e.g. React).** | Same look for a fraction of the work, and the Python pipeline, tests and deployment stay as they are. | Less pixel-level control than a hand-built site. |
