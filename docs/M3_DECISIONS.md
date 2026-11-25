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
