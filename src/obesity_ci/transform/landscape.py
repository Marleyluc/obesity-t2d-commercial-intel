"""Landscape views (M3, chunk 5): the tables the dashboard's Landscape page reads.

class_phase      active pipeline trials per class x phase
sponsor_share    who runs the active late-stage (Phase 2/3 and 3) trials
upcoming         active trials whose primary completion (readout proxy) falls in the next 18 months
assets           one row per tracked newer molecule: highest active phase, late-stage trial count,
                 next readout, US approval, Canada status, Ontario coverage

"Pipeline" here means (see docs/M3_DECISIONS.md):
- interventional, Phase 1 to Phase 3 (Phase 4 = already approved, so not pipeline);
- active: not yet recruiting, recruiting, enrolling by invitation, or active not recruiting;
- industry-sponsored, so it reflects company development decisions, not investigator studies.
"""

from __future__ import annotations

import pandas as pd

ACTIVE = {"NOT_YET_RECRUITING", "RECRUITING", "ENROLLING_BY_INVITATION", "ACTIVE_NOT_RECRUITING"}
PHASES = ["Phase 1", "Phase 1/2", "Phase 2", "Phase 2/3", "Phase 3"]
UPCOMING_MONTHS = 18


def pipeline_trials(trials: pd.DataFrame, links: pd.DataFrame) -> pd.DataFrame:
    """One row per (active industry pipeline trial, molecule), with trial fields attached."""
    t = trials[(trials["study_type"] == "INTERVENTIONAL") & trials["status"].isin(ACTIVE)
               & trials["phase"].isin(PHASES) & (trials["sponsor_class"] == "INDUSTRY")]
    return links.merge(t, on="nct_id")


def class_phase(pipe: pd.DataFrame, labels: dict[str, str]) -> pd.DataFrame:
    counts = (pipe.drop_duplicates(["nct_id", "class_id"])
              .pivot_table(index="class_id", columns="phase", values="nct_id", aggfunc="count", fill_value=0)
              .reindex(columns=PHASES, fill_value=0))
    counts["total"] = counts.sum(axis=1)
    counts.index = [labels.get(c, c) for c in counts.index]
    return counts.sort_values("total", ascending=False)


def sponsor_share(pipe: pd.DataFrame, top: int = 10) -> pd.DataFrame:
    late = pipe[pipe["phase_rank"] >= 2.5].drop_duplicates("nct_id")
    s = late["lead_sponsor"].value_counts()
    out = pd.DataFrame({"late_stage_trials": s, "share_pct": (100 * s / s.sum()).round(1)})
    if len(out) > top:
        rest = out.iloc[top:].sum()
        out = pd.concat([out.iloc[:top], pd.DataFrame([rest], index=["(all others)"])])
    return out


def upcoming(pipe: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    end = as_of + pd.DateOffset(months=UPCOMING_MONTHS)
    u = pipe[(pipe["phase_rank"] >= 2) & pipe["primary_completion_date"].between(as_of, end)]
    u = (u.groupby("nct_id", as_index=False)
         .agg(primary_completion_date=("primary_completion_date", "first"), molecules=("generic", "; ".join),
              classes=("class_id", lambda c: "; ".join(sorted(set(c)))), lead_sponsor=("lead_sponsor", "first"),
              acronym=("acronym", "first"), phase=("phase", "first"), status=("status", "first"),
              enrollment=("enrollment", "first"), title=("title", "first")))
    return u.sort_values("primary_completion_date").reset_index(drop=True)


def assets(mols: pd.DataFrame, pipe: pd.DataFrame, canada_mols: pd.DataFrame | None,
           fda_apps: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    tracked = mols[(mols["generation"] == "newer") & mols["track_trials"]]
    branded = fda_apps[fda_apps["app_type"] != "ANDA"]
    ca = canada_mols.set_index("generic") if canada_mols is not None else pd.DataFrame()
    rows = []
    for _, m in tracked.iterrows():
        g = m["generic"]
        p = pipe[pipe["generic"] == g]
        late = p[p["phase_rank"] >= 2.5]
        future = p[(p["phase_rank"] >= 2) & (p["primary_completion_date"] >= as_of)]
        us = branded[branded["molecules"] == g]["first_approval_date"].min()
        rows.append({
            "generic": g, "class_id": m["class_id"], "sponsor": m["sponsor"],
            "highest_active_phase": p.sort_values("phase_rank")["phase"].iloc[-1] if len(p) else "None active",
            "active_trials": p["nct_id"].nunique(),
            "active_late_stage": late["nct_id"].nunique(),
            "next_readout": future["primary_completion_date"].min(),
            "us_first_approval": us,
            "ca_status": ca.loc[g, "ca_status"] if g in ca.index else None,
            "ontario_coverage": ca.loc[g, "ontario_coverage"] if g in ca.index else None,
        })
    order = {p: i for i, p in enumerate(["None active", *PHASES])}
    df = pd.DataFrame(rows)
    return df.assign(_o=df["highest_active_phase"].map(order)).sort_values(
        ["_o", "active_late_stage"], ascending=False).drop(columns="_o").reset_index(drop=True)


def late_stage_trials(trials: pd.DataFrame, links: pd.DataFrame, generic: str) -> pd.DataFrame:
    """All Phase 2/3+ trials for one molecule, any status or sponsor: for the hand check."""
    j = links[links["generic"] == generic].merge(trials, on="nct_id")
    j = j[j["phase_rank"] >= 2.5]
    return j[["nct_id", "acronym", "phase", "status", "lead_sponsor", "primary_completion_date",
              "enrollment"]].sort_values("primary_completion_date").reset_index(drop=True)


def run(snapshot: str | None = None) -> dict:
    from obesity_ci import config
    from obesity_ci.transform import approvals, canada, trials

    t = trials.run(snapshot)
    a = approvals.run()
    canada_error = None
    try:
        c = canada.run()["canada_molecules"]
    except RuntimeError as e:
        # Canada pulls missing: the Canada columns stay empty, and we say why (never silently).
        c, canada_error = None, str(e)
    mols = config.molecules()
    labels = dict(zip(mols["class_id"], mols["class_label"]))
    as_of = pd.Timestamp(t["snapshot"])
    pipe = pipeline_trials(t["trials"], t["trial_molecules"])
    views = {
        "class_phase": class_phase(pipe, labels),
        "sponsor_share": sponsor_share(pipe),
        "upcoming": upcoming(pipe, as_of),
        "assets": assets(mols, pipe, c, a["fda_applications"], as_of),
    }
    out = config.path("processed") / "landscape" / t["snapshot"]
    out.mkdir(parents=True, exist_ok=True)
    for name, df in views.items():
        df.to_parquet(out / f"{name}.parquet")
    return {"snapshot": t["snapshot"], "out": out, "canada_error": canada_error, "trials": t["trials"], "links": t["trial_molecules"], **views}
