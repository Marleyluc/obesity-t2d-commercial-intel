"""Shared helpers for the dashboard: where the data is, how to load it, and the chart colours.

Every page reads only app/data/ (built by scripts/build_app_data.py). Nothing here calls an API.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

DATA = Path(__file__).parent / "data"
LOGO = Path(__file__).parent / "assets" / "logo.svg"

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


# One quiet Plotly look for every chart: the app's font, muted axis text, no chart titles.
pio.templates["ci"] = go.layout.Template(layout=dict(
    font=dict(family="Inter, system-ui, -apple-system, Segoe UI, sans-serif", size=13, color="#3b4557"),
    colorway=SERIES, hoverlabel=dict(font_size=13, bgcolor="white", bordercolor="#e2e6ec"),
    xaxis=dict(tickfont=dict(color="#5b6578")), yaxis=dict(tickfont=dict(color="#5b6578"))))
pio.templates.default = "plotly_white+ci"


REPO = "https://github.com/Marleyluc/obesity-t2d-commercial-intel"

CSS = """
<style>
/* ---- page frame: centred content, like a website ---- */
[data-testid="stMainBlockContainer"] {max-width: 1240px; padding-top: 4.2rem; padding-bottom: 2rem;}
[data-testid="stHeader"] {background: rgba(255,255,255,.92); backdrop-filter: blur(8px);
  border-bottom: 1px solid #e2e6ec;}
footer {visibility: hidden;}

/* ---- hero band ---- */
.ci-hero {background: linear-gradient(120deg, #0f1f35 0%, #163a6b 55%, #1b64be 100%); color: #fff;
  border-radius: 18px; padding: 2.2rem 2.4rem; margin: .4rem 0 1.4rem; position: relative; overflow: hidden;}
.ci-hero:after {content: ""; position: absolute; right: -80px; top: -80px; width: 320px; height: 320px;
  border-radius: 50%; background: radial-gradient(circle, rgba(255,255,255,.16), rgba(255,255,255,0) 70%);}
.ci-hero .eyebrow {font-size: .78rem; font-weight: 600; letter-spacing: .12em; text-transform: uppercase;
  color: #9dc8f7;}
.ci-hero h1 {color: #fff; font-size: 2.3rem; font-weight: 700; line-height: 1.15; margin: .35rem 0 .5rem;
  padding: 0;}
.ci-hero.small h1 {font-size: 1.9rem;}
.ci-hero p {color: #d6e4f5; font-size: 1.05rem; max-width: 760px; margin: 0;}
.ci-chips {margin-top: 1.1rem; display: flex; flex-wrap: wrap; gap: .5rem;}
.ci-chip {background: rgba(255,255,255,.12); border: 1px solid rgba(255,255,255,.22); color: #eef4fb;
  border-radius: 999px; padding: .22rem .75rem; font-size: .8rem;}

/* ---- KPI tiles (st.metric with border) ---- */
[data-testid="stMetric"] {background: #fff; box-shadow: 0 1px 2px rgba(16,24,40,.05), 0 4px 12px rgba(16,24,40,.04);
  border-top: 3px solid #1b64be !important;}
[data-testid="stMetricLabel"] p {font-size: .78rem !important; font-weight: 600; letter-spacing: .04em;
  text-transform: uppercase; color: #5b6578;}
[data-testid="stMetricValue"] {font-weight: 650; letter-spacing: -.01em;}
[data-testid="stColumn"] [data-testid="stMetric"] {min-height: 8.1rem;}
/* metrics inside cards are plain numbers, not tiles */
[class*="st-key-card"] [data-testid="stMetric"] {box-shadow: none; border-top: none !important; border: none !important;
  background: transparent; padding-left: 0; min-height: 0;}

/* ---- cards: st.container(border=True, key="card-...") ---- */
[class*="st-key-card"] {background: #fff; box-shadow: 0 1px 2px rgba(16,24,40,.05), 0 6px 16px rgba(16,24,40,.05);
  transition: box-shadow .15s ease, transform .15s ease;}
[class*="st-key-card"]:hover {box-shadow: 0 2px 4px rgba(16,24,40,.06), 0 12px 28px rgba(16,24,40,.09);
  transform: translateY(-1px);}

/* ---- section headings ---- */
.ci-section {margin: 2.2rem 0 .2rem;}
.ci-section h3 {font-size: 1.3rem; font-weight: 650; margin: 0; padding: 0; color: #1a2233;}
.ci-section p {color: #5b6578; margin: .25rem 0 0; font-size: .95rem;}

/* ---- links styled as buttons ---- */
[data-testid="stPageLink"] a {border: 1px solid #d5dde8; border-radius: 999px; padding: .15rem .9rem;
  background: #fff;}
[data-testid="stPageLink"] a:hover {border-color: #1b64be; background: #f2f7fd;}

/* ---- footer ---- */
.ci-footer {margin-top: 3rem; padding: 1.6rem 0 .4rem; border-top: 1px solid #e2e6ec; display: grid;
  grid-template-columns: 2fr 1fr 1fr; gap: 1.5rem; color: #5b6578; font-size: .85rem;}
.ci-footer b {color: #1a2233;}
.ci-footer a {color: #5b6578; text-decoration: none; display: block; margin: .15rem 0;}
.ci-footer a:hover {color: #1b64be;}
@media (max-width: 760px) {.ci-footer {grid-template-columns: 1fr;} .ci-hero {padding: 1.6rem;}
  .ci-hero h1 {font-size: 1.7rem;}}
</style>
"""


def inject_css() -> None:
    st.html(CSS)


def page_header(eyebrow: str, title: str, subtitle: str = "", chips: list[str] | None = None,
                small: bool = True) -> None:
    """The coloured band at the top of every page: section label, title, purpose, data-freshness chips."""
    m = meta()
    chips = chips if chips is not None else [f"Trials {m['landscape_snapshot']}", f"Brief {m['brief']}",
                                             f"Part D {m['part_d_data_year']} data"]
    chip_html = "".join(f"<span class='ci-chip'>{c}</span>" for c in chips)
    st.html(f"<div class='ci-hero{' small' if small else ''}'><div class='eyebrow'>{eyebrow}</div>"
            f"<h1>{title}</h1><p>{subtitle}</p><div class='ci-chips'>{chip_html}</div></div>")


def section(title: str, subtitle: str = "") -> None:
    st.html(f"<div class='ci-section'><h3>{title}</h3>{f'<p>{subtitle}</p>' if subtitle else ''}</div>")


def footer() -> None:
    m = meta()
    docs = REPO + "/blob/main/docs/"
    st.html(f"""<div class='ci-footer'>
      <div><b>Obesity &amp; T2D Intelligence</b><br>Internal tool for the {m['anchor_brand']} brand team.
        Built from public data: ClinicalTrials.gov, openFDA, Health Canada, Ontario Drug Benefit and CMS
        Medicare Part D. Data built {m['built_at']}.</div>
      <div><b>Methodology</b><a href='{docs}M3_DECISIONS.md' target='_blank'>Landscape</a>
        <a href='{docs}M4_DECISIONS.md' target='_blank'>Segmentation</a>
        <a href='{docs}M5_DECISIONS.md' target='_blank'>Weekly brief</a></div>
      <div><b>Project</b><a href='{REPO}' target='_blank'>Source code</a>
        <a href='{docs}DATA_NOTES.md' target='_blank'>Data notes</a>
        <a href='{docs}ROADMAP.md' target='_blank'>Roadmap</a></div></div>""")


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
