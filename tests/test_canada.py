"""Offline tests for the M3 Canada tables, using tiny fake Health Canada and Ontario files."""

import json

import pandas as pd

from obesity_ci import config
from obesity_ci.transform import canada as C


def hc_product(code, din, brand, ingredient, status, market=None, history="2022-11-24", unit="ML"):
    return {"drug_code": code, "found_by": "x",
            "product": [{"drug_identification_number": din, "brand_name": brand, "descriptor": "",
                         "company_name": "CO"}],
            "status": [{"status": status, "history_date": history, "original_market_date": market}],
            "ingredients": [{"ingredient_name": ingredient, "dosage_unit": unit}]}


ODB_XML = """<?xml version="1.0"?>
<extract createDate="2026-10-28"><manufacturerList><manufacturer id="A">A</manufacturer></manufacturerList>
<formulary createDate="2026-10-28" edition="43" formularyDate="2026-10-28" updateVer="x">
 <pcg2 id="1"><name>X</name><pcg6><genericName id="g1"><name>SEMAGLUTIDE</name>
  <pcgGroup lccId="1">
   <pcg9 id="p1"><strength>1.34mg/mL</strength><dosageForm>Inj Sol-Pref Pen 3mL Pk</dosageForm>
    <drug id="02471477" sec3="Y"><name>Ozempic</name><manufacturerId>A</manufacturerId>
     <individualPrice>227.94</individualPrice><listingDate>2019-09-30</listingDate><amountMOHLTCPays>78.141</amountMOHLTCPays></drug>
   </pcg9>
   <lccNote seq="001" reasonForUseId="666">For type 2 diabetes after metformin</lccNote>
   <lccNote seq="002" type="R">LU Authorization Period: Indefinite</lccNote>
  </pcgGroup>
  <pcgGroup><pcg9 id="p2"><strength>4mg/3mL</strength><dosageForm>Inj Sol-3mL Pref Pen</dosageForm>
    <drug id="02528525" notABenefit="Y"><name>Wegovy</name><manufacturerId>A</manufacturerId><listingDate>2026-08-31</listingDate></drug>
  </pcg9></pcgGroup>
 </genericName></pcg6></pcg2>
 <pcg2 id="2"><name>Y</name><pcg6><genericName id="g2"><name>EMPAGLIFLOZIN</name><pcgGroup>
  <pcg9 id="p3"><strength>10mg</strength><dosageForm>Tab</dosageForm>
   <drug id="02443937"><name>Jardiance</name><manufacturerId>A</manufacturerId><individualPrice>2.8868</individualPrice>
    <listingDate>2016-05-31</listingDate><amountMOHLTCPays>2.8868</amountMOHLTCPays></drug></pcg9>
 </pcgGroup></genericName></pcg6></pcg2>
</formulary></extract>"""


def test_hc_odb_and_lag(tmp_path):
    mols = config.molecules()
    (tmp_path / "tirzepatide.json").write_text(json.dumps({"products": [
        hc_product(1, "02532891", "MOUNJARO", "TIRZEPATIDE", "Marketed", market="2023-10-23"),
        hc_product(2, "02532905", "MOUNJARO", "TIRZEPATIDE", "Approved")]}))
    (tmp_path / "semaglutide.json").write_text(json.dumps({"products": [
        hc_product(3, "02497581", "RYBELSUS", "SEMAGLUTIDE", "Marketed", market="2020-04-19", unit=""),
        hc_product(4, "02471477", "OZEMPIC", "SEMAGLUTIDE", "Marketed", market="2018-02-22")]}))
    (tmp_path / "insulin_regular.json").write_text(json.dumps({"products": [
        hc_product(5, "00586714", "HUMULIN R", "INSULIN SEMI SYNTHETIC HUMAN", "Marketed", market="1983-12-31")]}))
    hc = C.hc_products(tmp_path, mols).set_index("din")
    assert hc.loc["02497581", "molecules"] == "oral semaglutide"  # tablet: no per-mL strength
    assert hc.loc["02471477", "molecules"] == "semaglutide"
    assert hc.loc["00586714", "molecules"] == "insulin regular" and hc.loc["00586714", "matched_by"] == "brand"

    xml = tmp_path / "odb.xml"
    xml.write_text(ODB_XML)
    odb = C.odb_listings(xml, mols).set_index("odb_name")
    assert odb.loc["Ozempic", "coverage"] == "Limited Use"
    assert odb.loc["Ozempic", "ministry_pays"] < odb.loc["Ozempic", "list_price"]
    assert odb.loc["Wegovy", "coverage"] == "Listed, not a benefit"
    assert odb.loc["Jardiance", "coverage"] == "General benefit"
    assert odb.loc["Jardiance", "molecules"] == "empagliflozin"

    fda = pd.DataFrame([
        {"app_type": "NDA", "molecules": "tirzepatide", "brands": "MOUNJARO", "first_approval_date": pd.Timestamp("2022-05-13")},
        {"app_type": "ANDA", "molecules": "tirzepatide", "brands": "X", "first_approval_date": pd.Timestamp("2020-01-01")}])
    s = C.molecule_summary(mols, hc.reset_index(), odb.reset_index(), fda).set_index("generic")
    assert s.loc["tirzepatide", "canada_lag_months"] == 17.3  # ANDA ignored; 2022-05-13 -> 2023-10-23
    assert s.loc["tirzepatide", "ca_status"] == "Marketed"
    assert s.loc["tirzepatide", "ontario_coverage"] == "Not listed"
    assert s.loc["semaglutide", "ontario_coverage"] == "Limited Use"  # best status across brands
    assert s.loc["retatrutide", "ca_status"] == "Not in Canada"
    assert s.loc["glyburide", "ca_status"] == "Not found under US brand names"
