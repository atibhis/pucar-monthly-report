# 24x7 ON Court Kerala — Monthly Case Performance Report
**Court**: Special Court of Judicial Magistrate First Class (NI Act Sec 138), Kollam (KLKM52)  
**Period**: October 2026 • Live Database Pipeline

---

## Executive Summary (Core Metrics Up Top)

### 1. Matters
* **1,633 Total Active Matters**
* **+177 new** (10.8% intake)
* **895 in Appearance** (54.8% of active stock)
* Breakdown:
  - Summary Trial (`ST`): **1,511** (92.5%) — *+163 new*
  - Misc Petition (`CMP`): **122** (7.5%) — *+14 new*

### 2. Disposals
* **445 Total Disposed Cases**
* **21.0% clearance rate** (+26 disposals this month)
* **15.8% 6-month cohort disposal benchmark** (March 2026 cohort)
* Breakdown:
  - Withdrawn / Settled: **342** (76.9%) — *+15 this month*
  - Dismissed: **61** (13.7%) — *+6 this month*
  - Judgement / Conviction: **42** (9.4%) — *+5 this month*

### 3. Hearings
* **1,017 Total Proceedings Recorded**
* **21.0 days median gap** between successive hearing dates
* **14.7% substantive trial ratio** (149 substantive vs 868 procedural)
* Breakdown:
  - Substantive Trial: **149** (14.7%) — Evidence / Plea / Bail
  - Awaiting Return Reports: **406** (39.9%) — Police / postal return delays
  - Take Steps / Re-issue: **238** (23.4%) — Procedural cycle

### 4. Process & Summons
* **3,521 Total Process Tasks Issued**
* **49.3% delivery rate** (1,279 delivered)
* **82.5% RPAD / Post • 17.5% Police**
* Breakdown:
  - Delivered: **1,279** (49.3%) — Successfully served
  - Expired: **780** (22.1%) — Unreturned at hearing date
  - Police Warrants (5+): **534** (15.2%) — Repeat warrant backlog (1.8% police execution rate)

---

## Secondary Server Setup (Detailed Registers)

*Key summary fields are shown up top. The remaining detailed registers and case-level queues are tracked on the secondary server setup below:*

### 1. Case Delay & Velocity Bottlenecks
* **MoM Disposal Rate vs 15% Floor (Police Station Complexes)**: Current rate **1.59%** (-13.41% deficit vs floor) across Police Station Court Complexes • [View Drill-down](CHECKLIST_VIEWS/Q01_disposal_rate.html)
* **60-Day Silent Cases (Stage-Wise Breakdown)**: **50 cases** active with zero hearings or orders (88% stalled in pre-registration: **26 in Defect Correction**, **18 in Filing**, 2 in Cognizance, 1 in Appearance, 1 in Judgement, 2 Unclassified) • [View Register](CHECKLIST_VIEWS/Q04_silent_cases.html)
* **Hearing Interval Outliers (>60 Days)**: **20 cases** with extreme gaps (P75: 27 days) • [View Register](CHECKLIST_VIEWS/Q05_hearing_gaps.html)
* **Cognizance Delay > 90 Days**: **53 cases** stalled (38 blocked by Delay Petitions) • [View Register](CHECKLIST_VIEWS/Q07_cognizance_bottlenecks.html)
* **Delay Condonation Repeat Cycles**: **55 cases** stuck in >5 DCA hearings • [View Register](CHECKLIST_VIEWS/Q09_dca_cycle.html)

### 2. Process Delivery & Police Enforcement
* **Unexecuted Warrants (>21 Working Days)**: **145 police stations** tracked (1.8% execution rate) • [View Station Table](CHECKLIST_VIEWS/Q11_warrant_laggards.html)
* **Repeat Warrant Backlog**: **534 cases** with ≥ 5 warrants issued • [View Defaulter Register](CHECKLIST_VIEWS/Q12_repeat_warrants.html)
* **Expired Process Tasks**: **780 tasks** expired before hearing return was recorded • [View Register](CHECKLIST_VIEWS/Q13_expired_processes.html)
* **Clean Summons Cohorts**: Fast-track cohort velocity analysis • [View Cohorts](CHECKLIST_VIEWS/Q17_clean_summons.html)

### 3. Caseflow & Litigant Management
* **Mediation Duration (>6 Months)**: **305 cases** in mediation > 6 months (123 > 1 year) • [View Register](CHECKLIST_VIEWS/Q08_mediation_cases.html)
* **Bail Hearing Count**: **306 cases** requiring 3+ hearings to secure bail • [View Register](CHECKLIST_VIEWS/Q10_bail_hearings.html)
* **Case Consolidation Pairs**: **31 case pairs** sharing identical complainant and accused • [View Pairs](CHECKLIST_VIEWS/Q15_consolidation_pairs.html)
* **Top Advocates Caseload**: Top 15 advocates represent **42.1%** of active docket • [View Caseload Table](CHECKLIST_VIEWS/Q16_advocate_caseload.html)
* **First Appearance to Plea Recording**: **59 days** median engagement latency • [View Register](CHECKLIST_VIEWS/Q18_engagement_latency.html)
* **Institutional & Bulk Complainants**: **101 entities** with ≥3 cases (HDFC Bank, Akshaya, Haritha) • [View Register](CHECKLIST_VIEWS/Q19_institutional_filers.html)

### 4. Court Administration & Data Quality
* **Long Pending Register (LPR) Movement**: **18 cases** in LPR; 3 revived upon appearance • [View Register](CHECKLIST_VIEWS/Q14_lpr_movements.html)
* **Data Quality Audit**: **17.7%** mobile number capture; 28.7% blank police returns • [View Audit](CHECKLIST_VIEWS/Q20_data_quality.html)

---
*Automated Report • 24x7 ON Court Kerala • Live Metabase Database Pipeline*
