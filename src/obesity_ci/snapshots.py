"""Dated raw snapshots: data/raw/<source>/<YYYY-MM-DD>/

Raw files are saved exactly as the API returned them and never overwritten.
Each snapshot folder gets a manifest.json describing what was pulled, when and how,
so any number in the dashboard can be traced back to its source pull.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

from obesity_ci import config


def snapshot_dir(source: str, snapshot_date: date | None = None) -> Path:
    d = config.path("raw") / source / (snapshot_date or date.today()).isoformat()
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def write_manifest(folder: Path, source: str, entries: list[dict], extra: dict | None = None) -> Path:
    manifest = {
        "source": source,
        "pulled_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "files": entries,
        **(extra or {}),
    }
    path = folder / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


def list_snapshots(source: str) -> list[Path]:
    """All snapshot folders for a source, oldest first. M3 diffs the last two."""
    root = config.path("raw") / source
    return sorted(p for p in root.iterdir() if p.is_dir()) if root.exists() else []
