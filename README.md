# 24x7 ON Court Kerala — Monthly Case Performance Report

An automated data extraction pipeline and reporting suite for the **Special Court of Judicial Magistrate First Class (NI Act Sec 138), Kollam (KLKM52)**.

This repository generates:
1. **Executive Monthly Performance Report** (`OUTPUT/monthly_case_performance_report_{DDMMYY}.html`, e.g. `monthly_case_performance_report_161026.html`): High-level executive dashboard showing top-line intake/disposal/hearing metrics and deep links to all operational registers.
2. **20 Interactive Drill-Down Views** (`OUTPUT/CHECKLIST_VIEWS/`): Standalone client-side data views with live search, column sorting, month filters, stage-wise breakdown pills, and CSV downloads.
3. **Markdown Briefing** (`OUTPUT/monthly_case_performance_note_{DDMMYY}.md`, e.g. `monthly_case_performance_note_161026.md`): Clean text summary for documentation and briefs.

---

## Quick Start: View Existing Reports (No Setup Needed)

Pre-built reports and datasets are already committed in `OUTPUT/`. You can view them immediately in any browser:

### Option 1: View Live on GitHub Pages
- **Live URL**: [https://atibhis.github.io/pucar-monthly-report/](https://atibhis.github.io/pucar-monthly-report/) (automatically routes to the latest executive report)

### Option 2: Open Directly in Your Browser
- **Executive Master Report**: Open the latest report in `OUTPUT/` (e.g. `OUTPUT/monthly_case_performance_report_161026.html`) in Chrome, Safari, or Firefox.
- **Register Drill-Downs**: Open any file in `OUTPUT/CHECKLIST_VIEWS/` (e.g. `Q01_disposal_rate.html`, `Q04_silent_cases.html`).

### Option 3: Run a Local Web Server
```bash
# From the repository root
python3 -m http.server 8000
```
Then visit in your browser:
- Master Report: [http://localhost:8000/OUTPUT/monthly_case_performance_report_161026.html](http://localhost:8000/OUTPUT/monthly_case_performance_report_161026.html)
- Interactive Views Directory: [http://localhost:8000/OUTPUT/CHECKLIST_VIEWS/](http://localhost:8000/OUTPUT/CHECKLIST_VIEWS/)

---

## Installation & Setup

If you want to re-generate reports or run the live data extraction pipeline, set up your Python environment:

### 1. Clone the Repository
```bash
git clone git@github.com:atibhis/pucar-monthly-report.git
cd pucar-monthly-report
```

### 2. Set Up Python Environment
Requires **Python 3.9+**:
```bash
python3 -m venv .venv
source .venv/bin/activate       # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## How to Run

The repository supports two operating workflows:

### Workflow 1: Regenerate Reports from Existing Data (Offline Mode)
Re-builds all HTML reports and drill-down views using the pre-extracted data in `DATA/`. **No database connection or credentials required.**

```bash
./run_report.sh --generate-only
```
*Equivalent command:*
```bash
python3 SRC/generate_checklist_htmls.py --all
```
All outputs will be updated in the `OUTPUT/` directory.

---

### Workflow 2: Live Data Extraction & Rebuild (Full Pipeline)
Connects to the ON Courts Metabase / PostgreSQL instance, pulls live transactional case and hearing records, re-computes metrics, saves updated CSVs to `DATA/`, and re-renders all reports in `OUTPUT/`.

#### Step 1: Set Up Credentials
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Open `.env` and fill in your Metabase credentials:
```ini
MB_BASE_URL=https://your-metabase-instance.com
MB_USERNAME=your_email@domain.com
MB_PASSWORD=your_secure_password
MB_DATABASE_ID=2
```

#### Step 2: Run the Pipeline
```bash
./run_report.sh
```
> **7-Day Cadence Policy**: The script checks if a report was already generated within the last 7 days. If so, it will cleanly skip re-running. To force a run anyway, add `--force` (or `-f`):
> ```bash
> ./run_report.sh --force
> ```

*Equivalent step-by-step commands:*
```bash
# 1. Fetch live records from Metabase and save datasets to DATA/
python3 SRC/extract_monthly_checklist_data.py

# 2. Re-render executive report and 20 interactive views
python3 SRC/generate_checklist_htmls.py --all
```

---

## Navigating the Reports

### 1. Executive Performance Report (`OUTPUT/monthly_case_performance_report_{MMYY}.html`)
- **Top 4 Core Metric Cards**:
  - **Matters**: Total case docket (1,633), new monthly filings (+177), case type breakdown (Summary Trial 92.5% vs Misc Petitions 7.5%).
  - **Disposals**: Total clearance (445), monthly additions (+26), outcome mix (Withdrawn/Settled 76.9%, Dismissed 13.7%, Judgement 9.4%).
  - **Hearings**: Hearing count (1,017), median interval between successive dates (21.0 days), substantive trial ratio (14.7%).
  - **Process & Summons**: Total process tasks (3,521), overall delivery rate (49.3%), RPAD vs Police warrant breakdown.
- **Secondary Server Setup Table**:
  - Categorizes all 20 operational registers under 4 domains:
    1. *Case Delay & Velocity Bottlenecks* (Q01, Q04, Q05, Q07, Q09)
    2. *Process Delivery & Police Enforcement* (Q11, Q12, Q13, Q17)
    3. *Caseflow & Litigant Management* (Q08, Q10, Q15, Q16, Q18, Q19)
    4. *Administration & Data Quality Audit* (Q14, Q20)
  - Every row features an **Open Register →** link leading directly to the interactive data table.

### 2. Interactive Register Views (`OUTPUT/CHECKLIST_VIEWS/`)
Each of the 20 views is a self-contained HTML page featuring:
- **Instant Search**: Type any keyword into the search bar to filter records in real time across all columns.
- **Column Sorting**: Click any table header to sort ascending or descending (supports numeric and alphabetical).
- **CSV Export**: Click "📥 Export Dataset (CSV)" to download the raw underlying data file.
- **Specialized Filters**:
  - **Q02 (Disposal Mix)**: Interactive month dropdown (defaults to latest month `September 2026`) that dynamically re-computes KPIs and row counts.
  - **Q04 (Silent Cases)**: Stage-wise clickable pills (`Defect Correction`, `Filing`, `Cognizance`, `Appearance`, `Judgement`) with live counts.

### 3. Visual Status Indicators
To maintain a clean visual interface, text status flags are replaced with standard color indicators:
| Indicator | Color | Meaning |
| :--- | :--- | :--- |
| 🟢 | Emerald (`#10b981`) | **Meets Floor** (≥15% disposal rate) / **Active** / **Pass** / **Fast-Track Ready** |
| 🔴 | Red (`#ef4444`) | **Below Floor** (<15%) / **Silent Unparked Gap** / **Expired** / **Critical Lag** |
| 🟠 | Amber (`#f59e0b`) | **Pending Action** / **Pending Payment** / **Moderate Concern** |
| 🟣 | Purple (`#8b5cf6`) | **Long Pending Register (LPR)** (Parked dormant caseload) |

*Hovering over any indicator displays a tooltip explaining the status. Searchability is preserved via hidden searchable tokens.*

---

## Analytical Questions Index (Q01 – Q20)

| View | Analytical Focus | Dataset (`DATA/`) |
| :--- | :--- | :--- |
| **Q01** | Month-on-Month Disposal Rate vs 15% Floor | `Q01_monthly_disposal_rates.csv` |
| **Q02** | Disposal Mix by Outcome & Contested Pipeline | `Q02_all_disposals_master.csv` |
| **Q03** | 6-Month Cohort Disposal Benchmark | `Q03_cohort_disposal_rates.csv` |
| **Q04** | 60-Day Silent Cases & LPR Gap (Stage Breakdown) | `Q04_silent_cases_not_in_lpr.csv` |
| **Q05** | Hearing Interval Outliers (>60 Days) | `Q05_hearing_gap_cases_over_60d.csv` |
| **Q06** | Substantive vs Non-Substantive Hearing Breakdown | `Q06_hearing_substantive_reasons.csv` |
| **Q07** | Cognizance Bottlenecks (>90 Days) & Root Causes | `Q07_cognizance_bottlenecks.csv` |
| **Q08** | Mediation Duration (>6 & >12 Months) & Hearing Tail | `Q08_mediation_cases.csv` |
| **Q09** | Delay Condonation (DCA) Repeat Cycles (>5 Hearings)| `Q09_dca_cycle_cases.csv` |
| **Q10** | Bail Hearing Count & Time to Secure Bail | `Q10_bail_hearings_cases.csv` |
| **Q11** | Unexecuted Warrants Across Police Stations | `Q11_unexecuted_warrants_police_stations.csv` |
| **Q12** | Repeat Warrant Backlog (5+ Warrants Issued) | `Q12_cases_5plus_warrants.csv` |
| **Q13** | Process Tasks Expired or Stalled Before Dispatch | `Q13_expired_pending_process_tasks.csv` |
| **Q14** | Long Pending Register (LPR) Status & CJM Approvals| `Q14_lpr_cases_register.csv` |
| **Q15** | Complainant Evidence Multi-Case Party Pairs | `Q15_complainant_evidence_pairs.csv` |
| **Q16** | Top Advocates Caseload Concentration | `Q16_top_advocates_caseload.csv` |
| **Q17** | Clean Summons Cohorts & Fast-Track Velocity | `Q17_clean_summons_cohorts.csv` |
| **Q18** | First Appearance to Plea Recording Latency | `Q10_bail_hearings_cases.csv` |
| **Q19** | Institutional & Out-of-District Complainants | `Q19_institutional_filers.csv` |
| **Q20** | Data Quality Audit (Mobiles, Return Codes, Tagging)| `Q13_expired_pending_process_tasks.csv` |

---

## Directory Structure

```
pucar-monthly-report/
├── .env.example                   # Metabase credentials template
├── .gitignore                     # Git ignore rules (environments, caches, OS)
├── requirements.txt               # Dependencies: pandas, requests, python-dotenv
├── run_report.sh                  # Pipeline runner script
├── README.md                      # System documentation & usage guide
├── DATA/                          # Committed CSV datasets & master JSON payload
│   ├── monthly_checklist_data.json
│   ├── Q01_monthly_disposal_rates.csv
│   ├── Q02_all_disposals_master.csv
│   └── ... (20 CSV datasets)
├── OUTPUT/                        # Generated reports & interactive views
│   ├── monthly_case_performance_report_161026.html # Master executive report (DDMMYY tagged)
│   ├── monthly_case_performance_note_161026.md     # Markdown briefing (DDMMYY tagged)
│   └── CHECKLIST_VIEWS/           # 20 standalone interactive HTML data views
│       ├── Q01_disposal_rate.html
│       ├── Q02_disposal_mix.html
│       └── ... (Q01 to Q20)
└── SRC/                           # Pipeline source code
    ├── oncourts_api.py            # Metabase authentication & query wrapper
    ├── extract_monthly_checklist_data.py # Live data extraction engine
    └── generate_checklist_htmls.py       # HTML & markdown report generator
```

---

