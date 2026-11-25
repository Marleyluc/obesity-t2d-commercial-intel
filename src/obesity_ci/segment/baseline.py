"""Rules-based baseline segmentation (M4, chunk 3): value tier x GLP-1 adoption tier.

This is how most pharma brand teams segment prescribers, so it's the bar the clustering
(chunk 4) has to beat: if k-means tells us nothing this grid doesn't, we use the grid.

  value tier      from volume decile among eligible prescribers (in-scope claims)
                  High = deciles 8-10, Medium = 5-7, Low = 1-4
  adoption tier   incretin share of the prescriber's claims (GLP-1, oral GLP-1, GIP/GLP-1)
                  High >= 25%, Moderate 10-25%, Low < 10%  (close to the tertiles: 10.3% and 24.0%)

Priority for the orforglipron launch (an oral incretin):
  A  first-wave rep calls     High value with Moderate or High adoption: big, and already
                              comfortable with the class, so the fastest to try a new option
  B  second wave              High value, Low adoption (big, but a class-conversion sell);
                              Medium value with Moderate or High adoption
  C  non-personal channels    everyone else profiled (email, digital, speaker programmes)
  -  not profiled             fewer than MIN_CLAIMS in-scope claims
"""

from __future__ import annotations

import pandas as pd

from obesity_ci import config

VALUE_TIERS = [("Low", 1, 4), ("Medium", 5, 7), ("High", 8, 10)]
ADOPTION_CUTS = [0.10, 0.25]
ADOPTION_TIERS = ["Low", "Moderate", "High"]
PRIORITY = {
    ("High", "High"): "A", ("High", "Moderate"): "A",
    ("High", "Low"): "B", ("Medium", "High"): "B", ("Medium", "Moderate"): "B",
}


def value_tier(decile) -> str | None:
    if pd.isna(decile):
        return None
    return next(name for name, lo, hi in VALUE_TIERS if lo <= decile <= hi)


def adoption_tier(share: float) -> str:
    lo, hi = ADOPTION_CUTS
    return "Low" if share < lo else "Moderate" if share < hi else "High"


def assign(prescribers: pd.DataFrame) -> pd.DataFrame:
    f = prescribers.copy()
    elig = f["eligible"]
    f["value_tier"] = f["volume_decile"].map(value_tier).astype(object)
    f["adoption_tier"] = None
    f.loc[elig, "adoption_tier"] = f.loc[elig, "incretin_share"].map(adoption_tier)
    f["baseline_segment"] = "Low volume (not profiled)"
    f.loc[elig, "baseline_segment"] = (f.loc[elig, "value_tier"] + " value / "
                                       + f.loc[elig, "adoption_tier"] + " adoption")
    f["priority"] = "-"
    f.loc[elig, "priority"] = [PRIORITY.get((v, a), "C") for v, a in
                               zip(f.loc[elig, "value_tier"], f.loc[elig, "adoption_tier"])]
    return f


def profile(seg: pd.DataFrame, by: str) -> pd.DataFrame:
    """One row per segment: size, share of value, and what they prescribe."""
    tot, inc = seg["total_claims"].sum(), seg["incretin_claims"].sum()
    g = seg.groupby(by)
    out = pd.DataFrame({
        "prescribers": g.size(),
        "pct_of_claims": 100 * g["total_claims"].sum() / tot,
        "pct_of_incretin_claims": 100 * g["incretin_claims"].sum() / inc,
        "median_claims": g["total_claims"].median(),
        "incretin_share": 100 * g["incretin_share"].mean(),
        "sglt2_share": 100 * g["share_sglt2"].mean(),
        "legacy_oral_share": 100 * g["share_legacy_oral"].mean(),
        "pct_writing_rybelsus": 100 * g["writes_oral_glp1"].mean(),
        "lilly_of_incretin": 100 * g["lilly_of_incretin"].mean(),
        "pct_endocrinology": 100 * g["specialty_group"].apply(lambda s: (s == "Endocrinology").mean()),
        "pct_primary_care_or_np_pa": 100 * g["specialty_group"].apply(
            lambda s: s.isin(["Primary care physician", "NP / PA"]).mean()),
    })
    return out.round(1)


def run(snapshot: str | None = None) -> dict:
    from obesity_ci.transform import prescribers

    p = prescribers.run(snapshot)
    seg = assign(p["prescribers"])
    out = config.path("processed") / "segments" / p["snapshot"]
    out.mkdir(parents=True, exist_ok=True)
    seg[["npi", "specialty_group", "region", "eligible", "volume_decile", "value_tier", "adoption_tier",
         "baseline_segment", "priority"]].to_parquet(out / "baseline.parquet", index=False)
    by_seg, by_pri = profile(seg, "baseline_segment"), profile(seg, "priority")
    by_seg.to_csv(out / "baseline_profile.csv")
    return {"snapshot": p["snapshot"], "data_year": p["data_year"], "out": out, "segments": seg,
            "by_segment": by_seg, "by_priority": by_pri}
