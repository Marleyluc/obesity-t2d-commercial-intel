"""Offline tests for the Part D reconciliation, with tiny fake files."""

import duckdb

from obesity_ci.sources import partd, partd_check

GEO = (
    "Prscrbr_Geo_Lvl,Prscrbr_Geo_Cd,Prscrbr_Geo_Desc,Brnd_Name,Gnrc_Name,Tot_Prscrbrs,Tot_Clms\n"
    "National,,National,Ozempic,Semaglutide,\"1,000\",\"1,050\"\n"
    "National,,National,Lantus,\"Insulin Glargine,Hum.Rec.Anlog\",500,400\n"
    "National,,National,Mounjaro,Tirzepatide,800,90000\n"
    "National,,National,Brenzavvy,Bexagliflozin,3,20\n"
    "National,,National,Lipitor,Atorvastatin Calcium,9000,99999\n"
    "State,01,Alabama,Ozempic,Semaglutide,50,60\n"
)


def _ours(tmp_path):
    csv = tmp_path / "ours.csv"
    csv.write_text(
        "Prscrbr_NPI,Brnd_Name,Gnrc_Name,Tot_Clms\n"
        "1,Ozempic,Semaglutide,600\n"
        "2,Ozempic,Semaglutide,400\n"
        "3,Lantus,\"Insulin Glargine,Hum.Rec.Anlog\",450\n"
    )
    pq = tmp_path / "ours.parquet"
    duckdb.connect().execute(
        f"COPY (SELECT * FROM read_csv('{csv}', header=true, all_varchar=true)) TO '{pq}' (FORMAT parquet)")
    return pq


def test_national_extract_keeps_only_national_rows_for_our_drugs(tmp_path):
    geo = tmp_path / "geo.csv"
    geo.write_text(GEO)
    n = partd_check.national_extract(geo, tmp_path / "nat.csv", partd.name_patterns())
    assert n == 4  # no State row, no atorvastatin


def test_reconcile_statuses(tmp_path):
    geo = tmp_path / "geo.csv"
    geo.write_text(GEO)
    nat = tmp_path / "nat.csv"
    partd_check.national_extract(geo, nat, partd.name_patterns())
    df = partd_check.reconcile(_ours(tmp_path), nat).set_index("brand_name")
    assert df.loc["Ozempic", "our_claims"] == 1000
    assert df.loc["Ozempic", "national_claims"] == 1050  # comma in "1,050" handled
    assert df.loc["Ozempic", "status"] == "ok"
    assert df.loc["Lantus", "status"] == "OVER"  # 450 > 400 means double counting
    assert df.loc["Mounjaro", "status"] == "MISSING"  # big drug absent from ours
    assert df.loc["Brenzavvy", "status"] == "all suppressed (small)"
    s = partd_check.summary(df.reset_index())
    assert not s["passed"] and len(s["problems"]) == 2
