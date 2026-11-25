"""Targeting recommendation for the orforglipron launch (M4, chunk 5).

Combines the two views built earlier:
  value        how much a prescriber writes (volume decile -> High / Medium / Low, chunk 3)
  launch fit   how close their prescribing style is to an oral incretin (cluster, chunk 4)

into a targeting matrix and four tiers, then fills a call plan up to what a field force
can actually reach (CALL_CAPACITY). Each segment gets a card: name, one-line description,
size, and the recommended action and message.

The launch-fit rating per cluster is a judgement, written down here so it can be argued with:
  High    already in the class: oral GLP-1 users, Lilly-led (tirzepatide) and injectable
          GLP-1 adopters. A new oral option is an easy addition.
  Medium  pill-first prescribers not yet using incretins much (generic-first, DPP-4 loyal):
          the oral form is the hook, but it's a class-conversion sell. Insulin-intensive:
          in the class sometimes, but injection-comfortable, so the oral advantage matters less.
  Low     SGLT2 cardiorenal: heart and kidney specialists, a different conversation.
"""

from __future__ import annotations

import pandas as pd

from obesity_ci import config
from obesity_ci.segment.clusters import LOW_VOLUME

# Assumption, not data: ~300 reps x ~150 targets each. Change it to test other sizes.
CALL_CAPACITY = 45_000

LAUNCH_FIT = {
    "Oral GLP-1 users (Rybelsus)": "High",
    "Tirzepatide-led (Mounjaro)": "High",
    "Injectable GLP-1 adopters (Ozempic / Trulicity)": "High",
    "DPP-4 loyal": "Medium",
    "Generic-first (metformin / sulfonylurea)": "Medium",
    "Insulin-intensive": "Medium",
    "SGLT2 cardiorenal": "Low",
}
TIERS = {  # (value tier, launch fit) -> tier
    ("High", "High"): 1,
    ("High", "Medium"): 2, ("Medium", "High"): 2,
    ("Medium", "Medium"): 3, ("Low", "High"): 3,
}
TIER_ACTION = {
    1: "Rep calls from launch, high frequency; peer-to-peer and speaker programmes",
    2: "Rep calls in the first 6 months as capacity allows; samples and patient-start support",
    3: "Remote / inside sales and targeted digital; promote to Tier 2 on early uptake",
    4: "Non-personal only (email, peer-reviewed content, formulary news)",
}
SEGMENT_CARDS = {
    "Oral GLP-1 users (Rybelsus)": (
        "Already prescribe an oral GLP-1; proven willingness to use a pill in the class.",
        "Lead target. Message: a once-daily oral GLP-1 without Rybelsus's fasting and water rules."),
    "Tirzepatide-led (Mounjaro)": (
        "Heaviest Mounjaro users; Lilly writes about two-thirds of their incretin scripts.",
        "Lead target via the existing Lilly relationship. Message: an oral Lilly option for patients "
        "who won't inject or need a step-down."),
    "Injectable GLP-1 adopters (Ozempic / Trulicity)": (
        "Mainstream GLP-1 users, mostly Ozempic and Trulicity; the largest share of class volume.",
        "Core target. Message: start earlier, as a pill, for needle-averse patients; conversion from "
        "Novo is the prize."),
    "DPP-4 loyal": (
        "Pill-first prescribers who use DPP-4s (Januvia-type) a lot more than average.",
        "Upgrade play. Message: same oral routine, much greater A1c and weight effect than a DPP-4."),
    "Generic-first (metformin / sulfonylurea)": (
        "Largest group: about 70% of their scripts are metformin and sulfonylureas.",
        "Volume play for later waves. Message: the first incretin can be a pill; needs access and cost support."),
    "Insulin-intensive": (
        "Complex patients on insulin; many endocrinologists; high volume.",
        "Selective. Message: GLP-1 add-on to reduce insulin needs; oral form is a secondary benefit."),
    "SGLT2 cardiorenal": (
        "Cardiologists and nephrologists who write almost only SGLT2s for heart and kidney protection.",
        "Deprioritise for the T2D launch; revisit with cardiovascular outcomes data (medical, not sales)."),
    LOW_VOLUME: (
        "Fewer than 50 diabetes scripts a year in Medicare.",
        "No personal promotion."),
}


def assign(seg: pd.DataFrame, capacity: int = CALL_CAPACITY) -> pd.DataFrame:
    f = seg.copy()
    unknown = set(f.loc[f["eligible"], "cluster"]) - set(LAUNCH_FIT)
    if unknown:
        raise ValueError(f"Clusters without a launch-fit rating: {sorted(unknown)}")
    f["launch_fit"] = f["cluster"].map(LAUNCH_FIT)
    f["target_tier"] = [TIERS.get((v, l), 4) if e else 4
                        for v, l, e in zip(f["value_tier"], f["launch_fit"], f["eligible"])]
    # Fill the call plan: best tier first, then most incretin claims, then most claims overall.
    order = f[f["eligible"] & (f["target_tier"] <= 3)].sort_values(
        ["target_tier", "incretin_claims", "total_claims"], ascending=[True, False, False])
    f["in_call_plan"] = f["npi"].isin(order["npi"].head(capacity))
    f["action"] = f["target_tier"].map(TIER_ACTION)
    return f


def matrix(t: pd.DataFrame, values: str = "npi", how: str = "count") -> pd.DataFrame:
    e = t[t["eligible"]]
    m = pd.pivot_table(e, index="value_tier", columns="launch_fit", values=values, aggfunc=how, fill_value=0)
    return m.reindex(index=["High", "Medium", "Low"], columns=["High", "Medium", "Low"], fill_value=0)


def cards(t: pd.DataFrame) -> pd.DataFrame:
    tot, inc = t["total_claims"].sum(), t["incretin_claims"].sum()
    g = t.groupby("cluster")
    out = pd.DataFrame({
        "launch_fit": g["launch_fit"].first(),
        "prescribers": g.size(),
        "pct_of_claims": (100 * g["total_claims"].sum() / tot).round(1),
        "pct_of_incretin_claims": (100 * g["incretin_claims"].sum() / inc).round(1),
        "in_call_plan": g["in_call_plan"].sum(),
        "tier_1": g["target_tier"].apply(lambda s: (s == 1).sum()),
        "tier_2": g["target_tier"].apply(lambda s: (s == 2).sum()),
    })
    out["description"] = [SEGMENT_CARDS[c][0] for c in out.index]
    out["recommended_action"] = [SEGMENT_CARDS[c][1] for c in out.index]
    return out.sort_values(["in_call_plan", "prescribers"], ascending=False)


def compare_with_baseline(t: pd.DataFrame, capacity: int = CALL_CAPACITY) -> dict:
    """Same capacity, filled from the baseline grid instead (priority A then B, by incretin claims)."""
    e = t[t["eligible"]]
    base = e[e["priority"].isin(["A", "B"])].sort_values(
        ["priority", "incretin_claims", "total_claims"], ascending=[True, False, False]).head(capacity)
    plan = e[e["in_call_plan"]]
    inc = t["incretin_claims"].sum()
    return {
        "baseline_reach": 100 * base["incretin_claims"].sum() / inc,
        "cluster_reach": 100 * plan["incretin_claims"].sum() / inc,
        "overlap": int(plan["npi"].isin(base["npi"]).sum()),
        "added": plan.loc[~plan["npi"].isin(base["npi"]), "cluster"].value_counts(),
        "dropped": base.loc[~base["npi"].isin(plan["npi"]), "cluster"].value_counts(),
        "high_fit_pct": {"cluster plan": 100 * (plan["launch_fit"] == "High").mean(),
                         "baseline plan": 100 * (base["launch_fit"] == "High").mean()},
    }


def run(snapshot: str | None = None) -> dict:
    from obesity_ci.segment import clusters

    c = clusters.run(snapshot)
    t = assign(c["segments"])
    out = c["out"]
    keep = ["npi", "specialty_group", "region", "state", "eligible", "total_claims", "incretin_claims",
            "volume_decile", "value_tier", "adoption_tier", "baseline_segment", "priority", "cluster",
            "launch_fit", "target_tier", "in_call_plan", "action"]
    t[keep].to_parquet(out / "targeting.parquet", index=False)
    seg_cards = cards(t)
    seg_cards.to_csv(out / "segment_cards.csv")
    return {**c, "targeting": t, "cards": seg_cards, "vs_baseline": compare_with_baseline(t),
            "matrix_prescribers": matrix(t), "matrix_incretin": matrix(t, "incretin_claims", "sum")}
