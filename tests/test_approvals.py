"""Offline tests for the M3 FDA approvals tables, using a tiny fake snapshot."""

import json

from obesity_ci import config
from obesity_ci.transform import approvals as A


def product(brand, ingredients, route, status="Prescription"):
    return {"brand_name": brand, "route": route, "marketing_status": status,
            "active_ingredients": [{"name": i} for i in ingredients]}


def sub(kind, num, status, date, cls=None):
    return {"submission_type": kind, "submission_number": num, "submission_status": status,
            "submission_status_date": date, "submission_class_code": cls}


def test_product_matching_rules():
    m = A.build_matchers(config.molecules())
    assert A.match_product(["SEMAGLUTIDE"], "SUBCUTANEOUS", m) == {"semaglutide"}
    assert A.match_product(["SEMAGLUTIDE"], "ORAL", m) == {"oral semaglutide"}
    assert A.match_product(["INSULIN DEGLUDEC", "LIRAGLUTIDE"], "SUBCUTANEOUS", m) == {"insulin degludec/liraglutide"}
    assert A.match_product(["SITAGLIPTIN PHOSPHATE", "METFORMIN HYDROCHLORIDE"], "ORAL", m) == {"sitagliptin", "metformin"}
    assert A.match_product(["NALTREXONE HYDROCHLORIDE"], "INTRAMUSCULAR", m) == set()  # Vivitrol is not Contrave
    assert A.match_product(["INSULIN SUSP ISOPHANE RECOMBINANT HUMAN"], "INJECTION", m) == {"insulin isophane (nph)"}
    assert A.match_product(["INSULIN RECOMBINANT HUMAN"], "INJECTION", m) == {"insulin regular"}


def test_build_tables(tmp_path):
    apps = {"results": [
        {"application_number": "NDA215866", "sponsor_name": "ELI LILLY AND CO",
         "products": [product("MOUNJARO", ["TIRZEPATIDE"], "SUBCUTANEOUS")],
         "submissions": [sub("ORIG", "1", "AP", "20220513"), sub("SUPPL", "41", "AP", "20260827", "EFFICACY")]},
        {"application_number": "ANDA220314", "sponsor_name": "APOTEX INC",
         "products": [product("SEMAGLUTIDE", ["SEMAGLUTIDE"], "SOLUTION", "None (Tentative Approval)")],
         "submissions": [sub("ORIG", "1", "TA", "20260407")]}]}
    labels = {"results": [
        {"set_id": "a", "version": "40", "effective_time": "20260827", "indications_and_usage": ["1 INDICATIONS"],
         "openfda": {"brand_name": ["Mounjaro"], "application_number": ["NDA215866"], "manufacturer_name": ["Eli Lilly and Company"]}},
        {"set_id": "b", "version": "52", "effective_time": "20260901",
         "openfda": {"brand_name": ["MOUNJARO"], "application_number": ["NDA215866"], "manufacturer_name": ["REMEDYREPACK INC."]}}]}
    (tmp_path / "approvals__tirzepatide.json").write_text(json.dumps(apps))
    (tmp_path / "label__mounjaro.json").write_text(json.dumps(labels))
    (tmp_path / "manifest.json").write_text("{}")
    t = A.build(tmp_path)

    ap = t["fda_applications"].set_index("application_number")
    assert ap.loc["NDA215866", "app_type"] == "NDA"
    assert str(ap.loc["NDA215866", "first_approval_date"].date()) == "2022-05-13"
    assert ap.loc["ANDA220314", "marketing_status"] == "None (Tentative Approval)"
    assert str(ap.loc["ANDA220314", "tentative_approval_date"].date()) == "2026-04-07"
    assert ap.loc["ANDA220314", "molecules"] == "semaglutide"

    ev = t["fda_events"]
    assert list(ev["event_type"]) == ["Efficacy supplement", "Tentative approval", "Original approval"]  # newest first

    lb = t["fda_labels"]
    primary = lb[lb["is_primary"]]
    assert list(primary["set_id"]) == ["a"]  # Lilly's label, not the repackager's higher version


def test_unindexed_manufacturer_label_becomes_primary(tmp_path):
    """2026-11-24: Novo's own Ozempic label had no openfda block, so only a repackager copy was
    primary. A label without the index gets its application from Drugs@FDA, by dosage form."""
    apps = {"results": [
        {"application_number": "NDA209637", "sponsor_name": "NOVO",
         "products": [product("OZEMPIC", ["SEMAGLUTIDE"], "SUBCUTANEOUS")], "submissions": [sub("ORIG", "1", "AP", "20171205")]},
        {"application_number": "NDA213051", "sponsor_name": "NOVO",
         "products": [product("OZEMPIC", ["SEMAGLUTIDE"], "ORAL"), product("RYBELSUS", ["SEMAGLUTIDE"], "ORAL")],
         "submissions": [sub("ORIG", "1", "AP", "20190920")]}]}
    labels = {"results": [
        {"set_id": "repack", "version": "6", "effective_time": "20231117",
         "openfda": {"brand_name": ["OZEMPIC"], "application_number": ["NDA209637"],
                     "manufacturer_name": ["A-S Medication Solutions"]}},
        {"set_id": "novo", "version": "30", "effective_time": "20260901",   # no openfda block
         "spl_product_data_elements": ["Ozempic semaglutide injection SEMAGLUTIDE"],
         "description": ["OZEMPIC (semaglutide) injection, for subcutaneous use"]},
        {"set_id": "novo-tabs", "version": "3", "effective_time": "20260901",
         "spl_product_data_elements": ["Ozempic semaglutide tablet SEMAGLUTIDE"],
         "dosage_forms_and_strengths": ["Tablets: 1.5 mg, 4 mg, 9 mg"]},
        {"set_id": "repack2", "version": "50", "effective_time": "20260901",  # no openfda, repackager panel
         "spl_product_data_elements": ["Ozempic semaglutide injection"],
         "package_label_principal_display_panel": ["Ozempic ... Repackaged by Proficient Rx LP"]}]}
    (tmp_path / "approvals__semaglutide.json").write_text(json.dumps(apps))
    (tmp_path / "label__ozempic.json").write_text(json.dumps(labels))
    (tmp_path / "manifest.json").write_text("{}")
    lb = A.build(tmp_path)["fda_labels"].set_index("set_id")
    assert lb.loc["novo", "application_number"] == "NDA209637" and lb.loc["novo", "manufacturer"] == "NOVO"
    assert lb.loc["novo-tabs", "application_number"] == "NDA213051"  # tablets -> oral application
    assert lb.loc["novo", "manufacturer_source"] == "Drugs@FDA (label not indexed)"
    assert bool(lb.loc["repack2", "is_repackager"])
    assert set(lb.index[lb["is_primary"]]) == {"novo", "novo-tabs"}
