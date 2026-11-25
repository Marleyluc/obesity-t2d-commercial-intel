"""What changed: this week's brief, and the change log behind it (M3 change log + M5 brief)."""

import json

import streamlit as st

import common as C

m = C.meta()
C.page_header("Market", "What changed this week", "New approvals, label changes and trial moves since the last pull, with an analyst-style brief.")
log = C.table("changes") if (C.DATA / "changes.parquet").exists() else None
if log is None or log.empty:
    st.info("No change log yet: run a second pull, then scripts/build_changes.py and scripts/build_app_data.py.")
    st.stop()
SOURCES = {"ctgov": "ClinicalTrials.gov", "openfda": "FDA", "canada": "Health Canada / Ontario"}
log = log.assign(source=log["source"].map(SOURCES).fillna(log["source"]))
period = f"{log['old_snapshot'].min()} to {log['new_snapshot'].max()}"
C.source_note(f"Snapshots compared: {period}", "ClinicalTrials.gov, FDA (Drugs@FDA and labels), "
              "Health Canada and Ontario Drug Benefit")

housekeeping = {"Primary label source changed", "No longer returned"}
k1, k2, k3, k4 = st.columns(4)
k1.metric("Changes found", len(log), border=True)
k2.metric("High importance", int((log["importance"] == "high").sum()), border=True)
k3.metric("Medium importance", int((log["importance"] == "medium").sum()), border=True)
k4.metric("Held for a human check", int(log["change_type"].isin(housekeeping).sum()),
          help="Pipeline housekeeping (e.g. our label search changed which document it uses). "
               "Never sent to the brief until a person has checked it.", border=True)

tab_brief, tab_log = st.tabs([":material/description: The brief", ":material/table_rows: All changes"])

with tab_brief:
    text = C.brief()
    if not text:
        st.info("No brief yet: run scripts/build_brief.py, then scripts/build_app_data.py.")
    else:
        body = text.split("\n", 1)[1] if text.startswith("# ") else text  # the page already has a title
        body = body.replace("\n## ", "\n##### ")  # section headings sized for a panel, not a page
        body = "\n".join(ln for ln in body.splitlines() if not ln.startswith("*Obesity and T2D landscape brief"))
        with st.container(border=True, key="card-brief"):
            st.markdown(C.link_ids(body))
        st.caption("Every [ID] links to its source record. The brief was written by an LLM that saw only "
                   "the rows below, and an automatic check rejects any brief that cites an ID not in them.")
        inp = C.DATA / "brief.input.json"
        if inp.exists():
            with st.expander("Evidence: the exact rows the model saw"):
                rows = json.loads(inp.read_text())["changes"]
                st.dataframe(rows, hide_index=True, width="stretch")

with tab_log:
    f1, f2, f3 = st.columns(3)
    imp = f1.segmented_control("Importance", ["high", "medium", "low"], selection_mode="multi",
                               default=["high", "medium", "low"])
    src = f2.multiselect("Source", sorted(log["source"].unique()), placeholder="All sources")
    show_hk = f3.toggle("Show housekeeping rows", value=False)
    v = log[log["importance"].isin(imp or ["high", "medium", "low"])]
    if src:
        v = v[v["source"].isin(src)]
    if not show_hk:
        v = v[~v["change_type"].isin(housekeeping)]
    v = v.assign(link=v["id"].map(C.id_url)).sort_values(["importance", "source", "change_type"],
                                                         key=lambda s: s.map({"high": 0, "medium": 1, "low": 2})
                                                         if s.name == "importance" else s)
    st.dataframe(
        v[["importance", "source", "change_type", "id", "link", "title", "molecules", "field", "old", "new",
           "detail"]],
        hide_index=True, width="stretch",
        column_config={"importance": "Importance", "source": "Source", "change_type": "Change", "id": "ID",
                       "link": st.column_config.LinkColumn("Source record", display_text="open"),
                       "title": "Title / brand", "molecules": "Molecules", "field": "Field",
                       "old": "Was", "new": "Now", "detail": "Detail"})
    st.caption(f"{len(v)} of {len(log)} changes shown.")
    st.download_button("Download the change log (CSV)", log.to_csv(index=False),
                       f"changes_{log['new_snapshot'].max()}.csv", "text/csv")
