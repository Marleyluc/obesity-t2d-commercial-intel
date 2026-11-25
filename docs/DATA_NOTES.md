# Data notes

What each source contains, what it doesn't, and the problems we found while pulling it.
Written during Milestone 2, from the first pulls on 24–25 Nov 2026 (snapshot folders `data/raw/<source>/2026-11-24/`).

**Why this document exists:** every number in the dashboard inherits the limits of its source. Writing them down once, with evidence, means the dashboard, the README and interview answers all say the same honest thing.

## Summary

| Source | What it answers | Snapshot size | Biggest limitation |
|---|---|---|---|
| ClinicalTrials.gov | Who is developing what, at which phase, and when results are due | 6,848 unique trials (43 queries) | Sponsor-reported; early trials often registered under code names |
| openFDA (Drugs@FDA + labels) | What is approved in the US, when, and for what | 466 applications (355 ANDA, 76 NDA, 35 BLA) | Harmonised `openfda` fields are missing on some records |
| Health Canada DPD | What is approved and marketed in Canada, and when it launched | 328 products (by DIN) | Gives current status only, not the full status history |
| Ontario ODB Formulary | What Ontario's public plan pays for, and at what price | Edition dated 2026-10-28 (3.6 MB XML) | One province, public plan only; coverage codes need the schema to decode |
| CMS Medicare Part D | Who prescribes what, how much, where | 2,574,196 prescriber × drug rows, data year 2024 | Medicare only, ~2-year lag, <11-claim rows suppressed, weight-loss drugs excluded |

---

## 1. ClinicalTrials.gov (API v2)

**Contains:** one record per registered trial: status, phase, sponsor, start and primary completion dates, enrolment, interventions, conditions, countries. We pull only the fields we use (no results section).

**How we query:** one search per tracked molecule (generic + brand + code names), plus a sweep of recent (2018+) interventional Phase 2/3 trials for obesity and type 2 diabetes to catch assets not yet in our config.

**Limitations**
- Sponsor-reported and not audited; dates slip and statuses can be stale.
- "Primary completion date" is a proxy for when results arrive, not the readout itself.
- Many records are investigator-initiated (e.g. only 82 of 324 tirzepatide trials are Lilly-sponsored). Useful as a signal of medical interest, but not "pipeline".
- About 30% of tirzepatide records have no phase or `NA` (observational / non-drug studies). M3 must decide how to treat these.

**Issues found and fixed**
- **Synonym expansion over-matches.** Searching "insulin regular" returned 8,261 trials, mostly unrelated studies that merely measure insulin. The API expands terms to medical concepts. Fix: trial searches switched off for regular and NPH human insulin (`track_trials: false`).
- **Code names hide major assets.** Amycretin returned 1 trial by name; the condition sweep found 12+ registered only as `NNC0487-0111`. Fix: alias added (now 23 trials). M3 will list sweep trials that match no configured molecule, so new code names surface automatically.
- **Duplicate condition terms.** "Type 2 Diabetes" and "Diabetes Mellitus, Type 2" returned identical results (844), so one was dropped, along with "Overweight" (overlaps Obesity).
- **Trade-off accepted:** removing the short alias `BIF` reduced efsitora from 30 to 19 trials. Some of the 11 may be genuine early studies; precision was chosen over recall.

**Canada:** no separate pull. Every record has `LocationCountry`, so "trials with Canadian sites" is a filter (e.g. 25 tirzepatide trials).

## 2. openFDA: Drugs@FDA and drug labels

**Contains:** one record per FDA application (NDA, BLA or ANDA) with every submission (original approval, supplements for new indications, labelling and manufacturing changes), and current labels per brand.

**Limitations**
- US only.
- An application is not a product launch: an approval date doesn't mean the drug is on the market.
- ANDAs (generics) dominate counts for old drugs (e.g. 214 metformin results). Useful as a generic-competition signal, noise for pipeline views.

**Issues found and fixed**
- **Missing harmonised fields.** Searching only `openfda.*` found 1 semaglutide application and missed Ozempic and Wegovy. Fix: also search `products.brand_name` and `products.active_ingredients.name` (now 6).
- **Config was out of date.** The data showed FDA approvals our config had as pipeline: orforglipron (**Foundayo**, 2026-04-01), insulin efsitora alfa (**Onswik**, 2026-09-23) and insulin icodec (**Awiqli**, 2026-03-26). This is why approval status always comes from data, never from config.
- **Label-search gaps.** Some marketed brands return no label (Bydureon BCise, Adlyxin, Symlin, Onglyza, Glucophage, Amaryl): most likely discontinued brands, not yet verified. Awiqli returns no label because it is stored as "Awiqli FlexTouch" (naming mismatch, to handle in M3).

**Notable finding:** Apotex holds a **tentative approval** for generic semaglutide (ANDA220314, 2026-04-07): approved on quality, but blocked from launch by patents.

## 3. Health Canada Drug Product Database (DPD API)

**Contains:** every Canadian drug product (one per strength/form, each with a DIN): brand, company, ingredients, and current status (Approved, Marketed, Dormant, Cancelled) with first market date.

**Limitations**
- **Current status only.** For marketed products we get the first market date but not the original approval date; for approved-only products we get the approval date. "Canada lag" will be defined as *US approval → first Canadian market date* (decided in M3).
- Products, not drugs: one brand can have many DINs (e.g. 24 tirzepatide products).
- For legacy molecules we search brand names only (an ingredient search returns hundreds of generics).

**Issues found and fixed**
- **Brand search is a "contains" match.** "Alli" returned 191 products, mostly homeopathics ("ALLIUM CEPA", "PLUMBUM METALLICUM"). Fix: keep only the exact brand or brand + another word.
- **Brands differ by country.** Linagliptin is Tradjenta in the US but **Trajenta** in Canada. Fix: both listed.

**Notable findings**
- **Generic semaglutide is marketed in Canada:** Dr. Reddy's (2026-05-06) and Apotex (2026-05-14); Sandoz and Aspen approved.
- Novo has two new semaglutide brands approved 2025-12-22 (**Plosbrio**, **Poviztra**). Purpose not yet verified: do not interpret without a source.
- Canada can lead the US: Awiqli has been marketed in Canada since 2024-06-13, almost two years before its FDA approval.
- Mounjaro: approved in Canada 2022-11-24, first marketed 2023-10-23 (US approval 2022-05-13). Zepbound marketed 2025-07-09 (US approval 2023-11-08).
- Not available in Canada: Symlin, Qsymia, glipizide, efsitora.

## 4. Ontario Drug Benefit (ODB) Formulary

**Contains:** every product on Ontario's public drug plan, by DIN, grouped into interchangeable product groups, with the listed price and the amount the ministry pays, listing date and coverage attributes.

**Limitations**
- One province, and only the public plan (people 65+, social assistance, under-25s without private coverage, and some other groups). Most working-age Canadians are covered by private insurers, which this doesn't show.
- Coverage attributes (`sec3`, `sec12`, `notABenefit`, etc.) are codes. **Their meaning has not been verified yet**: decode from the XSD schema and Ontario's documentation in M3 before labelling anything.
- It is a listing, not utilisation: it tells us what is covered, not how much is used.

**Issue found and fixed**
- **The official open-data catalogue is stale.** data.ontario.ca points to a 2019 file on the retired health.gov.on.ca domain, which no longer resolves. Fix: read the current ontario.ca formulary page and follow its XML and XSD links.

**Notable findings (edition dated 2026-10-28)**
- Generic semaglutide was listed on 2026-06-30. Since then, **Ontario pays the generic price ($78.14) for Ozempic too**, against a listed price of $227.94 (about 66% less).
- Wegovy is listed (2026-08-31) as **not a benefit**.
- Mounjaro and Zepbound are **not on the formulary**.

**Join key:** the formulary `id` is the **DIN**, the same as Health Canada's, so approval → coverage is a direct join.

## 5. CMS Medicare Part D Prescribers: by Provider and Drug

**Contains:** for each prescriber (NPI) and drug in a year: claims, 30-day fills, days' supply, drug cost, beneficiaries, plus prescriber specialty and location. Data year **2024** (published May 2026), filtered with DuckDB from a ~3.9 GB national CSV to the drugs in our config.

**Limitations (state these wherever Part D numbers appear)**
1. **Medicare only.** Mostly people 65+ and people with disabilities. Not the commercial or Medicaid market, and nothing for Canada.
2. **About a two-year lag.** 2024 prescribing, before orforglipron, efsitora, icodec and generic-semaglutide events.
3. **Small counts suppressed.** CMS removes any prescriber × drug row with fewer than 11 claims, so low-volume prescribers and new launches are undercounted. That biases "early adopter" signals downward.
   *Measured (reconciliation against CMS's national totals, `scripts/check_partd_totals.py`):* our file holds **85% of all national claims** for the matched drugs (115.6M of 135.6M). Big drugs are well covered (metformin 97%, Ozempic 95%, Jardiance 94%, Mounjaro 92%), older drugs written by many occasional prescribers less so (Januvia 87%, glipizide 87%), and drugs with few or occasional prescribers least (Rybelsus 72%, Wegovy 36%). 32 tiny items (mostly insulin syringes, pens and pods, under 1,300 claims each nationally) are fully suppressed. No drug exceeds its national total, so nothing is double counted.
4. **Weight-loss drugs excluded by law.** In 2024 Medicare: Ozempic 9.9M claims vs Wegovy 76k, Zepbound 14 and Contrave 220. So **the segmentation is really a type 2 diabetes / cardiometabolic segmentation**, and must be described that way.

**Issues found (to handle in M4 mapping)**
- **Deliberate over-match:** matching each half of combination products also pulled in bupropion (antidepressant, ~6M claims), topiramate (epilepsy) and naltrexone / methylnaltrexone. The M4 drug-to-class mapping must drop these.
- **NPH insulin false alarm:** reported as unmatched, but present as "Insulin Nph Human Isophane" (~198k claims). The name check needs to handle CMS spellings.
- **Genuinely absent:** pipeline assets; drugs approved after 2024 (orforglipron, icodec, efsitora); weight-loss drugs (Qsymia, orlistat); very small volumes probably below the suppression threshold (bexagliflozin, setmelanotide).

**Kept on disk:** only the filtered Parquet (78 MB) plus a name report. The full CSV is an immutable annual release, re-downloadable from the URL recorded in the manifest.

---

## Open items carried into M3/M4
- [x] Reconcile Part D filtered totals against CMS's published national totals (done 2026-11-24: passed, 85% captured overall; see section 5).
- [ ] Decode ODB coverage attributes from the XSD before labelling them.
- [ ] Confirm the zero-label brands are discontinued.
- [ ] Decide the treatment of trials with no phase or `NA`.
- [ ] Define "Canada lag" precisely (US approval → first Canadian market date).
- [ ] Map CMS generic names to config molecules explicitly (drop over-matches, fix NPH), and drop insulin devices such as syringes, pens and pods).
