"""Offline tests for the openFDA puller."""

import pandas as pd

from obesity_ci import config
from obesity_ci.sources import openfda


def test_fda_name_formats_combinations_and_oral_forms():
    assert openfda._fda_name("insulin degludec/liraglutide") == "insulin degludec and liraglutide"
    assert openfda._fda_name("oral semaglutide") == "semaglutide"
    assert openfda._fda_name("insulin isophane (NPH)") == "insulin isophane"


def test_approvals_search_ors_generic_and_brands():
    row = pd.Series({"generic": "tirzepatide", "brands": ["Mounjaro", "Zepbound"]})
    q = openfda.approvals_search(row)
    assert 'openfda.generic_name:"tirzepatide"' in q and 'products.active_ingredients.name:"tirzepatide"' in q
    assert 'openfda.brand_name:"Zepbound"' in q and 'products.brand_name:"Zepbound"' in q
    assert " AND " not in q  # spaces = OR


def test_one_label_query_per_brand():
    names = [q["name"] for q in openfda.build_queries()]
    assert "label__zepbound" in names and "label__mounjaro" in names
    assert not any(n == "label__retatrutide" for n in names)  # pipeline: no brand, no label


class FakeSession:
    """Two pages for anything with 'tirzepatide'; 404 (None) for anything else."""

    def get_json(self, url, params=None, none_on_404=False):
        if "tirzepatide" not in params["search"]:
            return None
        page = [{"application_number": f"NDA{params['skip'] + i}"} for i in range(2)]
        return {"meta": {"results": {"total": 3}}, "results": page[: 3 - params["skip"]]}


def test_paging_and_404(monkeypatch):
    monkeypatch.setitem(config.settings()["sources"]["openfda"], "page_limit", 2)
    results, total = openfda.fetch_all(FakeSession(), "drug/drugsfda", {"search": "tirzepatide"})
    assert total == 3 and len(results) == 3
    assert openfda.fetch_all(FakeSession(), "drug/drugsfda", {"search": "retatrutide"}) == ([], 0)


def test_pull_saves_files(tmp_path, monkeypatch):
    monkeypatch.setitem(config.settings()["paths"], "raw", str(tmp_path))
    result = openfda.pull(only="retatrutide", session=FakeSession())
    assert result["files"][0]["n_results"] == 0


def test_label_search_also_reads_the_labels_own_product_text():
    q = openfda.label_search("Ozempic")
    assert 'openfda.brand_name:"Ozempic"' in q and 'spl_product_data_elements:"Ozempic"' in q
    assert " AND " not in q  # spaces = OR
