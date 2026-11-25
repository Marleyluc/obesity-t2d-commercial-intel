"""Offline tests for the M3 trials table, using a tiny fake snapshot."""

import json

from obesity_ci.transform import trials as T


def study(nct, interventions, phases=("PHASE3",), sponsor="Eli Lilly and Company", countries=("Canada",)):
    return {"protocolSection": {
        "identificationModule": {"nctId": nct, "briefTitle": f"Trial {nct}"},
        "statusModule": {"overallStatus": "RECRUITING",
                         "primaryCompletionDateStruct": {"date": "2027-03"}},
        "sponsorCollaboratorsModule": {"leadSponsor": {"name": sponsor, "class": "INDUSTRY"}},
        "designModule": {"studyType": "INTERVENTIONAL", "phases": list(phases)},
        "armsInterventionsModule": {"interventions": [{"type": t, "name": n} for t, n in interventions]},
        "contactsLocationsModule": {"locations": [{"country": c} for c in countries]},
    }}


def test_term_pattern_tolerates_spacing_and_respects_word_edges():
    p = T.term_pattern("BI 456906")
    assert p.search("bi456906") and p.search("bi-456906 low dose")
    s = T.term_pattern("semaglutide")
    assert s.search("cagrilintide/semaglutide") and not s.search("xsemaglutidey")
    assert T.term_pattern("insulin isophane (NPH)").search("insulin isophane")


def test_phase_labels():
    assert T.phase_label(["PHASE2", "PHASE3"]) == ("Phase 2/3", 2.5)
    assert T.phase_label(["NA"])[0] == "Not applicable"
    assert T.phase_label([])[0] == "Not applicable"


def test_combination_absorbs_parts_and_sponsor_check(tmp_path):
    mols = T.config.molecules()
    m = T.build_matchers(mols)
    assert T.match_molecules(["CagriSema", "Semaglutide", "Cagrilintide"], m) == ["cagrilintide/semaglutide"]
    assert T.match_molecules(["Oral semaglutide"], m) == ["oral semaglutide"]
    assert T.match_molecules(["Tirzepatide", "Semaglutide"], m) == ["semaglutide", "tirzepatide"]
    assert T.match_molecules(["Metformin", "Placebo"], m) == []  # legacy: not tracked
    assert T.sponsor_is_originator("Eli Lilly and Company", "Eli Lilly")
    assert T.sponsor_is_originator("Boehringer Ingelheim", "Boehringer Ingelheim / Eli Lilly")
    assert not T.sponsor_is_originator("Hudson Biotech", "Eli Lilly")


def test_build_dedupes_links_and_lists_unmatched(tmp_path):
    a = study("NCT001", [("DRUG", "Retatrutide (LY3437943)"), ("DRUG", "Placebo"),
                         ("BEHAVIORAL", "Tirzepatide education")])
    b = study("NCT002", [("DRUG", "Tirzepatide"), ("DRUG", "Semaglutide")], sponsor="Novo Nordisk A/S")
    c = study("NCT003", [("DRUG", "XYZ-123")], phases=("PHASE2",), countries=("Japan",))
    (tmp_path / "molecule__retatrutide.json").write_text(json.dumps({"studies": [a, b]}))
    (tmp_path / "condition__obesity.json").write_text(json.dumps({"studies": [a, c]}))
    (tmp_path / "manifest.json").write_text("{}")
    out = T.build(tmp_path)
    tr = out["trials"].set_index("nct_id")
    assert len(tr) == 3  # NCT001 found twice, kept once
    assert tr.loc["NCT001", "found_by"] == "condition__obesity; molecule__retatrutide"
    assert tr.loc["NCT001", "molecules"] == "retatrutide"  # behavioural "tirzepatide" ignored
    assert tr.loc["NCT002", "molecules"] == "semaglutide; tirzepatide"  # head-to-head: both
    assert bool(tr.loc["NCT001", "has_canada_site"]) and not tr.loc["NCT003", "has_canada_site"]
    assert str(tr.loc["NCT001", "primary_completion_date"].date()) == "2027-03-01"
    links = out["trial_molecules"].set_index(["nct_id", "generic"])
    assert bool(links.loc[("NCT001", "retatrutide"), "sponsor_is_originator"])
    assert bool(links.loc[("NCT002", "semaglutide"), "sponsor_is_originator"])
    assert not links.loc[("NCT002", "tirzepatide"), "sponsor_is_originator"]
    assert list(out["unmatched"]["nct_id"]) == ["NCT003"]
