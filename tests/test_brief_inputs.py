"""Offline tests for the M5 brief input."""

import pandas as pd

from obesity_ci.brief import inputs as I

MOLS = pd.DataFrame([
    {"generic": "retatrutide", "class_label": "Glucagon-receptor combination agonists", "sponsor": "Eli Lilly"},
    {"generic": "metformin", "class_label": "Legacy oral T2D agents", "sponsor": "generic"},
    {"generic": "alogliptin", "class_label": "DPP-4 inhibitor", "sponsor": "Takeda"},
])


def change(id_, change_type, importance, molecules="retatrutide", source="ctgov"):
    return {"old_snapshot": "2026-11-24", "new_snapshot": "2026-12-01", "source": source,
            "change_type": change_type, "importance": importance, "id": id_, "molecules": molecules,
            "title": f"Title {id_}", "field": "status", "old": "RECRUITING", "new": "COMPLETED", "detail": None}


LOG = pd.DataFrame(
    [change("NCT00000001", "Status change", "high"),
     change("NDA022271", "New FDA action", "low", "alogliptin; metformin", "openfda"),
     change("NCT00000002", "Primary completion moved", "medium"),
     change("NDA209637", "Primary label source changed", "low", "semaglutide", "openfda"),
     change("NCT00000003", "No longer returned", "low")]
    + [change(f"NCT1{i:07d}", "Primary completion moved", "low") for i in range(30)])


def test_selection_rules():
    chosen, omitted = I.select(LOG, max_low=5)
    assert list(chosen["importance"][:2]) == ["high", "medium"]  # most important first
    assert len(chosen) == 7 and not chosen["change_type"].isin(I.REVIEW_ONLY).any()
    assert omitted["needs_human_review"] == {"Primary label source changed": 1, "No longer returned": 1}
    assert omitted["low_importance_not_sent"] == 26  # 31 low changes, 5 sent


def test_row_limit():
    chosen, omitted = I.select(LOG, max_low=50, max_rows=10)
    assert len(chosen) == 10 and omitted["over_row_limit"] == 23


def test_context_and_ids():
    d = I.build(LOG, MOLS)
    by_id = {c["id"]: c for c in d["changes"]}
    assert by_id["NCT00000001"]["sponsors"] == "Eli Lilly"
    assert by_id["NDA022271"]["sponsors"] == "Takeda"  # "generic" placeholder dropped
    assert by_id["NDA022271"]["classes"] == "DPP-4 inhibitor; Legacy oral T2D agents"
    assert by_id["NDA022271"]["source"] == "FDA (Drugs@FDA and labels)"
    assert by_id["NCT00000001"]["detail"] == ""  # missing values become empty strings, never "nan"
    assert "NDA209637" not in I.allowed_ids(d) and "NCT00000001" in I.allowed_ids(d)
    assert d["period"] == {"from": "2026-11-24", "to": "2026-12-01"} and d["counts"]["all_changes"] == len(LOG)
