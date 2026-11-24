"""Offline tests for the ClinicalTrials.gov puller: no internet needed.

A fake session stands in for the real API, so we can test pagination and saving
without depending on the website being up.
"""

import json

import pandas as pd
import pytest

from obesity_ci import config, snapshots
from obesity_ci.sources import ctgov


def test_clean_term_quotes_phrases_and_drops_parentheses():
    assert ctgov._clean_term("tirzepatide") == "tirzepatide"
    assert ctgov._clean_term("BI 456906") == '"BI 456906"'
    assert ctgov._clean_term("insulin isophane (NPH)") == '"insulin isophane"'
    assert ctgov._clean_term("cagrilintide/semaglutide") == '"cagrilintide/semaglutide"'


def test_search_terms_include_brands_and_aliases_without_duplicates():
    row = pd.Series({"generic": "tirzepatide", "brands": ["Mounjaro", "Zepbound"],
                     "aliases": ["LY3298176", "Tirzepatide"]})
    assert ctgov.molecule_search_terms(row) == ["tirzepatide", "Mounjaro", "Zepbound", "LY3298176"]


def test_legacy_comparators_are_not_queried():
    names = {q["name"] for q in ctgov.build_queries()}
    assert "molecule__metformin" not in names
    assert "molecule__insulin_regular" not in names  # molecule-level switch-off
    assert "molecule__tirzepatide" in names
    assert any(n.startswith("condition__") for n in names)


def _study(nct):
    return {"protocolSection": {"identificationModule": {"nctId": nct}}}


class FakeSession:
    """Returns two pages for any query, like the real API does for big result sets."""

    def __init__(self):
        self.calls = []

    def get_json(self, url, params=None):
        self.calls.append(params)
        if "pageToken" not in params:
            return {"studies": [_study("NCT1"), _study("NCT2")], "totalCount": 3, "nextPageToken": "p2"}
        return {"studies": [_study("NCT3")]}


def test_pagination_collects_every_page():
    studies, total = ctgov.fetch_all_pages(FakeSession(), {"query.intr": "x"})
    assert total == 3 and [s["protocolSection"]["identificationModule"]["nctId"] for s in studies] == ["NCT1", "NCT2", "NCT3"]


def test_pull_writes_raw_files_and_manifest(tmp_path, monkeypatch):
    st = config.settings()
    monkeypatch.setitem(st["paths"], "raw", str(tmp_path))
    result = ctgov.pull(only="tirzepatide", session=FakeSession())
    folder = snapshots.list_snapshots("ctgov")[-1]
    manifest = json.loads((folder / "manifest.json").read_text())
    assert manifest["files"][0]["n_studies"] == 3 and manifest["files"][0]["complete"]
    assert result["unique_trials"] == 3


def test_unknown_only_filter_fails_loudly():
    with pytest.raises(ValueError):
        ctgov.pull(only="not_a_drug", session=FakeSession())
