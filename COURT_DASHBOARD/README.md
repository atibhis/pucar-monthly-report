# Court Dashboard (live)

Fills the Court Dashboard design template with live data from Oncourts-Live (Metabase DB #3), and can email it.

## Setup
1. `pip install -r ../requirements.txt` (pandas, numpy, beautifulsoup4, python-dotenv).
2. Put the design template at `COURT_DASHBOARD/TEMPLATE/Court-Dashboard.html`. It contains sample case data, so it is
   git-ignored and must be copied in by hand. `../Court-Dashboard.html` also works.
3. Add credentials to `.env` in the repository root (git-ignored):
   ```ini
   METABASE_USER=...
   METABASE_PASS=...
   GMAIL_USER=your_address@gmail.com      # only needed for emailing
   GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx # a Gmail App Password, not the account password
   ```
   Metabase access goes through `../SRC/oncourts_api.py`.

## Run
```
./run_court_dashboard.sh [--month YYYY-MM] [--offline] [--send | --send-to "a@x.com, b@y.com"]
```
* No flags: pulls live data and writes the dashboard and email body to `OUTPUT/` (git-ignored, timestamped).
* `--offline`: re-renders from the last pull without querying.
* `--send`: also emails the summary (body) and the full dashboard (attachment) to `GMAIL_USER`. Use this as a test.
* `--send-to "a, b"`: emails the listed recipients instead.
* `DASHBOARD_URL=https://… ./run_court_dashboard.sh --send-to "…"`: once the dashboard is hosted, the email links to it.

`DATA/`, `OUTPUT/` and the template hold party names and case histories. They are never committed; do not host
the dashboard publicly (this repository is deployed to GitHub Pages).

| File | Purpose |
|---|---|
| `SRC/court_dashboard_sql.py` | All SQL, one query per dashboard dataset. Each runs as-is in a Metabase native question (replace `$M_START$` with e.g. `2026-10-01 00:00:00`). |
| `SRC/extract_court_dashboard.py` | Runs the queries and builds `DATA/court_dashboard_data.json` (+ raw CSVs in `DATA/csv/`, raw results in `DATA/raw_results.json`). |
| `SRC/render_court_dashboard.py` | Fills the template, embeds the data, and wires up search / pills / CSV export / row downloads. |
| `SRC/render_email_body.py` | Email-safe summary (inline styles, no scripts). With `DASHBOARD_URL` set it links to the hosted dashboard; otherwise it points readers to the attachment. |
| `SRC/send_court_dashboard_email.py` | Sends the email through Gmail SMTP. |
| `OUTPUT/Court-Dashboard_<DDMMYY_HHMM>.html`, `OUTPUT/Court-Dashboard_email_<DDMMYY_HHMM>.html` | Outputs (timestamped per run). |

## Definitions
* **Filed case**: `filingdate` set and status not draft / pending payment / pending signature. **Disposed**: `outcome` set; disposal date = first published disposal order (incl. composite orders). Disposed cases with no such order have no disposal date: they are in the totals but left out of every month-wise / 30-day figure (never estimated). **Pending** = filed − disposed. ST = court case number `ST/…`; CMP = has CMP number but no ST number.
* **Reporting month** = last complete month (IST) unless `--month`. Arrows on case and process counts = change over the last 30 days. Arrows on hearing statistics = reporting month vs previous month.
* **Hearings**: completed hearings in the month. Duration = median of recorded `hearingdurationinmillis` (> 0), no cut-off. Median gap = median days between successive hearing dates for a case.
* **Processes**: `dristi_task` NOTICE / SUMMONS / WARRANT. Served: notice DELIVERED, summons DELIVERED/EXECUTED, warrant EXECUTED.
* **Monthly disposal %** = disposals in month ÷ pending stock at the start of the month (target floor 15%).
* **Silent**: pending, not in LPR, no future hearing, no order / hearing / task / application / case update for 60+ days.
* **Hearing gap outliers**: pending cases whose median gap (completed + scheduled hearings) is over 60 days.
* **Cognizance delay**: stage Cognizance, no TAKE_COGNIZANCE order, 90+ days since registration. Reason (first that applies): delay-condonation application pending; no notice task; notice issued but none DELIVERED; notice served.
* **DCA cycle**: pending cases with more than 5 completed delay-condonation hearings. Also shows the number of DELAY_CONDONATION applications filed.
* **Unexecuted warrants**: iCOPS warrants (excluding FAILED pushes) not delivered and booked more than 21 working days ago.
* **Repeat warrants**: 5+ warrant orders. Chart = recorded task status of each case's most recent warrant task. Executed = task EXECUTED or iCOPS DELIVERED.
* **Process failures**: hearing date in the last 180 days has passed while the task is still recorded as PENDING_PAYMENT, ISSUE_* (issued, not sent) or EXPIRED.
* **Clean first summons**: cohort = month of first cognizance order. Clean = ACCEPT_BAIL order (accused's first recorded appearance), no warrant / proclamation / attachment order, at most one summons order.
* **Mediation**: cases with a REFERRAL_CASE_TO_ADR order. Days = referral → disposal order, or → today while pending. Hearings = completed hearings since referral.
* **Bail**: hearings from the first BAIL-purpose hearing (or the grant hearing) up to the first ACCEPT_BAIL order.
* **Joint scheduling**: same complainant + accused (from the case title), 2+ pending cases at the same trial stage.
* **Advocates**: active vakalats. Avg disposal = filing → disposal order. Avg trial = first evidence / S.351 / arguments hearing → disposal order, or today while pending. Undated disposals are not averaged.
* **Appearance → plea**: first ACCEPT_BAIL order → first completed PLEA hearing.
* **Institutional**: complainant type REPRESENTATIVE, pending cases. District and state come from the company's registered address and are counted only when recorded under the exact official name (misspellings / localities are left out, not mapped). Individual addresses are encrypted.
* **LPR**: In LPR = `lifecyclestatus='LPR'`. Revived = has a move-out-of-LPR order.
* **Disposed cases register** ("View cases"): every disposed case with outcome, disposal-order date and nature of disposal as recorded.
* No metric reads free-text order wording or police remarks; every table shows all rows.
