"""Smoke tests for the dashboard: every page runs on the committed app/data/ without errors.

Uses Streamlit's own test runner (no browser). Also checks the M6 speed target loosely:
each page must render in well under 5 seconds.
"""

import time
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app"
PAGES = sorted(p.name for p in (APP / "views").glob("*.py"))


@pytest.fixture(autouse=True)
def app_on_path(monkeypatch):
    monkeypatch.syspath_prepend(str(APP))  # pages do `import common`, as Streamlit allows


@pytest.mark.parametrize("page", PAGES)
def test_page_runs(page):
    start = time.perf_counter()
    at = AppTest.from_file(str(APP / "streamlit_app.py"), default_timeout=30).run()
    at.switch_page(f"views/{page}").run()
    assert not at.exception, at.exception
    assert at.title, "every page has a title"
    assert time.perf_counter() - start < 5


def test_headlines_drop_citations():
    import common as C
    text = "## Headlines\n\n- Takeda updated three labels [NDA022271][NDA022426].\n\n## Next\n- x"
    assert C.brief_headlines(text) == ["Takeda updated three labels."]


def test_brief_ids_become_links():
    import common as C
    out = C.link_ids("Takeda [NDA022271][NCT01234567] and a DIN [02512345], not [a note].")
    assert out.startswith("Takeda ([NDA022271](https://www.accessdata.fda.gov/") and "ApplNo=022271" in out
    assert ", [NCT01234567](https://clinicaltrials.gov/study/NCT01234567))" in out
    assert "(DIN 02512345)" in out and "[a note]" in out
