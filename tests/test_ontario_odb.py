"""Offline tests for the Ontario ODB formulary puller."""

from obesity_ci import config
from obesity_ci.sources import ontario_odb

PAGE = "https://www.ontario.ca/document/odb"
HTML = """
<a href="https://www.ontario.ca/files/2026-06/moh-odb-data-extract.xml">XML Data Extract (XML)</a>
<a href="/files/2021-04/odb-schema.xsd?download=1">Schema (XSD)</a>
<a href="https://www.ontario.ca/files/2026-06/edition-43.pdf">Edition 43 (PDF)</a>
<a href="https://www.ontario.ca/files/2026-06/moh-odb-data-extract.xml">duplicate link</a>
"""


def test_find_links_keeps_xml_and_xsd_only_absolute_and_unique():
    links = ontario_odb.find_links(HTML, PAGE, ["xml", "xsd"])
    assert links == ["https://www.ontario.ca/files/2026-06/moh-odb-data-extract.xml",
                     "https://www.ontario.ca/files/2021-04/odb-schema.xsd"]


def test_safe_filename():
    assert ontario_odb.safe_filename("https://x/dl/moh formulary.xml?v=2") == "moh_formulary.xml"


class FakeSession:
    def __init__(self):
        self.downloaded = []

    def download(self, url, dest):
        self.downloaded.append(url)
        dest.write_text(HTML if url.endswith("odb-page") else "<formulary/>")
        return 12


def test_pull_follows_page_links(tmp_path, monkeypatch):
    monkeypatch.setitem(config.settings()["paths"], "raw", str(tmp_path))
    monkeypatch.setitem(config.settings()["sources"]["ontario_odb"], "page_url", "https://www.ontario.ca/odb-page")
    s = FakeSession()
    result = ontario_odb.pull(session=s)
    assert [f["file"] for f in result["files"]] == ["moh-odb-data-extract.xml", "odb-schema.xsd"]
