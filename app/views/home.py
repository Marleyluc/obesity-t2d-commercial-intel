"""Overview: the three answers a brand lead wants on Monday morning, with links to the detail."""

import streamlit as st

import common as C

m = C.meta()
st.title("Obesity & T2D commercial intelligence")
st.markdown(f"Internal dashboard for the **{m['anchor_brand']}** (Eli Lilly, oral GLP-1) brand team: "
            "the competitive landscape, what changed this week, and who to call.")

up = C.table("landscape_upcoming")
cp = C.table("landscape_class_phase")
late = int(cp["Phase 3"].sum() + cp["Phase 2/3"].sum())

c1, c2, c3 = st.columns(3)
with c1, st.container(border=True):
    st.subheader("The pipeline")
    st.metric("Late-stage trials (Phase 2/3 and 3)", f"{late:,}", help="Counted once per class a trial tests.")
    st.metric("Readouts expected in the next 18 months", f"{len(up):,}")
    st.page_link("views/landscape.py", label="Open the landscape", icon="🧪")
with c2, st.container(border=True):
    st.subheader("What changed")
    changes = C.table("changes") if (C.DATA / "changes.parquet").exists() else None
    st.metric(f"Changes in the latest log ({m['change_log']})", f"{0 if changes is None else len(changes):,}")
    for h in C.brief_headlines(C.brief()):
        st.markdown(f"- {h}")
    st.page_link("views/changes.py", label="Read the brief", icon="📰")
with c3, st.container(border=True):
    st.subheader("Who to call")
    st.metric(f"Share of GLP-1 claims reached by {m['call_capacity']:,} calls",
              f"{m['plan_pct_incretin_claims']}%",
              f"{m['plan_pct_incretin_claims'] - m['baseline_pct_incretin_claims']:+.1f} pts vs a volume-only list",
              help="GLP-1 and GIP/GLP-1 claims in Medicare Part D written by the prescribers in the call plan.")
    st.markdown(f"{m['plan_pct_high_fit']}% of the names already prescribe in the class, "
                f"vs {m['baseline_pct_high_fit']}% for a list built on volume and adoption alone.")

C.source_note(f"Trials: ClinicalTrials.gov, {m['landscape_snapshot']}",
              f"Prescribing: CMS Medicare Part D, {m['part_d_data_year']} data",
              f"Data built {m['built_at']}")
