# 24x7 ON Court Kerala — Monthly Case Performance Report
**Court**: Special Court of Judicial Magistrate First Class (NI Act Sec 138), Kollam (KLKM52)  
**Period**: October 2026 • Live Database Pipeline

---

## Executive Summary (Core Metrics Up Top)

### 1. Matters
* **1,927 Total Active Matters**
* **1,251 in Appearance** (64.9% of active stock)
* Breakdown:
  - Summary Trial (`ST`): **1,748** (90.7%)
  - Misc Petition (`CMP`): **114** (5.9%)

### 2. Disposals
* **497 Total Disposed Cases**
* **0.5% clearance rate** (+9 disposals this month)
* **15.8% 6-month cohort disposal benchmark** (2026-03 (Filed 6 Months Ago))
* Breakdown:
  - Withdrawn / Settled: **378** (76.1%) — *+6 this month*
  - Dismissed: **71** (14.3%) — *+1 this month*
  - Judgement / Conviction: **40** (8.0%) — *+2 this month*

### 3. Hearings
* **979 Total Proceedings Recorded**
* **21.1 days median gap** between successive hearing dates
* **16.8% substantive trial ratio** (164 substantive vs 815 procedural)
* Breakdown:
  - Substantive Trial: **164** (16.8%) — Evidence / Plea / Bail
  - Awaiting Return Reports: **413** (42.2%) — Police / postal return delays
  - Take Steps / Re-issue: **254** (25.9%) — Procedural cycle

### 4. Process & Summons
* **13,590 Total Process Tasks Issued**
* **15.8% delivery rate** (2,149 delivered)
* **4,368 Summons • 7,313 Warrants**
* Breakdown:
  - Delivered: **2,149** (15.8%) — Successfully served
  - Expired: **2,534** (18.6%) — Unreturned at hearing date
  - Police Warrants (5+): **626 cases** — Repeat warrant backlog

---

## Secondary Server Setup (Detailed Registers)

*Key summary fields are shown up top. The remaining detailed registers and case-level queues are tracked on the secondary server setup below:*

### 1. Case Delay & Velocity Bottlenecks
* **MoM Disposal Rate vs 15% Floor (Police Station Complexes)**: Current rate **0.47%** (-14.53% deficit vs floor) across Police Station Court Complexes • [View Drill-down](CHECKLIST_VIEWS/Q01_disposal_rate.html)
* **60-Day Silent Cases (Stage-Wise Breakdown)**: **49 cases** active with zero hearings or orders (25 in Defect Correction, 18 in Filing, 6 In-Court) • [View Register](CHECKLIST_VIEWS/Q04_silent_cases.html)
* **Hearing Interval Outliers (>60 Days)**: **17 cases** with extreme gaps (P75: 27.9 days) • [View Register](CHECKLIST_VIEWS/Q05_hearing_gaps.html)
* **Cognizance Delay > 90 Days**: **31 cases** stalled (25 blocked by Delay Petitions) • [View Register](CHECKLIST_VIEWS/Q07_cognizance_bottlenecks.html)
* **Delay Condonation Repeat Cycles**: **66 cases** stuck in >5 DCA hearings • [View Register](CHECKLIST_VIEWS/Q09_dca_cycle.html)

### 2. Process Delivery & Police Enforcement
* **Unexecuted Warrants (>21 Working Days)**: **145 police stations** tracked • [View Station Table](CHECKLIST_VIEWS/Q11_warrant_laggards.html)
* **Repeat Warrant Backlog**: **626 cases** with ≥ 5 warrants issued • [View Defaulter Register](CHECKLIST_VIEWS/Q12_repeat_warrants.html)
* **Expired Process Tasks**: **928 tasks** stalled or expired (789 unpaid fee steps) • [View Register](CHECKLIST_VIEWS/Q13_expired_processes.html)
* **Clean Summons Cohorts**: Fast-track cohort velocity analysis • [View Cohorts](CHECKLIST_VIEWS/Q17_clean_summons.html)

### 3. Caseflow & Litigant Management
* **Mediation Duration (>6 Months)**: **305 cases** in mediation > 6 months (123 > 1 year) • [View Register](CHECKLIST_VIEWS/Q08_mediation_cases.html)
* **Bail Hearing Count**: **335 cases** requiring 3+ hearings to secure bail (2.8 avg hearings) • [View Register](CHECKLIST_VIEWS/Q10_bail_hearings.html)
* **Case Consolidation Pairs**: **14 case pairs** sharing identical complainant and accused (41 stuck cases) • [View Pairs](CHECKLIST_VIEWS/Q15_consolidation_pairs.html)
* **Top Advocates Caseload**: Top 15 advocates represent **30.2%** of active docket • [View Caseload Table](CHECKLIST_VIEWS/Q16_advocate_caseload.html)
* **First Appearance to Plea Recording**: **59 days** median engagement latency (Mean: 78.5d) • [View Register](CHECKLIST_VIEWS/Q18_engagement_latency.html)
* **Institutional & Bulk Complainants**: **105 entities** with ≥3 cases (HDFC Bank, Akshaya, Haritha) • [View Register](CHECKLIST_VIEWS/Q19_institutional_filers.html)

### 4. Court Administration & Data Quality
* **Long Pending Register (LPR) Movement**: **17 cases** in LPR; 448 awaiting CJM approval • [View Register](CHECKLIST_VIEWS/Q14_lpr_movements.html)
* **Data Quality Audit**: **17.9%** mobile number capture; 82.1% missing phone • [View Audit](CHECKLIST_VIEWS/Q20_data_quality.html)

---
*Automated Report • 24x7 ON Court Kerala • Live Metabase Database Pipeline*
