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

## Chunk 4: change log (`src/obesity_ci/transform/changes.py`)

| Decision | Why | Cost |
|---|---|---|
| **Compare tidy tables, not raw JSON.** Both snapshots are rebuilt with the same rules, then compared field by field. | Raw records change for trivial reasons (field order, formatting). Comparing the fields we use means every change is one a reader can act on. | A change in a field we don't keep (e.g. eligibility criteria) is invisible. |
| **One row per change, always with its ID** (NCT number, application number, DIN). | The M5 brief must cite IDs, and its guardrail checks every cited ID exists in this file. | None. |
| **New trials that name none of our molecules are dropped**, unless found by the condition sweep. | Same reason as chunk 1: the API's search expansion would otherwise report noise as "new trials". | A genuinely new trial under an unknown code name appears only if the condition sweep finds it. |
| **"No longer returned" is reported as low importance, not as a deletion.** | Trials rarely disappear from the registry; usually our search stopped matching them. | Needs a human check before it goes in a brief. |
| **Importance rules** (high / medium / low): high = new or stopped Phase 2/3+ trial, late-stage completion or results, new approval / tentative approval / efficacy supplement, Canadian launch, Ontario coverage change. Medium = phase change, late-stage readout slip > 90 days, generic final approval, label indication change. Everything else low. | Lets the brief and dashboard lead with what a brand team would act on. | A simple rule set, not a model; tune it after reading a few real change logs. |
| **Sanity check on real data:** comparing the 2026-11-24 snapshot with an identical copy gives **0 changes**; editing one trial's status gives exactly that 1 change. | Proves there are no false positives from the rebuild itself. | The ~10 real changes hand check (exit criterion) still needs a second real pull. |

## Chunk 5: landscape views (`src/obesity_ci/transform/landscape.py`)

| Decision | Why | Cost |
|---|---|---|
| **"Pipeline" = interventional, active (not yet recruiting / recruiting / enrolling by invitation / active not recruiting), Phase 1 to 3, industry-sponsored.** | This is the set that reflects company development bets. Phase 4 means already approved; completed or stopped trials are history; investigator studies don't signal a company's plans. | An active trial can have already read out (e.g. ATTAIN-1, REDEFINE 1 are "active, not recruiting" with 2024-25 completion dates), so counts include some trials that are in follow-up. |
| **Class × phase counts each trial once per class.** A CagriSema vs semaglutide trial counts once for amylin and once for injectable GLP-1. | Answers "how much activity is there in this class", which is what the table is for. | Row totals add up to more than the number of distinct trials. |
| **Sponsor share uses late-stage trials only** (Phase 2/3 and 3), by lead sponsor. | Late-stage trials are expensive, so they show real commitment; Phase 1 counts are inflated by small PK studies. | Counts trials, not patients or spend; a few huge outcomes trials look the same as small ones. Collaborators (e.g. Zealand with Roche) are not credited. |
| **"Upcoming readout" = primary completion date in the next 18 months, Phase 2+.** | Primary completion is the registry's best proxy for when topline data can come. | It is the sponsor's estimate and slips often (the change log tracks slips); topline press releases usually follow 1 to 3 months later. |
| **Assets table covers "newer" tracked molecules only.** | Legacy molecules (metformin, sulfonylureas) aren't where competitive moves happen. | None for the use case. |
| **If the Canada build fails, the landscape still builds and prints a warning** with the reason; the Canada columns stay empty. | Trials and FDA data shouldn't be blocked by a missing Canada pull, but a silent gap would be misleading. | None. |
| **Hand check (exit criterion), 2026-11-24 data:** retatrutide = Phase 3, 9 active late-stage trials (TRIUMPH-1 to -9 present, TRIUMPH-1 to -4 completed), no US approval; orforglipron = US approval 2026-04-01 (Foundayo), 17 active late-stage trials (ACHIEVE / ATTAIN programmes), approved but not yet marketed in Canada; CagriSema = Phase 3, 9 active late-stage trials (REDEFINE / REIMAGINE), no US approval. | Matches the companies' public pipelines as of our knowledge. | Approval status depends on our openFDA pull; anything approved after 2026-11-24 appears only after the next pull. |
