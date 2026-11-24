"""Load project settings, the drug class list, and secrets.

Everything else in the project imports from here, so there is exactly one place
that knows where files live and how secrets are read.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd
import yaml
from dotenv import load_dotenv

# Repo root = two levels above this file (src/obesity_ci/config.py -> repo/)
ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"

load_dotenv(ROOT / ".env")  # no-op if .env is missing; real env vars take precedence


@lru_cache
def settings() -> dict:
    """Non-secret settings from config/settings.yaml."""
    with open(CONFIG_DIR / "settings.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache
def drug_config() -> dict:
    """Raw drug class config from config/drug_classes.yaml."""
    with open(CONFIG_DIR / "drug_classes.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def molecules() -> pd.DataFrame:
    """One row per molecule, with its class attributes attached.

    This flat table is what the pullers iterate over and what M2 maps to
    ClinicalTrials.gov, openFDA and CMS Part D names.
    """
    rows = []
    for class_id, c in drug_config()["classes"].items():
        for m in c["molecules"]:
            rows.append(
                {
                    "class_id": class_id,
                    "class_label": c["label"],
                    "area": c["area"],
                    "generation": c["generation"],
                    "generic": m["generic"].lower(),
                    "brands": m.get("brands", []),
                    "route": m["route"],
                    "sponsor": m["sponsor"],
                    "aliases": m.get("aliases", []),
                    "is_pipeline": len(m.get("brands", [])) == 0,
                    "track_trials": m.get("track_trials", c.get("track_trials", True)),
                }
            )
    return pd.DataFrame(rows)


def path(key: str) -> Path:
    """Absolute path for a key under `paths:` in settings.yaml (e.g. path("raw"))."""
    p = ROOT / settings()["paths"][key]
    if p.suffix == "":  # a directory, not a file like the .duckdb
        p.mkdir(parents=True, exist_ok=True)
    return p


@dataclass(frozen=True)
class Secrets:
    anthropic_api_key: str | None
    openfda_api_key: str | None


def secrets() -> Secrets:
    """Read secrets from the environment (.env locally, Streamlit secrets / CI vars in deployment)."""
    return Secrets(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
        openfda_api_key=os.getenv("OPENFDA_API_KEY") or None,
    )
