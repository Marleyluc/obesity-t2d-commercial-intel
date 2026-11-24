# Milestone 1: decisions and why (interview prep)

## Why these choices

**Config-driven drug list (`config/drug_classes.yaml`).** Scope is a business decision, not a coding one. Keeping it in one YAML file means a non-programmer can add a molecule, every puller picks it up, and a test catches typos and duplicates. Approval status is *not* stored there; it comes from openFDA, so the config never goes stale.
*Interview line:* "I separated the market definition from the code, the same way a CI team keeps a master asset list."

**Legacy agents are in scope on purpose.** Metformin, sulfonylureas, DPP-4s and older insulins are not the competitive set, but they are the denominator for "uptake of newer agents". Without them you can measure how much tirzepatide a prescriber writes, but not whether they are an early adopter or just a high-volume prescriber.

**DuckDB alongside pandas.** The full Part D Prescriber file is ~25 million rows (several GB). Pandas loads everything into memory; DuckDB queries CSV/Parquet on disk with SQL and only materialises what you ask for. So: DuckDB to filter and aggregate the big file, pandas for the small analysis-ready tables. It also lets you show SQL skills, which commercial analytics roles ask for.

**Cache raw pulls, never overwrite.** Every pull goes to `data/raw/<source>/<date>/`. Three reasons: (1) reproducibility, any result can be rebuilt from a dated snapshot; (2) the weekly "what changed" brief *needs* two snapshots to diff; (3) politeness and speed, you don't hammer public APIs while iterating on analysis.

**raw → interim → processed.** Standard data-pipeline layering. The dashboard reads only `processed/`, so it never makes live API calls and loads fast.

**Secrets in `.env`, never in code or YAML.** `.env` is git-ignored; `.env.example` documents what's needed. In deployment, Streamlit Cloud secrets / GitHub Actions secrets set the same environment variables, so the code doesn't change. A test also fails if a key pattern ever appears in `settings.yaml`.

**`src/` package + `pip install -e .`.** Notebooks and scripts import the same tested code instead of copy-pasting functions. Notebooks are for exploration only.

**Data is not committed; briefs are.** Data is large and rebuildable. Briefs are small and their history is the product ("look at 8 weeks of briefs").

## Data limitations to own (not hide)

1. **Part D is US Medicare only.** Mostly 65+ and disabled beneficiaries. No Canadian equivalent exists publicly. *Framing:* "A proof of method. With IQVIA or provincial claims (e.g. ODB in Ontario) the same pipeline produces a Canadian targeting list."
2. **~2-year lag.** The latest release describes prescribing from about two years ago, before the most recent launches and coverage changes. *Framing:* segmentation is about prescriber *behaviour* (adoption propensity), which is more stable than the specific product mix.
3. **Small-count suppression.** CMS removes any prescriber × drug row with fewer than 11 claims. Low-volume prescribers and newly launched drugs are undercounted, which biases "early adopter" signals downward. We will quantify how many prescribers are affected.
4. **Biggest one: Medicare Part D has historically excluded drugs used for weight loss.** Wegovy/Zepbound appear mainly under covered indications (CV risk reduction, sleep apnoea) and tirzepatide/semaglutide mostly as Mounjaro/Ozempic for T2D. So the Part D half of this project is really a **T2D / cardiometabolic** segmentation. Obesity coverage policy is changing, but that change is after the data window.
5. **ClinicalTrials.gov is sponsor-reported.** Completion dates slip and results are often missing; "primary completion date" is a proxy for readout timing, not the readout itself.
6. **openFDA is US only.** No Health Canada approvals.

## Where I'd push back on the original plan

- **Reframe Part 2 honestly** as T2D/cardiometabolic prescriber segmentation (limitation 4). Pretending it's an obesity targeting model is the first thing an interviewer from Novo or Lilly would catch. Owning it is a strength.
- **"Uptake of newer agents" needs a definition up front.** Proposed: share of a prescriber's in-scope claims from GLP-1, GIP/GLP-1, SGLT2 and GLP-1 fixed-ratio combos. Decided now, tested in M4.
- **K-means alone is a weak story.** We will compare against a simple decile/rules baseline. If clustering doesn't beat it on interpretability or actionability, say so; that is a real analyst finding.
- **The LLM is the smallest part.** The value is in the structured diff (M3). The LLM only writes prose from it, with an ID check so it can't invent trials.
- **Canadian angle.** Your Roche/McKesson background is Canadian. In the write-up, add a short "how this translates to Canada" section (CADTH/CDA-AMC reviews, provincial formularies, private payers). That turns the US-only data from a weakness into a talking point.
