"""Offline tests for the M4 rules-based baseline segments."""

import pandas as pd

from obesity_ci.segment import baseline as B


def p(npi, decile, incretin_share, eligible=True):
    return {"npi": npi, "eligible": eligible, "volume_decile": decile if eligible else pd.NA,
            "incretin_share": incretin_share, "total_claims": 100 * (decile or 0), "incretin_claims": 10,
            "share_sglt2": 0.1, "share_legacy_oral": 0.5, "writes_oral_glp1": False, "lilly_of_incretin": 0.4,
            "specialty_group": "NP / PA", "region": "South"}


F = pd.DataFrame([p("hi-hi", 10, 0.40), p("hi-mod", 8, 0.10), p("hi-low", 9, 0.09), p("med-mod", 5, 0.249),
                  p("med-low", 7, 0.0), p("low-hi", 1, 0.9), p("small", None, 0.5, eligible=False)])


def test_tiers_and_boundaries():
    s = B.assign(F).set_index("npi")
    assert s.loc["hi-hi", "baseline_segment"] == "High value / High adoption"
    assert s.loc["hi-mod", "adoption_tier"] == "Moderate"   # 10% is the lower edge of Moderate
    assert s.loc["med-mod", "adoption_tier"] == "Moderate"  # just under 25%
    assert s.loc["med-low", "value_tier"] == "Medium" and s.loc["low-hi", "value_tier"] == "Low"


def test_launch_priority():
    s = B.assign(F).set_index("npi")["priority"].to_dict()
    assert s == {"hi-hi": "A", "hi-mod": "A", "hi-low": "B", "med-mod": "B", "med-low": "C", "low-hi": "C",
                 "small": "-"}


def test_low_volume_kept_but_not_profiled():
    s = B.assign(F).set_index("npi").loc["small"]
    assert s["baseline_segment"] == "Low volume (not profiled)" and pd.isna(s["value_tier"])


def test_profile_shares_add_up():
    prof = B.profile(B.assign(F), "priority")
    assert round(prof["pct_of_claims"].sum()) == 100 and prof["prescribers"].sum() == len(F)
