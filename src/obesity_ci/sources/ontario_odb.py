"""Ontario Drug Benefit (ODB) Formulary puller: what Ontario's public drug plan pays for.

Ontario publishes the formulary as an "XML Data Extract" (plus an XSD schema describing
its structure), linked from an ontario.ca page that is updated with each monthly edition.
File URLs can change between editions, so we:
1. download the page and find every link ending in .xml / .xsd,
2. download those files untouched into the dated snapshot folder,
3. record the page and links in the manifest.

Why not the open-data catalogue? data.ontario.ca still lists a 2019 link on the retired
health.gov.on.ca domain, which no longer resolves (found on our first run, 2026-11-24).

Parsing waits for M3. Once parsed, each drug gets a coverage status: General Benefit
(covered for everyone on the plan), Limited Use (covered only when set criteria are met)
or not listed.
"""

from __future__ import annotations

import re
from datetime import date
from urllib.parse import urljoin

from obesity_ci import config, snapshots
from obesity_ci.http import PoliteSession

SOURCE = "ontario_odb"


def find_links(html: str, base_url: str, extensions: list[str]) -> list[str]:
    """Absolute URLs of every link on the page ending in one of the extensions, in page order."""
    pattern = r'href="([^"]+\.(?:' + "|".join(re.escape(e) for e in extensions) + r'))(?:\?[^"]*)?"'
    seen, out = set(), []
    for href in re.findall(pattern, html, flags=re.IGNORECASE):
        url = urljoin(base_url, href)
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


def safe_filename(url: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", url.rsplit("/", 1)[-1].split("?")[0])


def pull(snapshot_date: date | None = None, session=None) -> dict:
    st = config.settings()["sources"]["ontario_odb"]
    session = session or PoliteSession(delay_s=1.0)
    folder = snapshots.snapshot_dir(SOURCE, snapshot_date)
    for old in folder.iterdir():
        old.unlink()

    page = folder / "source_page.html"
    session.download(st["page_url"], page)
    links = find_links(page.read_text(encoding="utf-8", errors="replace"), st["page_url"],
                       st["link_extensions"])
    if not links:
        raise RuntimeError("No .xml/.xsd links found on the ontario.ca page. The page may have "
                           f"changed: open {page} in a browser and look for the XML Data Extract.")

    entries = []
    for url in links:
        fname = safe_filename(url)
        n = session.download(url, folder / fname)
        entries.append({"file": fname, "url": url, "bytes": n})
        print(f"saved {fname:<45} {n / 1e6:>6.1f} MB   from {url}")

    snapshots.write_manifest(folder, SOURCE, entries, extra={"page_url": st["page_url"]})
    print(f"\nSaved {len(entries)} file(s) to {folder}")
    return {"folder": str(folder), "files": entries}
