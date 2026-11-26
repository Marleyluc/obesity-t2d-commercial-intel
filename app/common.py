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


FONT = ('-apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", Inter, "Helvetica Neue", '
        'Helvetica, Arial, sans-serif')

# One quiet Plotly look for every chart: the app's font, muted axis text, no chart titles.
pio.templates["ci"] = go.layout.Template(layout=dict(
    font=dict(family=FONT, size=13, color="#1d1d1f"),
    colorway=SERIES, hoverlabel=dict(font_size=13, bgcolor="white", bordercolor="#e5e5ea", font_family=FONT),
    xaxis=dict(tickfont=dict(color="#6e6e73")), yaxis=dict(tickfont=dict(color="#6e6e73"))))
pio.templates.default = "plotly_white+ci"


REPO = "https://github.com/Marleyluc/obesity-t2d-commercial-intel"

# The look: Apple-style product pages. Big tight headlines, lots of white space, frosted navigation,
# soft rounded tiles, and motion: things fade up as the page loads, slide in as you scroll (CSS
# scroll-driven animations, no JavaScript), numbers count up, bars grow, a ticker scrolls this week's
# changes. Browsers without scroll-driven animations (older Firefox) just show everything, still.
# Everything is switched off for people who set "reduce motion" in their system settings.
CSS = """
<style>
:root {--ink:#1d1d1f; --ink2:#6e6e73; --ink3:#86868b; --bg2:#f5f5f7; --line:rgba(0,0,0,.08);
  --blue:#0071e3; --grad: linear-gradient(90deg,#2f7bff 0%,#7b5cff 30%,#e04fa0 60%,#ff8a3d 80%,#2f7bff 100%);
  --ease: cubic-bezier(.2,.75,.2,1);
  --font: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", Inter, "Helvetica Neue", Arial, sans-serif;}

/* ---- type: the system font (San Francisco on a Mac), tight tracking like Apple's pages ---- */
.stApp, .stApp p, .stApp li, .stApp a, .stApp label, .stApp button, .stApp input, .stApp textarea,
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6, .stApp div,
.stApp span:not([data-testid="stIconMaterial"]):not([role="img"]) {font-family: var(--font) !important;}
.stApp {color: var(--ink); -webkit-font-smoothing: antialiased;}
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5 {letter-spacing: -.022em; color: var(--ink);}

/* ---- page frame ---- */
[data-testid="stMainBlockContainer"] {max-width: 1180px; padding-top: 4.6rem; padding-bottom: 2rem;}
.stMain {scroll-timeline: --page block; scroll-behavior: smooth;}
footer {visibility: hidden;}

/* ---- frosted navigation bar ---- */
[data-testid="stHeader"] {background: rgba(255,255,255,.72) !important; backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px); border-bottom: 1px solid var(--line);}
[data-testid="stTopNavLink"], [data-testid="stTopNavSection"] {border-radius: 999px !important;
  transition: background .25s var(--ease);}
[data-testid="stTopNavLink"] p, [data-testid="stTopNavSection"] p {font-size: .84rem !important; color: #1d1d1fcc;
  letter-spacing: -.01em;}
[data-testid="stTopNavLink"]:hover, [data-testid="stTopNavSection"]:hover {background: rgba(0,0,0,.05);}
[data-testid="stHeaderLogo"] {transition: transform .4s var(--ease);}
[data-testid="stHeaderLogo"]:hover {transform: scale(1.04);}

/* ---- scroll progress line under the nav ---- */
.ci-progress {position: fixed; top: 0; left: 0; right: 0; height: 3px; z-index: 1000000; background: var(--grad);
  background-size: 200% 100%; transform-origin: 0 50%; transform: scaleX(0); pointer-events: none;}
@supports (animation-timeline: scroll()) {
  .ci-progress {animation: ci-progress linear both; animation-timeline: --page;}}

/* ---- keyframes ---- */
@keyframes ci-up {from {opacity: 0; transform: translateY(28px); filter: blur(8px);} to {opacity: 1; transform: none; filter: none;}}
@keyframes ci-shine {to {background-position: 200% center;}}
@keyframes ci-drift1 {0%,100% {transform: translate(0,0) scale(1);} 50% {transform: translate(120px,60px) scale(1.25);}}
@keyframes ci-drift2 {0%,100% {transform: translate(0,0) scale(1.1);} 50% {transform: translate(-140px,-40px) scale(.9);}}
@keyframes ci-drift3 {0%,100% {transform: translate(0,0) scale(.9);} 50% {transform: translate(60px,-80px) scale(1.2);}}
@keyframes ci-marquee {to {transform: translateX(-50%);}}
@keyframes ci-pulse {0% {box-shadow: 0 0 0 0 rgba(52,199,89,.55);} 100% {box-shadow: 0 0 0 10px rgba(52,199,89,0);}}
@keyframes ci-grow {from {transform: scaleX(0);}}
@keyframes ci-reveal {from {opacity: 0; transform: translateY(48px) scale(.97);} to {opacity: 1; transform: none;}}
@keyframes ci-progress {to {transform: scaleX(1);}}
@keyframes ci-count {from {--n: 0;}}
@property --n {syntax: "\\3c integer\\3e "; inherits: false; initial-value: 0;}

/* ---- gradient text that slowly shimmers ---- */
.ci-grad {background: var(--grad); background-size: 200% auto; -webkit-background-clip: text; background-clip: text;
  color: transparent !important; -webkit-text-fill-color: transparent; animation: ci-shine 8s linear infinite;}

/* ---- numbers that count up on load ---- */
.ci-count {--n: var(--to); counter-reset: c var(--n); animation: ci-count 2.2s var(--ease) both;
  animation-delay: var(--d, .3s); font-variant-numeric: tabular-nums;}
.ci-count::after {content: counter(c);}

/* ---- home hero: black stage, drifting colour light, huge headline ---- */
.ci-hero {position: relative; overflow: hidden; border-radius: 30px; margin: .2rem 0 1.2rem;}
.ci-hero > * {position: relative;}
.ci-hero-home {background: #000; color: #f5f5f7; padding: 6.5rem 3rem 5.5rem; text-align: center; min-height: 34rem;}
.ci-orb {position: absolute !important; border-radius: 50%; filter: blur(70px); opacity: .55; pointer-events: none;}
.ci-orb.o1 {width: 520px; height: 520px; background: #2f7bff; left: -120px; top: -160px; animation: ci-drift1 16s ease-in-out infinite;}
.ci-orb.o2 {width: 460px; height: 460px; background: #b04cff; right: -140px; top: 40px; animation: ci-drift2 19s ease-in-out infinite;}
.ci-orb.o3 {width: 380px; height: 380px; background: #ff5f8f; left: 35%; bottom: -260px; opacity: .4; animation: ci-drift3 22s ease-in-out infinite;}
.ci-lines {position: absolute !important; inset: 0; pointer-events: none; opacity: .5;
  background-image: linear-gradient(rgba(255,255,255,.06) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.06) 1px, transparent 1px);
  background-size: 56px 56px; mask-image: radial-gradient(ellipse at center, #000 20%, transparent 70%);
  -webkit-mask-image: radial-gradient(ellipse at center, #000 20%, transparent 70%);}
.ci-hero .eyebrow {font-size: .82rem; font-weight: 600; letter-spacing: .14em; text-transform: uppercase;
  animation: ci-up 1s var(--ease) both;}
.ci-hero-home .eyebrow {color: #a1a1a6;}
.ci-hero-home h1 {font-size: clamp(2.6rem, 6.4vw, 5.2rem) !important; line-height: 1.04 !important; font-weight: 700 !important;
  letter-spacing: -.035em !important; color: #f5f5f7 !important; margin: .9rem auto 1.3rem !important; padding: 0 !important;}
.ci-hero h1 .l1 {display: block; animation: ci-up 1.1s var(--ease) .12s both;}
.ci-hero h1 .l2 {display: block; animation: ci-up 1.1s var(--ease) .28s both, ci-shine 8s linear infinite;}
.ci-hero-home p {font-size: clamp(1.05rem, 1.8vw, 1.35rem); color: #a1a1a6; max-width: 720px; margin: 0 auto;
  line-height: 1.45; animation: ci-up 1.1s var(--ease) .45s both;}
.ci-hero-home p b {color: #f5f5f7; font-weight: 600;}
.ci-ctas {display: flex; gap: 1.6rem; justify-content: center; align-items: center; margin-top: 2.2rem;
  flex-wrap: wrap; animation: ci-up 1.1s var(--ease) .6s both;}
.ci-btn {background: var(--blue); color: #fff !important; text-decoration: none !important; border-radius: 999px;
  padding: .78rem 1.45rem; font-size: 1rem; font-weight: 500; transition: transform .3s var(--ease), background .3s, box-shadow .3s;}
.ci-btn:hover {background: #0077ed; transform: scale(1.04); box-shadow: 0 10px 30px rgba(0,113,227,.45);}
.ci-more {color: #2997ff !important; text-decoration: none !important; font-size: 1rem;}
.ci-more:after {content: "\\00a0›"; display: inline-block; transition: transform .3s var(--ease);}
.ci-more:hover:after {transform: translateX(4px);}
.ci-more:hover {text-decoration: underline !important;}
.ci-chips {margin-top: 2.4rem; display: flex; flex-wrap: wrap; gap: .5rem; justify-content: center;
  animation: ci-up 1.1s var(--ease) .75s both;}
.ci-chip {border-radius: 999px; padding: .28rem .8rem; font-size: .78rem; letter-spacing: -.005em;}
.ci-hero-home .ci-chip {background: rgba(255,255,255,.08); border: 1px solid rgba(255,255,255,.14); color: #d2d2d7;
  backdrop-filter: blur(10px);}

/* ---- inner-page header: light, big, calm ---- */
.ci-hero-page {background: #fbfbfd; border: 1px solid var(--line); padding: 3.2rem 2.8rem 2.6rem;}
.ci-hero-page .ci-orb {opacity: .16; filter: blur(80px);}
.ci-hero-page .eyebrow {color: var(--blue);}
.ci-hero-page h1 {font-size: clamp(2.2rem, 4.6vw, 3.5rem) !important; line-height: 1.06 !important; font-weight: 700 !important;
  letter-spacing: -.032em !important; margin: .5rem 0 .8rem !important; padding: 0 !important; color: var(--ink) !important;}
.ci-hero-page p {color: var(--ink2); font-size: 1.2rem; line-height: 1.45; max-width: 760px; margin: 0;
  animation: ci-up 1.1s var(--ease) .3s both;}
.ci-hero-page .ci-chips {justify-content: flex-start; margin-top: 1.6rem;}
.ci-hero-page .ci-chip {background: #fff; border: 1px solid var(--line); color: var(--ink2);}

/* ---- stat band (home) ---- */
.ci-stats {display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin: 1.6rem 0 .6rem;}
.ci-stat {text-align: center; padding: 1.6rem .8rem;}
.ci-stat .num {font-size: clamp(2.4rem, 4.4vw, 3.6rem); font-weight: 700; letter-spacing: -.04em; line-height: 1;}
.ci-stat .lbl {font-size: 1.02rem; font-weight: 600; color: var(--ink); margin-top: .6rem; letter-spacing: -.01em;}
.ci-stat .sub {font-size: .86rem; color: var(--ink3); margin-top: .2rem;}

/* ---- this week's ticker ---- */
.ci-ticker {display: flex; align-items: center; gap: 1rem; background: var(--bg2); border-radius: 999px; padding: .55rem .6rem .55rem 1rem;
  overflow: hidden; margin: .6rem 0 2.4rem;}
.ci-live {display: flex; align-items: center; gap: .5rem; font-size: .78rem; font-weight: 600; color: var(--ink);
  white-space: nowrap; text-transform: uppercase; letter-spacing: .08em;}
.ci-dot {width: 8px; height: 8px; border-radius: 50%; background: #34c759; animation: ci-pulse 1.8s ease-out infinite;}
.ci-track {overflow: hidden; flex: 1; mask-image: linear-gradient(90deg, transparent, #000 6%, #000 94%, transparent);
  -webkit-mask-image: linear-gradient(90deg, transparent, #000 6%, #000 94%, transparent);}
.ci-rail {display: flex; gap: 2.6rem; width: max-content; animation: ci-marquee 48s linear infinite;}
.ci-ticker:hover .ci-rail {animation-play-state: paused;}
.ci-item {white-space: nowrap; font-size: .9rem; color: var(--ink2);}
.ci-item b {color: var(--ink); font-weight: 600;}
.ci-tag {font-size: .7rem; font-weight: 600; border-radius: 6px; padding: .1rem .4rem; margin-right: .45rem;
  background: #fff; color: var(--ink2); border: 1px solid var(--line);}
.ci-tag.high {background: #fff1e6; color: #c2410c; border-color: #fed7aa;}

/* ---- bento grid of feature tiles (home) ---- */
.ci-head {text-align: center; margin: 3.4rem 0 1.8rem;}
.ci-head h2 {font-size: clamp(2rem, 4vw, 3rem) !important; font-weight: 700 !important; letter-spacing: -.035em !important;
  line-height: 1.08 !important; margin: 0 !important; padding: 0 !important;}
.ci-head p {color: var(--ink2); font-size: 1.15rem; margin: .7rem auto 0; max-width: 640px;}
.ci-bento {display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.1rem;}
.ci-tile {position: relative; overflow: hidden; background: var(--bg2); border-radius: 28px; padding: 2rem 2rem 1.7rem;
  display: flex; flex-direction: column; gap: .5rem; min-height: 17rem;
  transition: translate .5s var(--ease), box-shadow .5s var(--ease), scale .5s var(--ease);}
.ci-tile:hover {translate: 0 -6px; scale: 1.01; box-shadow: 0 30px 60px -20px rgba(0,0,0,.25);}
.ci-tile.wide {grid-column: span 2;}
.ci-tile.full {grid-column: span 3;}
.ci-tile.tall {grid-row: span 2;}
.ci-tile.dark {background: #000; color: #f5f5f7;}
.ci-tile.dark:before {content: ""; position: absolute; width: 420px; height: 420px; right: -160px; bottom: -180px; border-radius: 50%;
  background: radial-gradient(circle, rgba(123,92,255,.55), rgba(47,123,255,.2) 45%, transparent 70%); filter: blur(20px);
  animation: ci-drift2 18s ease-in-out infinite;}
.ci-tile > * {position: relative;}
.ci-tile .k {font-size: .8rem; font-weight: 600; letter-spacing: .1em; text-transform: uppercase; color: var(--ink3);}
.ci-tile.dark .k {color: #a1a1a6;}
.ci-tile h3 {font-size: 1.75rem !important; font-weight: 700 !important; letter-spacing: -.03em !important;
  line-height: 1.12 !important; margin: .1rem 0 .3rem !important; padding: 0 !important;}
.ci-tile.dark h3 {color: #f5f5f7 !important;}
.ci-tile .t {color: var(--ink2); font-size: 1rem; line-height: 1.45; margin: 0;}
.ci-tile.dark .t {color: #a1a1a6;}
.ci-tile .big {font-size: clamp(3.4rem, 6vw, 5rem); font-weight: 700; letter-spacing: -.05em; line-height: 1; margin: .4rem 0;}
.ci-tile .go {margin-top: auto; padding-top: .8rem; color: var(--blue) !important; text-decoration: none !important; font-size: 1rem;}
.ci-tile.dark .go {color: #2997ff !important;}
.ci-tile .go:after {content: "\\00a0›"; display: inline-block; transition: transform .3s var(--ease);}
.ci-tile:hover .go:after {transform: translateX(5px);}
.ci-tile ul {margin: .2rem 0 0; padding-left: 1.1rem; color: var(--ink2); font-size: .97rem; line-height: 1.45;}
.ci-tile li {margin-bottom: .35rem;}

/* bars inside tiles: they grow in as they scroll into view */
.ci-bars {display: flex; flex-direction: column; gap: .55rem; margin: .6rem 0 .2rem;}
.ci-bar {display: grid; grid-template-columns: 9.5rem 1fr 3.2rem; align-items: center; gap: .7rem; font-size: .88rem; color: var(--ink2);}
.ci-bar .track {height: 10px; border-radius: 999px; background: rgba(0,0,0,.06); overflow: hidden;}
.ci-tile.dark .ci-bar .track {background: rgba(255,255,255,.1);}
.ci-bar .fill {height: 100%; border-radius: 999px; background: var(--c, var(--grad)); transform-origin: 0 50%;
  animation: ci-grow 1.6s var(--ease) both; animation-delay: var(--d, .2s);}
.ci-bars.stacked .ci-bar {grid-template-columns: 1fr auto; row-gap: .35rem;}
.ci-bars.stacked .ci-bar .track {grid-column: 1 / -1; grid-row: 2; height: 12px;}
.ci-tile .delta {font-size: 1.05rem; color: #f5f5f7; margin-top: 1rem; font-weight: 600; letter-spacing: -.01em;}
.ci-tile .delta span {color: #a1a1a6; font-weight: 400;}
.ci-bar .v {text-align: right; font-weight: 600; color: var(--ink); font-variant-numeric: tabular-nums;}
.ci-tile.dark .ci-bar .v {color: #f5f5f7;}
.ci-tile.dark .ci-bar {color: #a1a1a6;}
.ci-stack {display: flex; height: 46px; border-radius: 14px; overflow: hidden; margin: 1rem 0 1rem; gap: 3px;}
.ci-stack div {height: 100%; transform-origin: 0 50%; animation: ci-grow 1.4s var(--ease) both; animation-delay: var(--d);
  transition: filter .3s;}
.ci-stack div:hover {filter: brightness(1.12);}
.ci-legend {display: flex; flex-wrap: wrap; gap: .5rem 1.4rem; font-size: .88rem; color: var(--ink2);}
.ci-legend span:before {content: ""; display: inline-block; width: 10px; height: 10px; border-radius: 3px;
  background: var(--c); margin-right: .45rem; vertical-align: -1px;}
.ci-legend b {color: var(--ink); font-weight: 600;}

/* sources strip */
.ci-sources {display: flex; flex-wrap: wrap; justify-content: center; gap: .6rem 2.4rem; margin: 3rem 0 .5rem;
  color: var(--ink3); font-size: .95rem; font-weight: 500;}
.ci-sources span {transition: color .3s;}
.ci-sources span:hover {color: var(--ink);}

/* ---- KPI tiles (st.metric with border=True) ---- */
[data-testid="stMetric"] {background: var(--bg2) !important; border: none !important; border-radius: 22px !important;
  padding: 1.25rem 1.4rem !important; transition: translate .45s var(--ease), box-shadow .45s var(--ease), background .3s;}
[data-testid="stMetric"]:hover {translate: 0 -4px; background: #fff !important; box-shadow: 0 20px 44px -18px rgba(0,0,0,.22);}
[data-testid="stMetricLabel"] p {font-size: .8rem !important; font-weight: 600; letter-spacing: .02em; color: var(--ink2);}
[data-testid="stMetricValue"] {font-weight: 700; letter-spacing: -.035em; font-size: 2.4rem !important;}
[data-testid="stColumn"] [data-testid="stMetric"] {min-height: 9.6rem; height: 100%;}
/* equal-height KPI tiles in a row */
[data-testid="stColumn"]:has([data-testid="stMetric"]) > [data-testid="stVerticalBlock"],
[data-testid="stColumn"] [data-testid="stElementContainer"]:has(> [data-testid="stMetric"]) {height: 100%;}
[data-testid="stMetricLabel"] *, [data-testid="stMetricDelta"] * {white-space: normal !important; overflow: visible !important;
  text-overflow: clip !important;}
[class*="st-key-card"] [data-testid="stMetric"] {background: transparent !important; padding-left: 0 !important; min-height: 0;}
[class*="st-key-card"] [data-testid="stMetric"]:hover {translate: none; box-shadow: none;}

/* ---- cards: st.container(border=True, key="card-...") ---- */
[class*="st-key-card"] {background: #fff; border: 1px solid var(--line) !important; border-radius: 24px !important;
  box-shadow: 0 2px 6px rgba(0,0,0,.03); padding: 1.5rem 1.7rem !important;
  transition: translate .5s var(--ease), box-shadow .5s var(--ease);}
[class*="st-key-card"]:hover {translate: 0 -4px; box-shadow: 0 26px 54px -22px rgba(0,0,0,.22);}
.st-key-card-reco {background: linear-gradient(135deg, #f5f9ff, #f7f3ff) !important; border-color: rgba(0,113,227,.15) !important;}

/* ---- section headings ---- */
.ci-section {margin: 3.4rem 0 .6rem;}
.ci-section h3 {font-size: clamp(1.6rem, 2.8vw, 2.2rem) !important; font-weight: 700 !important; margin: 0 !important;
  padding: 0 !important; letter-spacing: -.03em !important; line-height: 1.1 !important;}
.ci-section p {color: var(--ink2); margin: .5rem 0 0; font-size: 1.05rem; max-width: 820px; line-height: 1.45;}

/* ---- tabs as an Apple segmented control ---- */
[role="tablist"] {background: var(--bg2); border-radius: 999px; padding: 4px; gap: 2px; width: fit-content;
  border: none !important; box-shadow: none !important;}
[data-testid="stTab"] {border-radius: 999px !important; padding: .5rem 1.2rem !important; height: auto !important;
  border: none !important; transition: background .3s var(--ease), box-shadow .3s var(--ease);}
[data-testid="stTab"] p {color: var(--ink2) !important; font-weight: 500;}
[data-testid="stTab"][data-selected="true"] {background: #fff; box-shadow: 0 2px 10px rgba(0,0,0,.1);}
[data-testid="stTab"][data-selected="true"] p {color: var(--ink) !important;}
.react-aria-SelectionIndicator {display: none !important;}

/* ---- buttons, links, inputs, expanders ---- */
[data-testid="stDownloadButton"] button, .stButton button {border-radius: 999px !important; padding: .45rem 1.2rem !important;
  transition: transform .3s var(--ease), box-shadow .3s;}
[data-testid="stDownloadButton"] button:hover, .stButton button:hover {transform: scale(1.03); box-shadow: 0 8px 22px -8px rgba(0,113,227,.5);}
[data-testid="stPageLink"] a {border: none; padding: .1rem 0; background: transparent !important;}
[data-testid="stPageLink"] a p {color: var(--blue) !important; font-size: 1rem;}
[data-testid="stPageLink"] a:hover p {text-decoration: underline;}
[data-testid="stExpander"] details {border-radius: 18px !important; border-color: var(--line) !important;}
[data-baseweb="select"] > div, [data-baseweb="input"] {border-radius: 12px !important;}
[data-testid="stDataFrame"] {border-radius: 16px; overflow: hidden;}
[data-testid="stCaptionContainer"] {color: var(--ink3);}

/* ---- scroll reveals: content slides up as it enters the screen ---- */
@supports (animation-timeline: view()) {
  [data-testid="stMetric"], [class*="st-key-card"], .ci-section, [data-testid="stPlotlyChart"], [data-testid="stDataFrame"],
  [data-testid="stExpander"], .ci-tile, .ci-stat, .ci-head, .ci-sources, .ci-ticker {
    animation: ci-reveal linear both; animation-timeline: view(); animation-range: entry 0% entry 260px;}
  .ci-bar .fill, .ci-stack div {animation: ci-grow linear both; animation-timeline: view(); animation-range: entry 10% cover 40%;}
}

/* ---- footer ---- */
.ci-footer {margin-top: 4rem; padding: 1.8rem 0 .4rem; border-top: 1px solid var(--line); display: grid;
  grid-template-columns: 2fr 1fr 1fr; gap: 1.5rem; color: var(--ink3); font-size: .8rem; line-height: 1.5;}
.ci-footer b {color: var(--ink); font-weight: 600;}
.ci-footer a {color: var(--ink2); text-decoration: none; display: block; margin: .2rem 0;}
.ci-footer a:hover {color: var(--ink); text-decoration: underline;}

@media (max-width: 900px) {
  .ci-bento {grid-template-columns: 1fr;} .ci-tile.wide, .ci-tile.full {grid-column: auto;} .ci-tile.tall {grid-row: auto;}
  .ci-stats {grid-template-columns: repeat(2, 1fr);} .ci-footer {grid-template-columns: 1fr;}
  .ci-hero-home {padding: 4rem 1.4rem 3.6rem; min-height: 0;} .ci-hero-page {padding: 2.2rem 1.4rem;}
  .ci-bar {grid-template-columns: 7rem 1fr 2.8rem;}}
@media (prefers-reduced-motion: reduce) {
  .stApp *, .stApp *:before, .stApp *:after {animation: none !important; transition: none !important;}
  .ci-count {--n: var(--to);}}
</style>
"""


def inject_css() -> None:
    st.html(CSS)


def count(text: str, delay: float = .3) -> str:
    """A number that counts up on load: '45,000' -> 0..45 then ',000'; '61.9%' -> 0..61 then '.9%'."""
    m = re.match(r"^(\d+)(.*)$", text)
    if not m:
        return text
    return f"<span class='ci-count' style='--to:{int(m.group(1))};--d:{delay}s'></span>{m.group(2)}"


def _chips(chips: list[str] | None) -> str:
    m = meta()
    chips = chips if chips is not None else [f"Trials {m['landscape_snapshot']}", f"Brief {m['brief']}",
                                             f"Part D {m['part_d_data_year']} data"]
    return "".join(f"<span class='ci-chip'>{c}</span>" for c in chips)


def page_header(eyebrow: str, title: str, subtitle: str = "", chips: list[str] | None = None,
                small: bool = True) -> None:
    """The header at the top of every inner page: section label, big title, purpose, freshness chips."""
    st.html(f"<div class='ci-hero ci-hero-page'><div class='ci-orb o1'></div><div class='ci-orb o2'></div>"
            f"<div class='eyebrow'>{eyebrow}</div><h1><span class='l1'>{title}</span></h1><p>{subtitle}</p>"
            f"<div class='ci-chips'>{_chips(chips)}</div></div>")


def home_hero(eyebrow: str, line1: str, line2: str, subtitle: str, ctas: list[tuple[str, str]]) -> None:
    """The home page's black stage: drifting colour light, a two-line headline, two calls to action."""
    btns = "".join(f"<a class='{'ci-btn' if i == 0 else 'ci-more'}' href='{href}' target='_self'>{label}</a>"
                   for i, (label, href) in enumerate(ctas))
    st.html(f"<div class='ci-hero ci-hero-home'><div class='ci-orb o1'></div><div class='ci-orb o2'></div>"
            f"<div class='ci-orb o3'></div><div class='ci-lines'></div>"
            f"<div class='eyebrow'>{eyebrow}</div><h1><span class='l1'>{line1}</span>"
            f"<span class='l2 ci-grad'>{line2}</span></h1><p>{subtitle}</p>"
            f"<div class='ci-ctas'>{btns}</div><div class='ci-chips'>{_chips(None)}</div></div>")


def section(title: str, subtitle: str = "") -> None:
    st.html(f"<div class='ci-section'><h3>{title}</h3>{f'<p>{subtitle}</p>' if subtitle else ''}</div>")


def footer() -> None:
    m = meta()
    docs = REPO + "/blob/main/docs/"
    st.html(f"""<div class='ci-progress'></div><div class='ci-footer'>
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
                      hoverlabel=dict(align="left"), legend_title_text="",
                      transition=dict(duration=500, easing="cubic-in-out"))
    fig.update_xaxes(showgrid=True, gridcolor="rgba(0,0,0,0.06)", zeroline=False)
    fig.update_yaxes(showgrid=False, zeroline=False)
    return fig
