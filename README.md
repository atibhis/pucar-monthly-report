# 24x7 ON Court Kerala — Monthly Case Performance Report System

A self-contained analytical data pipeline and report generation engine for the **Special Court of Judicial Magistrate First Class (NI Act Sec 138), Kollam (KLKM52)**.

This repository extracts real-time transactional case data from the **ON Courts PostgreSQL / Metabase live database**, calculates key judicial efficiency metrics, and compiles:
1. **The Executive Case Performance Report (`OUTPUT/monthly_case_performance_report.html`)**: An executive-grade monthly digest featuring core intake/flow metrics up top and deep-linking to 20 detailed analytical registers.
2. **20 Interactive Drill-Down Views (`OUTPUT/CHECKLIST_VIEWS/`)**: Complete client-side searchable, sortable, paginated data views with dynamic month filters, stage-wise breakdown pills, and CSV download capabilities.
3. **The Executive Markdown Briefing (`OUTPUT/monthly_case_performance_note.md`)**: Clean text summary suitable for documentation and briefs.

---

## Visual Design & Aesthetics

The reports and interactive views use a curated executive palette:
* **Primary / Header**: Deep Midnight Navy (`#0b1239`, `#16205b`)
* **Accents / Highlights**: Vivid Emerald Green (`#10b981`, `#ecfdf5`, `#a7f3d0`)
* **Borders / Dividers**: Cool Slate Gray (`#e2e8f0`, `#cbd5e1`)
* **Background / Cards**: Clean Slate & White (`#f8fafc`, `#ffffff`)
* **Typography**: Modern system font stack (`-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`)

---

## Directory Structure

```
MONTHLY_PERFORMANCE_REPORT/
├── README.md                      # Complete system documentation
├── requirements.txt               # Python package dependencies
├── run_report.sh                  # One-click pipeline runner script
├── .env.example                   # Metabase API credentials template
├── .gitignore                     # Git ignore rules for environments and OS files
├── DATA/                          # Raw & aggregated transactional datasets
│   ├── monthly_checklist_data.json # Master JSON data payload for all 20 questions
│   ├── Q01_monthly_disposal_rates.csv
│   ├── Q02_all_disposals_master.csv
│   ├── Q04_silent_cases_not_in_lpr.csv
│   └── ... (20 CSV datasets)
├── OUTPUT/                        # Generated reports & interactive views
│   ├── monthly_case_performance_report.html # Master executive report
│   ├── monthly_case_performance_note.md     # Markdown executive briefing
│   └── CHECKLIST_VIEWS/           # 20 standalone interactive HTML data views
│       ├── Q01_disposal_rate.html
│       ├── Q02_disposal_mix.html
│       ├── Q03_cohort_disposal.html
│       ├── Q04_silent_cases.html
│       └── ... (Q01 to Q20)
└── SRC/                           # Pipeline source code
    ├── oncourts_api.py            # Metabase authentication & query wrapper
    ├── extract_monthly_checklist_data.py # Live data extraction engine
    └── generate_checklist_htmls.py       # HTML & markdown report generator
```

---

## Key Question Specifications & Standards

* **No Workflow Advice**: All 20 questions and summary cards report purely objective, factual data metrics (counts, percentages, durations, percentiles). No prescriptive advice, subjective recommendations, or artificial thresholds are included.
* **Court Complex Definition (Q1)**: In this jurisdiction (Special Court for NI Act Cases, Kollam - KLKM52), *"Court Complex"* refers to the **Police Station Court Complex** where cases originate and are tagged across the revenue district.
* **Month-Wise Filter (Q2)**: `Q02_disposal_mix.html` includes an interactive month dropdown that defaults to the latest month (`September 2026`), allowing instant client-side switching across any historical month while dynamically recomputing totals, outcome splits (withdrawn, judgement, dismissed), and percentages.
* **Stage-Wise Breakdown (Q4)**: `Q04_silent_cases.html` breaks down 60-day silent cases by judicial lifecycle stage (`Defect Correction: 26`, `Filing: 18`, `Cognizance: 2`, `Appearance: 1`, `Judgement: 1`, `Unclassified: 2`) with interactive clickable stage pills that filter the register.

---

## Setup & Installation

### 1. Requirements
* Python 3.9+
* Required packages:
```bash
pip install -r requirements.txt
```

### 2. Metabase Credentials (Only needed for live data extraction)
Copy `.env.example` to `.env` and fill in your Metabase credentials:
```bash
cp .env.example .env
```
*(If you only need to generate reports from existing data in `DATA/`, you do not need `.env` or network access).*

---

## How to Run

### Option A: Complete End-to-End Pipeline (Extract + Generate)
Extracts live data from Metabase and rebuilds all reports:
```bash
./run_report.sh
```
Or directly via Python:
```bash
python3 SRC/extract_monthly_checklist_data.py
python3 SRC/generate_checklist_htmls.py --all
```

### Option B: Offline Report Generation (Using existing `DATA/`)
Generates the master report and all 20 views instantly from pre-extracted data without connecting to the database:
```bash
./run_report.sh --generate-only
```
Or directly via Python:
```bash
python3 SRC/generate_checklist_htmls.py --all
```

---

## Committing to GitHub

To commit this folder to a standalone GitHub repository or branch:

```bash
cd MONTHLY_PERFORMANCE_REPORT
git init
git add .
git commit -m "feat: 24x7 ON Court monthly case performance report system"
git branch -M main
git remote add origin <your-github-repo-url>
git push -u origin main
```
