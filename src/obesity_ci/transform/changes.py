"""Change log between two snapshots (M3, chunk 4): the input to the M5 "what changed" brief.

Compares the tidy tables of an OLD and a NEW snapshot and emits one row per change:

  source    change_type                 example
  ctgov     New trial                   a Phase 3 retatrutide trial appears
  ctgov     Status change               RECRUITING -> TERMINATED (with the reason, if given)
  ctgov     Phase change                Phase 2 -> Phase 2/3
  ctgov     Primary completion moved    readout proxy slips by 120 days
  ctgov     Results posted              has_results False -> True
  ctgov     Lead sponsor change
  ctgov     No longer returned          trial dropped out of our searches (often noise)
  openfda   New FDA action              original / tentative approval, efficacy supplement, ...
  openfda   Marketing status change     Prescription -> Discontinued
  openfda   Label updated               new version of a brand's primary label
  canada    New Canadian product / Canadian status change
  canada    Ontario listing change      new listing, or coverage changed

Every row carries the ID (NCT number, application number, DIN) so the M5 brief can cite it
and its guardrail can check that every ID it mentions exists here.

importance: high / medium / low, a simple rule set (see IMPORTANCE below) so the brief and
the dashboard can lead with what a brand team would care about.
"""

from __future__ import annotations

import pandas as pd

from obesity_ci import config

STOPPED = {"TERMINATED", "WITHDRAWN", "SUSPENDED"}
SLIP_DAYS = 90  # a primary completion move bigger than this is "medium"
COLUMNS = ["source", "change_type", "importance", "id", "molecules", "title",
           "field", "old", "new", "detail"]


def _row(source, change_type, importance, id_, molecules="", title="", field="", old="", new="", detail=""):
    return dict(zip(COLUMNS, [source, change_type, importance, id_, molecules, title,
                              field, _s(old), _s(new), detail]))


def _s(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)) or v is pd.NaT:
        return ""
    if isinstance(v, pd.Timestamp):
        return v.date().isoformat()
    return str(v)


def _same(a, b) -> bool:
    """Equal, treating two missing values (None / NaN / NaT) as equal."""
    if pd.isna(a) or pd.isna(b):
        return bool(pd.isna(a) and pd.isna(b))
    return a == b


# ---------- trials ----------

def trial_changes(old: pd.DataFrame, new: pd.DataFrame) -> list[dict]:
    """old/new: trials tables from transform.trials (one row per NCT ID)."""
    o, n = old.set_index("nct_id"), new.set_index("nct_id")
    rows = []
    for nct in n.index.difference(o.index):
        t = n.loc[nct]
        if not t["molecules"] and "condition__" not in t["found_by"]:
            continue  # returned by a molecule search but names none of our molecules: noise
        imp = "high" if t["phase_rank"] >= 2.5 else "medium" if t["phase_rank"] >= 2 else "low"
        rows.append(_row("ctgov", "New trial", imp, nct, t["molecules"], t["title"], "phase", "", t["phase"],
                         f"{t['lead_sponsor']}; {t['status']}; primary completion "
                         f"{_s(t['primary_completion_date']) or 'n/a'}"))
    for nct in o.index.difference(n.index):
        t = o.loc[nct]
        if t["molecules"]:
            rows.append(_row("ctgov", "No longer returned", "low", nct, t["molecules"], t["title"],
                             detail="Dropped out of our search results; check the record before reporting."))

    for nct in o.index.intersection(n.index):
        a, b = o.loc[nct], n.loc[nct]
        mol, title = b["molecules"], b["title"]
        late = b["phase_rank"] >= 2.5
        if a["status"] != b["status"]:
            imp = "high" if (b["status"] in STOPPED and b["phase_rank"] >= 2) or (late and b["status"] == "COMPLETED") \
                else "medium" if late or b["status"] in STOPPED else "low"
            rows.append(_row("ctgov", "Status change", imp, nct, mol, title, "status", a["status"], b["status"],
                             f"Why stopped: {b['why_stopped']}" if b["status"] in STOPPED and b["why_stopped"] else ""))
        if a["phase"] != b["phase"]:
            rows.append(_row("ctgov", "Phase change", "high" if late else "medium", nct, mol, title,
                             "phase", a["phase"], b["phase"]))
        pa, pb = a["primary_completion_date"], b["primary_completion_date"]
        if not _same(pa, pb):
            days = (pb - pa).days if pd.notna(pa) and pd.notna(pb) else None
            imp = "medium" if days is not None and abs(days) > SLIP_DAYS and late else "low"
            rows.append(_row("ctgov", "Primary completion moved", imp, nct, mol, title,
                             "primary_completion_date", pa, pb,
                             f"{'+' if days and days > 0 else ''}{days} days" if days is not None else ""))
        if not a["has_results"] and b["has_results"]:
            rows.append(_row("ctgov", "Results posted", "high" if late else "medium", nct, mol, title,
                             "has_results", False, True))
        if a["lead_sponsor"] != b["lead_sponsor"]:
            rows.append(_row("ctgov", "Lead sponsor change", "medium", nct, mol, title,
                             "lead_sponsor", a["lead_sponsor"], b["lead_sponsor"]))
    return rows


# ---------- FDA ----------

FDA_EVENT_IMPORTANCE = {"Original approval": "high", "Tentative approval": "high",
                        "Efficacy supplement": "high", "Labeling change": "low",
                        "Manufacturing change": "low", "REMS change": "medium", "Other supplement": "low"}


def fda_changes(old: dict[str, pd.DataFrame], new: dict[str, pd.DataFrame]) -> list[dict]:
    """old/new: dicts of the approvals tables (fda_applications, fda_events, fda_labels)."""
    rows = []
    apps = new["fda_applications"].set_index("application_number")
    key = ["application_number", "submission"]
    seen = set(map(tuple, old["fda_events"][key].values))
    for _, e in new["fda_events"].iterrows():
        if (e["application_number"], e["submission"]) in seen:
            continue
        a = apps.loc[e["application_number"]]
        imp = FDA_EVENT_IMPORTANCE.get(e["event_type"], "low")
        if a["app_type"] == "ANDA" and e["event_type"] != "Tentative approval":
            imp = "low"  # routine generic activity, except a new generic entrant queuing
        if a["app_type"] == "ANDA" and e["event_type"] == "Original approval":
            imp = "medium"  # a generic can now launch
        rows.append(_row("openfda", "New FDA action", imp, e["application_number"], a["molecules"], a["brands"],
                         "event_type", "", e["event_type"],
                         f"{a['sponsor']}; {e['submission']}; {_s(e['date'])}; {e['letter_url'] or ''}".rstrip("; ")))

    oa = old["fda_applications"].set_index("application_number")
    for num in apps.index.intersection(oa.index):
        if oa.loc[num, "marketing_status"] != apps.loc[num, "marketing_status"]:
            a = apps.loc[num]
            rows.append(_row("openfda", "Marketing status change",
                             "medium" if a["app_type"] != "ANDA" else "low", num, a["molecules"], a["brands"],
                             "marketing_status", oa.loc[num, "marketing_status"], a["marketing_status"]))

    def primary(df):
        return df[df["is_primary"]].set_index(["brand_query", "application_number"]) if len(df) else df

    ol, nl = primary(old["fda_labels"]), primary(new["fda_labels"])
    if len(nl):
        for k in nl.index.intersection(ol.index):
            a, b = ol.loc[k], nl.loc[k]
            if a["version"] != b["version"] or not _same(a["effective_date"], b["effective_date"]):
                changed = "" if (a["recent_major_changes"] or "") == (b["recent_major_changes"] or "") \
                    else f"Recent major changes now: {(b['recent_major_changes'] or '')[:300]}"
                indic = "Indications text changed. " if (a["indications"] or "") != (b["indications"] or "") else ""
                rows.append(_row("openfda", "Label updated", "medium" if indic else "low", k[1], "", k[0],
                                 "label version", a["version"], b["version"], (indic + changed).strip()))
    return rows


# ---------- Canada ----------

def canada_changes(old: dict[str, pd.DataFrame], new: dict[str, pd.DataFrame]) -> list[dict]:
    rows = []
    oh, nh = old["hc_products"].set_index("din"), new["hc_products"].set_index("din")
    for din in nh.index.difference(oh.index):
        p = nh.loc[din]
        rows.append(_row("canada", "New Canadian product", "medium", din, p["molecules"], p["brand"],
                         "status", "", p["status"], p["company"]))
    for din in nh.index.intersection(oh.index):
        if oh.loc[din, "status"] != nh.loc[din, "status"]:
            p = nh.loc[din]
            imp = "high" if p["status"] == "Marketed" and oh.loc[din, "status"] == "Approved" else "low"
            rows.append(_row("canada", "Canadian status change", imp, din, p["molecules"], p["brand"],
                             "status", oh.loc[din, "status"], p["status"], p["company"]))

    def ours(df):
        return df[df["molecules"] != ""].drop_duplicates("din").set_index("din")

    oo, no = ours(old["odb_listings"]), ours(new["odb_listings"])
    for din in no.index.difference(oo.index):
        p = no.loc[din]
        rows.append(_row("canada", "Ontario listing change", "high", din, p["molecules"], p["odb_name"],
                         "coverage", "Not listed", p["coverage"],
                         f"list {_s(p['list_price'])}, ministry pays {_s(p['ministry_pays'])}"))
    for din in no.index.intersection(oo.index):
        a, b = oo.loc[din], no.loc[din]
        if a["coverage"] != b["coverage"] or not _same(a["ministry_pays"], b["ministry_pays"]):
            rows.append(_row("canada", "Ontario listing change", "high" if a["coverage"] != b["coverage"] else "medium",
                             din, b["molecules"], b["odb_name"], "coverage / ministry_pays",
                             f"{a['coverage']} / {_s(a['ministry_pays'])}", f"{b['coverage']} / {_s(b['ministry_pays'])}"))
    for din in oo.index.difference(no.index):
        p = oo.loc[din]
        rows.append(_row("canada", "Ontario listing change", "medium", din, p["molecules"], p["odb_name"],
                         "coverage", p["coverage"], "Not listed"))
    return rows


# ---------- assemble ----------

def change_log(rows: list[dict], old_label: str, new_label: str) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=COLUMNS)
    df.insert(0, "new_snapshot", new_label)
    df.insert(0, "old_snapshot", old_label)
    order = {"high": 0, "medium": 1, "low": 2}
    return (df.assign(_o=df["importance"].map(order)).sort_values(["_o", "source", "change_type", "id"])
            .drop(columns="_o").reset_index(drop=True))


def run(old: str | None = None, new: str | None = None) -> dict:
    """Change log for each source between two raw snapshots (default: its last two).

    Tidy tables are (re)built for both snapshots first, so this needs only the raw pulls.
    A source with fewer than two snapshots is skipped and reported.
    """
    from obesity_ci import snapshots
    from obesity_ci.transform import approvals, canada, trials

    def pair(source):
        dates = [p.name for p in snapshots.list_snapshots(source)]
        if old and new:
            return (old, new) if old in dates and new in dates else None
        return tuple(dates[-2:]) if len(dates) >= 2 else None

    logs, skipped = [], {}
    p = pair("ctgov")
    if p:
        a, b = trials.run(p[0]), trials.run(p[1])
        logs.append(change_log(trial_changes(a["trials"], b["trials"]), *p))
    else:
        skipped["ctgov"] = [x.name for x in snapshots.list_snapshots("ctgov")]
    p = pair("openfda")
    if p:
        a, b = approvals.run(p[0]), approvals.run(p[1])
        logs.append(change_log(fda_changes(a, b), *p))
    else:
        skipped["openfda"] = [x.name for x in snapshots.list_snapshots("openfda")]
    p = pair("hc_dpd") if pair("ontario_odb") else None
    if p and pair("ontario_odb") == p:
        a, b = canada.run(p[0]), canada.run(p[1])
        logs.append(change_log(canada_changes(a, b), *p))
    else:
        skipped["canada"] = [x.name for x in snapshots.list_snapshots("hc_dpd")]

    df = pd.concat(logs, ignore_index=True) if logs else pd.DataFrame(columns=["old_snapshot", "new_snapshot", *COLUMNS])
    out = None
    if len(logs):
        out = config.path("processed") / "changes"
        out.mkdir(parents=True, exist_ok=True)
        stem = f"changes_{df['new_snapshot'].max()}"
        df.to_parquet(out / f"{stem}.parquet", index=False)
        df.to_csv(out / f"{stem}.csv", index=False)
        out = out / f"{stem}.csv"
    return {"changes": df, "skipped": skipped, "out": out}
