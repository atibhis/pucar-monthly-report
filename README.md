# Court Dashboard — 24x7 ON Court Kerala

A monthly dashboard for the Special Court of Judicial Magistrate First Class (NI Act Sec 138), Kollam. Each run pulls live
data from Oncourts-Live (Metabase, database #3), fills the dashboard design template and writes two files:

* the **full dashboard**: one self-contained HTML file with every indicator page, case lists, search, CSV export and per-case histories
* an **email summary**: key numbers only, email-safe HTML

The run can also email both: the summary goes in the email body and the dashboard is attached.

---

## Repository structure

```
.
├── run_court_dashboard.sh            # Entry point: extract → render → email body → (optional) send
├── requirements.txt                  # pandas, numpy, beautifulsoup4, python-dotenv
├── .env.example                      # Credential keys; copy to .env
├── SRC/
│   ├── court_dashboard_sql.py        # Every SQL query behind the dashboard (one per dataset)
│   ├── extract_court_dashboard.py    # Logs in to Metabase, runs the queries, builds DATA/court_dashboard_data.json
│   ├── render_court_dashboard.py     # Fills TEMPLATE/Court-Dashboard.html → OUTPUT/Court-Dashboard_<DDMMYY_HHMM>.html
│   ├── render_email_body.py          # Builds OUTPUT/Court-Dashboard_email_<DDMMYY_HHMM>.html
│   └── send_court_dashboard_email.py # Sends the email through Gmail SMTP
│
│   Local only (git-ignored, never commit):
├── .env                              # Credentials
├── TEMPLATE/Court-Dashboard.html     # Design template; contains real case data, so it is handed over separately
├── DATA/                             # Raw query results, CSVs and the JSON payload from the last pull
└── OUTPUT/                           # Generated dashboards and email bodies
```

---

## How to run (any system)

You need **Python 3.9+** and network access to `https://oncourts.kerala.gov.in/pucar-dashboard`.

### 1. Get the code and install dependencies

macOS / Linux:
```bash
git clone git@github.com:atibhis/pucar-monthly-report.git
cd pucar-monthly-report
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows (PowerShell):
```powershell
git clone git@github.com:atibhis/pucar-monthly-report.git
cd pucar-monthly-report
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Add the template and credentials

1. Put the design template at `TEMPLATE/Court-Dashboard.html`. You will receive it separately; it is not in git.
2. Copy `.env.example` to `.env` and fill it in:
   ```ini
   METABASE_USER=...            # Metabase login with read access to DB #3
   METABASE_PASS=...
   GMAIL_USER=...               # only needed for sending
   GMAIL_APP_PASSWORD=...       # Gmail App Password (Google Account → Security → App passwords), not the account password
   ```

### 3. Run

macOS / Linux:
```bash
./run_court_dashboard.sh                     # live pull; reporting month = last complete month (IST)
./run_court_dashboard.sh --month 2026-10     # a specific reporting month
./run_court_dashboard.sh --offline           # re-render from the last pull in DATA/, without querying
./run_court_dashboard.sh --send              # also email it to GMAIL_USER (use this as a test)
./run_court_dashboard.sh --send-to "a@example.com, b@example.com"   # email these recipients
DASHBOARD_URL=https://host/path.html ./run_court_dashboard.sh --send-to "..."  # once hosted: the email links to it
```

Windows has no `bash` unless you use Git Bash or WSL; both run the commands above unchanged. Without them, run the
steps by hand:
```powershell
python SRC\extract_court_dashboard.py                 # add --month 2026-10 or --offline as needed
python SRC\render_court_dashboard.py
python SRC\render_email_body.py --dashboard OUTPUT\Court-Dashboard_<DDMMYY_HHMM>.html
python SRC\send_court_dashboard_email.py --dashboard OUTPUT\Court-Dashboard_<DDMMYY_HHMM>.html --body OUTPUT\Court-Dashboard_email_<DDMMYY_HHMM>.html [--to "a@example.com"]
```

A live pull takes a few minutes. Every output carries a `DDMMYY_HHMM` timestamp, so earlier runs are never overwritten.
Open the dashboard in any browser; it works offline.

---

## Rules followed

### Data
* **Live data only.** Every number comes from a SQL query against Oncourts-Live, run at the time of the pull. Nothing
  is hard-coded, estimated or carried over from an earlier run. Every query is in `SRC/court_dashboard_sql.py` and
  runs unchanged as a Metabase native question (replace `$M_START$` with e.g. `2026-10-01 00:00:00`).
* **Structured fields only.** Metrics use order types, hearing types, task statuses and application types. No metric
  reads free-text order wording or police remarks.
* **No guessing.** If a value is not recorded, it is shown as not recorded, not filled in. For example, a disposed case
  with no disposal order has no disposal date: it counts in the totals but is left out of every month-wise or 30-day
  figure. Addresses are counted only under the exact official district or state name.
* **Complete tables.** Every table shows every row; nothing is cut off.
* **Dates** use IST. Month buckets are calendar months in IST.
* **SQL note:** never put a bare `?` in a query. Metabase's JDBC driver treats it as a bind parameter.

### Privacy
* The dashboard, `DATA/`, `OUTPUT/` and the template hold party names, case numbers and case histories. They are
  git-ignored. Never commit them and never host them publicly; this repository deliberately has no web deployment.
* Credentials live only in `.env`. Never commit it, print it or paste it anywhere.
* Before emailing anyone new, run `--send` to send a test to yourself first, and send only to people authorised to see
  case-level data.

### Metric definitions
* **Filed case**: `filingdate` set and status not draft / pending payment / pending signature. **Disposed**: `outcome` set; disposal date = first published disposal order (including composite orders). **Pending** = filed − disposed. ST = court case number `ST/…`; CMP = has a CMP number but no ST number.
* **Reporting month** = last complete month (IST) unless `--month` is given. Arrows on case and process counts = change over the last 30 days. Arrows on hearing statistics = reporting month vs previous month.
* **Hearings**: completed hearings in the month. Duration = median of recorded `hearingdurationinmillis` (> 0), no cut-off. Median gap = median days between successive hearing dates for a case.
* **Processes**: `dristi_task` NOTICE / SUMMONS / WARRANT. Served: notice DELIVERED, summons DELIVERED/EXECUTED, warrant EXECUTED.
* **Monthly disposal %** = disposals in the month ÷ pending stock at the start of the month (target floor 15%).
* **Silent**: pending, not in LPR, no future hearing, and no order / hearing / task / application for 60+ days.
* **Hearing gap outliers**: pending cases whose median gap (completed + scheduled hearings) is over 60 days.
* **Cognizance delay**: stage Cognizance, no TAKE_COGNIZANCE order, 90+ days since registration. Reason (the first that applies): delay-condonation application pending; no notice task; notice issued but none DELIVERED; notice served.
* **DCA cycle**: pending cases with more than 5 completed delay-condonation hearings, plus the number of DELAY_CONDONATION applications filed.
* **Unexecuted warrants**: iCOPS warrants (excluding FAILED pushes) not delivered and booked more than 21 working days ago.
* **Repeat warrants**: 5+ warrant orders. Chart = recorded status of each case's most recent warrant task. Executed = task EXECUTED or iCOPS DELIVERED.
* **Process failures**: a hearing date in the last 180 days has passed while the task is still PENDING_PAYMENT, ISSUE_* (issued, not sent) or EXPIRED.
* **Clean first summons**: cohort = month of the first cognizance order. Clean = an ACCEPT_BAIL order (the accused's first recorded appearance), no warrant / proclamation / attachment order, and at most one summons order.
* **Mediation**: cases with a REFERRAL_CASE_TO_ADR order. Days = referral → disposal order, or → today while pending. Hearings = completed hearings since referral.
* **Bail**: hearings from the first BAIL-purpose hearing (or the grant hearing) up to the first ACCEPT_BAIL order.
* **Joint scheduling**: same complainant and accused (from the case title), 2+ pending cases at the same trial stage.
* **Advocates**: active vakalats. Avg disposal = filing → disposal order. Avg trial = first evidence / S.351 / arguments hearing → disposal order, or today while pending. Undated disposals are not averaged.
* **Appearance → plea**: first ACCEPT_BAIL order → first completed PLEA hearing.
* **Institutional**: complainant type REPRESENTATIVE, pending cases. District and state come from the company's registered address. Individual addresses are encrypted and not used.
* **LPR**: In LPR = `lifecyclestatus='LPR'`. Revived = has a move-out-of-LPR order.
* **Disposed cases register** ("View cases"): every disposed case with its outcome, disposal-order date and nature of disposal as recorded.
