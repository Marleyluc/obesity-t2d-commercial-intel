"""Offline tests for the Health Canada DPD puller."""

from obesity_ci import config
from obesity_ci.sources import hc_dpd


def test_ingredient_term():
    assert hc_dpd._ingredient_term("oral semaglutide") == "semaglutide"
    assert hc_dpd._ingredient_term("cagrilintide/semaglutide") == "cagrilintide"
    assert hc_dpd._ingredient_term("insulin isophane (NPH)") == "insulin isophane"


def test_legacy_molecules_search_brands_only():
    by_name = {s["name"]: s for s in hc_dpd.build_searches()}
    assert by_name["metformin"]["ingredient"] is None and by_name["metformin"]["brands"] == ["Glucophage"]
    assert by_name["tirzepatide"]["ingredient"] == "tirzepatide"
    assert "glyburide" not in by_name  # legacy and no brand: nothing to search


def test_as_list_handles_object_list_and_none():
    assert hc_dpd._as_list(None) == []
    assert hc_dpd._as_list({"a": 1}) == [{"a": 1}]
    assert hc_dpd._as_list([{"a": 1}]) == [{"a": 1}]


class FakeSession:
    def get_json(self, url, params=None, none_on_404=False):
        if url.endswith("/activeingredient/") and params.get("ingredientname") == "tirzepatide":
            return [{"drug_code": 1, "ingredient_name": "TIRZEPATIDE"}, {"drug_code": 2, "ingredient_name": "TIRZEPATIDE"}]
        if url.endswith("/drugproduct/") and params.get("brandname"):
            return [{"drug_code": 2}] if params["brandname"] == "Mounjaro" else None
        if url.endswith("/status/"):
            return {"drug_code": params["id"], "status": "Marketed", "original_market_date": "2022-11-24"}
        if "id" in params:
            return [{"drug_code": params["id"]}]
        return None


def test_pull_dedupes_codes_and_counts_marketed(tmp_path, monkeypatch):
    monkeypatch.setitem(config.settings()["paths"], "raw", str(tmp_path))
    result = hc_dpd.pull(only="tirzepatide", session=FakeSession())
    e = result["files"][0]
    assert e["n_products"] == 2 and e["n_marketed"] == 2


def test_brand_match_rejects_contains_noise():
    assert hc_dpd.brand_matches("MOUNJARO KWIKPEN", "Mounjaro")
    assert hc_dpd.brand_matches("ALLI", "Alli")
    assert not hc_dpd.brand_matches("ALLIUM CEPA", "Alli")
    assert not hc_dpd.brand_matches("PLUMBUM METALLICUM", "Alli")
