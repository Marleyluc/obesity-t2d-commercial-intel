"""Offline tests for the M4 targeting recommendation."""

import pandas as pd
import pytest

from obesity_ci.segment import targeting as T
from obesity_ci.segment.clusters import LOW_VOLUME


def p(npi, value, cluster, incretin, eligible=True, priority="A"):
    return {"npi": npi, "eligible": eligible, "value_tier": value if eligible else None, "cluster": cluster,
            "incretin_claims": incretin, "total_claims": 10 * incretin + 100, "priority": priority}


RYB, TZP, GEN, SGLT = ("Oral GLP-1 users (Rybelsus)", "Tirzepatide-led (Mounjaro)",
                       "Generic-first (metformin / sulfonylurea)", "SGLT2 cardiorenal")
F = pd.DataFrame([
    p("t1-big", "High", RYB, 500), p("t1-small", "High", TZP, 100),
    p("t2-hi-med", "High", GEN, 300, priority="A"), p("t2-med-hi", "Medium", TZP, 200, priority="B"),
    p("t3", "Low", RYB, 50, priority="C"), p("t4-sglt", "High", SGLT, 5, priority="B"),
    p("small", None, LOW_VOLUME, 3, eligible=False, priority="-"),
])


def test_tiers_follow_the_matrix():
    t = T.assign(F, capacity=10).set_index("npi")["target_tier"].to_dict()
    assert t == {"t1-big": 1, "t1-small": 1, "t2-hi-med": 2, "t2-med-hi": 2, "t3": 3, "t4-sglt": 4, "small": 4}


def test_call_plan_fills_by_tier_then_incretin_volume():
    plan = T.assign(F, capacity=3).set_index("npi")["in_call_plan"]
    assert set(plan[plan].index) == {"t1-big", "t1-small", "t2-hi-med"}  # 300 > 200 incretin claims
    assert not T.assign(F, capacity=100).set_index("npi").loc[["t4-sglt", "small"], "in_call_plan"].any()


def test_every_cluster_has_a_card_and_a_rating():
    from obesity_ci.segment.clusters import NAMES
    assert set(NAMES.values()) == set(T.LAUNCH_FIT) and set(T.SEGMENT_CARDS) == set(T.LAUNCH_FIT) | {LOW_VOLUME}
    c = T.cards(T.assign(F, capacity=3))
    assert c["description"].str.len().gt(20).all() and c["recommended_action"].str.len().gt(20).all()
    assert c["prescribers"].sum() == len(F)


def test_unrated_cluster_fails_loudly():
    with pytest.raises(ValueError, match="Brand new style"):
        T.assign(pd.concat([F, pd.DataFrame([p("x", "High", "Brand new style", 10)])]))


def test_comparison_with_baseline():
    """The grid would call the big SGLT2 cardiorenal prescriber (priority A); the clusters swap in
    the high-volume generic-first prescriber (Tier 2) instead."""
    f = F.copy()
    f.loc[f["npi"] == "t2-hi-med", "priority"] = "B"
    f.loc[f["npi"] == "t4-sglt", "priority"] = "A"
    v = T.compare_with_baseline(T.assign(f, capacity=3), capacity=3)
    assert v["overlap"] == 2
    assert v["added"].to_dict() == {GEN: 1} and v["dropped"].to_dict() == {SGLT: 1}
    assert v["cluster_reach"] > v["baseline_reach"]
