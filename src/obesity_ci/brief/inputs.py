"""Turn a change log into the compact, structured input the brief model sees (M5, chunk 1).

The model sees ONLY this input: the changes, plus each molecule's class and sponsor from our own
config (so it can say "Lilly's oral GLP-1" without guessing). Nothing from the web, nothing from
memory. Every change carries its ID; the guardrail (chunk 3) checks that the brief cites no other ID.

What goes in (see docs/M5_DECISIONS.md):
- every high and medium change;
- low changes up to MAX_LOW, taken in turn from each change type, so no one type drowns the rest;
- never the pipeline's own housekeeping rows (REVIEW_ONLY): "Primary label source changed" and
  "No longer returned" need a human check first, so they are counted but not sent.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from obesity_ci import config

REVIEW_ONLY = {"Primary label source changed", "No longer returned"}
MAX_LOW = 20
MAX_ROWS = 80  # keeps the prompt small and the brief focused
FIELDS = ["id", "source", "change_type", "importance", "molecules", "classes", "sponsors", "title",
          "field", "old", "new", "detail"]
SOURCE_NAMES = {"ctgov": "ClinicalTrials.gov", "openfda": "FDA (Drugs@FDA and labels)",
                "canada": "Health Canada / Ontario Drug Benefit"}


def latest_log(date: str | None = None) -> Path:
    folder = config.path("processed") / "changes"
    files = sorted(folder.glob("changes_*.parquet"))
    if date:
        files = [f for f in files if f.stem == f"changes_{date}"]
    if not files:
        raise RuntimeError(f"No change log{' for ' + date if date else ''} in {folder}. "
                           "Run scripts/build_changes.py after a second pull.")
    return files[-1]


NOT_A_SPONSOR = {"generic", "various", ""}  # placeholders in drug_classes.yaml


def _context(mols: pd.DataFrame) -> dict[str, tuple[str, str]]:
    return {g: (c, "" if str(s).strip().lower() in NOT_A_SPONSOR else str(s))
            for g, c, s in zip(mols["generic"], mols["class_label"], mols["sponsor"])}


def select(log: pd.DataFrame, max_low: int = MAX_LOW, max_rows: int = MAX_ROWS) -> tuple[pd.DataFrame, dict]:
    """Rows to send, plus counts of what was left out and why."""
    review = log[log["change_type"].isin(REVIEW_ONLY)]
    rest = log[~log["change_type"].isin(REVIEW_ONLY)]
    order = {"high": 0, "medium": 1, "low": 2}
    rest = rest.assign(_o=rest["importance"].map(order)).sort_values(["_o", "source", "change_type", "id"])
    hi_med = rest[rest["_o"] < 2]
    # Low rows are taken in turn from each change type, so 30 routine date moves can't crowd
    # out the one FDA labeling action.
    low = rest[rest["_o"] == 2]
    low = (low.assign(_turn=low.groupby("change_type").cumcount())
           .sort_values(["_turn", "source", "change_type", "id"]).head(max_low).drop(columns="_turn"))
    chosen = pd.concat([hi_med, low]).head(max_rows).drop(columns="_o")
    omitted = {
        "needs_human_review": review["change_type"].value_counts().to_dict(),
        "low_importance_not_sent": int((rest["_o"] == 2).sum() - len(low)),
        "over_row_limit": int(len(hi_med) + len(low) - len(chosen)),
    }
    return chosen.reset_index(drop=True), omitted


def build(log: pd.DataFrame, mols: pd.DataFrame | None = None) -> dict:
    mols = config.molecules() if mols is None else mols
    ctx = _context(mols)
    chosen, omitted = select(log)
    rows = []
    for r in chosen.to_dict("records"):
        names = [m.strip() for m in str(r.get("molecules") or "").split(";") if m.strip()]
        r["classes"] = "; ".join(sorted({ctx[m][0] for m in names if m in ctx}))
        r["sponsors"] = "; ".join(sorted({ctx[m][1] for m in names if m in ctx} - {""}))
        r["source"] = SOURCE_NAMES.get(r["source"], r["source"])
        rows.append({k: ("" if pd.isna(r.get(k)) else str(r.get(k))) for k in FIELDS})
    return {
        "period": {"from": str(log["old_snapshot"].min()), "to": str(log["new_snapshot"].max())},
        "counts": {
            "all_changes": int(len(log)),
            "sent": len(rows),
            "by_importance_sent": pd.Series([r["importance"] for r in rows]).value_counts().to_dict() if rows else {},
        },
        "omitted": omitted,
        "changes": rows,
    }


def allowed_ids(brief_input: dict) -> set[str]:
    return {c["id"] for c in brief_input["changes"]}


def run(date: str | None = None) -> dict:
    path = latest_log(date)
    data = build(pd.read_parquet(path))
    out = config.ROOT / "briefs"
    out.mkdir(exist_ok=True)
    target = out / f"{data['period']['to']}.input.json"
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"log": path, "out": target, "input": data}
