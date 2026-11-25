#!/usr/bin/env python3
"""
Email-safe summary of the Court Dashboard (inline styles, tables, no scripts),
styled like the GitHub monthly report. Links point at the full dashboard.

  python3 SRC/render_email_body.py --dashboard OUTPUT/Court-Dashboard_<ts>.html [--link URL]

Without --link (not hosted yet) the email carries no links and points to the attached dashboard.
Writes OUTPUT/Court-Dashboard_email_<DDMMYY_HHMM>.html (same timestamp as the dashboard).
"""
import argparse
import html
import json
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "DATA", "court_dashboard_data.json")
OUT_DIR = os.path.join(BASE, "OUTPUT")

NAVY, GREEN, RED, MUTED, BORDER, BG, SUBTLE = "#0b1239", "#10b981", "#ef4444", "#64748b", "#e2e8f0", "#f8fafc", "#f1f5f9"
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"

INDICATORS = [
    ("#Artboard-4roy", "Monthly case disposal rate"),
    ("#Artboard-e3az", "Cases inactive for more than 60 days"),
    ("#Artboard-3rf7", "Hearings set more than 60 days apart"),
    ("#CognizanceDelay", "Cognisance took more than 60 days"),
    ("#DelayCondonation", "Delay application steps repeated"),
    ("#Artboard-9to3", "Warrants not executed after 21 days"),
    ("#RepeatWarrants", "Cases with 5+ warrants issued"),
    ("#ProcessFailure", "Processes expired before hearing"),
    ("#CleanFirstSummons", "Accused joined on first summons"),
    ("#MediationOutliers", "In mediation more than 6 months"),
    ("#BailHearings", "3+ bail hearings needed to secure bail"),
    ("#JointScheduling", "Cases with same parties"),
    ("#AdvocateStats", "Advocate-wise statistics"),
    ("#AppearanceToPlea", "Appearance to recording of plea"),
    ("#InstitutionalComplainants", "Institutional complainant caseload"),
    ("#LPRCases", "Long Pending Register (LPR)"),
]


def fmt(v):
    if isinstance(v, float) and not v.is_integer():
        return f"{v:,.1f}"
    return f"{int(round(v)):,}"


def delta(d, up_is_good=True, unit=""):
    if d is None or d == 0:
        return f'<span style="color:{MUTED};">no change</span>'
    good = (d > 0) == up_is_good
    arrow = "&uarr;" if d > 0 else "&darr;"
    sign = "+" if d > 0 else "&minus;"
    mag = abs(d)
    mag = f"{mag:,.1f}" if isinstance(mag, float) else f"{mag:,}"
    return f'<span style="color:{GREEN if good else RED}; font-weight:700;">{arrow} {sign}{mag}{unit}</span>'


def tile(label, pair, sub, up_is_good=True, suffix="", dunit="", width="33%"):
    v, d = pair
    return f'''<td width="{width}" valign="top" style="padding:6px;">
  <div style="background:#ffffff; border:1px solid {BORDER}; border-radius:10px; padding:16px 18px;">
    <div style="font-size:11px; font-weight:700; color:{MUTED}; text-transform:uppercase; letter-spacing:0.8px;">{label}</div>
    <div style="font-size:30px; font-weight:800; color:{NAVY}; line-height:1.15; letter-spacing:-0.5px; margin-top:6px;">{fmt(v)}{suffix}</div>
    <div style="font-size:12px; margin-top:4px;">{delta(d, up_is_good, dunit)}</div>
    <div style="font-size:11px; color:{MUTED}; margin-top:2px;">{sub}</div>
  </div></td>'''


def section(title):
    return f'<div style="font-size:15px; font-weight:800; color:{NAVY}; margin:22px 0 8px 6px;">{title}</div>'


def build(d, link):
    m, meta = d["main"], d["meta"]
    month, prev = meta["month_name"], meta["prev_month_name"]
    year = meta["reporting_month"][:4]
    l30 = "vs 30 days ago"
    vs = f"vs {prev}"

    cases = "".join([
        tile("Cases filed", m["filed"], l30),
        tile("Cases disposed", m["disposed"], l30 + (f' &middot; <a href="{html.escape(link)}#DisposedCases" style="color:{GREEN}; font-weight:700; text-decoration:none;">View cases &rarr;</a>' if link else "")),
        tile("Cases pending", m["pending"], f'ST {fmt(m["pending_st"][0])} &middot; CMP {fmt(m["pending_cmp"][0])}', up_is_good=False),
    ])
    hearings_a = "".join([
        tile(f"Hearings in {month}", m["hearings"], vs, width="50%"),
        tile("Median hearing gap", m["median_gap"], f"days, {vs}", up_is_good=False, width="50%"),
    ])
    hearings_b = "".join([
        tile("Hearings per day", m["per_day"], vs, width="50%"),
        tile("Median hearing duration", m["duration"], f"min, {vs}", width="50%"),
    ])
    process = "".join([
        tile("Processes issued", m["issued_total"], l30),
        tile("Served / executed", m["served_total"], l30),
        tile("Warrants executed", m["served_warrant"], f'of {fmt(m["issued_warrant"][0])} issued'),
    ])

    rows = []
    for i, (href, name) in enumerate(INDICATORS):
        val, note = d["diagnostics"].get(href, ["—", None])
        bg = "#ffffff" if i % 2 == 0 else BG
        note_html = f'<div style="font-size:11px; color:{MUTED};">{html.escape(note)}</div>' if note else ""
        rows.append(f'''<tr style="background:{bg};">
  <td style="padding:10px 14px; border-top:1px solid {BORDER}; font-size:13px; color:{NAVY}; font-weight:600;">{html.escape(name)}</td>
  <td style="padding:10px 14px; border-top:1px solid {BORDER}; font-size:13px; color:{NAVY}; font-weight:800; white-space:nowrap; text-align:right;">{html.escape(val)}{note_html}</td>
  {f'<td style="padding:10px 14px; border-top:1px solid {BORDER}; font-size:12px; text-align:right; white-space:nowrap;"><a href="{html.escape(link + href)}" style="color:{GREEN}; font-weight:700; text-decoration:none;">Open &rarr;</a></td>' if link else ""}
</tr>''')

    if link:
        cta = (f'<div style="text-align:center; margin:28px 0 6px 0;"><a href="{html.escape(link)}" style="display:inline-block; '
               f'background:{NAVY}; color:#ffffff; font-weight:700; font-size:14px; padding:12px 26px; border-radius:8px; '
               f'text-decoration:none;">Open full dashboard &rarr;</a></div>')
    else:
        cta = (f'<div style="margin:24px 6px 6px 6px; background:{BG}; border:1px solid {BORDER}; border-left:4px solid {GREEN}; '
               f'border-radius:6px; padding:14px 18px; font-size:13px; color:{NAVY}; line-height:1.5;">'
               f'<b>Full dashboard attached.</b> Download the attached HTML file and open it in a browser (Chrome, Edge, Safari) '
               f'for every indicator page, case lists, search, CSV export and per-case histories.</div>')
    return f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Court Dashboard — {month} {year}</title></head>
<body style="font-family:{FONT}; background-color:{BG}; margin:0; padding:32px 16px; color:{NAVY};">
<div style="max-width:760px; margin:0 auto; background:#ffffff; border-radius:12px; border:1px solid {BORDER}; overflow:hidden;">
  <div style="padding:28px 32px 20px 32px; border-bottom:1px solid {BORDER};">
    <div style="font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:1px; color:{MUTED}; margin-bottom:6px;">24x7 ON Court Kerala</div>
    <h1 style="font-size:24px; font-weight:800; color:{NAVY}; margin:0 0 6px 0; letter-spacing:-0.5px;">Court Dashboard — {month} {year}</h1>
    <div style="font-size:13px; color:{MUTED};">Special Court of Judicial Magistrate First Class (NI Act Sec 138) &bull; Kollam</div>
    <div style="font-size:12px; color:{GREEN}; font-weight:600; margin-top:8px;">Live data &bull; generated {html.escape(meta["generated_at"])}</div>
  </div>
  <div style="padding:14px 26px 28px 26px;">
    {section("Cases")}
    <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;"><tr>{cases}</tr></table>
    {section("Hearings")}
    <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;"><tr>{hearings_a}</tr><tr>{hearings_b}</tr></table>
    {section("Processes")}
    <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;"><tr>{process}</tr></table>
    {section("Diagnostic indicators")}
    <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse; border:1px solid {BORDER}; border-radius:8px; margin:0 6px; width:calc(100% - 12px);">
      <tr style="background:{NAVY};">
        <th align="left" style="padding:10px 14px; font-size:11px; color:#ffffff; text-transform:uppercase; letter-spacing:0.6px;">Indicator</th>
        <th align="right" style="padding:10px 14px; font-size:11px; color:#ffffff; text-transform:uppercase; letter-spacing:0.6px;">{month}</th>
        {"<th></th>" if link else ""}
      </tr>
      {"".join(rows)}
    </table>
    {cta}
    <div style="font-size:11px; color:{MUTED}; text-align:center; margin-top:10px; line-height:1.5;">{html.escape(meta["delta_note"])}<br>Source: {html.escape(meta["source"])}</div>
  </div>
</div>
</body></html>
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dashboard", required=True, help="path to the full dashboard HTML from this run")
    ap.add_argument("--link", help="URL of the hosted dashboard. Without it the email has no links and says the dashboard is attached.")
    args = ap.parse_args()

    dash = os.path.abspath(args.dashboard)
    link = args.link or None
    ts = re.search(r"Court-Dashboard_(\d{6}_\d{4})\.html$", dash)
    tag = ts.group(1) if ts else "untimed"

    with open(DATA) as f:
        d = json.load(f)
    out = os.path.join(OUT_DIR, f"Court-Dashboard_email_{tag}.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(build(d, link))
    print(f"[✓] Email body written: {out}")


if __name__ == "__main__":
    main()
