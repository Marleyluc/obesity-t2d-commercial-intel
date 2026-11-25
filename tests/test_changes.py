"""Offline tests for the M3 change log, using small hand-made 'old' and 'new' tables."""

import pandas as pd

from obesity_ci.transform import changes as C

T = pd.Timestamp


def trial(nct, status="RECRUITING", phase="Phase 3", rank=3, pcd="2027-03-01", results=False,
          sponsor="Eli Lilly and Company", mol="retatrutide", found="molecule__retatrutide", why=None):
    return {"nct_id": nct, "title": f"Trial {nct}", "status": status, "why_stopped": why, "phase": phase,
            "phase_rank": rank, "primary_completion_date": T(pcd) if pcd else pd.NaT, "has_results": results,
            "lead_sponsor": sponsor, "molecules": mol, "found_by": found}


def test_trial_changes():
    old = pd.DataFrame([trial("NCT1"), trial("NCT2"), trial("NCT3", phase="Phase 2", rank=2), trial("NCT4"),
                        trial("NCT9")])
    new = pd.DataFrame([
        trial("NCT1", status="TERMINATED", why="Business decision"),   # status change, late stage -> high
        trial("NCT2", pcd="2027-09-01"),                               # slip of 184 days -> medium
        trial("NCT3", phase="Phase 2/3", rank=2.5),                    # phase change
        trial("NCT4", status="COMPLETED", results=True),              # completed + results
        trial("NCT5"),                                                 # new Phase 3 trial -> high
        trial("NCT6", mol="", found="molecule__semaglutide"),          # noise: no molecule named -> ignored
    ])
    log = C.change_log(C.trial_changes(old, new), "2026-11-24", "2026-12-01")
    got = {(r.id, r.change_type): r for r in log.itertuples()}
    assert got[("NCT1", "Status change")].importance == "high"
    assert "Business decision" in got[("NCT1", "Status change")].detail
    assert got[("NCT2", "Primary completion moved")].detail == "+184 days"
    assert got[("NCT2", "Primary completion moved")].importance == "medium"
    assert got[("NCT3", "Phase change")].new == "Phase 2/3"
    assert got[("NCT4", "Results posted")].importance == "high"
    assert got[("NCT5", "New trial")].importance == "high"
    assert got[("NCT9", "No longer returned")].importance == "low"
    assert not any(k[0] == "NCT6" for k in got)
    assert log["importance"].iloc[0] == "high"  # sorted high first
    assert set(log["old_snapshot"]) == {"2026-11-24"}


def test_fda_changes():
    apps = pd.DataFrame([{"application_number": "NDA1", "app_type": "NDA", "molecules": "orforglipron",
                          "brands": "FOUNDAYO", "sponsor": "LILLY", "marketing_status": "Prescription"},
                         {"application_number": "ANDA2", "app_type": "ANDA", "molecules": "semaglutide",
                          "brands": "SEMAGLUTIDE", "sponsor": "APOTEX", "marketing_status": "None (Tentative Approval)"}])
    ev_old = pd.DataFrame([{"application_number": "NDA1", "submission": "ORIG-1", "event_type": "Original approval",
                            "date": T("2026-04-01"), "letter_url": None}])
    ev_new = pd.concat([ev_old, pd.DataFrame([
        {"application_number": "NDA1", "submission": "SUPPL-5", "event_type": "Efficacy supplement",
         "date": T("2026-11-28"), "letter_url": "https://x/ltr.pdf"},
        {"application_number": "ANDA2", "submission": "ORIG-1", "event_type": "Original approval",
         "date": T("2026-11-29"), "letter_url": None}])], ignore_index=True)
    lab = lambda v, rmc: pd.DataFrame([{"brand_query": "foundayo", "application_number": "NDA1", "is_primary": True,
                                        "version": v, "effective_date": T("2026-07-29"), "indications": "x",
                                        "recent_major_changes": rmc}])
    old = {"fda_applications": apps.iloc[:1], "fda_events": ev_old, "fda_labels": lab(10, "")}
    new_apps = apps.copy()
    new = {"fda_applications": new_apps, "fda_events": ev_new, "fda_labels": lab(11, "Indications (1) 11/2026")}
    log = C.change_log(C.fda_changes(old, new), "a", "b")
    got = {(r.id, r.new): r for r in log.itertuples()}
    assert got[("NDA1", "Efficacy supplement")].importance == "high"
    assert got[("ANDA2", "Original approval")].importance == "medium"  # a generic can now launch
    lbl = log[log["change_type"] == "Label updated"].iloc[0]
    assert lbl["old"] == "10" and "Recent major changes now" in lbl["detail"]


def test_canada_changes():
    hc = lambda status: pd.DataFrame([{"din": "02532891", "molecules": "tirzepatide", "brand": "MOUNJARO",
                                       "status": status, "company": "LILLY"}])
    odb_old = pd.DataFrame([{"din": "02471477", "molecules": "semaglutide", "odb_name": "Ozempic",
                             "coverage": "Limited Use", "list_price": 227.94, "ministry_pays": 227.94}])
    odb_new = pd.concat([odb_old.assign(ministry_pays=78.141),
                         pd.DataFrame([{"din": "02532891", "molecules": "tirzepatide", "odb_name": "Mounjaro",
                                        "coverage": "Limited Use", "list_price": 300.0, "ministry_pays": 300.0}])])
    log = C.canada_changes({"hc_products": hc("Approved"), "odb_listings": odb_old},
                           {"hc_products": hc("Marketed"), "odb_listings": odb_new})
    types = {(r["id"], r["change_type"], r["importance"]) for r in log}
    assert ("02532891", "Canadian status change", "high") in types        # approved -> marketed
    assert ("02532891", "Ontario listing change", "high") in types        # newly listed
    assert ("02471477", "Ontario listing change", "medium") in types      # price paid changed


def test_incomplete_snapshots_are_ignored(tmp_path, monkeypatch):
    from obesity_ci import config, snapshots
    monkeypatch.setitem(config.settings()["paths"], "raw", str(tmp_path))
    (tmp_path / "ctgov" / "2026-11-24").mkdir(parents=True)
    (tmp_path / "ctgov" / "2026-11-24" / "manifest.json").write_text("{}")
    (tmp_path / "ctgov" / "2026-11-25").mkdir()  # interrupted pull: no manifest
    assert [p.name for p in snapshots.list_snapshots("ctgov")] == ["2026-11-24"]
