# Roadmap: Obesity & T2D Commercial Intelligence App

Each milestone has an **exit criterion**: a concrete, checkable thing that must be true before moving on. If it isn't true, the milestone isn't done.

| # | Milestone | Status |
|---|-----------|--------|
| 1 | Setup | ✅ Done (2026-11-24) |
| 2 | Data acquisition | ✅ Done (2026-11-24) |
| 3 | Landscape tracker | 🟡 Built; waiting on the change-log hand check after a second pull |
| 4 | Prescriber segmentation | ✅ Done (2026-11-25) |
| 5 | LLM "what changed" brief | 🟡 Built; first real brief 2026-11-25 (guardrail passed). Needs 3 weekly briefs in a row |
| 6 | Streamlit dashboard | ⚪ Not started |
| 7 | Write-up & README | ⚪ Not started |

## Canada scope (added 2026-11-24)
There is **no public Canadian equivalent of Part D**, meaning no prescriber-level claims data. So Canada enters as a **market access layer**, not as a second segmentation:
- **Health Canada approvals** (Drug Product Database API), compared with FDA dates to show the approval lag
- **Reimbursement funnel:** Health Canada approved → CDA-AMC recommendation → listed on the Ontario Drug Benefit formulary (plus its Limited Use criteria)
- **Canadian trial activity:** ClinicalTrials.gov trials with Canadian sites, by sponsor and class
- **Translation section** in the write-up: how the US segmentation method would run on Canadian data (IQVIA, provincial claims via ICES)

---

## M1. Setup
**Goal:** a clean, reproducible repo that anyone can clone and run.

Deliverables
- Repo structure, `pyproject.toml`, virtual environment, `.gitignore`, `.env.example`
- `config/drug_classes.yaml`: the single source of truth for which molecules and classes are in scope
- `config/settings.yaml`: API endpoints, paths, Part D year, LLM model
- `scripts/check_setup.py`: verifies Python version, packages, secrets, and that each API answers
- `tests/test_config.py`: validates the drug class config
- First commit pushed to a public GitHub repo

**Exit criteria**
- `pytest` passes
- `python scripts/check_setup.py` shows all required checks green
- Repo is on GitHub with no secrets in history (`git log -p | grep -i "sk-"` returns nothing)

## M2. Data acquisition
**Goal:** raw data from all three sources, cached locally, reproducible with one command per source.

Deliverables
- `src/obesity_ci/sources/ctgov.py`: ClinicalTrials.gov API v2 puller (paginated, by condition and intervention)
- `src/obesity_ci/sources/openfda.py`: Drugs@FDA approvals + label pulls for in-scope molecules
- `src/obesity_ci/sources/partd.py`: CMS Part D Prescriber (by Provider and Drug) download, filtered to in-scope drugs, saved as Parquet
- `src/obesity_ci/sources/hc_dpd.py` and `ontario_odb.py`: Health Canada approvals and Ontario formulary listings; `config/cda_amc_reviews.csv` curated by hand
- Dated raw snapshots in `data/raw/<source>/<YYYY-MM-DD>/` (never overwritten)
- A short data profile note per source: row counts, date coverage, missingness, suppression

**Exit criteria**
- Each puller re-runs end to end from a clean `data/` folder
- Every in-scope molecule in `drug_classes.yaml` is matched (or explicitly flagged as unmatched) in each source
- Part D filtered extract loads into DuckDB and row counts reconcile with CMS's published totals for those drugs

## M3. Landscape tracker
**Goal:** turn raw trial/approval data into a structured view of the competitive landscape, and a diff between two snapshots.

Deliverables
- Normalised tables: `trials` (NCT ID, sponsor, molecule, class, phase, status, primary completion date, enrolment) and `approvals` (molecule, brand, indication, approval date, label changes)
- Snapshot diff logic: new trials, phase changes, status changes (e.g. Recruiting → Completed / Terminated), new approvals or label updates
- Landscape views: pipeline by class × phase, sponsor share of late-stage trials, upcoming primary completion dates (a proxy for readout timing)

**Exit criteria**
- Diff function produces a correct change log between two real snapshots (validated by hand on ~10 changes)
- Class × phase table matches a manual sanity check on 3 known assets (e.g. retatrutide, orforglipron, CagriSema)

Canada view: approval lag vs. FDA and the reimbursement funnel (approved → CDA-AMC → ODB listed) per molecule.

**So what:** competitive intelligence teams maintain exactly this view to anticipate competitor launches, readouts and label expansions.

## M4. Prescriber segmentation
**Goal:** cluster Medicare Part D prescribers by behaviour and translate clusters into a targeting recommendation.

Deliverables
- Prescriber-level feature table: total claims in scope, class mix shares, newer-agent share (GLP-1 / GIP-GLP-1 / SGLT2 vs. legacy agents), specialty, state / urban-rural, beneficiary counts (urban-rural not done: needs the Part D "by Provider" file; see docs/M4_DECISIONS.md)
- Clustering (k-means on scaled features, with k chosen by silhouette + business interpretability; compare with a simple rules-based decile segmentation as a baseline)
- Segment profiles and a targeting matrix (value vs. opportunity)

**Exit criteria**
- Segments are stable (similar profiles across random seeds / bootstrap samples)
- Each segment has a name, a one-line description, size, and a recommended action a brand team could take
- Data limitations written up (see below)

**So what:** sales force targeting, call-plan prioritisation, and medical/peer-to-peer programme design.

## M5. LLM "what changed" brief
**Goal:** a weekly, grounded brief generated from the M3 change log.

Deliverables
- Prompt that receives **only** the structured change log (no free-roaming), with instructions to cite NCT IDs / application numbers
- Output saved to `briefs/YYYY-MM-DD.md`
- Simple guardrail check: every NCT ID or application number in the brief exists in the input change log

**Exit criteria**
- Three consecutive briefs generated from real snapshots with zero ungrounded IDs
- Brief reads like something a CI analyst would send to a brand lead (sections: approvals, late-stage readouts, new entrants, implications)

## M6. Streamlit dashboard
**Goal:** one app combining both parts.

Deliverables
- Pages: Landscape (pipeline, timeline), What changed (latest brief + diff table), Prescriber segments (profiles, map, targeting matrix), About the data (sources, limits)
- Reads only from `data/processed/` (no live API calls on page load)
- Deployed to Streamlit Community Cloud

**Exit criteria**
- App loads in under ~5 seconds from processed data
- A non-technical person can answer "who should we target and why?" in under 2 minutes

## M7. Write-up
**Goal:** the version a hiring manager reads.

Deliverables
- Business-focused README: problem, approach, key findings, screenshots, limitations, how to run
- 1–2 page write-up / LinkedIn post: the question, three findings, what a brand team would do, what I'd do with real commercial data (IQVIA, Symphony, Canadian provincial claims)

**Exit criteria**
- README explains the commercial question in the first three lines
- Every claim in the write-up is traceable to a chart or table in the app
