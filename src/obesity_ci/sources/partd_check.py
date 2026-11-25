"""Check our filtered Part D extract against CMS's own national totals (M2 exit criterion).

Why: our extract is built by matching drug names and dropping nothing else, so if the
pull worked, our claim totals per drug should be close to (and never above) what CMS
publishes nationally. The gap is the claims CMS suppressed (prescriber x drug rows with
fewer than 11 claims), which tells us how much the prescriber-level file undercounts.

Reference: "Medicare Part D Prescribers - by Geography and Drug", same data year. Its
"National" rows give total claims per drug, built by CMS from all prescribers, so they
include the small prescribers that the by-Provider file leaves out.
"""

from __future__ import annotations

import json

import duckdb
import pandas as pd

from obesity_ci import config, snapshots
from obesity_ci.http import PoliteSession
from obesity_ci.sources import partd

# A drug whose national total is below this can legitimately vanish from the prescriber
# file: every prescriber may be under the 11-claim threshold.
SMALL_DRUG_CLAIMS = 5_000
# Our total may not exceed the national one. Allow a hair for rounding.
OVER_TOLERANCE_PCT = 100.5
# Explicit CSV settings: CMS names contain quoted commas ("Insulin Glargine,Hum.Rec.Anlog"),
# which can confuse DuckDB's automatic format detection on small files.
CSV_OPTS = "header = true, delim = ',', quote = '\"', all_varchar = true"


def _pattern_where(column: str, patterns: list[str]) -> str:
    return " OR ".join(f"lower({column}) LIKE '%{p.replace(chr(39), '')}%'" for p in patterns)


def national_extract(geo_csv, out_csv, patterns: list[str]) -> int:
    """Keep only the National rows for our drugs from the by-Geography file. Returns rows kept."""
    con = duckdb.connect()
    con.execute(f"""
        COPY (
            SELECT * FROM read_csv('{geo_csv}', {CSV_OPTS})
            WHERE lower(Prscrbr_Geo_Lvl) = 'national' AND ({_pattern_where('Gnrc_Name', patterns)})
        ) TO '{out_csv}' (HEADER, DELIMITER ',')
    """)
    return con.execute(f"SELECT count(*) FROM read_csv('{out_csv}', {CSV_OPTS})").fetchone()[0]


def reconcile(parquet_path, national_csv) -> pd.DataFrame:
    """One row per (generic, brand): our claims, CMS national claims, % captured, and a status."""
    con = duckdb.connect()
    df = con.execute(f"""
        WITH ours AS (
            SELECT trim(Gnrc_Name) AS gnrc, trim(Brnd_Name) AS brnd,
                   sum(TRY_CAST(Tot_Clms AS BIGINT)) AS our_claims,
                   count(*) AS our_prescriber_rows
            FROM '{parquet_path}' GROUP BY 1, 2
        ),
        nat AS (
            SELECT trim(Gnrc_Name) AS gnrc, trim(Brnd_Name) AS brnd,
                   sum(TRY_CAST(replace(Tot_Clms, ',', '') AS DOUBLE)) AS national_claims,
                   sum(TRY_CAST(replace(Tot_Prscrbrs, ',', '') AS DOUBLE)) AS national_prescribers
            FROM read_csv('{national_csv}', {CSV_OPTS}) GROUP BY 1, 2
        )
        SELECT coalesce(n.gnrc, o.gnrc) AS generic_name, coalesce(n.brnd, o.brnd) AS brand_name,
               o.our_claims, n.national_claims, o.our_prescriber_rows, n.national_prescribers
        FROM nat n FULL OUTER JOIN ours o
          ON lower(n.gnrc) = lower(o.gnrc) AND lower(n.brnd) = lower(o.brnd)
        ORDER BY n.national_claims DESC NULLS LAST
    """).df()
    df["captured_pct"] = (100 * df["our_claims"] / df["national_claims"]).round(1)

    def status(r) -> str:
        if pd.isna(r.national_claims):
            return "not in national file"
        if pd.isna(r.our_claims):
            return "all suppressed (small)" if r.national_claims < SMALL_DRUG_CLAIMS else "MISSING"
        if r.captured_pct > OVER_TOLERANCE_PCT:
            return "OVER"
        return "ok"

    df["status"] = df.apply(status, axis=1)
    return df


def summary(df: pd.DataFrame) -> dict:
    both = df.dropna(subset=["our_claims", "national_claims"])
    problems = df[df["status"].isin(["OVER", "MISSING"])]
    return {
        "drugs_compared": len(both),
        "our_claims": int(both["our_claims"].sum()),
        "national_claims": int(both["national_claims"].sum()),
        "captured_pct": round(100 * both["our_claims"].sum() / both["national_claims"].sum(), 2),
        "status_counts": df["status"].value_counts().to_dict(),
        "problems": problems[["generic_name", "brand_name", "status"]].to_dict("records"),
        "passed": problems.empty,
    }


def run(session=None) -> dict:
    """Reconcile the latest Part D snapshot. Saves files next to it and returns the summary."""
    folder = snapshots.list_snapshots(partd.SOURCE)[-1]
    manifest = json.loads((folder / "manifest.json").read_text())
    year = manifest["data_year"]
    parquet = folder / f"partd_prescriber_drug_{year}_in_scope.parquet"
    st = config.settings()["sources"]["cms_partd"]
    session = session or PoliteSession(delay_s=1.0)

    dists = partd.find_distributions(session.get_json(st["catalog_url"]), st["geo_dataset_title"])
    dist = partd.choose(dists, year)
    print(f"Reference file ({year}): {dist['title']}\n  {dist['url']}")

    geo_csv = folder / f"partd_geo_drug_{year}_FULL.csv"
    print("Downloading the by-Geography file (smaller, usually under a minute)...")
    session.download(dist["url"], geo_csv)
    national_csv = folder / f"partd_national_drug_{year}.csv"
    rows = national_extract(geo_csv, national_csv, partd.name_patterns())
    geo_csv.unlink()
    print(f"Kept {rows} national drug rows matching our names.")

    df = reconcile(parquet, national_csv)
    df.to_csv(folder / f"partd_reconciliation_{year}.csv", index=False)
    s = summary(df)
    (folder / f"partd_reconciliation_{year}.json").write_text(json.dumps(
        {**s, "reference_url": dist["url"], "data_year": year}, indent=2))
    return {"summary": s, "table": df, "folder": str(folder), "year": year}
