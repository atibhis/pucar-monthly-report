#!/usr/bin/env python3
"""
Fill Court-Dashboard.html (the design template, left untouched) with the live payload from
extract_court_dashboard.py and write OUTPUT/Court-Dashboard_<DDMMYY>.html (timestamped, DDMMYY_HHMM).

Static values, charts, pills and the first rows of every table are written into the HTML.
The full datasets are embedded as JSON and a small script makes search, stage pills,
"Export dataset (CSV)" and the per-row Download buttons work offline.
"""

import argparse
import copy
import json
import os
import re
from datetime import datetime

from bs4 import BeautifulSoup, NavigableString

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
# Design template (contains sample case data, so it is never committed). First one found wins.
TEMPLATE = next((t for t in (os.path.join(ROOT, "TEMPLATE", "Court-Dashboard.html"),
                             os.path.join(os.path.dirname(ROOT), "Court-Dashboard.html")) if os.path.exists(t)),
                os.path.join(ROOT, "TEMPLATE", "Court-Dashboard.html"))
DATA = os.path.join(ROOT, "DATA", "court_dashboard_data.json")
OUT_DIR = os.path.join(ROOT, "OUTPUT")
STATIC_ROWS = 50

GOOD, BAD, FLAT = "rgb(4, 120, 87)", "rgb(185, 28, 28)", "rgb(91, 100, 117)"
UP, DOWN, LEVEL = "M12 19V5M5 12l7-7 7 7", "M12 5v14M19 12l-7 7-7-7", "M5 12h14"


# ---------------------------------------------------------------------------
# DOM helpers
# ---------------------------------------------------------------------------

def fmt_int(n):
    return f"{int(n):,}"


def fmt_delta(d):
    if isinstance(d, float):
        s = f"{abs(d):.1f}"
    else:
        s = fmt_int(abs(d))
    return ("+" if d > 0 else "−" if d < 0 else "") + s


def own_text(el):
    return "".join(t for t in el.find_all(string=True, recursive=False)).strip()


def find_text(scope, text, names=("p", "h1", "h2", "span", "td", "th", "button")):
    for el in scope.find_all(names):
        if el.get_text(" ", strip=True) == text or own_text(el) == text:
            return el
    raise KeyError(f"text not found: {text!r}")


def set_first_text(el, value):
    """Replace the element's first non-empty text node (keeps child spans such as 'days')."""
    for node in el.find_all(string=True):
        if node.strip():
            node.replace_with(NavigableString(str(value) + (" " if node.endswith(" ") else "")))
            return
    el.append(str(value))


def set_style(el, prop, value):
    st = el.get("style", "")
    if re.search(rf"(^|;)\s*{prop}\s*:", st):
        st = re.sub(rf"((?:^|;)\s*{prop}\s*:)[^;]*", rf"\g<1> {value}", st, count=1)
    else:
        st = (st.rstrip("; ") + f"; {prop}: {value};").lstrip("; ")
    el["style"] = st


def get_style(el, prop):
    m = re.search(rf"(?:^|;)\s*{prop}\s*:\s*([^;]+)", el.get("style", ""))
    return m.group(1).strip() if m else None


def set_delta(p, delta, good_when_up=True):
    """p = the <p> holding the arrow svg and the .sc-interp delta text."""
    if p is None:
        return
    span = p.find("span", class_="sc-interp")
    span.string = fmt_delta(delta) if delta else ("0.0" if isinstance(delta, float) else "0")
    path = p.find("path")
    if path is not None:
        path["d"] = UP if delta > 0 else DOWN if delta < 0 else LEVEL
    colour = FLAT if not delta else (GOOD if (delta > 0) == good_when_up else BAD)
    set_style(p, "color", colour)


def delta_p(container):
    for p in container.find_all("p"):
        if p.find("svg") is not None and p.find("span", class_="sc-interp") is not None:
            return p
    return None


def kpi(scope, label, value, delta=None, good_when_up=True, new_label=None, sub=None):
    """Label element followed by a container (or sibling <p>s) holding the value / delta / sub-text."""
    lab = find_text(scope, label)
    if new_label is not None:
        lab.string = new_label
    sib = lab.find_next_sibling()
    if sib.name == "p":                      # <p>label</p><p>value</p><p>sub</p>
        set_first_text(sib, value)
        if sub is not None:
            nxt = sib.find_next_sibling("p")
            if nxt is not None:
                nxt.string = sub
        return
    vp = sib if sib.name == "p" else sib.find("p")
    set_first_text(vp, value)
    if delta is not None:
        set_delta(delta_p(sib), delta, good_when_up)
    if sub is not None:
        nxt = sib.find_next_sibling("p")
        if nxt is not None:
            nxt.string = sub


def hbars(img, items, show_pct=False, total=None, label_fn=str):
    """Horizontal bar chart: one grid row per item (label, track/fill, value)."""
    rows = [c for c in img.find_all(recursive=False) if c.name]
    tpls = [copy.copy(r) for r in rows]
    for r in rows:
        r.decompose()
    mx = max([i["value"] for i in items] + [1])
    total = total or sum(i["value"] for i in items) or 1
    parts = []
    for n, it in enumerate(items):
        row = copy.copy(tpls[min(n, len(tpls) - 1)])
        ps = row.find_all("p")
        ps[0].string = label_fn(it["label"])
        fill = [d for d in row.find_all("div") if get_style(d, "width") and get_style(d, "height") == "100%"][0]
        set_style(fill, "width", f"{round(100 * it['value'] / mx, 1)}%")
        set_first_text(ps[-1], fmt_int(it["value"]))
        sp = ps[-1].find("span")
        if sp is not None:
            sp.string = f"({100 * it['value'] / total:.1f}%)"
        img.append(row)
        parts.append(f"{it['label']} {fmt_int(it['value'])}")
    img["aria-label"] = img.get("aria-label", "").split(":")[0] + ": " + ", ".join(parts)


EXTRA_COLOURS = ["rgb(124, 58, 237)", "rgb(4, 120, 87)", "rgb(202, 138, 4)", "rgb(100, 116, 139)"]


def donut(img, items):
    """Conic-gradient donut (role=img) + legend rows in the next sibling."""
    legend = img.find_next_sibling()
    rows = [c for c in legend.find_all(recursive=False) if c.name]
    tpls = [copy.copy(r) for r in rows]
    colours = [get_style(r.find("span"), "background") for r in rows]
    for r in rows:
        r.decompose()
    total = sum(i["value"] for i in items) or 1
    stops, acc, parts = [], 0.0, []
    for n, it in enumerate(items):
        col = colours[n] if n < len(colours) else EXTRA_COLOURS[(n - len(colours)) % len(EXTRA_COLOURS)]
        row = copy.copy(tpls[min(n, len(tpls) - 1)])
        spans = row.find_all("span", recursive=False)
        set_style(spans[0], "background", col)
        spans[1].string = it["label"]
        set_first_text(spans[2], fmt_int(it["value"]))
        spans[2].find("span").string = f"({100 * it['value'] / total:.1f}%)"
        legend.append(row)
        start, acc = acc, acc + 100 * it["value"] / total
        stops.append(f"{col} {start:.2f}%, {col} {acc:.2f}%")
        parts.append(f"{it['label']} {fmt_int(it['value'])} ({100 * it['value'] / total:.1f}%)")
    set_style(img, "background", f"conic-gradient({', '.join(stops)})" if stops else "rgb(238, 241, 246)")
    img["aria-label"] = img.get("aria-label", "").split(":")[0] + ": " + ", ".join(parts)


def vbars(img, items, show_pct=False):
    """Vertical bars: columns of (value span, bar div); labels live in the next sibling row."""
    cols = [c for c in img.find_all(recursive=False) if c.name]
    heights = [int(re.sub(r"\D", "", get_style(c.find_all("div")[-1], "height") or "0") or 0) for c in cols]
    hmax = max(heights) if heights else 150
    mx = max([i["value"] for i in items] + [1])
    total = sum(i["value"] for i in items) or 1
    tpls = [copy.copy(c) for c in cols]
    for c in cols:
        c.decompose()
    for n, it in enumerate(items):
        col = copy.copy(tpls[min(n, len(tpls) - 1)])
        span = col.find("span")
        target = span.find("span", class_="sc-interp") or span
        set_first_text(target, fmt_int(it["value"]))
        inner = span.find("span")
        if show_pct and inner is not None and "sc-interp" not in (inner.get("class") or []):
            inner.string = f"({100 * it['value'] / total:.1f}%)"
        bar = col.find_all("div")[-1]
        set_style(bar, "height", f"{max(2, round(hmax * it['value'] / mx))}px")
        img.append(col)
    labels = img.find_next_sibling()
    if labels is not None:
        spans = [s for s in labels.find_all("span", recursive=False)]
        for s, it in zip(spans, items):
            inner = s.find("span", class_="sc-interp")
            (inner or s).string = it["label"]
    img["aria-label"] = img.get("aria-label", "").split(":")[0] + ": " + ", ".join(f"{i['label']} {fmt_int(i['value'])}" for i in items)


def pills(group, items, all_label=None):
    """items: [(label, count)], first is the 'All' pill."""
    btns = group.find_all("button", recursive=False)
    active, inactive = copy.copy(btns[0]), copy.copy(btns[1] if len(btns) > 1 else btns[0])
    for b in btns:
        b.decompose()
    for n, (label, count) in enumerate(items):
        b = copy.copy(active if n == 0 else inactive)
        b.contents[0].replace_with(NavigableString(label))
        b.find("span").string = fmt_int(count)
        b["data-g"] = "__all" if n == 0 else label
        group.append(b)


def table_rows(tbody, rows, cols):
    trs = tbody.find_all("tr", recursive=False)
    tpl = copy.copy(trs[0])
    for tr in trs:
        tr.decompose()
    for r in rows[:STATIC_ROWS]:
        tr = copy.copy(tpl)
        tds = tr.find_all("td", recursive=False)
        for td, key in zip(tds, cols):
            if key is None:
                btn = td.find("button")
                if btn is not None and btn.get("aria-label"):
                    btn["aria-label"] = re.sub(r"for .*$", f"for {r.get('filing') or r.get('station') or r.get('advocate') or ''}", btn["aria-label"])
                continue
            td.string = str(r.get(key, "—"))
        tbody.append(tr)


def group_counts(rows, order=None):
    counts = {}
    for r in rows:
        for g in r.get("_g", []):
            counts[g] = counts.get(g, 0) + 1
    keys = [k for k in (order or []) if k in counts] + sorted([k for k in counts if not order or k not in order], key=lambda k: -counts[k])
    return [(k, counts[k]) for k in keys]


# ---------------------------------------------------------------------------
# page renderers
# ---------------------------------------------------------------------------

def render(soup, d):
    meta, m, pg = d["meta"], d["main"], d["pages"]
    js_pages = {}

    def S(pid):
        return soup.select_one(f"section#pg-{pid}")

    # ---------------- disposed-cases register (new page behind "View cases") ----------------
    silent = S("Artboard-e3az")
    reg = copy.copy(silent)
    reg["id"], reg["data-title"] = "pg-DisposedCases", "Disposed Cases"
    reg.select_one(".sc-host")["data-sc-name"] = "DisposedCases"
    back = reg.find("a", href="#Diagnostics")
    back["href"] = "#Main"
    back.contents[-1].replace_with(NavigableString("Case Statistics"))
    reg.find("h1").string = "Disposed Cases"
    reg.find("h1").find_next_sibling("p").string = ("Every disposed case, with its outcome and the date of its disposal order")
    for th, label in zip(reg.find_all("th"), ["Filing number", "Court case number", "Case title", "Outcome",
                                              "Disposal date", "Nature of disposal", "Case history"]):
        th.string = label
    for td in reg.find("tbody").find("tr").find_all("td"):
        set_style(td, "color", "inherit")
        set_style(td, "font-weight", "400")
    grp = reg.select_one("[role=group]")
    grp["aria-label"] = "Filter by outcome"
    first = grp.find("button")
    first.contents[0].replace_with(NavigableString("All Outcomes"))
    silent.insert_after(reg)

    # ---------------- main ----------------
    main = S("Main")
    h1 = find_text(main, "Case Statistics")
    stamp = soup.new_tag("p")
    stamp["style"] = "margin: 6px 0 0; font-size: 13px; color: rgb(91, 100, 117); text-align: center;"
    stamp.string = (f"Live data from {meta['source']} · generated {meta['generated_at']} · reporting month "
                    f"{datetime.strptime(meta['reporting_month'], '%Y-%m').strftime('%B %Y')}. {meta['delta_note']}"
                    + (f" {meta['disposed_undated']} disposed cases have no disposal order in the database, so no disposal date: "
                       "they are in the totals but not in any month-wise or 30-day figure." if meta.get("disposed_undated") else ""))
    h1.parent.append(stamp)

    def card(h2text, key, good=True):
        h2 = find_text(main, h2text, ("h2",))
        box = h2.find_next_sibling("div")
        set_first_text(box.find("p"), fmt_int(m[key][0]) if isinstance(m[key][0], int) else m[key][0])
        set_delta(delta_p(box), m[key][1], good)
        return h2.parent

    card("Cases Filed", "filed")
    vbars(main.select_one("[role=img]"), m["filed_last3"])
    disp = card("Cases Disposed", "disposed")
    for lbl, key in (("Withdrawn / Settled", "withdrawn"), ("Dismissed", "dismissed"), ("Judgement", "judgement"), ("Abated", "abated")):
        kpi(disp, lbl, fmt_int(m[key][0]), m[key][1])
    pend = card("Cases Pending", "pending", good=False)
    kpi(pend, "ST", fmt_int(m["pending_st"][0]), m["pending_st"][1], good_when_up=False)
    kpi(pend, "CMP", fmt_int(m["pending_cmp"][0]), m["pending_cmp"][1], good_when_up=False)
    hs = card("Hearings", "hearings")
    find_text(hs, "Total hearings").string = f"Hearings held in {meta['month_name']}"
    kpi(hs, "Median Gap", m["median_gap"][0], m["median_gap"][1], good_when_up=False)
    find_text(hs, "Substantive Ratio").parent.decompose()          # not shown (removed on request)
    kpi(hs, "Avg Hearings per Day", m["per_day"][0], m["per_day"][1])
    kpi(hs, "Avg Hearing Duration", m["duration"][0], m["duration"][1], new_label="Median Hearing Duration")
    tp = card("Total Processes", "issued_total")
    for lbl, key in (("Notices", "issued_notice"), ("Summons", "issued_summons"), ("Warrants", "issued_warrant")):
        kpi(tp, lbl, fmt_int(m[key][0]), m[key][1])
    sv = card("Processes Delivered / Executed", "served_total")
    for lbl, key in (("Notices", "served_notice"), ("Summons", "served_summons"), ("Warrants", "served_warrant")):
        kpi(sv, lbl, fmt_int(m[key][0]), m[key][1])

    # ---------------- diagnostics table ----------------
    diag = soup.select_one("#pg-Diagnostics")
    for a in diag.select("a[href]"):
        if a["href"] in d["diagnostics"]:
            val, status = d["diagnostics"][a["href"]]
            tds = a.find_parent("tr").find_all("td")
            tds[1].string = val
            if status:
                tds[2].string = status

    # ---------------- monthly disposal rate ----------------
    s, p = S("Artboard-4roy"), pg["monthly"]
    mn, pmn = p["month_name"], p["prev_month_name"]
    kpi(s, "October filed", fmt_int(p["filed"]), new_label=f"{mn} filed")
    kpi(s, "October disposed", fmt_int(p["disposed"]), new_label=f"{mn} disposed")
    kpi(s, "October disposal %", f"{p['rate']:.2f}%", new_label=f"{mn} disposal %", sub=f"Target floor: {p['target']:.1f}%")
    kpi(s, "September disposal %", f"{p['prev_rate']:.2f}%", new_label=f"{pmn} disposal %", sub=f"Target floor: {p['target']:.1f}%")
    kpi(s, "Pending cases", fmt_int(p["pending"]))
    find_text(s, "Disposal %", ("th",)).string = "Disposal % of opening stock"
    cols = ["month", "filings", "disposals", "contested", "uncontested", "rate"]
    table_rows(s.find("tbody"), p["rows"], cols)
    js_pages["Artboard-4roy"] = {"rows": p["rows"], "cols": cols, "dl": None,
                                 "export": cols + ["pending_at_start"]}

    # ---------------- generic case-table pages ----------------
    def case_page(pid, page, cols, dl="history", group_order=None, all_label=None, extra_export=()):
        s = S(pid)
        rows = page["rows"] if isinstance(page, dict) else page
        grp = s.select_one("[role=group]")
        if grp is not None:
            first = grp.find("button")
            al = all_label or own_text(first)
            pills(grp, [(al, len(rows))] + group_counts(rows, group_order))
        table_rows(s.find("tbody"), rows, cols)
        js_pages[pid] = {"rows": rows, "cols": cols, "dl": dl, "export": [c for c in cols if c] + list(extra_export)}
        return s

    case_page("Artboard-e3az", pg["silent"], ["filing", "ccn", "title", "stage", "days", "last", None])

    s = case_page("Artboard-3rf7", pg["gaps"], ["filing", "ccn", "title", "stage", "hearings", "gap", None])
    vbars(s.select_one("[role=img]"), pg["gaps"]["buckets"])
    find_text(s, "Cases by Median Hearing Gap").string = f"Pending Cases by Median Hearing Gap · {fmt_int(pg['gaps']['cases'])} cases"

    s = case_page("CognizanceDelay", pg["cognizance"], ["filing", "ccn", "title", "reason", "days", None],
                  group_order=[r["label"] for r in pg["cognizance"]["reasons"]])
    find_text(s, "Reasons for Delay · 31 cases").string = f"Reasons for Delay · {len(pg['cognizance']['rows'])} cases"
    hbars(s.select_one("[role=img]"), pg["cognizance"]["reasons"])

    s = case_page("DelayCondonation", pg["dca"], ["filing", "ccn", "title", "dca", "steps", "last", None])
    s.find("h1").find_next_sibling("p").string = "Pending cases with more than 5 completed delay condonation hearings"
    find_text(s, "Take steps orders", ("th",)).string = "DCA applications filed"

    # ---------------- unexecuted warrants ----------------
    s, p = S("Artboard-9to3"), pg["warrants"]
    last = datetime.strptime(p["last_booking"], "%Y-%m-%d").strftime("%-d %b %Y")
    kpi(s, "Warrants sent", fmt_int(p["sent"]), sub=f"Through iCOPS police feed (last booking {last})")
    kpi(s, "Warrants executed", fmt_int(p["executed"]))
    kpi(s, "Execution rate", f"{p['rate']:.1f}%")
    cols = ["station", "district", "total", "unexecuted", "executed", "rate", None]
    table_rows(s.find("tbody"), p["rows"], cols)
    js_pages["Artboard-9to3"] = {"rows": p["rows"], "cols": cols, "dl": "list", "export": [c for c in cols if c]}

    s = case_page("RepeatWarrants", pg["repeat_warrants"],
                  ["filing", "ccn", "title", "stage", "total", "executed", "unexecuted", "span", None], extra_export=("reason",))
    donut(s.select_one("[role=img]"), pg["repeat_warrants"]["reasons"])
    find_text(s, "Reasons for Repeat Warrants").string = "Recorded status of the latest warrant"
    js_pages["RepeatWarrants"]["export"].append("latest_status")

    # ---------------- process failures ----------------
    p = pg["process_failures"]
    s = case_page("ProcessFailure", p, ["filing", "ccn", "title", "process", "failure", "hearing", None], dl="log")
    s.find("p").string = ("Summons, notices and warrants whose hearing date (last 180 days) has passed while the process "
                          "is still recorded as pending payment, issued but not sent, or expired")
    kpi(s, "Total failures", fmt_int(p["total"]), sub=f"Includes {fmt_int(p['expired'])} recorded as expired")
    kpi(s, "Delayed payment", fmt_int(p["payment"]), new_label="Pending payment", sub="Status: process fee not paid")
    kpi(s, "Delayed dispatch", fmt_int(p["dispatch"]), new_label="Issued, not sent", sub="Status: issued, never sent out")
    find_text(s, "PROCESE LOGS", ("th",)).string = "Process log"

    # ---------------- clean first summons ----------------
    s, p = S("CleanFirstSummons"), pg["clean_summons"]
    mn, pmn = p["month_name"], p["prev_month_name"]
    kpi(s, "October cognised", fmt_int(p["cognised"]), new_label=f"{mn} cognised")
    kpi(s, "October clean appearances", fmt_int(p["clean"]), new_label=f"{mn} clean appearances")
    kpi(s, "October clean rate", f"{p['rate']:.1f}%", new_label=f"{mn} clean rate")
    kpi(s, "September clean rate", f"{p['prev_rate']:.1f}%", new_label=f"{pmn} clean rate")
    cols = ["month", "cognised", "clean", "warrant", "rate"]
    table_rows(s.find("tbody"), p["rows"], cols)
    js_pages["CleanFirstSummons"] = {"rows": p["rows"], "cols": cols, "dl": None, "export": cols}

    # ---------------- mediation ----------------
    p = pg["mediation"]
    s = case_page("MediationOutliers", p, ["filing", "ccn", "title", "stage", "days", "hearings", "duration", None],
                  group_order=["Under 6 months", "6 to 12 months", "Over 12 months", "3+ Hearings"])
    n = p["total"] or 1
    s.find("h1").find_next_sibling("p").string = ("Cases referred to ADR: days since the referral order (to disposal, or to today "
                                                  "while pending) and completed hearings since referral")
    find_text(s, "Days in mediation", ("th",)).string = "Days since referral"
    find_text(s, "Mediation hearings", ("th",)).string = "Hearings since referral"
    kpi(s, "Total cases in mediation", fmt_int(p["total"]), new_label="Cases referred to ADR",
        sub=f"{p['still_in']} still pending")
    kpi(s, "In mediation > 6 months", fmt_int(p["over6"]), sub=f"{100 * p['over6'] / n:.1f}% of mediation cases")
    kpi(s, "In mediation > 12 months", fmt_int(p["over12"]), sub=f"{100 * p['over12'] / n:.1f}% stuck over 1 year")
    kpi(s, "3+ mediation hearings", fmt_int(p["h3"]), new_label="3+ hearings since referral", sub=f"{100 * p['h3'] / n:.1f}% of referred cases")

    # ---------------- bail ----------------
    p = pg["bail"]
    s = case_page("BailHearings", p, ["filing", "ccn", "title", "stage", "hearings", "days", None], group_order=p["group_order"])
    kpi(s, "Average hearings to bail", f"{p['avg']:.2f}")
    kpi(s, "3+ hearing tail share", f"{p['tail_pct']:.1f}%", sub=f"{fmt_int(p['tail'])} cases needed 3+ hearings")
    kpi(s, "Secured in 1 hearing", fmt_int(p["one"]), sub=f"{p['one_pct']:.1f}% bail on the first day")

    # ---------------- joint scheduling ----------------
    s = case_page("JointScheduling", pg["joint"], ["complainant", "accused", "stage", "cases", "filings", None], dl="list",
                  group_order=pg["joint"]["group_order"])

    # ---------------- advocates ----------------
    s, p = S("AdvocateStats"), pg["advocates"]
    grp = s.select_one("[role=group]")
    pills(grp, list(p["counts"].items()))
    for b in grp.find_all("button"):
        b["data-g"] = own_text(b)
    top = [{"label": r["advocate"], "value": r["active"]} for r in p["datasets"]["All Stages"][:10]]
    hbars(s.select_one("[role=img]"), top)
    cols = ["advocate", "active", "disposed", "avg_disposal", "avg_trial", None]
    find_text(s, "Avg time to disposal (days)", ("th",)).string = "Avg filing to disposal (days)"
    table_rows(s.find("tbody"), p["datasets"]["All Stages"], cols)
    js_pages["AdvocateStats"] = {"datasets": p["datasets"], "cols": cols, "dl": "list", "export": [c for c in cols if c]}

    # ---------------- appearance to plea ----------------
    p = pg["plea"]
    s = case_page("AppearanceToPlea", p, ["ccn", "appeared", "plea", "days", None],
                  group_order=[b["label"] for b in p["buckets"]], extra_export=("filing",))
    s.find("h1").find_next_sibling("p").string = ("Days from the first bail-granted order (the accused's first recorded appearance) "
                                                  "to the first completed plea hearing")
    find_text(s, "Cases by Time to Plea · 615 cases").string = f"Cases by Time to Plea · {fmt_int(len(p['rows']))} cases"
    vbars(s.select_one("[role=img]"), p["buckets"], show_pct=True)

    # ---------------- institutional ----------------
    s, p = S("InstitutionalComplainants"), pg["institutional"]
    s.find("p").string = ("Active (pending) cases of institutional complainants, and of those registered outside Kollam district or "
                          "outside Kerala (Section 142(2) NI Act). Locations use the institution's registered address; "
                          "individual complainants' addresses are encrypted in the database and are not counted. Only "
                          "districts and states recorded under their exact official name are counted; misspelt or "
                          "locality-only entries are left out rather than guessed.")
    find_text(s, "Complainants with 3+ cases · 225 cases").string = f"Complainants with 3+ cases · {fmt_int(p['entity_cases'])} cases"
    find_text(s, "Cases by complainant's district · 188 cases").string = f"Institutions registered elsewhere in Kerala · {fmt_int(p['district_cases'])} cases"
    find_text(s, "Cases by complainant's state · 42 cases").string = f"Institutions registered outside Kerala · {fmt_int(p['state_cases'])} cases"
    imgs = s.select("[role=img]")
    hbars(imgs[0], p["institutions"], label_fn=lambda x: x if len(x) <= 30 else x[:28].rstrip() + "…")
    hbars(imgs[1], p["districts"])
    hbars(imgs[2], p["states"])

    # ---------------- LPR ----------------
    p = pg["lpr"]
    s = case_page("LPRCases", p, ["filing", "ccn", "title", "lpr", "status", "stage", None],
                  group_order=[x["label"] for x in p["statuses"]])
    s.find("h1").find_next_sibling("p").string = "Cases currently in the Long Pending Register, and cases revived out of it"
    find_text(s, "LPR Status · 471 cases").string = f"LPR Status · {len(p['rows'])} cases"
    donut(s.select_one("[role=img]"), p["statuses"])

    # ---------------- disposed register ----------------
    case_page("DisposedCases", pg["disposed"], ["filing", "ccn", "title", "outcome", "date", "nature", None],
              group_order=pg["disposed"]["group_order"], all_label="All Outcomes", extra_export=("order",))

    return js_pages


# ---------------------------------------------------------------------------
# client-side behaviour
# ---------------------------------------------------------------------------

CLIENT_JS = r"""
(function(){
  var D = window.__DASH__; if(!D) return;
  var MAXROWS = Infinity;
  function csv(rows, cols){
    var esc = function(v){ v = (v===null||v===undefined)?'':String(v); return /[",\n]/.test(v) ? '"'+v.replace(/"/g,'""')+'"' : v; };
    return [cols.map(esc).join(',')].concat(rows.map(function(r){ return cols.map(function(c){ return esc(r[c]); }).join(','); })).join('\n');
  }
  function save(name, text){
    var a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob(['﻿'+text], {type:'text/csv;charset=utf-8'}));
    a.download = name; document.body.appendChild(a); a.click();
    setTimeout(function(){ URL.revokeObjectURL(a.href); a.remove(); }, 500);
  }
  function caseList(filings){
    return filings.map(function(f){ var c = D.cases[f] || ['','','']; return {filing:f, court_case_number:c[0], title:c[1], stage:c[2]}; });
  }
  function rowDownload(cfg, r){
    var id = r.filing || r.station || r.advocate || 'rows';
    if(cfg.dl==='history'){
      var h = (D.history[r.filing]||[]).map(function(e){ return {date:e[0], event:e[1], type:e[2], detail:e[3]}; });
      save(r.filing+'_case_history.csv', csv(h, ['date','event','type','detail']));
    } else if(cfg.dl==='log'){
      save(r.filing+'_'+r._log.task_number+'_process_log.csv', csv([r._log], Object.keys(r._log)));
    } else if(cfg.dl==='list'){
      var rows = r._list ? r._list : caseList(r._list_filings||[]);
      save(String(id).replace(/[^A-Za-z0-9_-]+/g,'_')+'_cases.csv', csv(rows, rows.length?Object.keys(rows[0]):['filing']));
    }
  }
  Object.keys(D.pages).forEach(function(pid){
    var cfg = D.pages[pid], sec = document.getElementById('pg-'+pid); if(!sec) return;
    var tbody = sec.querySelector('tbody'); if(!tbody) return;
    var tpl = tbody.querySelector('tr').cloneNode(true);
    var st = {g:'__all', q:'', ds: cfg.datasets ? Object.keys(cfg.datasets)[0] : null};
    var note = document.createElement('p');
    note.style.cssText = 'margin:0;font-size:12px;color:rgb(91,100,117);text-align:right';
    tbody.closest('table').parentNode.after(note);
    function source(){ return cfg.datasets ? cfg.datasets[st.ds] : cfg.rows; }
    function filtered(){
      var q = st.q.toLowerCase();
      return source().filter(function(r){
        if(!cfg.datasets && st.g!=='__all' && (r._g||[]).indexOf(st.g)<0) return false;
        if(!q) return true;
        return cfg.cols.some(function(c){ return c && String(r[c]).toLowerCase().indexOf(q)>=0; });
      });
    }
    function render(){
      var rows = filtered(); tbody.innerHTML='';
      rows.slice(0, MAXROWS).forEach(function(r){
        var tr = tpl.cloneNode(true), tds = tr.children;
        cfg.cols.forEach(function(c, i){
          if(!tds[i]) return;
          if(c===null){ var b = tds[i].querySelector('button'); if(b){ b.onclick=function(){ rowDownload(cfg, r); }; } }
          else tds[i].textContent = (r[c]===null||r[c]===undefined) ? '—' : r[c];
        });
        tbody.appendChild(tr);
      });
      if(!rows.length){ var tr = document.createElement('tr'); var td = document.createElement('td'); td.colSpan = cfg.cols.length;
        td.style.cssText='padding:16px;text-align:center;color:rgb(91,100,117)'; td.textContent='No matching rows'; tr.appendChild(td); tbody.appendChild(tr); }
      note.textContent = rows.length.toLocaleString()+(rows.length===1?' row':' rows');
      if(cfg.datasets) topChart(rows);
    }
    function topChart(rows){
      var img = sec.querySelector('[role=img]'); if(!img) return;
      var items = Array.prototype.slice.call(img.children), max = rows.length ? rows[0].active : 1;
      items.forEach(function(row, i){
        var r = rows.slice().sort(function(a,b){ return b.active-a.active; })[i];
        row.style.display = r ? '' : 'none'; if(!r) return;
        var ps = row.querySelectorAll('p'); ps[0].textContent = r.advocate; ps[ps.length-1].textContent = r.active;
        var fill = row.querySelector('div > div > div') || row.querySelector('div > div');
        if(fill) fill.style.width = (100*r.active/Math.max(max,1)).toFixed(1)+'%';
      });
    }
    var group = sec.querySelector('[role=group]');
    if(group){
      var btns = Array.prototype.slice.call(group.querySelectorAll('button'));
      var on = btns[0].getAttribute('style'), off = (btns[1]||btns[0]).getAttribute('style');
      var onS = btns[0].querySelector('span').getAttribute('style'), offS = (btns[1]||btns[0]).querySelector('span').getAttribute('style');
      btns.forEach(function(b){
        b.addEventListener('click', function(){
          btns.forEach(function(x){ var a = x===b; x.setAttribute('aria-pressed', a); x.setAttribute('style', a?on:off); x.querySelector('span').setAttribute('style', a?onS:offS); });
          if(cfg.datasets) st.ds = b.getAttribute('data-g'); else st.g = b.getAttribute('data-g');
          render();
        });
      });
    }
    var input = sec.querySelector('input[type=search]');
    if(input) input.addEventListener('input', function(){ st.q = input.value.trim(); render(); });
    Array.prototype.forEach.call(sec.querySelectorAll('button'), function(b){
      if(/Export dataset/.test(b.textContent)) b.addEventListener('click', function(){
        save(pid+'_'+D.meta.reporting_month+'.csv', csv(filtered(), cfg.export));
      });
    });
    render();
  });
  Array.prototype.forEach.call(document.querySelectorAll('button'), function(b){
    if(b.textContent.trim()==='View cases') b.addEventListener('click', function(){
      window.open(location.href.split('#')[0]+'#DisposedCases', '_blank');
    });
  });
})();
"""


# --- Theme: match the GitHub monthly report (pucar-monthly-report) -----------------
# navy #0b1239 primary, emerald #10b981 accent, slate greys, system font stack.
SYSTEM_FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
THEME = {
    (11, 21, 51): "#0b1239",     # ink / headings
    (30, 58, 138): "#0b1239",    # primary blue -> navy
    (63, 74, 92): "#334155",     # dark slate text
    (91, 100, 117): "#64748b",   # muted text
    (100, 116, 139): "#64748b",
    (148, 163, 184): "#94a3b8",
    (203, 210, 220): "#cbd5e1",  # strong border
    (227, 231, 238): "#e2e8f0",  # border
    (238, 241, 246): "#f1f5f9",  # subtle fill
    (245, 247, 250): "#f8fafc",  # page bg
    (247, 249, 252): "#f8fafc",
    (6, 95, 70): "#065f46",      # green dark
    (4, 120, 87): "#10b981",     # green accent
    (230, 244, 238): "#ecfdf5",  # green light
    (185, 28, 28): "#ef4444",    # danger
    (194, 65, 12): "#f59e0b",    # warning
    (234, 88, 12): "#f59e0b",
    (202, 138, 4): "#f59e0b",
    (96, 165, 250): "#16205b",   # secondary series -> navy hover
    (124, 58, 237): "#475569",   # violet series -> slate
}


def apply_theme(html):
    def rgb_sub(m):
        key = tuple(int(x) for x in m.group(1, 2, 3))
        return THEME.get(key, m.group(0))
    html = re.sub(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", rgb_sub, html)
    html = re.sub(r"rgba\(\s*11\s*,\s*21\s*,\s*51\s*,", "rgba(11, 18, 57,", html)
    hexmap = {"#{:02x}{:02x}{:02x}".format(*k): v for k, v in THEME.items()}
    html = re.sub(r"#[0-9a-fA-F]{6}\b", lambda m: hexmap.get(m.group(0).lower(), m.group(0)), html)
    # font: drop the Google font, use the report's system stack
    html = re.sub(r'<link[^>]*fonts\.(googleapis|gstatic)\.com[^>]*>', "", html)
    html = html.replace("font-family: &quot;Nunito Sans&quot;, system-ui, sans-serif", "font-family: " + SYSTEM_FONT.replace("'", "&quot;"))
    html = re.sub(r"font-family: &quot;Nunito Sans&quot;[^;\"]*", "font-family: " + SYSTEM_FONT.replace("'", "&quot;"), html)
    html = html.replace("font-family:'Nunito Sans',system-ui,sans-serif", "font-family:" + SYSTEM_FONT)
    html = html.replace('"Nunito Sans", system-ui, sans-serif', SYSTEM_FONT.replace("'", '"'))
    return html


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", default=TEMPLATE)
    ap.add_argument("--data", default=DATA)
    args = ap.parse_args()

    with open(args.data) as f:
        d = json.load(f)
    with open(args.template, encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    js_pages = render(soup, d)

    client = {"meta": d["meta"], "pages": js_pages, "cases": d["case_index"], "history": d["history"]}
    data_tag = soup.new_tag("script")
    data_tag.string = "window.__DASH__=" + json.dumps(client, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + ";"
    js_tag = soup.new_tag("script")
    js_tag.string = CLIENT_JS
    soup.body.append(data_tag)
    soup.body.append(js_tag)

    os.makedirs(OUT_DIR, exist_ok=True)
    tag = datetime.now().strftime("%d%m%y_%H%M")
    html = apply_theme(str(soup))
    out = os.path.join(OUT_DIR, f"Court-Dashboard_{tag}.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[✓] Dashboard written: {out} ({len(html) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
