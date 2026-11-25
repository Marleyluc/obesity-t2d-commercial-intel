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

## Chunk 2: one row per prescriber (`src/obesity_ci/transform/prescribers.py`)

| Decision | Why | Cost |
|---|---|---|
| **Five feature groups:** value (in-scope claims, cost, incretin claims), mix (share of claims by class group, sums to 100%), adoption (newer-agent share, incretin share), launch fit (oral share and Lilly share of the prescriber's incretin claims), context (specialty group, Census region, state). | Mirrors how a brand team describes a prescriber: how big, what they write, how modern, how close to our product. | Only what Part D shows; no patient mix, payer mix or rep access. |
| **"Incretin" = injectable GLP-1, oral GLP-1, GIP/GLP-1 and insulin/GLP-1 combinations.** | The class orforglipron competes in. | SGLT2 is "newer" but not incretin; cardiometabolic prescribers who live on SGLT2 look low on incretin adoption by design. |
| **Launch-fit shares are blank, not zero, for prescribers with no incretin claims.** | "0% oral" for someone who writes no GLP-1 at all would be misleading. | Clustering must handle the blanks (chunk 4). |
| **Eligible for segmentation = at least 50 in-scope claims** (229,476 prescribers, 72.5%, writing 98.0% of claims). The rest stay in the table as a "low volume" group. | Shares from a handful of claims are noise, and CMS already hides drug rows under 11 claims. | 87k small prescribers aren't profiled; together they write 2% of claims. |
| **Beneficiaries = the largest single-drug patient count**, not a sum. | One patient can be on several drugs; summing double-counts. | It's a floor on the diabetes panel, not the panel size. |
| **Specialty groups:** primary care physician, NP/PA, endocrinology, cardiology, nephrology, other. | 131 CMS specialty labels are too many to profile; these are the groups a field force is organised around. | "Other" mixes small specialties. |
| **Volume deciles among eligible prescribers** (10 = top 10% by in-scope claims). | The standard pharma value measure; also the rules baseline in chunk 3. | Volume = Medicare claims only. |

**Result on real data (2024):** top 10% of eligible prescribers write 38.7% of claims (each has
964+ claims). Endocrinologists: median 1,228 claims, 30.5% incretin share. Cardiology and
nephrology: about 85% SGLT2 (heart and kidney indications), little incretin. 79.4% of eligible
prescribers write some incretin; 15.3% (35,045) write Rybelsus; only 522 top-decile prescribers
write none.

## Chunk 3: rules-based baseline (`src/obesity_ci/segment/baseline.py`)

| Decision | Why | Cost |
|---|---|---|
| **Baseline = value tier x GLP-1 adoption tier**, a 3 x 3 grid plus "low volume (not profiled)". | It's what most brand teams actually use, so it's the bar the clustering must beat: if k-means adds nothing, we keep the grid. | Two dimensions only: it can't see oral preference, specialty or SGLT2-led cardiometabolic prescribers. |
| **Value tiers from volume deciles:** High = 8-10, Medium = 5-7, Low = 1-4. | Top three deciles is the usual "core target" cut. | Volume is Medicare claims only. |
| **Adoption tiers at fixed cut-offs:** Low < 10%, Moderate 10-25%, High >= 25% incretin share. | Round numbers a brand lead can remember, close to the data's tertiles (10.3% and 24.0%). | Fixed cut-offs drift as the class grows; revisit with each data year. |
| **Launch priority for orforglipron:** A = High value with Moderate or High adoption; B = High value with Low adoption, or Medium value with Moderate or High adoption; C = the rest of the profiled. | A new incretin is adopted first by big prescribers already comfortable with the class; big non-users need a class-conversion sell (slower, so second wave). | A rule, not an estimate of response; chunk 5 sanity-checks it against reach (how many prescribers a field force can actually cover). |

**Result on real data (2024):** priority A = 53,472 prescribers (23% of profiled) writing 52% of
in-scope claims and 64% of incretin claims; 38% of them already write Rybelsus. B = 65,166
(24% of incretin claims); C = 110,838 (10.5%). The "Low value / Low adoption" cell is 40% SGLT2,
which is the cardiology/nephrology group the grid can't tell apart from small generic prescribers:
one reason to try clustering in chunk 4.

## Chunk 4: behavioural clusters (`src/obesity_ci/segment/clusters.py`)

| Decision | Why | Cost |
|---|---|---|
| **Cluster on the 7 class-mix shares only** (standardised), not volume. | The grid already ranks by volume. Clustering on mix answers a different question, "what kind of prescriber is this?", and chunk 5 crosses it with value. | Two prescribers with the same mix but 10x different volume land in the same cluster (by design). |
| **k-means, k = 7.** Scan of k = 3..10: silhouette peaks at k = 6 (0.275); k = 7 is 0.266 with stability 0.984 (k = 4 and 10 are unstable, ~0.8 and 0.5). | k = 7 splits GLP-1 users into Ozempic/Trulicity-led and Mounjaro-led, the distinction a Lilly launch needs; the separation cost is small. | Silhouette ~0.27 means real but overlapping groups: prescribers sit on a continuum, so cluster edges are soft. Said wherever clusters are shown. |
| **Stability = adjusted Rand index between the reference fit and 5 refits on bootstrap samples with new seeds.** | Directly tests the exit criterion "segments are stable". | Tests stability to sampling, not to a new data year (check that with 2025 data). |
| **Clusters are named from their most distinctive feature** (highest centre z-score). | Names don't depend on k-means' arbitrary label numbers, so they're reproducible run to run. | A name summarises a tendency: "Generic-first" prescribers still write 10% incretin on average. |
| **Low-volume prescribers keep the label "Low volume (not profiled)".** | Same rule as chunk 3. | None. |

**Result on real data (2024):** silhouette 0.266; stability mean ARI 0.981 (min 0.970): PASS.
Agreement with the baseline grid is low (ARI 0.104), so the clusters add information.
The seven groups: Generic-first (70k prescribers, 26% of claims), Injectable GLP-1 adopters
(61k, 36% of incretin claims), Insulin-intensive (24k, 16% endocrinologists), DPP-4 loyal (28k),
Tirzepatide-led (18k, Lilly = 65% of their incretin claims), Oral GLP-1 users (10k, all write
Rybelsus), SGLT2 cardiorenal (18k, 95% SGLT2, mostly cardiology/nephrology).

**What the grid misses (corrected in chunk 5):** half of the Tirzepatide-led (9,339) and a third of
the Oral GLP-1 users (3,524) are in baseline priority C. Chunk 5 showed these are almost all
*low-volume* prescribers (Tirzepatide-led in C: median 102 claims, 2.5% of GLP-1 claims), so they
rightly stay off the rep call list. The clusters' real contribution is the prescribing *style*:
it changes about 6,000 names on a 45,000-name call plan and, above all, the message to each group.

## Chunk 5: targeting recommendation (`src/obesity_ci/segment/targeting.py`)

| Decision | Why | Cost |
|---|---|---|
| **Targeting matrix = value tier (chunk 3) x launch fit (from the cluster, chunk 4).** | Value says how much a prescriber matters; launch fit says how easy the orforglipron conversation is. Together they are the classic "value vs opportunity" matrix. | Opportunity is inferred from 2024 behaviour, not measured intent. |
| **Launch fit per cluster is a written judgement:** High = oral GLP-1 users, Tirzepatide-led, injectable GLP-1 adopters; Medium = DPP-4 loyal, generic-first, insulin-intensive; Low = SGLT2 cardiorenal. | Prescribers already in the class adopt a new option fastest; pill-first non-users are a slower class-conversion sell; cardiorenal specialists are a different conversation. Written in code so it can be challenged. | A different launch (e.g. an injectable) would rate the clusters differently. |
| **Tiers:** 1 = High value x High fit; 2 = High x Medium or Medium x High; 3 = Medium x Medium or Low x High; 4 = everything else. Each tier has one channel action. | Simple enough for a brand lead to remember and defend. | Tier edges are hard cut-offs. |
| **Call plan capacity = 45,000 prescribers** (assumed ~300 reps x ~150 targets), filled by tier, then by incretin claims. | A target list longer than the field force can reach isn't a plan. | The size is an assumption (`CALL_CAPACITY`); real field forces for a major launch range widely. |
| **The plan is compared with the same-size list from the baseline grid.** | To show honestly what the clustering adds. | None. |
| **Segment cards:** each cluster has a name, one-line description, size, tier counts and a recommended action and message. | The M4 exit criterion; also what goes on the dashboard. | Messages are illustrative brand thinking, not tested claims; orforglipron vs Rybelsus wording would need medical/legal review. |

**Result on real data (2024):** Tier 1 = 25,570 prescribers (32% of GLP-1 claims), all in the call plan;
the remaining 19,430 call slots go to the top of Tier 2 (72,323 prescribers). The 45,000-prescriber
call plan reaches **61.9% of GLP-1 claims** and 47.7% of all in-scope claims: 28.8k primary care
physicians, 10.5k NPs/PAs, 4.5k endocrinologists.

**What the clusters add, honestly:** a grid-based list of the same size reaches 60.5% of GLP-1
claims, and 39,024 prescribers (87%) are on both lists. So the clusters don't change *who* much.
They raise the share of the list already prescribing in the class from 54% to 66% (swapping about
6,000 generic-first, DPP-4 and cardiorenal prescribers for GLP-1, Mounjaro and Rybelsus users),
and they give each group its own message, which the grid can't.

## Data limitations (exit criterion)

1. **Medicare Part D only**, mostly people aged 65+. Commercially insured and Medicaid patients
   (most new GLP-1 use in younger adults) are not here, so the targeting is for the Medicare book.
   Commercial prescribing could rank prescribers differently.
2. **2024 data, before orforglipron launched (April 2026).** The targeting uses analogue behaviour
   (GLP-1 and oral GLP-1 use), not actual orforglipron uptake.
3. **Weight-loss-only drugs are largely excluded from Part D**, so this is a T2D / cardiometabolic
   segmentation. Obesity-focused prescribers (e.g. Zepbound and Wegovy for weight) are invisible.
4. **Rows under 11 claims are hidden by CMS.** A prescriber's occasional use of a drug disappears,
   which makes small-volume behaviour look more concentrated, and makes early adopters of new
   drugs look like non-users.
5. **Claims, not patients or outcomes.** 90-day fills count as one claim; patient counts are a floor.
6. **No access or payer information:** formulary status, prior-authorisation burden and rep access
   ("no-see" offices) all drive real targeting and are not in this data.
7. **Rural/urban not included.** The ROADMAP listed it; it needs the Part D "by Provider" file
   (prescriber ZIP and RUCA code), a possible later addition.
8. **Clusters overlap** (silhouette 0.27): prescribers sit on a spectrum, so segment edges are soft.
   Stable to resampling (adjusted Rand 0.98), but not yet tested on a second data year.
9. **Launch-fit ratings, tier rules and the 45,000 call capacity are judgements or assumptions**,
   stated in the code, not estimated from response data.

**Exit criteria check (2026-11-25):** stable segments (bootstrap adjusted Rand 0.981, PASS); every
segment has a name, description, size and recommended action (`segment_cards.csv`); limitations
written up (above). M4 done.
