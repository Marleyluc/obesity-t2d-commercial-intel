"""CMS Medicare Part D Prescribers (by Provider and Drug) puller.

One row per prescriber (NPI) x drug per year: claims, days' supply, cost and
beneficiaries, plus prescriber specialty and location. The national file is several GB,
so the pull is:
1. Find the latest year's CSV in CMS's catalogue (data.json).
2. Check there is enough disk space, then stream the CSV to disk.
3. Filter it with DuckDB to the drugs in our config, straight from disk (never loaded
   into memory), and save the result as Parquet: typically a few % of the original size.
4. Save a name report: every CMS generic/brand name we kept, with claim totals, and every
   config molecule we could NOT find. This is how we check the match in M2.
5. Delete the big CSV (an immutable annual release we can always re-download).

Known limits, to state in every output (details in docs/M1_DECISIONS.md):
- Medicare Part D only (mostly 65+), not the whole US market, and nothing for Canada.
- About a two-year lag.
- Rows with fewer than 11 claims are suppressed by CMS, so low-volume prescribers are missing.
- Medicare has historically excluded weight-loss drugs, so obesity use is under-represented.
"""

from __future__ import annotations

import re
import shutil
from datetime import date

import duckdb

from obesity_ci import config, snapshots
from obesity_ci.http import PoliteSession

SOURCE = "cms_partd"


def find_distributions(catalog: dict, title: str) -> list[dict]:
    """Every CSV download of the dataset in the DCAT catalogue, with the data year it covers."""
    out = []
    for ds in catalog.get("dataset", []):
        if title.lower() not in ds.get("title", "").lower():
            continue
        for dist in ds.get("distribution", []):
            url = dist.get("downloadURL") or ""
            fmt = (dist.get("mediaType") or dist.get("format") or "").lower()
            if not url or ("csv" not in fmt and not url.lower().endswith(".csv")):
                continue
            text = " ".join(str(dist.get(k, "")) for k in ("title", "temporal", "description"))
            years = [int(y) for y in re.findall(r"\b(20\d{2})\b", text)]
            out.append({"year": max(years) if years else None, "url": url,
                        "title": dist.get("title"), "modified": dist.get("modified") or ds.get("modified")})
    return sorted([d for d in out if d["year"]], key=lambda d: d["year"])


def choose(dists: list[dict], year: int | None) -> dict:
    if not dists:
        raise RuntimeError("No CSV found for the Part D dataset in the CMS catalogue.")
    if year is None:
        return dists[-1]
    match = [d for d in dists if d["year"] == year]
    if not match:
        raise RuntimeError(f"No {year} file. Available years: {sorted({d['year'] for d in dists})}")
    return match[-1]


def name_patterns() -> list[str]:
    """Lower-case substrings to match CMS generic names (e.g. 'Insulin Glargine,Hum.Rec.Anlog').

    We match each component of each molecule ('insulin degludec/liraglutide' gives both),
    plus 'insulin' broadly, because CMS spells insulins many ways. Over-matching here is
    fine: the name report shows exactly what was kept, and M4 maps names to our classes.
    """
    pats = {"insulin"}
    for g in config.molecules()["generic"]:
        g = re.sub(r"\(.*?\)", "", g)
        g = re.sub(r"^oral\s+", "", g.strip())
        for part in g.split("/"):
            part = part.strip()
            if part and not part.startswith("insulin"):
                pats.add(part)
    return sorted(pats)


def filter_csv(csv_path, out_parquet, patterns: list[str]) -> int:
    """Filter the national CSV to our drugs with DuckDB, writing Parquet. Returns rows kept."""
    where = " OR ".join(f"lower(Gnrc_Name) LIKE '%{p.replace(chr(39), '')}%'" for p in patterns)
    con = duckdb.connect()
    con.execute(f"""
        COPY (
            SELECT * FROM read_csv('{csv_path}', header = true, all_varchar = true)
            WHERE {where}
        ) TO '{out_parquet}' (FORMAT parquet)
    """)
    return con.execute(f"SELECT count(*) FROM '{out_parquet}'").fetchone()[0]


def name_report(parquet_path, report_csv) -> list[str]:
    """Write distinct CMS names with claim totals; return config molecules with no match."""
    con = duckdb.connect()
    con.execute(f"""
        COPY (
            SELECT Gnrc_Name, Brnd_Name,
                   count(*) AS n_prescriber_rows,
                   sum(TRY_CAST(Tot_Clms AS BIGINT)) AS total_claims
            FROM '{parquet_path}' GROUP BY 1, 2 ORDER BY total_claims DESC
        ) TO '{report_csv}' (HEADER, DELIMITER ',')
    """)
    names = [r[0].lower() for r in con.execute(f"SELECT DISTINCT Gnrc_Name FROM '{parquet_path}'").fetchall()]
    missing = []
    for g in config.molecules()["generic"]:
        parts = [p.strip() for p in re.sub(r"^oral\s+", "", re.sub(r"\(.*?\)", "", g)).split("/")]
        if not any(all(p in n for p in parts) for n in names):
            missing.append(g)
    return missing


def pull(snapshot_date: date | None = None, keep_csv: bool | None = None, session=None) -> dict:
    st = config.settings()["sources"]["cms_partd"]
    session = session or PoliteSession(delay_s=1.0)
    folder = snapshots.snapshot_dir(SOURCE, snapshot_date)
    keep_csv = st["keep_full_csv"] if keep_csv is None else keep_csv

    catalog = session.get_json(st["catalog_url"])
    dists = find_distributions(catalog, st["dataset_title"])
    print(f"Years available: {sorted({d['year'] for d in dists})}")
    dist = choose(dists, st["data_year"])
    print(f"Using data year {dist['year']}: {dist['title']}\n  {dist['url']}")

    size = session.content_length(dist["url"])
    free = shutil.disk_usage(folder).free
    print(f"File size: {size / 1e9:.1f} GB, free disk: {free / 1e9:.1f} GB" if size else
          f"File size unknown, free disk: {free / 1e9:.1f} GB")
    if size and free < size * 1.3:
        raise RuntimeError("Not enough free disk space for the download plus the filtered copy. "
                           "Free up space, then re-run.")

    csv_path = folder / f"partd_prescriber_drug_{dist['year']}_FULL.csv"
    if csv_path.exists() and size and csv_path.stat().st_size == size:
        print("Full CSV already downloaded, skipping download.")
    else:
        print("Downloading (this can take 5-20 minutes)...")
        session.download(dist["url"], csv_path, progress=True)

    out = folder / f"partd_prescriber_drug_{dist['year']}_in_scope.parquet"
    print("Filtering to our drugs with DuckDB...")
    rows = filter_csv(csv_path, out, name_patterns())
    missing = name_report(out, folder / f"partd_drug_names_{dist['year']}.csv")
    print(f"Kept {rows:,} prescriber x drug rows ({out.stat().st_size / 1e6:.0f} MB Parquet)")
    print(f"Config molecules with NO Part D match ({len(missing)}): {', '.join(missing) or 'none'}")

    snapshots.write_manifest(folder, SOURCE, [{"file": out.name, "rows": rows}], extra={
        "data_year": dist["year"], "source_url": dist["url"], "source_bytes": size,
        "patterns": name_patterns(), "unmatched_molecules": missing})
    if not keep_csv:
        csv_path.unlink()
        print("Deleted the full CSV (re-downloadable; use --keep-csv to keep it).")
    return {"folder": str(folder), "rows": rows, "year": dist["year"], "missing": missing}
