"""Offline tests for the Part D puller, using a tiny fake CSV in place of the 3 GB file."""

from obesity_ci.sources import partd

CATALOG = {"dataset": [
    {"title": "Medicare Part D Prescribers - by Provider and Drug", "distribution": [
        {"title": "Medicare Part D Prescribers - by Provider and Drug : 2022", "mediaType": "text/csv",
         "downloadURL": "https://x/2022.csv"},
        {"title": "Medicare Part D Prescribers - by Provider and Drug : 2023", "mediaType": "text/csv",
         "downloadURL": "https://x/2023.csv"},
        {"title": "API", "format": "API", "accessURL": "https://x/api"}]},
    {"title": "Medicare Part D Prescribers - by Provider", "distribution": [
        {"title": "by Provider : 2023", "mediaType": "text/csv", "downloadURL": "https://x/other.csv"}]},
]}


def test_find_and_choose_latest_year():
    dists = partd.find_distributions(CATALOG, "Medicare Part D Prescribers - by Provider and Drug")
    assert [d["year"] for d in dists] == [2022, 2023]
    assert partd.choose(dists, None)["url"] == "https://x/2023.csv"
    assert partd.choose(dists, 2022)["url"] == "https://x/2022.csv"


def test_patterns_cover_components_and_insulin():
    pats = partd.name_patterns()
    assert {"insulin", "semaglutide", "tirzepatide", "metformin", "liraglutide"} <= set(pats)
    assert "oral semaglutide" not in pats and "insulin degludec" not in pats


def test_duckdb_filter_and_name_report(tmp_path):
    csv = tmp_path / "full.csv"
    csv.write_text(
        "Prscrbr_NPI,Prscrbr_Type,Brnd_Name,Gnrc_Name,Tot_Clms\n"
        "1,Endocrinology,Ozempic,Semaglutide,40\n"
        "2,Family Practice,Lantus,\"Insulin Glargine,Hum.Rec.Anlog\",25\n"
        "3,Cardiology,Lipitor,Atorvastatin Calcium,90\n"
        "4,Internal Medicine,Xultophy,Insulin Degludec/Liraglutide,12\n"
    )
    out = tmp_path / "f.parquet"
    rows = partd.filter_csv(csv, out, partd.name_patterns())
    assert rows == 3  # atorvastatin dropped
    missing = partd.name_report(out, tmp_path / "names.csv")
    assert "semaglutide" not in missing and "insulin glargine" not in missing
    assert "insulin degludec/liraglutide" not in missing
    assert "tirzepatide" in missing  # not in the fake file
    assert "Semaglutide" in (tmp_path / "names.csv").read_text()
