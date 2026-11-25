"""Shared helpers for the dashboard: where the data is, how to load it, and the chart colours.

Every page reads only app/data/ (built by scripts/build_app_data.py). Nothing here calls an API.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
import streamlit as st

DATA = Path(__file__).parent / "data"

# Colours: a validated colour-blind-safe categorical order (blue, orange, aqua) and a one-hue blue
# ramp for magnitude (heatmaps, maps). Grey is for "everything else".
SERIES = ["#257de0", "#f47230", "#00b894"]
BLUE_RAMP = ["#cce3fd", "#9dc8f7", "#6aabf1", "#338ced", "#2370cd", "#1757ac", "#0e3d7e"]
GREY = "#9c9c9c"

CTGOV = "https://clinicaltrials.gov/study/{}"
NPI_REGISTRY = "https://npiregistry.cms.hhs.gov/provider-view/{}"
US_STATES = set("AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ "
                "NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split())
DRUGS_AT_FDA = "https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&ApplNo={}"


@st.cache_data
def table(name: str) -> pd.DataFrame:
    return pd.read_parquet(DATA / f"{name}.parquet")


@st.cache_data
def meta() -> dict:
    return json.loads((DATA / "meta.json").read_text())


@st.cache_data
def brief() -> str | None:
    p = DATA / "brief.md"
    return p.read_text(encoding="utf-8") if p.exists() else None


def brief_headlines(text: str | None, n: int = 3) -> list[str]:
    """The bullets under '## Headlines', without their [ID] citations, for the home page."""
    if not text or "## Headlines" not in text:
        return []
    section = text.split("## Headlines", 1)[1].split("\n## ", 1)[0]
    bullets = [ln.strip()[2:] for ln in section.splitlines() if ln.strip().startswith("- ")]
    return [re.sub(r"\s*\[[^\]]+\]", "", b).strip() for b in bullets[:n]]


def id_url(id_: str) -> str | None:
    """Where a change-log ID can be checked: ClinicalTrials.gov or Drugs@FDA. DINs have no stable link."""
    id_ = id_.replace(" ", "")
    if re.fullmatch(r"NCT\d{8}", id_):
        return CTGOV.format(id_)
    if re.fullmatch(r"(NDA|BLA|ANDA)\d{6}", id_):
        return DRUGS_AT_FDA.format(re.sub(r"\D", "", id_))
    return None


def link_ids(text: str) -> str:
    """Turn the brief's [ID] citations into clickable links, e.g. [NDA022271] -> [NDA022271](url)."""
    def one(m):
        parts = [p.strip() for p in re.split(r"[;,]", m.group(1))]
        if not all(id_url(p) or re.fullmatch(r"\d{8}", p) for p in parts):
            return m.group(0)  # not a citation (e.g. ordinary brackets): leave it
        return "(" + ", ".join(f"[{p}]({id_url(p)})" if id_url(p) else f"DIN {p}" for p in parts) + ")"
    text = re.sub(r"\]\s*\[", "; ", text)  # [A][B] -> [A; B], so one citation group reads as one list
    return re.sub(r"\[([^\[\]]+)\](?!\()", one, text)


def source_note(*parts: str) -> None:
    """A one-line, small-print source and freshness note under a page's title."""
    st.caption(" · ".join(p for p in parts if p))


def chart_layout(fig, height: int = 420):
    """Quiet chart chrome: no title (the page heading names the chart), light grid, tight margins."""
    fig.update_layout(height=height, margin=dict(l=8, r=8, t=8, b=8),
                      hoverlabel=dict(align="left"), legend_title_text="")
    fig.update_xaxes(showgrid=True, gridcolor="rgba(128,128,128,0.15)", zeroline=False)
    fig.update_yaxes(showgrid=False, zeroline=False)
    return fig
