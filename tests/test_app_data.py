"""Offline tests for the M6 app data export."""

import pandas as pd

from obesity_ci import app_data as A

T = pd.DataFrame([
    # npi, state, region, eligible, value, fit, tier, plan, claims, incretin, cluster, priority
    ("1", "TX", "South", True, "High", "High", 1, True, 900, 400, "Tirzepatide-led (Mounjaro)", "A"),
    ("2", "TX", "South", True, "High", "Medium", 2, True, 800, 100, "DPP-4 loyal", "B"),
    ("3", "NY", "Northeast", True, "Medium", "Medium", 3, False, 300, 20, "Generic-first (metformin / sulfonylurea)", "C"),
    ("4", "NY", "Northeast", True, "Low", "Low", 4, False, 60, 0, "SGLT2 cardiorenal", "C"),
    ("5", "NY", "Northeast", False, "", "", 4, False, 20, 5, "Low volume (not profiled)", ""),
], columns=["npi", "state", "region", "eligible", "value_tier", "launch_fit", "target_tier", "in_call_plan",
            "total_claims", "incretin_claims", "cluster", "priority"])
T["specialty_group"] = "Primary care physician"
T["action"] = "x"


def test_matrix_covers_every_cell_and_only_eligible():
    m = A.matrix(T)
    assert len(m) == 9 and m["prescribers"].sum() == 4  # 3x3 grid; npi 5 is not eligible
    hh = m[(m["value_tier"] == "High") & (m["launch_fit"] == "High")].iloc[0]
    assert hh["incretin_claims"] == 400 and hh["pct_of_incretin_claims"] == round(100 * 400 / 525, 1)


def test_by_state_adds_up():
    s = A.by_state(T).set_index("state")
    assert s["prescribers"].sum() == len(T) and s.loc["TX", "in_call_plan"] == 2
    assert s.loc["TX", "pct_incretin_in_plan"] == 100.0 and s.loc["NY", "pct_incretin_in_plan"] == 0.0


def test_call_list_has_only_targets_and_no_names():
    c = A.call_list(T)
    assert list(c.columns) == A.CALL_LIST_COLS
    assert not any("name" in col for col in c.columns)  # names were dropped in M4; keep it that way
    assert set(c["npi"]) == {"1", "2", "3"} and c.iloc[0]["npi"] == "1"  # plan first, best tier first


def test_class_ids_become_labels():
    up = pd.DataFrame({"classes": ["glp1_oral; dpp4", None]})
    out = A.label_classes(up, "classes", {"glp1_oral": "GLP-1 (oral)", "dpp4": "DPP-4 inhibitor"})
    assert list(out["classes"]) == ["GLP-1 (oral); DPP-4 inhibitor", ""]
