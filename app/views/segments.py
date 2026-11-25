"""Prescriber segments: who to target for the orforglipron launch, and why (M4 results)."""

import plotly.graph_objects as go
import streamlit as st

import common as C

m = C.meta()
st.title(f"Who to target for {m['anchor_brand']}")
C.source_note(f"CMS Medicare Part D prescribers, {m['part_d_data_year']} data",
              f"{m['eligible']:,} prescribers with 50+ diabetes claims profiled",
              f"call capacity of {m['call_capacity']:,} is an assumption (~300 reps x 150 targets)")

# ---- the answer first ----
plan = m["plan_by_segment"]
lead = [s for s in plan if s in {"Oral GLP-1 users (Rybelsus)", "Tirzepatide-led (Mounjaro)",
                                 "Injectable GLP-1 adopters (Ozempic / Trulicity)"}]
with st.container(border=True):
    st.markdown(
        f"**The recommendation.** Call **{m['in_call_plan']:,}** prescribers. Lead with those already in the "
        f"GLP-1 class ({', '.join(f'{s}: {plan[s]:,}' for s in lead)}), then the biggest-volume "
        f"pill-first and insulin prescribers. This list reaches **{m['plan_pct_incretin_claims']}%** of "
        f"Medicare GLP-1 and GIP/GLP-1 claims, and **{m['plan_pct_high_fit']}%** of its names already "
        f"prescribe in the class (a list built on volume and adoption alone: "
        f"{m['baseline_pct_incretin_claims']}% and {m['baseline_pct_high_fit']}%).")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Names in the call plan", f"{m['in_call_plan']:,}")
k2.metric("GLP-1 claims reached", f"{m['plan_pct_incretin_claims']}%",
          f"{m['plan_pct_incretin_claims'] - m['baseline_pct_incretin_claims']:+.1f} pts vs volume-only")
k3.metric("Already in the class (high fit)", f"{m['plan_pct_high_fit']}%",
          f"{m['plan_pct_high_fit'] - m['baseline_pct_high_fit']:+.1f} pts vs volume-only")
k4.metric("Same names as the volume-only list", f"{100 * m['overlap_with_baseline'] / m['in_call_plan']:.0f}%")

# ---- targeting matrix ----
st.subheader("The targeting matrix")
st.caption("Rows: how much a prescriber writes (value). Columns: how close their prescribing is to an oral "
           "GLP-1 (launch fit, from their segment). Each box: prescribers, their share of all GLP-1 claims, "
           "and the tier it earns. Darker = higher priority.")
mx = C.table("matrix")
tiers = ["High", "Medium", "Low"]
TIER_FILL = {1: "#1757ac", 2: "#338ced", 3: "#9dc8f7", 4: "#efefef"}
z, text, colors = [], [], []
for v in tiers:
    row = mx[mx["value_tier"] == v].set_index("launch_fit").reindex(tiers)
    z.append([5 - t for t in row["target_tier"]])
    text.append([f"<b>Tier {t}</b><br>{p:,} prescribers<br>{pct}% of GLP-1 claims"
                 for t, p, pct in zip(row["target_tier"], row["prescribers"], row["pct_of_incretin_claims"])])
fig = go.Figure(go.Heatmap(
    z=z, x=[f"{t} launch fit" for t in tiers], y=[f"{t} value" for t in tiers], text=text,
    texttemplate="%{text}", hoverinfo="text", xgap=3, ygap=3, showscale=False, zmin=1, zmax=4,
    colorscale=[[0, TIER_FILL[4]], [0.33, TIER_FILL[3]], [0.67, TIER_FILL[2]], [1, TIER_FILL[1]]],
    textfont=dict(size=13)))
fig.update_yaxes(autorange="reversed")
fig.update_xaxes(side="top", showgrid=False)
st.plotly_chart(C.chart_layout(fig, 380), width="stretch")
st.caption("Tier 1: rep calls from launch, high frequency. Tier 2: rep calls in the first 6 months. "
           "Tier 3: remote / inside sales and digital. Tier 4: non-personal only.")

# ---- segment cards ----
st.subheader("The segments")
st.caption("Seven behaviour-based segments from k-means clustering on what each prescriber writes, "
           "plus a low-volume group. Sorted by how many names each puts in the call plan.")
cards = C.table("segment_cards")
FIT_ICON = {"High": "🟢 High fit", "Medium": "🟡 Medium fit", "Low": "⚪ Low fit"}
cols = st.columns(2)
for i, r in enumerate(cards.itertuples()):
    with cols[i % 2], st.container(border=True):
        st.markdown(f"**{r.cluster}**  \n{FIT_ICON.get(r.launch_fit, 'Not profiled')}")
        a, b, c = st.columns(3)
        a.metric("Prescribers", f"{r.prescribers:,}")
        b.metric("Share of GLP-1 claims", f"{r.pct_of_incretin_claims}%")
        c.metric("In the call plan", f"{r.in_call_plan:,}")
        st.markdown(f"{r.description}  \n**Action:** {r.recommended_action}")

with st.expander("What each segment prescribes (averages, %)"):
    prof = C.table("cluster_profile")
    st.dataframe(prof, hide_index=True, width="stretch", column_config={
        "cluster": "Segment", "prescribers": st.column_config.NumberColumn("Prescribers", format="%d"),
        "pct_of_claims": "% of all claims", "pct_of_incretin_claims": "% of GLP-1 claims",
        "median_claims": "Median claims", "incretin_share": "GLP-1 share", "sglt2_share": "SGLT2 share",
        "legacy_oral_share": "Metformin / SU share", "pct_writing_rybelsus": "% writing Rybelsus",
        "lilly_of_incretin": "Lilly share of GLP-1", "pct_endocrinology": "% endocrinologists",
        "pct_primary_care_or_np_pa": "% primary care / NP / PA"})

# ---- map ----
st.subheader("Where the call plan lands")
measure = st.segmented_control(
    "Show", ["Names in the call plan", "% of the state's GLP-1 claims reached"],
    default="Names in the call plan")
st_df = C.table("by_state")
us = st_df[st_df["state"].isin(C.US_STATES)]
col = "in_call_plan" if measure != "% of the state's GLP-1 claims reached" else "pct_incretin_in_plan"
fig = go.Figure(go.Choropleth(
    locations=us["state"], z=us[col], locationmode="USA-states",
    colorscale=[[i / (len(C.BLUE_RAMP) - 1), c] for i, c in enumerate(C.BLUE_RAMP)],
    marker_line_color="white", marker_line_width=1,
    colorbar=dict(thickness=10, len=0.6, title=""),
    customdata=us[["in_call_plan", "tier_1", "tier_2", "pct_incretin_in_plan"]].values,
    hovertemplate="<b>%{location}</b><br>%{customdata[0]:,} names in the call plan<br>"
                  "Tier 1: %{customdata[1]:,} · Tier 2: %{customdata[2]:,}<br>"
                  "%{customdata[3]}% of the state's GLP-1 claims reached<extra></extra>"))
fig.update_geos(scope="usa", bgcolor="rgba(0,0,0,0)", lakecolor="rgba(0,0,0,0)")
st.plotly_chart(C.chart_layout(fig, 460), width="stretch")
st.caption("A low % means GLP-1 prescribing there is spread over many smaller prescribers: "
           "a case for inside sales and digital rather than more reps.")
with st.expander("Table view, all states and territories"):
    st.dataframe(st_df, hide_index=True, width="stretch")
st.page_link("views/call_list.py", label="Open the call list (filter and download)", icon="📇")
