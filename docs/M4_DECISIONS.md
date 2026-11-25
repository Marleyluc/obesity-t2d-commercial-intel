# M4 decisions: prescriber segmentation

**Objective.** Decide which US prescribers a brand should prioritise, and why. The brand lens is
the **launch of orforglipron** (Lilly's oral GLP-1, US approval 2026-04-01, brand Foundayo).
Orforglipron is not in the data (Part D data year 2024), so we use **analogue behaviour**: who
already prescribes GLP-1s, and especially the oral GLP-1 Rybelsus, are the natural early targets
for a new oral GLP-1.

**Limits that apply to everything below** (details in `docs/DATA_NOTES.md`, section 5):
Medicare Part D only (mostly 65+); 2024 data; prescriber x drug rows under 11 claims are
hidden by CMS; weight-loss-only drugs are largely excluded from Part D coverage, so this
is really a **T2D / cardiometabolic** segmentation, not an obesity one.

## Chunk 1: scope and drug mapping (`src/obesity_ci/transform/prescriptions.py`)

| Decision | Why | Cost |
|---|---|---|
| **Every CMS generic name is mapped by hand** in `config/partd_names.csv` (77 names: 59 in scope, 18 excluded, each with a reason). An unmapped name stops the build. | CMS spells and truncates names its own way ("Dapaglifloz Propaned/Metformin", "Insulin Glargine,hum.Rec.Anlog"). A hand-checked list is reviewable; a new data year can't silently add or lose drugs. | Needs a few minutes of upkeep per data year. |
| **Excluded: bupropion, topiramate and naltrexone on their own, Auvelity, Relistor, Vivitrol.** | The M2 extract caught them because they are *parts* of Contrave and Qsymia, but alone they are antidepressant, epilepsy/migraine and addiction drugs: 11.2M claims and 170k prescribers (incl. psychiatrists) with nothing to do with diabetes. Left in, they would create fake segments. | None. Contrave itself (220 claims) and phentermine alone (378) stay in. |
| **Excluded: insulin syringes, pump cartridges (Omnipod), insulin devices.** | Supplies, not therapy choices. | The insulin pump signal (a marker of complex insulin users) is lost; could come back as a flag later. |
| **A fixed-dose combination counts once, under its newest-mechanism part** (Janumet → DPP-4, Synjardy and Trijardy → SGLT2, Actoplus Met → pioglitazone). | Class shares then add up to 100%, and the prescriber's "most advanced" choice is what matters for adoption. | The metformin part of combinations is not counted as metformin use. |
| **Insulin premixes (70/30, 75/25) count under one part:** human 70/30 → NPH (basal); Novolog/Humalog Mix → the rapid analogue (prandial). | Our classes are basal vs prandial; a premix is both. | Premix users look a little more "basal" or "prandial" than they are. |
| **Biosimilars and new formulations count under their molecule** (Semglee, Rezvoglar → glargine; Lyumjev → lispro; Fiasp → aspart). | Same molecule for the prescriber's therapy choice. | Biosimilar uptake isn't separated (could be a later feature: the CMS brand is kept). |
| **Semaglutide is split by brand:** Rybelsus → oral semaglutide; Ozempic and Wegovy → injectable. | CMS lists all three as "Semaglutide"; oral vs injectable is the key distinction for an oral launch. | None. |
| **Prescriber names and cities are dropped** from the tidy table (NPI, specialty and state kept). | The portfolio shows segments, not named doctors. The data is public, but naming individual "targets" in a public repo is poor form. | A real targeting list would need names; they can be joined back from NPI. |
| **Beneficiary counts hidden by CMS (<11) stay blank, never zero** (`beneficiaries_hidden`). | Zero would understate patients for small prescribers. | Patient-based features must handle blanks. |

**Result on real data (2024):** 89.8% of the extract's claims are kept: 103.8M claims,
316,495 prescribers. Legacy orals are 45% of claims; SGLT2 16%; injectable GLP-1 13.5%;
GIP/GLP-1 (Mounjaro) 4.5%; oral GLP-1 (Rybelsus) 0.9%. Family practice, internal medicine
and nurse practitioners write 77% of claims; endocrinologists are 2% of prescribers but 9% of claims.
