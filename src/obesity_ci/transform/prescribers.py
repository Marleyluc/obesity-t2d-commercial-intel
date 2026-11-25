"""One row per prescriber: the features the segmentation uses (M4, chunk 2).

Input: data/interim/cms_partd/<snapshot>/claims.parquet (chunk 1).
Output: data/interim/cms_partd/<snapshot>/prescribers.parquet

Feature groups (see docs/M4_DECISIONS.md):
  value        total_claims, total_cost, incretin_claims   (how much relevant prescribing)
  mix          share_<group> of in-scope claims             (what they prescribe; sums to 1)
  adoption     newer_share, incretin_share                  (how far they've moved to newer agents)
  launch fit   oral_glp1_of_incretin, lilly_of_incretin     (analogues for an oral GLP-1 from Lilly)
  context      specialty_group, region, state

Shares are only meaningful with enough claims, so `eligible` marks prescribers with at least
MIN_CLAIMS in-scope claims; the rest are kept (they become the "low volume" group) but are
not clustered.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from obesity_ci import config

MIN_CLAIMS = 50

# Our classes, grouped into the mix features a brand team would talk about.
MIX_GROUPS = {
    "legacy_oral": ["legacy_oral_t2d"],
    "dpp4": ["dpp4"],
    "sglt2": ["sglt2"],
    "glp1_injectable": ["glp1_injectable"],
    "glp1_oral": ["glp1_oral"],
    "gip_glp1": ["gip_glp1"],
    "insulin": ["insulin_basal", "insulin_prandial", "insulin_glp1_frc"],
    "other": ["amylin", "legacy_aom", "emerging_other", "glp1_gipr_antagonist", "glucagon_combos"],
}
INCRETIN = ["glp1_injectable", "glp1_oral", "gip_glp1", "insulin_glp1_frc"]
LILLY = "Eli Lilly"  # matched inside the sponsor string in drug_classes.yaml

SPECIALTY_GROUPS = {
    "Primary care physician": ["Family Practice", "Family Medicine", "Internal Medicine", "General Practice",
                               "Geriatric Medicine", "Osteopathic Manipulative Medicine", "Preventive Medicine"],
    "NP / PA": ["Nurse Practitioner", "Physician Assistant", "Certified Clinical Nurse Specialist"],
    "Endocrinology": ["Endocrinology"],
    "Cardiology": ["Cardiology", "Interventional Cardiology", "Advanced Heart Failure and Transplant Cardiology",
                   "Clinical Cardiac Electrophysiology"],
    "Nephrology": ["Nephrology"],
}
# US Census regions; everything else (territories, military 'AE'/'AP', unknown 'XX'/'ZZ') = "Other / unknown".
REGIONS = {
    "Northeast": "CT ME MA NH RI VT NJ NY PA",
    "Midwest": "IL IN MI OH WI IA KS MN MO NE ND SD",
    "South": "DE DC FL GA MD NC SC VA WV AL KY MS TN AR LA OK TX",
    "West": "AZ CO ID MT NV NM UT WY AK CA HI OR WA",
}


def specialty_group(s: str) -> str:
    return next((g for g, members in SPECIALTY_GROUPS.items() if s in members), "Other specialty")


def region(state: str) -> str:
    return next((r for r, states in REGIONS.items() if state in states.split()), "Other / unknown")


def build(claims: pd.DataFrame, min_claims: int = MIN_CLAIMS) -> pd.DataFrame:
    c = claims.copy()
    group_of = {cls: g for g, classes in MIX_GROUPS.items() for cls in classes}
    c["mix_group"] = c["class_id"].map(group_of)
    if c["mix_group"].isna().any():
        raise ValueError(f"Classes missing from MIX_GROUPS: {sorted(c.loc[c['mix_group'].isna(), 'class_id'].unique())}")
    c["is_incretin"] = c["class_id"].isin(INCRETIN)
    c["is_newer"] = c["generation"] == "newer"
    c["is_oral_glp1"] = c["class_id"] == "glp1_oral"
    c["is_lilly_incretin"] = c["is_incretin"] & c["sponsor"].fillna("").str.contains(LILLY, regex=False)

    g = c.groupby("npi")
    out = pd.DataFrame({
        "specialty": g["specialty"].first(),
        "state": g["state"].first(),
        "total_claims": g["claims"].sum(),
        "total_cost": g["drug_cost"].sum(),
        "n_molecules": g["generic"].nunique(),
        # Beneficiaries can't be summed across drugs (one patient can be on several);
        # the largest single-drug count is a floor on the prescriber's diabetes patients.
        "max_drug_beneficiaries": g["beneficiaries"].max(),
    })
    mix = c.pivot_table(index="npi", columns="mix_group", values="claims", aggfunc="sum", fill_value=0)
    mix = mix.reindex(columns=list(MIX_GROUPS), fill_value=0)
    for grp in MIX_GROUPS:
        out[f"share_{grp}"] = mix[grp] / out["total_claims"]

    def claims_where(flag):
        return c[c[flag]].groupby("npi")["claims"].sum().reindex(out.index, fill_value=0)

    out["incretin_claims"] = claims_where("is_incretin")
    out["newer_share"] = claims_where("is_newer") / out["total_claims"]
    out["incretin_share"] = out["incretin_claims"] / out["total_claims"]
    inc = out["incretin_claims"].replace(0, np.nan)  # undefined (blank) for non-users, not 0
    out["oral_glp1_of_incretin"] = claims_where("is_oral_glp1") / inc
    out["lilly_of_incretin"] = claims_where("is_lilly_incretin") / inc
    out["writes_incretin"] = out["incretin_claims"] > 0
    out["writes_oral_glp1"] = claims_where("is_oral_glp1") > 0

    out["specialty_group"] = out["specialty"].map(specialty_group)
    out["region"] = out["state"].map(region)
    out["eligible"] = out["total_claims"] >= min_claims
    # Value deciles among eligible prescribers (10 = top 10% by in-scope claims).
    elig = out["eligible"]
    out["volume_decile"] = pd.Series(pd.NA, index=out.index, dtype="Int64")
    out.loc[elig, "volume_decile"] = pd.qcut(out.loc[elig, "total_claims"].rank(method="first"), 10,
                                             labels=False).astype("Int64") + 1
    return out.reset_index()


def run(snapshot: str | None = None) -> dict:
    from obesity_ci.transform import prescriptions

    p = prescriptions.run(snapshot)
    feats = build(p["claims"])
    feats.to_parquet(p["out"] / "prescribers.parquet", index=False)
    return {"snapshot": p["snapshot"], "data_year": p["data_year"], "out": p["out"], "prescribers": feats}
