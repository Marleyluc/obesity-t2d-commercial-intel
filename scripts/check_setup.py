"""Milestone 1 exit check: is this machine ready to build the project?

Run from the repo root:
    python scripts/check_setup.py

Checks Python version, packages, config, secrets, folders, and that each
external API answers. Exits with code 1 if any REQUIRED check fails.
"""

from __future__ import annotations

import importlib
import sys

import requests

from obesity_ci import config

OK, WARN, FAIL = "\033[32mOK  \033[0m", "\033[33mWARN\033[0m", "\033[31mFAIL\033[0m"
failures = 0


def report(status: str, name: str, detail: str = "") -> None:
    global failures
    if status == FAIL:
        failures += 1
    print(f"[{status}] {name}" + (f": {detail}" if detail else ""))


def check_python() -> None:
    v = sys.version_info
    report(OK if v >= (3, 11) else FAIL, "Python >= 3.11", f"{v.major}.{v.minor}.{v.micro}")


def check_packages() -> None:
    for pkg in ["requests", "pandas", "pyarrow", "duckdb", "yaml", "dotenv",
                "sklearn", "anthropic", "streamlit", "plotly"]:
        try:
            mod = importlib.import_module(pkg)
            report(OK, f"import {pkg}", getattr(mod, "__version__", ""))
        except ImportError:
            report(FAIL, f"import {pkg}", "run: pip install -e \".[dev]\"")


def check_config() -> None:
    mols = config.molecules()
    n_classes = mols["class_id"].nunique()
    n_pipe = int(mols["is_pipeline"].sum())
    report(OK, "drug_classes.yaml",
           f"{n_classes} classes, {len(mols)} molecules ({n_pipe} pipeline, {len(mols) - n_pipe} marketed)")
    for key in ["raw", "interim", "processed", "briefs"]:
        config.path(key)
    report(OK, "data folders", str(config.path("raw").parent))


def check_secrets() -> None:
    s = config.secrets()
    report(OK if s.anthropic_api_key else WARN, "ANTHROPIC_API_KEY",
           "set" if s.anthropic_api_key else "not set (only needed from Milestone 5)")
    report(OK if s.openfda_api_key else WARN, "OPENFDA_API_KEY",
           "set" if s.openfda_api_key else "not set (optional, raises daily limit)")


def check_apis() -> None:
    st = config.settings()
    headers = {"User-Agent": st["http"]["user_agent"]}
    timeout = st["http"]["timeout_s"]
    probes = {
        "ClinicalTrials.gov API v2": (
            f"{st['sources']['ctgov']['base_url']}/studies",
            {"query.intr": "tirzepatide", "pageSize": 1, "countTotal": "true"},
            lambda j: f"{j.get('totalCount', '?')} tirzepatide studies",
        ),
        "openFDA drugsfda": (
            f"{st['sources']['openfda']['base_url']}/drug/drugsfda.json",
            {"search": 'openfda.generic_name:"tirzepatide"', "limit": 1},
            lambda j: f"{j['meta']['results']['total']} tirzepatide application(s)",
        ),
        "CMS data catalog": (
            st["sources"]["cms_partd"]["catalog_url"], None,
            lambda j: f"{sum(st['sources']['cms_partd']['dataset_title'] in d.get('title', '') for d in j.get('dataset', []))} matching Part D dataset(s)",
        ),
    }
    for name, (url, params, summarise) in probes.items():
        try:
            r = requests.get(url, params=params, headers=headers, timeout=timeout)
            r.raise_for_status()
            report(OK, name, summarise(r.json()))
        except Exception as e:  # noqa: BLE001 - we want to report any failure
            report(FAIL, name, f"{type(e).__name__}: {e}"[:160])


if __name__ == "__main__":
    print("Milestone 1 setup check\n")
    for check in [check_python, check_packages, check_config, check_secrets, check_apis]:
        check()
    print("\nAll required checks passed." if failures == 0 else f"\n{failures} required check(s) failed.")
    sys.exit(1 if failures else 0)
