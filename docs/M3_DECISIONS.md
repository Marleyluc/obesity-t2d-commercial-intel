# M3 decisions: landscape tracker

Each rule below changes the numbers in the dashboard, so it is written down with the reason.

## Chunk 1: trials table (`src/obesity_ci/transform/trials.py`)

| Decision | Why | Cost |
|---|---|---|
| **We decide which molecule a trial is about** by matching our names (generic, brands, code names) against the trial's listed drug interventions. Which search found the trial is kept (`found_by`) but not trusted. | The API expands search terms. In the 2026-11-24 snapshot, 1,047 trials returned by molecule searches name no tracked molecule at all: they list a class ("GLP-1 receptor agonists", "SGLT2 inhibitor"), a procedure, or an unrelated drug. | Misspellings ("tirzapatide", "dapagliflozine") and non-US brands ("Forxiga") are missed. Small, and visible in `trials_unmatched.csv`. |
| **One trial can link to several molecules** (`trial_molecules` table). Views count a trial once per class. | Head-to-head trials (semaglutide vs tirzepatide) genuinely involve both. | Comparator arms count as involvement (see open item). |
| **A combination absorbs its parts.** A CagriSema trial links to cagrilintide/semaglutide only; an oral semaglutide trial links to oral semaglutide only. | Otherwise every CagriSema trial inflates the semaglutide count. | A trial that tests the combination against a component loses the component link. |
| **Only `track_trials: true` molecules are linked.** | Metformin, sulfonylureas and older insulins appear mostly as background therapy. | Legacy agents have no trial view (by design: they are the denominator in M4, not competitors). |
| **No-phase trials kept, labelled "Not applicable"** (1,172 trials). Pipeline views will use Phase 1–3 only. | They show medical interest (real-world and investigator studies) but are not pipeline. | None; it's a filter. |
| **"Originator-sponsored" flag**: lead sponsor contains the config sponsor name. | Separates company pipeline from investigator-initiated research (tirzepatide: 80 of 254 linked trials are Lilly-sponsored). | Name-based; a subsidiary with a different name would be missed. |
| **Month-only dates** ("2027-03") are read as the 1st of the month. | CT.gov often gives month precision for future dates. | Readout timing is approximate to the month anyway. |

**Open item:** we don't pull arm roles (experimental vs active comparator), so a trial that uses insulin glargine as the comparator counts as a glargine trial. Adding `ArmGroupType` and `ArmGroupInterventionName` to the CT.gov fields before the next pull would fix this. Decide in chunk 5.

## Chunk 2: FDA approvals (`src/obesity_ci/transform/approvals.py`)

| Decision | Why | Cost |
|---|---|---|
| **Molecules come from each product's active ingredients**, not from which search found the application. A combination needs all its parts in the same product, then absorbs them. | Searches over-match (e.g. a naltrexone search also returns Vivitrol, which is not Contrave). Ingredients are the regulator's own record. | FDA names human insulins differently ("INSULIN SUSP ISOPHANE RECOMBINANT HUMAN"), so those need a small alias list in the code. |
| **Oral vs injectable semaglutide is decided by product route.** | The ingredient is "SEMAGLUTIDE" in both Ozempic and Rybelsus. This also correctly files the oral Wegovy approval (NDA218316, 2025-12-22) under oral semaglutide. | Relies on the route field, which is occasionally filled with a dosage form ("SOLUTION"); those are treated as non-oral. |
| **Fixed-dose combinations with legacy drugs link to both** (Janumet = sitagliptin + metformin). | Both molecules are genuinely in the product. | Pipeline views should filter to NDA/BLA and newer classes to avoid counting FDCs as new entrants. |
| **"Efficacy supplement" is used as the signal for a new indication or population.** | It's the FDA class code for clinical-evidence supplements. | It doesn't say *which* indication. The label's "Recent major changes" section and a label diff between snapshots (chunk 4) fill that in. |
| **Primary label = highest-version label from a non-repackager.** | Pharmacies and distributors publish copies of labels; one repackager copy had a higher version than Lilly's own Mounjaro label. | For Ozempic (NDA209637), Wegovy and Levemir only repackager copies came back: the manufacturer's label is missing from the pull (same `openfda` field gap as M2). Fix the label search at the next pull. |

## Chunk 3: Canada (`src/obesity_ci/transform/canada.py`)

| Decision | Why | Cost |
|---|---|---|
| **Canada lag = first Canadian market date − first US approval** (NDA/BLA only, ANDAs ignored). Negative means Canada first. | Health Canada gives the current status only: for marketed products we have the market date, not the approval date. Market date is also what matters commercially (patients can get it). | It mixes "approval" (US) with "launch" (Canada), so it overstates the regulatory gap by the launch delay. Stated wherever the lag is shown. |
| **Lags are reliable only for "newer" molecules.** Legacy molecules were searched by US brand names only (`lag_reliable = False`). | The M2 puller searched legacy molecules by brand to avoid hundreds of generics. | Legacy lags are indicative at best; insulin aspart shows 200 months because NovoRapid (the Canadian brand) wasn't searched. |
| **Only single-molecule products set a molecule's dates.** A combination counts for the combination. | Otherwise Janumet could move sitagliptin's dates. | None in practice. |
| **Ontario coverage is matched from Ontario's own generic names**, not through Health Canada DINs. | Our Health Canada pull misses some legacy brands; the formulary lists everything it covers. | Ontario generic names are free text ("INSULIN (ISOPHANE) HUMAN BIOSYNTHETIC"); the matcher handles these, and the test file pins the examples. |
| **Coverage labels: General benefit / Limited Use / Listed, not a benefit / Not listed.** Limited Use = the product's group carries clinical criteria (`lccNote` with a reason-for-use id); "not a benefit" = the `notABenefit` flag. | These two are self-describing in the data (LU notes literally say "LU Authorization Period"). | Other flags (`sec3`, `sec12`, `sec3b`, `chronicUseMed`, ...) are kept raw in `raw_flags`, not labelled, because the schema doesn't define them. |
| **Oral vs injectable in Canada is inferred** from a per-mL strength or a pen/vial descriptor (Health Canada) and the dosage form (Ontario). | The DPD product record has no route field. | Heuristic; pinned by tests on Rybelsus vs Ozempic. |
| **CDA-AMC step not built yet.** | The funnel is approved → CDA-AMC recommendation → Ontario listing; CDA-AMC has no API, so `config/cda_amc_reviews.csv` has to be curated by hand. | The funnel currently skips the middle step. |
