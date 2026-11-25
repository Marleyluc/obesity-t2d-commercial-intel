"""Offline tests for the M4 Part D tidy table, using a few hand-made CMS rows."""

import pandas as pd
import pytest

from obesity_ci import config
from obesity_ci.transform import prescriptions as P


def row(npi, generic, brand, claims, benes="20", specialty="Family Practice"):
    return {"Prscrbr_NPI": npi, "Prscrbr_Last_Org_Name": "Doe", "Prscrbr_First_Name": "Jo", "Prscrbr_City": "X",
            "Prscrbr_State_Abrvtn": "PA", "Prscrbr_State_FIPS": "42", "Prscrbr_Type": specialty,
            "Prscrbr_Type_Src": "Claim-Specialty", "Brnd_Name": brand, "Gnrc_Name": generic,
            "Tot_Clms": str(claims), "Tot_30day_Fills": str(claims), "Tot_Day_Suply": str(30 * claims),
            "Tot_Drug_Cst": "100.5", "Tot_Benes": benes}


RAW = pd.DataFrame([
    row("1", "Semaglutide", "Ozempic", 50),
    row("1", "Semaglutide", "Rybelsus", 12, benes=None),
    row("1", "Sitagliptin Phos/Metformin Hcl", "Janumet", 30),
    row("2", "Bupropion Hcl", "Bupropion Xl", 105, specialty="Psychiatry"),
    row("2", "Syringe-Needle,insulin,0.5 Ml", "Bd Insulin Syringe", 20),
    row("3", "Insulin Glargine-Yfgn", "Semglee", 40, specialty="Endocrinology"),
])


def test_every_name_in_the_real_extract_is_mapped():
    names = P.name_map()
    assert set(names["status"]) == {"in_scope", "excluded"}
    assert not names["cms_generic_name"].duplicated().any()
    assert (names.loc[names["status"] == "excluded", "note"] != "").all()  # every exclusion has a reason


def test_mapping_rules():
    t = P.build(RAW, P.name_map(), config.molecules())
    c = t["claims"].set_index("cms_brand")
    assert c.loc["Ozempic", "generic"] == "semaglutide" and c.loc["Ozempic", "class_id"] == "glp1_injectable"
    assert c.loc["Rybelsus", "generic"] == "oral semaglutide" and c.loc["Rybelsus", "class_id"] == "glp1_oral"
    assert c.loc["Janumet", "class_id"] == "dpp4"            # combination counted once, newest mechanism
    assert c.loc["Semglee", "generic"] == "insulin glargine"  # biosimilar under its molecule
    assert bool(c.loc["Rybelsus", "beneficiaries_hidden"]) and pd.isna(c.loc["Rybelsus", "beneficiaries"])
    assert c.loc["Ozempic", "claims"] == 50
    assert "Prscrbr_Last_Org_Name" not in t["claims"].columns and "npi" in t["claims"].columns  # no names


def test_exclusions_are_reported_not_counted():
    t = P.build(RAW, P.name_map(), config.molecules())
    assert set(t["claims"]["npi"]) == {"1", "3"}
    ex = t["excluded"].set_index("cms_generic")
    assert ex.loc["Bupropion Hcl", "claims"] == 105 and "Contrave" in ex.loc["Bupropion Hcl", "note"]
    assert "device" in ex.loc["Syringe-Needle,insulin,0.5 Ml", "note"]


def test_unknown_name_stops_the_build():
    raw = pd.concat([RAW, pd.DataFrame([row("4", "Orforglipron", "Foundayo", 15)])])
    with pytest.raises(ValueError, match="Orforglipron"):
        P.build(raw, P.name_map(), config.molecules())
