"""Overview: a product-style landing page. The three answers a brand lead wants on Monday morning,
with motion, and links to the detail."""

import html

import streamlit as st

import common as C

m = C.meta()
up = C.table("landscape_upcoming")
cp = C.table("landscape_class_phase")
share = C.table("landscape_sponsor_share")
late = int(cp["Phase 3"].sum() + cp["Phase 2/3"].sum())
changes = C.table("changes") if (C.DATA / "changes.parquet").exists() else None
n_changes = 0 if changes is None else len(changes)
reach, base_reach = m["plan_pct_incretin_claims"], m["baseline_pct_incretin_claims"]
fit, base_fit = m["plan_pct_high_fit"], m["baseline_pct_high_fit"]

# ---- hero ----
C.home_hero("Obesity &amp; type 2 diabetes · Internal", "Know the market.", "Call the right doctors.",
            f"Competitive intelligence and launch targeting for the <b>{m['anchor_brand']}</b> brand team. "
            "What competitors are doing, what changed this week, and who the field force should call first.",
            [("See who to target", "segments"), ("Read this week's brief", "changes")])

# ---- headline numbers, counting up ----
stats = [(f"{late}", "Late-stage trials", "Active Phase 2/3 and 3"),
         (f"{len(up)}", "Readouts ahead", "Primary completion in 18 months"),
         (f"{n_changes}", "Changes this week", f"Change log {m['change_log']}"),
         (f"{reach}%", "GLP-1 claims reached", f"by {m['call_capacity']:,} names, {reach - base_reach:+.1f} pts")]
st.html("<div class='ci-stats'>" + "".join(
    f"<div class='ci-stat'><div class='num ci-grad'>{C.count(v, .3 + .15 * i)}</div><div class='lbl'>{l}</div>"
    f"<div class='sub'>{s}</div></div>" for i, (v, l, s) in enumerate(stats)) + "</div>")

# ---- this week's ticker ----
# Market changes only: pipeline housekeeping rows are held for a human check, as in the brief.
HOUSEKEEPING = {"Primary label source changed", "No longer returned"}
SOURCE = {"ctgov": "CT.gov", "openfda": "FDA", "canada": "Canada"}
news = None if changes is None else changes[~changes["change_type"].isin(HOUSEKEEPING)]
if news is not None and not news.empty:
    items = "".join(
        f"<span class='ci-item'><span class='ci-tag{' high' if r.importance == 'high' else ''}'>"
        f"{SOURCE.get(r.source, r.source)}</span><b>{html.escape(str(r.title).title())}</b> · "
        f"{html.escape(str(r.new) if str(r.new) not in ('', 'nan') else str(r.change_type))}"
        f" · {html.escape(str(r.molecules))}</span>"
        for r in news.itertuples())
    items *= max(1, 8 // len(news))  # enough copies to fill the rail
    st.html(f"<div class='ci-ticker'><div class='ci-live'><span class='ci-dot'></span>This week</div>"
            f"<div class='ci-track'><div class='ci-rail'>{items}{items}</div></div></div>")

# ---- bento grid ----
st.html("<div class='ci-head'><h2>Three questions.<br><span class='ci-grad'>One place to answer them.</span></h2>"
        "<p>Every tile opens the detail behind it.</p></div>")

top = cp.iloc[0]
duo = share["share_pct"].head(2).sum()
BAR = ["#2f7bff", "#7b5cff", "#e04fa0", "#ff8a3d", "#00b894"]
bars = "".join(
    f"<div class='ci-bar'><span>{html.escape(r.sponsor.replace(' and Company', '').replace(' A/S', ''))}</span>"
    f"<div class='track'><div class='fill' style='width:{r.share_pct / share['share_pct'].max() * 100:.0f}%;"
    f"--c:{BAR[i]};--d:{.2 + .1 * i}s'></div></div><span class='v'>{r.share_pct:.0f}%</span></div>"
    for i, r in enumerate(share.head(5).itertuples()))
heads = C.brief_headlines(C.brief(), n=3)
brief_list = ("<ul>" + "".join(f"<li>{html.escape(h)}</li>" for h in heads) + "</ul>") if heads \
    else "<p class='t'>No brief yet this week.</p>"
SEG = ["#2f7bff", "#7b5cff", "#00b894", "#ff8a3d", "#e04fa0", "#9c9c9c", "#c7c7cc"]
plan = sorted(m["plan_by_segment"].items(), key=lambda kv: -kv[1])
total = sum(v for _, v in plan)
stack = "".join(f"<div title='{html.escape(k)}: {v:,}' style='width:{100 * v / total:.1f}%;background:{SEG[i]};"
                f"--d:{.15 * i}s'></div>" for i, (k, v) in enumerate(plan))
legend = "".join(f"<span style='--c:{SEG[i]}'>{html.escape(k)} <b>{v:,}</b></span>" for i, (k, v) in enumerate(plan))

st.html(f"""<div class='ci-bento'>
  <div class='ci-tile wide'>
    <div class='k'>The pipeline</div>
    <h3>Lilly and Novo Nordisk run <span class='ci-grad'>{duo:.0f}%</span> of late-stage trials.</h3>
    <p class='t'>Share of active Phase 2/3 and Phase 3 trials by lead sponsor. The most crowded class is
      <b>{html.escape(str(top['class']))}</b>, with {int(top['total'])} active trials.</p>
    <div class='ci-bars'>{bars}</div>
    <a class='go' href='landscape' target='_self'>Open the landscape</a>
  </div>
  <div class='ci-tile dark tall'>
    <div class='k'>Who to call</div>
    <div class='big ci-grad'>{C.count(f"{m['in_call_plan']:,}", .5)}</div>
    <h3>prescribers in the launch call plan.</h3>
    <p class='t'>Led by doctors already writing GLP-1s, then the biggest pill-first and insulin prescribers.</p>
    <div class='ci-bars stacked'>
      <div class='ci-bar'><span>Already prescribe in the class</span><div class='track'><div class='fill' style='width:{fit}%;--c:linear-gradient(90deg,#2f7bff,#b04cff)'></div></div><span class='v'>{fit}%</span></div>
      <div class='ci-bar'><span>Volume-only list, same size</span><div class='track'><div class='fill' style='width:{base_fit}%;--c:#48484a;--d:.4s'></div></div><span class='v'>{base_fit}%</span></div>
      <div class='ci-bar'><span>GLP-1 claims reached</span><div class='track'><div class='fill' style='width:{reach}%;--c:linear-gradient(90deg,#2f7bff,#b04cff);--d:.6s'></div></div><span class='v'>{reach}%</span></div>
      <div class='ci-bar'><span>Volume-only list, same size</span><div class='track'><div class='fill' style='width:{base_reach}%;--c:#48484a;--d:.8s'></div></div><span class='v'>{base_reach}%</span></div>
    </div>
    <div class='delta'>+{fit - base_fit:.1f} pts <span>more names already prescribing in the class than a list built on volume alone.</span></div>
    <a class='go' href='segments' target='_self'>See who to target and why</a>
  </div>
  <div class='ci-tile'>
    <div class='k'><span class='ci-dot' style='display:inline-block;margin-right:.5rem'></span>What changed</div>
    <h3>This week, in one page.</h3>
    {brief_list}
    <a class='go' href='changes' target='_self'>Read the brief</a>
  </div>
  <div class='ci-tile'>
    <div class='k'>Readouts</div>
    <div class='big ci-grad'>{C.count(str(len(up)), .6)}</div>
    <p class='t'>trials expected to read out in the next 18 months, on a timeline you can filter by class and sponsor.</p>
    <a class='go' href='landscape' target='_self'>See the timeline</a>
  </div>
  <div class='ci-tile full'>
    <div class='k'>The call plan, by segment</div>
    <h3>{m['in_call_plan']:,} names, six behaviour-based segments.</h3>
    <div class='ci-stack'>{stack}</div>
    <div class='ci-legend'>{legend}</div>
    <a class='go' href='call_list' target='_self'>Open the call list</a>
  </div>
</div>""")

st.html("<div class='ci-sources'><span>ClinicalTrials.gov</span><span>openFDA</span><span>Health Canada</span>"
        "<span>Ontario Drug Benefit</span><span>CMS Medicare Part D</span></div>")
