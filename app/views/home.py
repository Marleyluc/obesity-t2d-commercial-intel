"""Overview: the three answers a brand lead wants on Monday morning, with links to the detail."""

import streamlit as st

import common as C

m = C.meta()
C.page_header("Internal dashboard · Obesity & type 2 diabetes", "Competitive intelligence and targeting",
              f"For the <b>{m['anchor_brand']}</b> brand team: what competitors are doing, what changed this "
              "week, and which prescribers the field force should call first.", small=False)

up = C.table("landscape_upcoming")
cp = C.table("landscape_class_phase")
late = int(cp["Phase 3"].sum() + cp["Phase 2/3"].sum())
changes = C.table("changes") if (C.DATA / "changes.parquet").exists() else None
n_changes = 0 if changes is None else len(changes)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Late-stage trials", f"{late:,}", help="Active Phase 2/3 and Phase 3 trials, counted once per class.",
          border=True)
k2.metric("Readouts in the next 18 months", f"{len(up):,}", border=True)
k3.metric(f"Changes this week ({m['change_log']})", f"{n_changes:,}", border=True)
k4.metric("Call plan reach", f"{m['plan_pct_incretin_claims']}%",
          f"{m['plan_pct_incretin_claims'] - m['baseline_pct_incretin_claims']:+.1f} pts vs volume-only list",
          help=f"Share of Medicare GLP-1 and GIP/GLP-1 claims written by the {m['call_capacity']:,} "
               "prescribers in the call plan.", border=True)

C.section("Start here", "Three questions this tool answers. Each card opens the detail.")
c1, c2, c3 = st.columns(3)
with c1, st.container(border=True, height="stretch", key="card-pipeline"):
    st.markdown("##### :material/science: The pipeline")
    top = C.table("landscape_class_phase").iloc[0]
    share = C.table("landscape_sponsor_share")
    st.markdown(f"The most crowded class is **{top['class']}** ({int(top['total'])} active trials). "
                f"Lilly and Novo Nordisk run **{share['share_pct'].head(2).sum():.0f}%** of late-stage trials.")
    st.page_link("views/landscape.py", label="Open the landscape", icon=":material/arrow_forward:")
with c2, st.container(border=True, height="stretch", key="card-changes"):
    st.markdown("##### :material/notifications: What changed")
    heads = C.brief_headlines(C.brief(), n=2)
    st.markdown("\n".join(f"- {h}" for h in heads) if heads else "No brief yet this week.")
    st.page_link("views/changes.py", label="Read the brief", icon=":material/arrow_forward:")
with c3, st.container(border=True, height="stretch", key="card-target"):
    st.markdown("##### :material/target: Who to call")
    st.markdown(f"Call **{m['in_call_plan']:,}** prescribers, led by those already using GLP-1s. "
                f"**{m['plan_pct_high_fit']}%** of the list already prescribes in the class, vs "
                f"{m['baseline_pct_high_fit']}% for a list built on volume alone.")
    st.page_link("views/segments.py", label="See who to target and why", icon=":material/arrow_forward:")

