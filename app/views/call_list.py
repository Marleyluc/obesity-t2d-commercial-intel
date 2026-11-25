"""Call list: the prescriber-level targets behind the recommendation, ready to filter and download."""

import streamlit as st

import common as C

m = C.meta()
C.page_header("Field force", "Call list", "The prescriber-level targets behind the recommendation: filter, look up, download.")
C.source_note(f"CMS Medicare Part D, {m['part_d_data_year']} data", "Tier 1-3 prescribers only",
              "names are left out; look up an NPI in the national registry")

cl = C.table("call_list")
f1, f2, f3 = st.columns(3)
states = f1.multiselect("State", sorted(cl["state"].unique()), placeholder="All states")
spec = f2.multiselect("Specialty", sorted(cl["specialty_group"].unique()), placeholder="All specialties")
seg = f3.multiselect("Segment", sorted(cl["cluster"].unique()), placeholder="All segments")
g1, g2, g3 = st.columns(3)
tiers = g1.segmented_control("Tier", [1, 2, 3], selection_mode="multi", default=[1, 2, 3],
                             format_func=lambda t: f"Tier {t}")
plan_only = g2.toggle("Only names in the call plan", value=True)
npi = g3.text_input("NPI starts with", placeholder="e.g. 1003")

v = cl[cl["target_tier"].isin(tiers or [1, 2, 3])]
if plan_only:
    v = v[v["in_call_plan"]]
if states:
    v = v[v["state"].isin(states)]
if spec:
    v = v[v["specialty_group"].isin(spec)]
if seg:
    v = v[v["cluster"].isin(seg)]
if npi:
    v = v[v["npi"].str.startswith(npi.strip())]

k1, k2, k3 = st.columns(3)
k1.metric("Prescribers shown", f"{len(v):,}", border=True)
k2.metric("Their GLP-1 claims", f"{int(v['incretin_claims'].sum()):,}", border=True)
k3.metric("Their diabetes claims", f"{int(v['total_claims'].sum()):,}", border=True)

v = v.assign(registry=v["npi"].map(C.NPI_REGISTRY.format))
st.dataframe(
    v[["npi", "registry", "target_tier", "in_call_plan", "cluster", "launch_fit", "specialty_group", "state",
       "total_claims", "incretin_claims", "action"]].head(5000),
    hide_index=True, width="stretch", height=520,
    column_config={
        "npi": "NPI", "registry": st.column_config.LinkColumn("Registry", display_text="look up"),
        "target_tier": st.column_config.NumberColumn("Tier", format="%d"), "in_call_plan": "In plan",
        "cluster": "Segment", "launch_fit": "Launch fit", "specialty_group": "Specialty", "state": "State",
        "total_claims": st.column_config.NumberColumn("Diabetes claims", format="%d"),
        "incretin_claims": st.column_config.NumberColumn("GLP-1 claims", format="%d"),
        "action": "Recommended action"})
if len(v) > 5000:
    st.caption(f"Showing the first 5,000 of {len(v):,} rows (best tier first). The download has them all.")
st.download_button(f"Download {len(v):,} rows (CSV)", v.drop(columns="registry").to_csv(index=False),
                   "orforglipron_call_list.csv", "text/csv", type="primary")
st.caption("Medicare Part D only: these are prescribers' Medicare patients, not their whole practice. "
           "Claims are 2024 data; refresh when CMS publishes the next year.")
