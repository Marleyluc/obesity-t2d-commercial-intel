"""Export the small set of files the dashboard reads (M6, chunk 1).

Why a separate export: data/processed/ is git-ignored (large, rebuilt from the pullers), but the
deployed app is built from GitHub. So the app reads only app/data/, which is small, committed,
and refreshed by running scripts/build_app_data.py after the pipeline.

What goes in app/data/:
  meta.json                  dates, data year, headline numbers, call capacity
  landscape_class_phase.parquet / landscape_sponsor_share.parquet /
  landscape_upcoming.parquet / landscape_assets.parquet     (M3 views, class ids -> labels)
  changes.parquet            the latest change log (M3)
  brief.md, brief.input.json the latest weekly brief and the rows it was written from (M5)
  segment_cards.parquet      one row per segment: size, fit, action (M4)
  cluster_profile.parquet    what each segment prescribes (M4)
  matrix.parquet             value tier x launch fit: prescribers and incretin claims (M4)
  by_state.parquet           per state: prescribers, call-plan names, tiers, claims (M4)
  call_list.parquet          every Tier 1-3 prescriber: NPI, specialty group, state, segment,
                             tier, claims, in call plan, action. No names (dropped since M4).

The app never calls an API or reads data/: page loads stay fast and work offline.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from obesity_ci import config
from obesity_ci.segment import targeting

OUT = config.ROOT / "app" / "data"
CALL_LIST_COLS = ["npi", "specialty_group", "state", "region", "cluster", "launch_fit", "value_tier",
                  "target_tier", "in_call_plan", "total_claims", "incretin_claims", "action"]
TIERS = ["High", "Medium", "Low"]


def latest(kind: str) -> Path:
    folders = sorted(p for p in (config.path("processed") / kind).iterdir() if p.is_dir())
    if not folders:
        raise RuntimeError(f"No {kind} output in data/processed/{kind}. Run the M3/M4 build scripts first.")
    return folders[-1]


# ---------- pure functions (tested offline) ----------

def class_labels(mols: pd.DataFrame) -> dict[str, str]:
    return dict(zip(mols["class_id"], mols["class_label"]))


def label_classes(df: pd.DataFrame, col: str, labels: dict[str, str]) -> pd.DataFrame:
    out = df.copy()
    out[col] = out[col].fillna("").map(
        lambda s: "; ".join(labels.get(c.strip(), c.strip()) for c in str(s).split(";") if c.strip()))
    return out


def matrix(t: pd.DataFrame) -> pd.DataFrame:
    """Long form: one row per (value tier, launch fit), eligible prescribers only."""
    e = t[t["eligible"]]
    m = (e.groupby(["value_tier", "launch_fit"])
         .agg(prescribers=("npi", "size"), incretin_claims=("incretin_claims", "sum"),
              in_call_plan=("in_call_plan", "sum"), target_tier=("target_tier", "min"))
         .reindex(pd.MultiIndex.from_product([TIERS, TIERS], names=["value_tier", "launch_fit"]))
         .fillna(0).astype(int).reset_index())
    m["pct_of_incretin_claims"] = (100 * m["incretin_claims"] / t["incretin_claims"].sum()).round(1)
    return m


def by_state(t: pd.DataFrame) -> pd.DataFrame:
    g = t.groupby("state")
    out = pd.DataFrame({
        "region": g["region"].first(),
        "prescribers": g.size(),
        "eligible": g["eligible"].sum(),
        "in_call_plan": g["in_call_plan"].sum(),
        "tier_1": g["target_tier"].apply(lambda s: int((s == 1).sum())),
        "tier_2": g["target_tier"].apply(lambda s: int((s == 2).sum())),
        "total_claims": g["total_claims"].sum(),
        "incretin_claims": g["incretin_claims"].sum(),
    })
    plan_inc = t[t["in_call_plan"]].groupby("state")["incretin_claims"].sum()
    out["pct_incretin_in_plan"] = (100 * plan_inc.reindex(out.index, fill_value=0)
                                   / out["incretin_claims"].replace(0, pd.NA)).astype(float).round(1)
    return out.reset_index().sort_values("in_call_plan", ascending=False)


def call_list(t: pd.DataFrame) -> pd.DataFrame:
    c = t[t["eligible"] & (t["target_tier"] <= 3)][CALL_LIST_COLS]
    return c.sort_values(["in_call_plan", "target_tier", "incretin_claims"], ascending=[False, True, False])


def headline(t: pd.DataFrame) -> dict:
    cmp = targeting.compare_with_baseline(t)
    plan = t[t["in_call_plan"]]
    top = plan["cluster"].value_counts()
    return {
        "call_capacity": targeting.CALL_CAPACITY,
        "prescribers": int(len(t)),
        "eligible": int(t["eligible"].sum()),
        "in_call_plan": int(len(plan)),
        "plan_pct_incretin_claims": round(cmp["cluster_reach"], 1),
        "baseline_pct_incretin_claims": round(cmp["baseline_reach"], 1),
        "plan_pct_high_fit": round(cmp["high_fit_pct"]["cluster plan"], 1),
        "baseline_pct_high_fit": round(cmp["high_fit_pct"]["baseline plan"], 1),
        "overlap_with_baseline": cmp["overlap"],
        "plan_by_segment": {k: int(v) for k, v in top.items()},
    }


# ---------- I/O ----------

def _part_d_year(snapshot: str):
    m = config.path("raw") / "cms_partd" / snapshot / "manifest.json"
    return json.loads(m.read_text()).get("data_year") if m.exists() else None


def _latest_brief() -> tuple[Path | None, Path | None]:
    folder = config.ROOT / "briefs"
    briefs = sorted(p for p in folder.glob("*.md") if not p.name.endswith((".rejected.md", ".draft.md")))
    if not briefs:
        return None, None
    b = briefs[-1]
    inp = b.with_name(b.name.replace(".md", ".input.json"))
    return b, inp if inp.exists() else None


def run(out: Path = OUT) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    labels = class_labels(config.molecules())
    written = {}

    def save(df: pd.DataFrame, name: str):
        df.to_parquet(out / name, index=False)
        written[name] = len(df)

    land = latest("landscape")
    save(pd.read_parquet(land / "class_phase.parquet").rename_axis("class").reset_index(), "landscape_class_phase.parquet")
    save(pd.read_parquet(land / "sponsor_share.parquet").rename_axis("sponsor").reset_index(), "landscape_sponsor_share.parquet")
    save(label_classes(pd.read_parquet(land / "upcoming.parquet"), "classes", labels), "landscape_upcoming.parquet")
    assets = pd.read_parquet(land / "assets.parquet")
    assets.insert(2, "class", assets["class_id"].map(labels).fillna(assets["class_id"]))
    save(assets, "landscape_assets.parquet")

    logs = sorted((config.path("processed") / "changes").glob("changes_*.parquet"))
    if logs:
        save(pd.read_parquet(logs[-1]), "changes.parquet")
    brief, brief_input = _latest_brief()
    if brief:
        shutil.copyfile(brief, out / "brief.md")
        written["brief.md"] = brief.name
    if brief_input:
        shutil.copyfile(brief_input, out / "brief.input.json")

    seg = latest("segments")
    t = pd.read_parquet(seg / "targeting.parquet")
    save(pd.read_csv(seg / "segment_cards.csv"), "segment_cards.parquet")
    save(pd.read_csv(seg / "cluster_profile.csv"), "cluster_profile.parquet")
    save(matrix(t), "matrix.parquet")
    save(by_state(t), "by_state.parquet")
    save(call_list(t), "call_list.parquet")

    meta = {
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "landscape_snapshot": land.name,
        "change_log": logs[-1].stem.replace("changes_", "") if logs else None,
        "brief": brief.stem if brief else None,
        "part_d_snapshot": seg.name,
        "part_d_data_year": _part_d_year(seg.name),
        "anchor_brand": "orforglipron",
        **headline(t),
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2))
    size_mb = sum(p.stat().st_size for p in out.iterdir() if p.is_file()) / 1e6
    return {"out": out, "written": written, "meta": meta, "size_mb": size_mb}
