"""Landscape: who is developing what, how far along, and when the next readouts land (M3 views)."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import common as C

m = C.meta()
st.title("Competitive landscape")
C.source_note("Active, industry-sponsored interventional trials, Phase 1 to 3 (ClinicalTrials.gov, "
              f"{m['landscape_snapshot']})", "a trial testing two classes counts once in each")

cp = C.table("landscape_class_phase").set_index("class")
phases = ["Phase 1", "Phase 1/2", "Phase 2", "Phase 2/3", "Phase 3"]
k1, k2, k3, k4 = st.columns(4)
k1.metric("Pipeline trials (class x trial)", f"{int(cp['total'].sum()):,}")
k2.metric("Late-stage (class x trial)", f"{int(cp[['Phase 2/3', 'Phase 3']].sum().sum()):,}")
share = C.table("landscape_sponsor_share")
k3.metric("Lilly + Novo share of late-stage", f"{share['share_pct'].head(2).sum():.0f}%")
k4.metric("Readouts, next 18 months", f"{len(C.table('landscape_upcoming')):,}")

# ---- class x phase ----
st.subheader("Where the pipeline is crowded")
st.caption("Number of active trials per class and phase. Darker = more trials.")
z = cp[phases]
fig = go.Figure(go.Heatmap(
    z=z.values, x=phases, y=z.index, text=z.where(z > 0, "").values, texttemplate="%{text}",
    colorscale=[[i / (len(C.BLUE_RAMP) - 1), c] for i, c in enumerate(C.BLUE_RAMP)],
    xgap=2, ygap=2, showscale=False,
    hovertemplate="%{y}<br>%{x}: %{z} trials<extra></extra>"))
fig.update_yaxes(autorange="reversed")
st.plotly_chart(C.chart_layout(fig, 440), width="stretch")
with st.expander("Table view"):
    st.dataframe(cp, width="stretch")

# ---- sponsors ----
left, right = st.columns([1, 1])
with left:
    st.subheader("Who runs the late-stage trials")
    st.caption("Share of active Phase 2/3 and Phase 3 trials, by lead sponsor.")
    s = share.iloc[::-1]
    colors = [C.GREY if n == "(all others)" else (C.SERIES[0] if "Lilly" in n else C.SERIES[1] if "Novo" in n
              else "#6aabf1") for n in s["sponsor"]]
    fig = go.Figure(go.Bar(
        x=s["share_pct"], y=s["sponsor"].str.slice(0, 40), orientation="h", marker_color=colors,
        text=[f"{v:.0f}%" for v in s["share_pct"]], textposition="outside", cliponaxis=False,
        customdata=s["late_stage_trials"],
        hovertemplate="%{y}<br>%{x:.1f}% (%{customdata:.0f} trials)<extra></extra>"))
    fig.update_xaxes(showticklabels=False, showgrid=False, range=[0, s["share_pct"].max() * 1.15])
    st.plotly_chart(C.chart_layout(fig, 420), width="stretch")
    st.caption("Blue = Lilly (our company), orange = Novo Nordisk, grey = all other sponsors.")

# ---- assets ----
with right:
    st.subheader("Key assets")
    st.caption("One row per tracked molecule. Next readout = earliest primary completion of its active trials.")
    a = C.table("landscape_assets")
    only_active = st.toggle("Only molecules with active trials", value=True)
    if only_active:
        a = a[a["active_trials"] > 0]
    st.dataframe(
        a[["generic", "sponsor", "class", "highest_active_phase", "active_late_stage", "next_readout",
           "us_first_approval", "ca_status", "ontario_coverage"]],
        hide_index=True, width="stretch", height=420,
        column_config={
            "generic": "Molecule", "sponsor": "Sponsor", "class": "Class",
            "highest_active_phase": "Highest phase", "active_late_stage": "Late-stage trials",
            "next_readout": st.column_config.DateColumn("Next readout", format="MMM YYYY"),
            "us_first_approval": st.column_config.DateColumn("US approval", format="MMM YYYY"),
            "ca_status": "Canada", "ontario_coverage": "Ontario (ODB)"})

# ---- readouts ----
st.subheader("Upcoming readouts")
st.caption("Active trials whose primary completion date (a proxy for when results arrive) falls in the "
           "next 18 months. Hover a dot for the trial.")
up = C.table("landscape_upcoming").copy()
up["class"] = up["classes"].str.split("; ").str[0]
up["molecules"] = up["molecules"].fillna("")
up["acronym"] = up["acronym"].fillna("")
up["status"] = up["status"].str.replace("_", " ").str.capitalize()
f1, f2, f3 = st.columns([2, 1, 1])
pick = f1.multiselect("Class", sorted(up["class"].unique()), placeholder="All classes")
phase = f2.segmented_control("Phase", ["Phase 3", "Phase 2"], selection_mode="multi",
                             default=["Phase 3", "Phase 2"])
mol = f3.text_input("Molecule contains", placeholder="e.g. orforglipron")
v = up[up["phase"].isin(phase or ["Phase 3", "Phase 2"])]
if pick:
    v = v[v["class"].isin(pick)]
if mol:
    v = v[v["molecules"].str.contains(mol, case=False)]

fig = go.Figure()
for i, ph in enumerate(["Phase 3", "Phase 2"]):
    d = v[v["phase"] == ph]
    fig.add_trace(go.Scatter(
        x=d["primary_completion_date"], y=d["class"], mode="markers", name=ph,
        marker=dict(size=11, color=C.SERIES[i], line=dict(width=2, color="white")),
        customdata=d[["nct_id", "lead_sponsor", "molecules", "title"]].values,
        hovertemplate="<b>%{customdata[0]}</b> · %{x|%b %Y}<br>%{customdata[1]}<br>%{customdata[2]}"
                      "<br>%{customdata[3]}<extra>" + ph + "</extra>"))
fig.update_layout(legend=dict(orientation="h", y=1.08, x=0))
fig.update_yaxes(categoryorder="category descending", showgrid=True, gridcolor="rgba(128,128,128,0.15)")
st.plotly_chart(C.chart_layout(fig, max(260, 40 * v["class"].nunique() + 80)), width="stretch")

v = v.assign(link=v["nct_id"].map(C.CTGOV.format))
st.dataframe(
    v[["primary_completion_date", "link", "phase", "lead_sponsor", "molecules", "acronym", "status",
       "enrollment", "title"]].sort_values("primary_completion_date"),
    hide_index=True, width="stretch",
    column_config={
        "primary_completion_date": st.column_config.DateColumn("Primary completion", format="DD MMM YYYY"),
        "link": st.column_config.LinkColumn("Trial", display_text=r"https://clinicaltrials.gov/study/(.*)"),
        "phase": "Phase", "lead_sponsor": "Sponsor", "molecules": "Molecules", "acronym": "Acronym",
        "status": "Status", "enrollment": st.column_config.NumberColumn("Enrolment", format="%d"),
        "title": "Title"})
st.download_button("Download these trials (CSV)", v.drop(columns="link").to_csv(index=False),
                   "upcoming_readouts.csv", "text/csv")
