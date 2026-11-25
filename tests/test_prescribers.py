"""Offline tests for the M4 prescriber feature table, using a few hand-made claim rows."""

import pandas as pd
import pytest

from obesity_ci.transform import prescribers as P


def claim(npi, class_id, claims, generic="x", generation="legacy", sponsor="generic",
          specialty="Family Practice", state="PA", benes=20.0):
    return {"npi": npi, "specialty": specialty, "state": state, "claims": claims, "drug_cost": 10.0 * claims,
            "beneficiaries": benes, "generic": generic, "class_id": class_id, "generation": generation,
            "sponsor": sponsor}


CLAIMS = pd.DataFrame([
    claim("A", "legacy_oral_t2d", 60, "metformin", benes=40.0),
    claim("A", "glp1_injectable", 20, "semaglutide", "newer", "Novo Nordisk", benes=None),
    claim("A", "glp1_oral", 10, "oral semaglutide", "newer", "Novo Nordisk"),
    claim("A", "gip_glp1", 10, "tirzepatide", "newer", "Eli Lilly"),
    claim("B", "sglt2", 30, "empagliflozin", "newer", "Boehringer Ingelheim / Eli Lilly",
          specialty="Cardiology", state="GU"),
    claim("C", "legacy_oral_t2d", 120, "metformin", specialty="Endocrinology", state="CA"),
])


def feats():
    return P.build(CLAIMS, min_claims=50).set_index("npi")


def test_value_and_mix():
    a = feats().loc["A"]
    assert a["total_claims"] == 100 and a["n_molecules"] == 4
    assert a["share_legacy_oral"] == 0.6 and a["share_glp1_oral"] == 0.1
    shares = [c for c in feats().columns if c.startswith("share_")]
    assert feats()[shares].sum(axis=1).round(9).eq(1).all()  # mix sums to 100%
    assert a["max_drug_beneficiaries"] == 40  # largest single-drug count, not a sum


def test_adoption_and_launch_fit():
    f = feats()
    a = f.loc["A"]
    assert a["newer_share"] == 0.4 and a["incretin_share"] == 0.4
    assert a["oral_glp1_of_incretin"] == 0.25 and a["lilly_of_incretin"] == 0.25
    assert bool(a["writes_oral_glp1"])
    # SGLT2 from BI/Lilly is not an incretin; non-users get blank (not 0) launch-fit shares
    assert f.loc["B", "incretin_claims"] == 0 and pd.isna(f.loc["B", "lilly_of_incretin"])


def test_context_and_eligibility():
    f = feats()
    assert f.loc["B", "specialty_group"] == "Cardiology" and f.loc["B", "region"] == "Other / unknown"
    assert f.loc["C", "region"] == "West" and f.loc["A", "specialty_group"] == "Primary care physician"
    assert not f.loc["B", "eligible"] and pd.isna(f.loc["B", "volume_decile"])  # 30 claims < 50
    assert f.loc["C", "volume_decile"] > f.loc["A", "volume_decile"]


def test_unknown_class_fails_loudly():
    with pytest.raises(ValueError, match="new_class"):
        P.build(pd.concat([CLAIMS, pd.DataFrame([claim("D", "new_class", 60)])]))
