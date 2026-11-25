#!/usr/bin/env python3
"""
Run the live Court Dashboard queries against Metabase and build the dashboard payload.

    python3 extract_court_dashboard.py                 # reporting month = last complete month (IST)
    python3 extract_court_dashboard.py --month 2026-10

Writes DATA/court_dashboard_data.json (consumed by render_court_dashboard.py) and one CSV
per dataset in DATA/csv/.
"""

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # repository root
sys.path.insert(0, HERE)

from dotenv import load_dotenv  # noqa: E402
from court_dashboard_sql import SQL  # noqa: E402

load_dotenv(os.path.join(ROOT, ".env"))
BASE_URL = "https://oncourts.kerala.gov.in/pucar-dashboard"

DB_ID = 3
IST = timezone(timedelta(hours=5, minutes=30))
DATA_DIR = os.path.join(ROOT, "DATA")
DAY_MS = 86400000
# Pages whose rows carry a per-case "Case history" download, and how much proceedings text to keep.
HISTORY_PAGES = {"silent", "gaps", "cognizance", "dca", "repeat_warrants", "mediation", "bail", "plea", "lpr", "disposed"}
HISTORY_TEXT = 100

STAGE_GROUP = {
    "Filing": "Filing", "Scrutiny": "Filing", "Registration": "Filing", "Defect Correction": "Filing",
    "Cognizance": "Cognizance",
    "Appearance": "Appearance",
    "Bail & Recording of Plea": "Bail and Recording of Plea",
    "Complainant Evidence": "Trial", "Examination of Accused": "Trial",
    "Defense Evidence": "Trial", "Arguments": "Trial",
    "Judgement": "Judgement",
    "Post-Disposal": "Disposed", "Post-Judgement": "Disposed",
}
STAGE_GROUP_ORDER = ["Filing", "Cognizance", "Appearance", "Bail and Recording of Plea", "Trial", "Judgement", "Disposed"]

TRIAL_STAGE_LABEL = {
    "Complainant Evidence": "Complainant Evidence", "Examination of Accused": "Accused Examination",
    "Defense Evidence": "Defence Evidence", "Arguments": "Arguments",
}

KERALA_DISTRICTS = {"Kollam", "Thrissur", "Ernakulam", "Thiruvananthapuram", "Alappuzha", "Pathanamthitta",
                    "Kottayam", "Idukki", "Kozhikode", "Malappuram", "Palakkad", "Kannur", "Kasaragod", "Wayanad"}
INDIAN_STATES = {"Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat", "Haryana",
                 "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur",
                 "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana",
                 "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal", "Delhi", "Jammu and Kashmir", "Ladakh",
                 "Puducherry", "Chandigarh", "Andaman and Nicobar Islands", "Lakshadweep",
                 "Dadra and Nagar Haveli and Daman and Diu"}
# Recorded task statuses -> readable labels (wording only; one label per status).
STATUS_LABEL = {
    "PENDING_PAYMENT": "Process fee not paid", "ISSUE_WARRANT": "Issued, not yet sent", "WARRANT_SENT": "Sent, no return yet",
    "EXPIRED": "Expired", "WARRANT_REISSUED": "Reissued", "WARRANT_REISSUED_WITH_NEW_WARRANT": "Reissued with new warrant",
    "NOT_EXECUTED": "Returned not executed", "EXECUTED": "Executed", "OTHER": "Other (as recorded)",
}
OUTCOME_LABEL = {"WITHDRAWN": "Withdrawn / Settled", "DISMISSED": "Dismissed", "CONVICTED": "Judgement: convicted",
                 "ACQUITTED": "Judgement: acquitted", "ABATED": "Abated"}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def ms_to_date(ms):
    if ms is None or (isinstance(ms, float) and np.isnan(ms)):
        return None
    return datetime.fromtimestamp(int(ms) / 1000, IST).date()


def fmt_date(ms):
    d = ms_to_date(ms)
    return f"{d.day} {d.strftime('%B %Y')}" if d else "—"


def iso_date(ms):
    d = ms_to_date(ms)
    return d.isoformat() if d else ""


def month_label(ym, short=False):
    d = datetime.strptime(ym, "%Y-%m")
    if short:
        return "Sept" if d.month == 9 else d.strftime("%b")
    return d.strftime("%B %Y")


def pct(n, d, nd=1):
    return round(100.0 * n / d, nd) if d else 0.0


def ccn(r):
    return r.get("courtcasenumber") or r.get("cmpnumber") or "—"


def nz(v, default=0):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return default
    return v


def clean_name(s):
    s = " ".join(str(s or "").split())
    return s


def norm_company(s):
    s = clean_name(s).upper().rstrip(". ")
    for a, b in ((" LIMITED", " LTD"), (" LTD.", " LTD"), (" PVT.", " PVT"), ("  ", " ")):
        s = s.replace(a, b)
    return s


def _exact(s, names):
    k = clean_name(s).lower()
    for n in names:
        if n.lower() == k:
            return n
    return None


def norm_district(s):
    """Recorded district if it is exactly a Kerala district name (any case), else None."""
    return _exact(s, KERALA_DISTRICTS)


def norm_state(s):
    """Recorded state if it is exactly an Indian state / UT name (any case), else None."""
    return _exact(s, INDIAN_STATES)


def busdays_between(start_date, end_date):
    return int(np.busday_count(start_date, end_date))


def case_row(r):
    return {"filing": r["filingnumber"], "ccn": ccn(r), "title": clean_name(r.get("casetitle")), "stage": r.get("stage") or "Unclassified"}


# ---------------------------------------------------------------------------
# Metabase access
# ---------------------------------------------------------------------------

class Metabase:
    def __init__(self):
        user, pw = os.environ.get("METABASE_USER"), os.environ.get("METABASE_PASS")
        if not user or not pw:
            raise SystemExit("METABASE_USER / METABASE_PASS missing from .env in the repository root")
        req = urllib.request.Request(f"{BASE_URL}/api/session", data=json.dumps({"username": user, "password": pw}).encode(),
                                     headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            self.session = json.loads(resp.read().decode("utf-8"))["id"]

    def query(self, sql):
        body = urllib.parse.urlencode({"query": json.dumps({"database": DB_ID, "type": "native", "native": {"query": sql}})}).encode()
        req = urllib.request.Request(f"{BASE_URL}/api/dataset/json", data=body, headers={
            "X-Metabase-Session": self.session, "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=300) as resp:
            res = json.loads(resp.read().decode("utf-8"))
        if isinstance(res, dict):
            raise RuntimeError(res.get("error") or str(res)[:500])
        return res


# ---------------------------------------------------------------------------
# payload builders (one per dashboard page)
# ---------------------------------------------------------------------------

def build(raw, month, now_ms):
    pm = (datetime.strptime(month, "%Y-%m").replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    out = {"meta": {
        "generated_at": datetime.fromtimestamp(now_ms / 1000, IST).strftime("%d %b %Y, %H:%M IST"),
        "reporting_month": month, "month_name": datetime.strptime(month, "%Y-%m").strftime("%B"),
        "prev_month": pm, "prev_month_name": datetime.strptime(pm, "%Y-%m").strftime("%B"),
        "delta_note": "Arrows on case and process counts show the change over the last 30 days; arrows on hearing "
                      "statistics compare the reporting month with the month before.",
        "source": "Oncourts-Live (Metabase DB #3)",
        "disposed_undated": raw["main_cases"][0].get("disposed_undated", 0),
    }}
    pages = {}

    # ---- main: cases ------------------------------------------------------------------
    mc = raw["main_cases"][0]
    monthly = {r["month"]: r for r in raw["monthly"]}
    months_desc = [r["month"] for r in raw["monthly"]]
    last3 = list(reversed(months_desc[:3]))
    main = {
        "filed": (mc["filed"], mc["filed"] - mc["filed_prev"]),
        "disposed": (mc["disposed"], mc["disposed"] - mc["disposed_prev"]),
        "withdrawn": (mc["withdrawn"], mc["withdrawn"] - mc["withdrawn_prev"]),
        "dismissed": (mc["dismissed"], mc["dismissed"] - mc["dismissed_prev"]),
        "judgement": (mc["judgement"], mc["judgement"] - mc["judgement_prev"]),
        "abated": (mc["abated"], mc["abated"] - mc["abated_prev"]),
        "pending": (mc["pending"], mc["pending"] - mc["pending_prev"]),
        "pending_st": (mc["pending_st"], mc["pending_st"] - mc["pending_st_prev"]),
        "pending_cmp": (mc["pending_cmp"], mc["pending_cmp"] - mc["pending_cmp_prev"]),
        "filed_last3": [{"label": month_label(m, short=True), "value": monthly[m]["filings"]} for m in last3],
    }

    # ---- main: hearings ----------------------------------------------------------------
    hm = {r["month"]: r for r in raw["hearings"]}
    cur, prev = hm.get(month, {}), hm.get(pm, {})

    def per_day(r):
        return round(r["hearings"] / r["sitting_days"], 1) if r.get("sitting_days") else 0.0

    main.update({
        "hearings": (cur.get("hearings", 0), cur.get("hearings", 0) - prev.get("hearings", 0)),
        "median_gap": (nz(cur.get("median_gap_days")), round(nz(cur.get("median_gap_days")) - nz(prev.get("median_gap_days")), 1)),
        "per_day": (per_day(cur), round(per_day(cur) - per_day(prev), 1)),
        "duration": (round(nz(cur.get("median_duration_min")), 1), round(nz(cur.get("median_duration_min")) - nz(prev.get("median_duration_min")), 1)),
    })

    # ---- main: processes ---------------------------------------------------------------
    pr = {r["tasktype"]: r for r in raw["process"]}
    g = lambda t, k: pr.get(t, {}).get(k, 0)  # noqa: E731
    for t in ("NOTICE", "SUMMONS", "WARRANT"):
        main[f"issued_{t.lower()}"] = (g(t, "issued"), g(t, "issued") - g(t, "issued_prev"))
        main[f"served_{t.lower()}"] = (g(t, "served"), g(t, "served") - g(t, "served_prev"))
    main["issued_total"] = tuple(sum(main[f"issued_{t}"][i] for t in ("notice", "summons", "warrant")) for i in (0, 1))
    main["served_total"] = tuple(sum(main[f"served_{t}"][i] for t in ("notice", "summons", "warrant")) for i in (0, 1))
    out["main"] = main

    # ---- monthly disposal rate ---------------------------------------------------------
    mrows = []
    for r in raw["monthly"][:8]:
        mrows.append({"month": month_label(r["month"]), "filings": r["filings"], "disposals": r["disposals"],
                      "contested": r["contested"], "uncontested": r["uncontested"],
                      "pending_at_start": r["pending_at_start"],
                      "rate": f"{pct(r['disposals'], r['pending_at_start'], 2):.2f}%"})
    cm, pmr = monthly.get(month, {}), monthly.get(pm, {})
    rate_cur = pct(cm.get("disposals", 0), cm.get("pending_at_start", 0), 2)
    rate_prev = pct(pmr.get("disposals", 0), pmr.get("pending_at_start", 0), 2)
    pages["monthly"] = {
        "month_name": out["meta"]["month_name"], "prev_month_name": out["meta"]["prev_month_name"],
        "filed": cm.get("filings", 0), "disposed": cm.get("disposals", 0),
        "rate": rate_cur, "prev_rate": rate_prev, "pending": mc["pending"], "target": 15.0,
        "rows": mrows,
    }

    # ---- silent cases ------------------------------------------------------------------
    rows = []
    for r in raw["silent"]:
        rows.append({**case_row(r), "days": r["days_silent"], "last": fmt_date(r["last_ms"]), "_g": [r.get("stage") or "Unclassified"]})
    pages["silent"] = {"rows": rows}

    # ---- hearing gaps ------------------------------------------------------------------
    gdf = pd.DataFrame(raw["gaps"])
    gaps = gdf["median_gap_days"].astype(float) if len(gdf) else pd.Series(dtype=float)
    buckets = [("0–15 days", (gaps <= 15).sum()), ("15–30 days", ((gaps > 15) & (gaps <= 30)).sum()),
               ("30–45 days", ((gaps > 30) & (gaps <= 45)).sum()), ("45–60 days", ((gaps > 45) & (gaps <= 60)).sum()),
               ("Over 60 days", (gaps > 60).sum())]
    rows = [{**case_row(r), "hearings": r["hearing_dates"], "gap": f"{float(r['median_gap_days']):.1f}", "_g": [r.get("stage") or "Unclassified"]}
            for r in raw["gaps"] if float(r["median_gap_days"]) > 60]
    pages["gaps"] = {"buckets": [{"label": l, "value": int(v)} for l, v in buckets], "rows": rows, "cases": int(len(gdf))}

    # ---- cognizance --------------------------------------------------------------------
    rows = [{**case_row(r), "reason": r["reason"], "days": r["days_pending"], "_g": [r["reason"]]} for r in raw["cognizance"]]
    order = ["Delay condonation application pending", "Notice issued, not yet served", "No notice issued", "Notice served"]
    pages["cognizance"] = {"rows": rows, "reasons": [{"label": k, "value": n} for k in order
                                                     for n in [sum(1 for x in rows if x["reason"] == k)] if n]}

    # ---- DCA cycle ---------------------------------------------------------------------
    pages["dca"] = {"rows": [{**case_row(r), "dca": r["dca_hearings"], "steps": r["dca_applications"], "last": fmt_date(r["last_dca_ms"])}
                             for r in raw["dca"]]}

    # ---- unexecuted warrants (iCOPS) ---------------------------------------------------
    today = datetime.fromtimestamp(now_ms / 1000, IST).date()
    w = pd.DataFrame(raw["icops_warrants"])
    w = w[w["delivery_status"] != "FAILED"].copy()          # FAILED = never reached iCOPS
    w["executed"] = w["delivery_status"].isin(["DELIVERED", "DELIVERED_ICOPS"])
    w["booked"] = pd.to_datetime(w["booking_date"], errors="coerce").dt.date
    w["wd_open"] = w["booked"].apply(lambda d: busdays_between(d, today) if pd.notna(d) else 0)
    w["unexecuted"] = (~w["executed"]) & (w["wd_open"] > 21)
    stations = []
    for (ps, dist), grp in w.groupby(["police_station", "district"]):
        cases = grp[grp["unexecuted"]]
        stations.append({
            "station": ps, "district": dist, "total": int(len(grp)), "unexecuted": int(grp["unexecuted"].sum()),
            "executed": int(grp["executed"].sum()), "rate": f"{pct(grp['executed'].sum(), len(grp)):.1f}%",
            "_list": [{"filing": c.filingnumber, "ccn": c.courtcasenumber or "—", "title": clean_name(c.casetitle),
                       "booked": c.booking_date, "status": c.delivery_status, "working_days_open": int(c.wd_open)}
                      for c in cases.itertuples()],
        })
    stations.sort(key=lambda s: (-s["unexecuted"], -s["total"]))
    pages["warrants"] = {
        "sent": int(len(w)), "executed": int(w["executed"].sum()), "rate": pct(w["executed"].sum(), len(w)),
        "unexecuted_cases": int(w.loc[w["unexecuted"], "filingnumber"].nunique()),
        "last_booking": str(w["booked"].max()), "rows": stations,
    }

    # ---- repeat warrants ---------------------------------------------------------------
    rows, tally = [], {}
    for r in raw["repeat_warrants"]:
        st = r["latest_status"] or "—"
        lbl = STATUS_LABEL.get(st, st.replace("_", " ").capitalize())
        tally[lbl] = tally.get(lbl, 0) + 1
        rows.append({**case_row(r), "total": r["total_warrants"], "executed": r["executed"],
                     "unexecuted": r["total_warrants"] - r["executed"], "span": int(nz(r["span_days"])),
                     "reason": lbl, "latest_status": st, "_g": [lbl]})
    pages["repeat_warrants"] = {"rows": rows, "reasons": [{"label": k, "value": v} for k, v in sorted(tally.items(), key=lambda x: -x[1])]}

    # ---- process failures --------------------------------------------------------------
    rows = []
    for r in raw["process_failures"]:
        rows.append({"filing": r["filingnumber"], "ccn": r.get("courtcasenumber") or "—", "title": clean_name(r.get("casetitle")),
                     "process": (r["tasktype"] or "").title(), "failure": r["failure_point"], "hearing": fmt_date(r["hearing_ms"]),
                     "_g": [r["failure_point"]],
                     "_log": {"task_number": r["tasknumber"], "process": r["tasktype"], "channel": r.get("channel") or "",
                              "status": r["status"], "created": iso_date(r["createdtime"]),
                              "last_updated": iso_date(r["lastmodifiedtime"]), "hearing_date": iso_date(r["hearing_ms"]),
                              "failure_point": r["failure_point"]}})
    pages["process_failures"] = {"rows": rows, "total": len(rows),
                                 "payment": sum(1 for r in rows if r["failure"] == "Pending payment"),
                                 "dispatch": sum(1 for r in rows if r["failure"] == "Issued, not sent"),
                                 "expired": sum(1 for r in rows if r["failure"] == "Expired")}

    # ---- clean first summons -----------------------------------------------------------
    cs = {r["month"]: r for r in raw["clean_summons"]}
    rows = [{"month": month_label(r["month"]), "cognised": r["cognised"], "clean": r["clean"], "warrant": r["warrant_issued"],
             "rate": f"{pct(r['clean'], r['cognised']):.1f}%"} for r in raw["clean_summons"][:8]]
    c0, c1 = cs.get(month, {}), cs.get(pm, {})
    pages["clean_summons"] = {"rows": rows, "cognised": c0.get("cognised", 0), "clean": c0.get("clean", 0),
                              "rate": pct(c0.get("clean", 0), c0.get("cognised", 0)), "prev_rate": pct(c1.get("clean", 0), c1.get("cognised", 0)),
                              "month_name": out["meta"]["month_name"], "prev_month_name": out["meta"]["prev_month_name"]}

    # ---- mediation ---------------------------------------------------------------------
    rows = []
    for r in raw["mediation"]:
        d = r["days_in_mediation"]
        if d is None:          # disposed without a dated disposal order
            continue
        dur = "Over 12 months" if d > 365 else ("6 to 12 months" if d > 182 else "Under 6 months")
        grp = [dur] + (["3+ Hearings"] if r["med_hearings"] >= 3 else [])
        rows.append({**case_row(r), "days": d, "hearings": r["med_hearings"], "duration": dur, "_g": grp})
    n = len(rows)
    over6 = sum(1 for r in rows if r["days"] > 182)
    over12 = sum(1 for r in rows if r["days"] > 365)
    h3 = sum(1 for r in rows if r["hearings"] >= 3)
    pages["mediation"] = {"rows": rows, "total": n, "over6": over6, "over12": over12, "h3": h3,
                          "still_in": sum(1 for r in raw["mediation"] if r["still_in_mediation"])}

    # ---- bail --------------------------------------------------------------------------
    rows = []
    for r in raw["bail"]:
        grp = STAGE_GROUP.get(r.get("stage"), "Unclassified")
        rows.append({**case_row(r), "stage": r.get("stage"), "hearings": r["bail_hearings"], "days": f"{float(r['days_to_bail']):.1f}", "_g": [grp]})
    n = len(rows)
    tail = sum(1 for r in rows if r["hearings"] >= 3)
    one = sum(1 for r in rows if r["hearings"] == 1)
    pages["bail"] = {"rows": rows, "total": n, "avg": round(sum(r["hearings"] for r in rows) / n, 2) if n else 0,
                     "tail": tail, "tail_pct": pct(tail, n), "one": one, "one_pct": pct(one, n),
                     "group_order": STAGE_GROUP_ORDER}

    # ---- joint scheduling --------------------------------------------------------------
    rows = []
    for r in raw["joint"]:
        lbl = TRIAL_STAGE_LABEL.get(r["stage"], r["stage"])
        rows.append({"complainant": r["complainant"], "accused": r["accused"], "stage": lbl, "cases": r["cases"],
                     "filings": r["filing_numbers"], "_g": [lbl], "_list_filings": [x.strip() for x in r["filing_numbers"].split(",")]})
    pages["joint"] = {"rows": rows, "pairs": len(rows), "group_order": list(TRIAL_STAGE_LABEL.values())}

    # ---- advocates ---------------------------------------------------------------------
    adv = pd.DataFrame(raw["advocates"])
    adv["group"] = adv["stage"].map(STAGE_GROUP).fillna("Unclassified")
    adv["pending"] = adv["outcome"].isna()
    adv["disp_days"] = (adv["disposal_ms"] - adv["filingdate"]) / DAY_MS
    end = adv["disposal_ms"].where(~adv["pending"], now_ms)   # undated disposals stay NaN (not averaged)
    adv["trial_days"] = (end - adv["trial_start_ms"]) / DAY_MS
    adv["advocate"] = adv["advocate"].map(clean_name)

    def adv_rows(sub_active):
        res = []
        for (aid, name), a in adv.groupby(["advocate_id", "advocate"]):
            act = sub_active[sub_active["advocate_id"] == aid]
            if act.empty:
                continue
            d = a[~a["pending"]]
            dd = d["disp_days"].dropna()          # disposals without a dated disposal order are not averaged
            t = a["trial_days"].dropna()
            res.append({"advocate": f"Adv. {name}", "active": int(len(act)), "disposed": int(len(d)),
                        "avg_disposal": int(round(dd.mean())) if len(dd) else "—",
                        "avg_trial": int(round(t.mean())) if len(t) else "—",
                        "_list_filings": sorted(act["filingnumber"].unique().tolist())})
        res.sort(key=lambda x: (-x["active"], x["advocate"]))
        return res

    active = adv[adv["pending"]]
    groups = {"All Stages": adv_rows(active)}
    counts = {"All Stages": int(active["filingnumber"].nunique())}
    for gname in STAGE_GROUP_ORDER:
        if gname == "Disposed":
            continue
        sub = active[active["group"] == gname]
        if len(sub):
            groups[gname] = adv_rows(sub)
            counts[gname] = int(sub["filingnumber"].nunique())
    pages["advocates"] = {"datasets": groups, "counts": counts}

    # ---- appearance to plea ------------------------------------------------------------
    rows = []
    for r in raw["plea"]:
        d = int(r["days_to_plea"])
        b = ("Plea before bail order" if d < 0 else "Same day" if d == 0 else
             "1 to 14 days" if d <= 14 else "15 to 30 days" if d <= 30 else "Over 30 days")
        rows.append({"filing": r["filingnumber"], "ccn": ccn(r), "appeared": fmt_date(r["appear_ms"]), "plea": fmt_date(r["plea_ms"]),
                     "days": d, "_g": [b]})
    order = ["Same day", "1 to 14 days", "15 to 30 days", "Over 30 days"]
    if any(r["days"] < 0 for r in rows):
        order = ["Plea before bail order"] + order
    days = sorted(r["days"] for r in rows)
    pages["plea"] = {"rows": rows, "buckets": [{"label": b, "value": sum(1 for r in rows if r["_g"][0] == b)} for b in order],
                     "median": float(np.median(days)) if days else 0}

    # ---- institutional complainants ----------------------------------------------------
    inst = pd.DataFrame(raw["institutional"])
    inst = inst[inst["outcome"].isna()].copy()                # active caseload
    inst["co"] = inst["company"].map(norm_company)
    inst["dist"] = inst["district"].map(norm_district)
    inst["st"] = inst["state"].map(norm_state)
    inst.loc[inst["dist"].notna() & inst["st"].isna(), "st"] = "Kerala"     # a Kerala district name implies Kerala
    per_case = inst.drop_duplicates("filingnumber")
    by_co = per_case.groupby("co")["filingnumber"].nunique().sort_values(ascending=False)
    big = by_co[by_co >= 3]
    ood = per_case[(per_case["st"] == "Kerala") & per_case["dist"].notna() & (per_case["dist"] != "Kollam")]
    oos = per_case[per_case["st"].notna() & (per_case["st"] != "Kerala")]
    pages["institutional"] = {
        "entities": int(len(big)), "entity_cases": int(big.sum()),
        "institutions": [{"label": k, "value": int(v)} for k, v in big.head(8).items()],
        "districts": [{"label": k, "value": int(v)} for k, v in ood.groupby("dist")["filingnumber"].nunique().sort_values(ascending=False).head(8).items()],
        "district_cases": int(ood["filingnumber"].nunique()),
        "states": [{"label": k, "value": int(v)} for k, v in oos.groupby("st")["filingnumber"].nunique().sort_values(ascending=False).head(8).items()],
        "state_cases": int(oos["filingnumber"].nunique()),
        "pending_institutional_cases": int(per_case["filingnumber"].nunique()),
    }

    # ---- LPR ---------------------------------------------------------------------------
    rows = [{**case_row(r), "lpr": r.get("lprnumber") or "—", "status": r["lpr_status"], "_g": [r["lpr_status"]]} for r in raw["lpr"]]
    order = ["In LPR", "Revived from LPR"]
    pages["lpr"] = {"rows": rows, "statuses": [{"label": s, "value": sum(1 for r in rows if r["status"] == s)} for s in order]}

    # ---- disposed cases register ("View cases") ------------------------------------------
    rows = []
    for r in raw["disposed"]:
        lbl = OUTCOME_LABEL.get(r["outcome"], r["outcome"])
        rows.append({**case_row(r), "outcome": lbl, "date": fmt_date(r["disposal_ms"]) if r["disposal_ms"] else "Not recorded",
                     "nature": (r.get("natureofdisposal") or "Not recorded").capitalize(),
                     "order": r.get("disposal_order_type") or "No disposal order", "_g": [lbl]})
    pages["disposed"] = {"rows": rows, "group_order": list(OUTCOME_LABEL.values())}

    # ---- diagnostics table -------------------------------------------------------------
    dr = rate_cur - rate_prev
    arrow = "↑" if dr > 0 else ("↓" if dr < 0 else "→")
    out["diagnostics"] = {
        "#Artboard-4roy": (f"{rate_cur:.2f}%", f"{arrow} {abs(dr):.2f} pts vs {out['meta']['prev_month_name']}"),
        "#Artboard-e3az": (f"{len(pages['silent']['rows'])} cases", None),
        "#Artboard-3rf7": (f"{len(pages['gaps']['rows'])} cases", None),
        "#CognizanceDelay": (f"{len(pages['cognizance']['rows'])} cases", None),
        "#DelayCondonation": (f"{len(pages['dca']['rows'])} cases", None),
        "#Artboard-9to3": (f"{pages['warrants']['unexecuted_cases']} cases", None),
        "#RepeatWarrants": (f"{len(pages['repeat_warrants']['rows'])} cases", None),
        "#ProcessFailure": (f"{pages['process_failures']['total']:,} tasks", None),
        "#CleanFirstSummons": (f"{pages['clean_summons']['clean']} cases", None),
        "#MediationOutliers": (f"{pages['mediation']['over6']} cases", None),
        "#BailHearings": (f"{pages['bail']['tail']} cases", None),
        "#JointScheduling": (f"{pages['joint']['pairs']} pairs", None),
        "#AdvocateStats": (f"{len(groups['All Stages'])} advocates", None),
        "#AppearanceToPlea": (f"{pages['plea']['median']:g} days (median)", None),
        "#InstitutionalComplainants": (f"{pages['institutional']['entities']} entities", None),
        "#LPRCases": (f"{pages['lpr']['statuses'][0]['value']} cases", None),
    }

    # ---- case index + histories for per-row downloads ----------------------------------
    case_index = {r["filingnumber"]: [ccn(r), clean_name(r.get("casetitle")), r.get("stage") or ""] for r in raw["case_index"]}
    listed, with_history = set(), set()
    for key, pg in pages.items():
        for r in pg.get("rows", []):
            if "filing" in r:
                listed.add(r["filing"])
                if key in HISTORY_PAGES:
                    with_history.add(r["filing"])
            listed.update(r.get("_list_filings", []))
            listed.update(x["filing"] for x in r.get("_list", []))
    for rs in pages["advocates"]["datasets"].values():
        for r in rs:
            listed.update(r["_list_filings"])
    hist = {}
    for r in raw["history"]:
        f = r["filingnumber"]
        if f in with_history and r["ms"]:
            hist.setdefault(f, []).append([int(r["ms"]), r["kind"], r["detail"] or "", (r["extra"] or "")[:HISTORY_TEXT]])
    for f in hist:
        hist[f].sort(key=lambda e: e[0])
        for e in hist[f]:
            e[0] = iso_date(e[0])
    out["case_index"] = {f: case_index[f] for f in listed if f in case_index}
    out["history"] = hist
    out["pages"] = pages
    return out


def write_csvs(raw):
    d = os.path.join(DATA_DIR, "csv")
    os.makedirs(d, exist_ok=True)
    for k, rows in raw.items():
        if k in ("history",):
            continue
        pd.DataFrame(rows).to_csv(os.path.join(d, f"{k}.csv"), index=False)


def default_month():
    today = datetime.now(IST).date().replace(day=1)
    return (today - timedelta(days=1)).strftime("%Y-%m")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", default=default_month(), help="Reporting month YYYY-MM (default: last complete month)")
    ap.add_argument("--offline", action="store_true", help="Rebuild the payload from DATA/raw_results.json without querying")
    args = ap.parse_args()
    month = args.month
    m_start = f"{month}-01 00:00:00"
    raw_path = os.path.join(DATA_DIR, "raw_results.json")
    os.makedirs(DATA_DIR, exist_ok=True)

    if args.offline:
        with open(raw_path) as f:
            cached = json.load(f)
        raw, now_ms, month = cached["raw"], cached["now_ms"], cached["month"]
    else:
        mb = Metabase()
        raw = {}
        now_ms = int(time.time() * 1000)
        for key, sql in SQL.items():
            t0 = time.time()
            raw[key] = mb.query(sql.replace("$M_START$", m_start))
            print(f"  [+] {key:<18} {len(raw[key]):>6} rows  {time.time() - t0:5.1f}s")
        with open(raw_path, "w") as f:
            json.dump({"month": month, "now_ms": now_ms, "raw": raw}, f, default=str)

    payload = build(raw, month, now_ms)
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, "court_dashboard_data.json")
    with open(path, "w") as f:
        json.dump(payload, f, default=str, ensure_ascii=False)
    write_csvs(raw)
    print(f"[✓] Payload written: {path}")


if __name__ == "__main__":
    main()
