"""Offline tests for the M3 landscape views, using small hand-made trial and molecule tables."""

import pandas as pd

from obesity_ci.transform import landscape as L

T = pd.Timestamp
AS_OF = T("2026-11-24")


def trial(nct, status="RECRUITING", phase="Phase 3", rank=3, pcd="2027-03-01", sponsor="Eli Lilly and Company",
          sponsor_class="INDUSTRY", study_type="INTERVENTIONAL", acronym=None):
    return {"nct_id": nct, "title": f"Trial {nct}", "status": status, "phase": phase, "phase_rank": rank,
            "primary_completion_date": T(pcd), "lead_sponsor": sponsor, "sponsor_class": sponsor_class,
            "study_type": study_type, "acronym": acronym, "enrollment": 100.0}


TRIALS = pd.DataFrame([
    trial("NCT1", acronym="TRIUMPH-1"),                                   # retatrutide, P3, counts
    trial("NCT2", phase="Phase 2", rank=2, pcd="2029-01-01"),             # retatrutide, P2, readout too far out
    trial("NCT3", status="COMPLETED"),                                    # not active -> out of pipeline
    trial("NCT4", sponsor_class="OTHER", sponsor="Some University"),      # investigator study -> out
    trial("NCT5", phase="Phase 4", rank=4),                               # post-approval -> out
    trial("NCT6", study_type="OBSERVATIONAL"),                            # not interventional -> out
    trial("NCT7", sponsor="Novo Nordisk A/S", pcd="2027-06-01"),          # CagriSema, P3
    trial("NCT8", sponsor="Novo Nordisk A/S", phase="Phase 1", rank=1),   # CagriSema vs semaglutide, P1
])
LINKS = pd.DataFrame([
    {"nct_id": n, "generic": g, "class_id": c} for n, g, c in [
        ("NCT1", "retatrutide", "glucagon_combos"), ("NCT2", "retatrutide", "glucagon_combos"),
        ("NCT3", "retatrutide", "glucagon_combos"), ("NCT4", "retatrutide", "glucagon_combos"),
        ("NCT5", "retatrutide", "glucagon_combos"), ("NCT6", "retatrutide", "glucagon_combos"),
        ("NCT7", "cagrilintide/semaglutide", "amylin"),
        ("NCT8", "cagrilintide/semaglutide", "amylin"), ("NCT8", "semaglutide", "glp1_injectable"),
    ]])
MOLS = pd.DataFrame([
    {"generic": "retatrutide", "class_id": "glucagon_combos", "sponsor": "Eli Lilly", "generation": "newer",
     "track_trials": True},
    {"generic": "cagrilintide/semaglutide", "class_id": "amylin", "sponsor": "Novo Nordisk",
     "generation": "newer", "track_trials": True},
    {"generic": "semaglutide", "class_id": "glp1_injectable", "sponsor": "Novo Nordisk", "generation": "newer",
     "track_trials": True},
    {"generic": "metformin", "class_id": "biguanide", "sponsor": None, "generation": "legacy",
     "track_trials": False},
])
FDA = pd.DataFrame([
    {"app_type": "NDA", "molecules": "semaglutide", "first_approval_date": T("2017-12-05")},
    {"app_type": "ANDA", "molecules": "retatrutide", "first_approval_date": T("2020-01-01")},  # generic: ignored
])


def pipe():
    return L.pipeline_trials(TRIALS, LINKS)


def test_pipeline_filter_keeps_only_active_industry_phase_1_to_3():
    assert set(pipe()["nct_id"]) == {"NCT1", "NCT2", "NCT7", "NCT8"}


def test_class_phase_counts_each_trial_once_per_class():
    cp = L.class_phase(pipe(), {"amylin": "Amylin", "glucagon_combos": "Glucagon combos"})
    assert cp.loc["Glucagon combos", "Phase 3"] == 1 and cp.loc["Glucagon combos", "Phase 2"] == 1
    assert cp.loc["Amylin", "total"] == 2
    assert cp.loc["glp1_injectable", "Phase 1"] == 1  # no label given -> falls back to the id
    assert list(cp.columns) == [*L.PHASES, "total"]


def test_sponsor_share_is_late_stage_only():
    s = L.sponsor_share(pipe())
    assert s["late_stage_trials"].to_dict() == {"Eli Lilly and Company": 1, "Novo Nordisk A/S": 1}
    assert s["share_pct"].sum() == 100.0


def test_upcoming_window_and_phase():
    u = L.upcoming(pipe(), AS_OF)
    assert list(u["nct_id"]) == ["NCT1", "NCT7"]  # NCT2 is 2029 (outside 18 months); NCT8 is Phase 1


def test_assets_table():
    canada = pd.DataFrame([{"generic": "semaglutide", "ca_status": "Marketed", "ontario_coverage": "Limited Use"}])
    a = L.assets(MOLS, pipe(), canada, FDA, AS_OF).set_index("generic")
    assert "metformin" not in a.index  # legacy molecules are not part of the asset view
    r = a.loc["retatrutide"]
    assert (r["highest_active_phase"], r["active_trials"], r["active_late_stage"]) == ("Phase 3", 2, 1)
    assert r["next_readout"] == T("2027-03-01")
    assert pd.isna(r["us_first_approval"])  # the ANDA row does not count as an approval
    assert a.loc["semaglutide", "us_first_approval"] == T("2017-12-05")
    assert a.loc["semaglutide", "ontario_coverage"] == "Limited Use"
    assert a.loc["semaglutide", "highest_active_phase"] == "Phase 1"
    assert pd.isna(a.loc["retatrutide", "ca_status"])  # no Canada row for it


def test_assets_without_canada_data():
    a = L.assets(MOLS, pipe(), None, FDA, AS_OF)
    assert a["ca_status"].isna().all()


def test_late_stage_hand_check_shows_all_statuses():
    h = L.late_stage_trials(TRIALS, LINKS, "retatrutide")
    assert set(h["nct_id"]) == {"NCT1", "NCT3", "NCT4", "NCT5", "NCT6"}  # any status or sponsor, Phase 2/3+
