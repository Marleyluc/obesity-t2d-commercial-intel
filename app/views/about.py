"""About the data: sources, freshness, method in brief, and the limits a reader must know."""

import streamlit as st

import common as C

m = C.meta()
C.page_header("Reference", "About the data", "Sources, freshness, method and the limits to keep in mind.")
st.markdown("Everything in this app comes from public sources, pulled and processed by the pipeline in this "
            "repository. The app itself never calls an API: it reads a small export built by "
            "`scripts/build_app_data.py`.")

st.subheader("Sources and freshness")
st.dataframe([
    {"Source": "ClinicalTrials.gov (API v2)", "Used for": "Pipeline, phases, readout timing",
     "As of": m["landscape_snapshot"], "Refresh": "Weekly pull"},
    {"Source": "openFDA (Drugs@FDA, labels)", "Used for": "US approvals, supplements, label changes",
     "As of": m["change_log"], "Refresh": "Weekly pull"},
    {"Source": "Health Canada DPD, Ontario Drug Benefit formulary", "Used for": "Canadian status and coverage",
     "As of": m["landscape_snapshot"], "Refresh": "Weekly pull"},
    {"Source": "CMS Medicare Part D Prescribers (by provider and drug)", "Used for": "Segments, call plan",
     "As of": f"{m['part_d_data_year']} data", "Refresh": "Yearly (CMS publishes with a ~2-year lag)"},
    {"Source": "Weekly brief (Claude, grounded on the change log)", "Used for": "What changed",
     "As of": m["brief"], "Refresh": "Weekly, after the pulls"},
], hide_index=True, width="stretch")
st.caption(f"App data built {m['built_at']}.")

st.subheader("How it works, in brief")
st.markdown("""
- **Landscape:** active, industry-sponsored Phase 1-3 trials mapped to our list of molecules and classes.
  "Next readout" is the primary completion date, a proxy: sponsors often report later.
- **What changed:** two snapshots are compared field by field. Each change gets an importance level.
  An LLM writes the brief from those rows only, cites an ID for every claim, and an automatic check
  rejects any brief that mentions an ID it wasn't given.
- **Who to target:** prescribers with 50+ diabetes claims are grouped by what they prescribe
  (k-means, 7 segments, stable across resamples). Each segment gets a launch-fit rating for an oral
  GLP-1. Value (volume decile) x launch fit gives four tiers. The call plan fills an assumed
  capacity of {cap:,} names, best tier first.
""".replace("{cap:,}", f"{m['call_capacity']:,}"))

st.subheader("Limits to keep in mind")
st.markdown("""
1. **Medicare Part D only**, mostly patients aged 65+. Commercial and Medicaid prescribing, where much
   new GLP-1 use is, could rank prescribers differently.
2. **Prescribing data is from 2024**, before orforglipron launched. Targeting uses analogue behaviour
   (GLP-1 and oral GLP-1 use), not actual uptake.
3. **Weight-loss-only use is largely excluded from Part D**, so the segments describe T2D and
   cardiometabolic prescribing, not obesity specialists.
4. **CMS hides rows under 11 claims**, so occasional use of a drug disappears and very early adopters
   can look like non-users.
5. **Claims, not patients or outcomes.** A 90-day fill counts as one claim.
6. **No payer or access data:** formulary status, prior authorisation and "no-see" offices all matter
   for real targeting and are not here.
7. **Call capacity (45,000) is an assumption**, roughly 300 reps x 150 targets. Change it in
   `segment/targeting.py` and rebuild.
8. **Segment edges are soft.** Prescribers sit on a spectrum (silhouette 0.27); the segments are stable
   when resampled, but not yet tested on a second year of data.
9. **Trial dates are sponsor-reported** and often move; the change log tracks those moves.
""")

st.subheader("More detail")
st.markdown("Every design decision, with its reason and its cost, is written up in the repository: "
            "`docs/M3_DECISIONS.md` (landscape), `docs/M4_DECISIONS.md` (segmentation), "
            "`docs/M5_DECISIONS.md` (brief), `docs/M6_DECISIONS.md` (this app), and `docs/DATA_NOTES.md`.")
