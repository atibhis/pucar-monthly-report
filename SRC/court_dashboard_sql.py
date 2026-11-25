"""
Live SQL for the Court Dashboard (Court-Dashboard.html).

Every query runs against Metabase database #3 (Oncourts-Live, PostgreSQL) through
/api/dataset/json. Each one is self-contained and can be pasted into a Metabase native
question; the only token is $M_START$ (the reporting month, 'YYYY-MM-01'). "Today" is
always now(). All month bucketing is done in IST (Asia/Kolkata).

Notes
-----
* Do not use a bare '?' in SQL sent through Metabase/JDBC: it is treated as a bind
  placeholder. Use jsonb_exists() / regex quantifiers like {0,1} instead.
* "Filed case": filingdate is set and the case has left the e-filing draft / payment /
  signing states.
* "Disposed": dristi_cases.outcome is set. Disposal date = first published disposal order
  (JUDGEMENT, WITHDRAWAL_ACCEPT, DISMISS_CASE, ABATE_CASE, SETTLEMENT_ACCEPT, else
  ADMIT_DISMISS_CASE), including items inside composite orders. A disposed case with no
  such order has no disposal date (it is never given an estimated one); it is counted in
  the disposed totals but left out of every month-wise / 30-day figure.
* Every classification below uses structured fields only (order types, hearing types,
  task / application statuses, case fields). Nothing is read out of free-text order
  wording or police remarks.
"""

# ---------------------------------------------------------------------------
# Shared CTE fragments
# ---------------------------------------------------------------------------

PARAMS = """params as (
  select (timestamp '$M_START$')                         as m_start,
         (timestamp '$M_START$' + interval '1 month')    as m_end,
         (timestamp '$M_START$' - interval '1 month')    as pm_start,
         (extract(epoch from now()) * 1000)::bigint      as now_ms,
         (extract(epoch from now() - interval '30 days') * 1000)::bigint as d30_ms
)"""

# Published orders, with composite orders exploded into their item types.
ORD = """ord as (
  select o.id, o.filingnumber, o.createdtime, o.hearingnumber, o.itemtext,
         coalesce(o.ordertype, ci->>'orderType') as t
  from dristi_orders o
  left join lateral jsonb_array_elements(
         case when jsonb_typeof(o.compositeitems) = 'array' then o.compositeitems else '[]'::jsonb end) ci on true
  where o.status = 'PUBLISHED'
)"""

# Filed cases + disposal date + ST / CMP / pre-registration type.
FC = ORD + """,
disp as (
  select filingnumber,
         coalesce(min(createdtime) filter (where t in ('JUDGEMENT','WITHDRAWAL_ACCEPT','DISMISS_CASE','ABATE_CASE','SETTLEMENT_ACCEPT')),
                  min(createdtime) filter (where t = 'ADMIT_DISMISS_CASE')) as disp_order_ms,
         coalesce((array_agg(t order by createdtime) filter (where t in ('JUDGEMENT','WITHDRAWAL_ACCEPT','DISMISS_CASE','ABATE_CASE','SETTLEMENT_ACCEPT')))[1],
                  (array_agg(t order by createdtime) filter (where t = 'ADMIT_DISMISS_CASE'))[1]) as disp_order_type
  from ord group by 1
),
fc as (
  select c.*,
         case when c.outcome is not null then d.disp_order_ms end as disposal_ms,
         case when c.outcome is not null then d.disp_order_type end as disposal_order_type,
         case when c.courtcasenumber ilike 'ST/%' then 'ST'
              when c.cmpnumber is not null then 'CMP'
              else 'Pre-registration' end as ctype,
         to_timestamp(c.filingdate / 1000.0) at time zone 'Asia/Kolkata' as filed_at
  from dristi_cases c
  left join disp d on d.filingnumber = c.filingnumber
  where c.filingdate is not null
    and c.status not in ('DRAFT_IN_PROGRESS','PENDING_PAYMENT','PENDING_E-SIGN','PENDING_E-SIGN-2','PENDING_SIGN')
)"""

# One row per (case, hearing). Hearings can list several filing numbers.
HH = """hh as (
  select fn.f as filingnumber, h.hearingid, h.starttime, h.hearingtype, h.status, h.hearingdurationinmillis
  from dristi_hearing h
  cross join lateral jsonb_array_elements_text(h.filingnumber) fn(f)
  where h.status in ('COMPLETED','SCHEDULED') and h.starttime > 0
)"""

CASE_COLS = "fc.filingnumber, fc.courtcasenumber, fc.cmpnumber, fc.casetitle, fc.stage, fc.status, fc.outcome"

# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------

SQL = {}

SQL["main_cases"] = f"""
with {PARAMS}, {FC}
select
  count(*)                                                            as filed,
  count(*) filter (where fc.filingdate < p.d30_ms)                    as filed_prev,
  count(*) filter (where fc.outcome is not null)                      as disposed,
  count(*) filter (where fc.outcome is not null and (fc.disposal_ms is null or fc.disposal_ms < p.d30_ms)) as disposed_prev,
  count(*) filter (where fc.outcome is not null and fc.disposal_ms is null) as disposed_undated,
  count(*) filter (where fc.outcome = 'WITHDRAWN')                    as withdrawn,
  count(*) filter (where fc.outcome = 'WITHDRAWN' and (fc.disposal_ms is null or fc.disposal_ms < p.d30_ms)) as withdrawn_prev,
  count(*) filter (where fc.outcome = 'DISMISSED')                    as dismissed,
  count(*) filter (where fc.outcome = 'DISMISSED' and (fc.disposal_ms is null or fc.disposal_ms < p.d30_ms)) as dismissed_prev,
  count(*) filter (where fc.outcome in ('CONVICTED','ACQUITTED'))     as judgement,
  count(*) filter (where fc.outcome in ('CONVICTED','ACQUITTED') and (fc.disposal_ms is null or fc.disposal_ms < p.d30_ms)) as judgement_prev,
  count(*) filter (where fc.outcome = 'ABATED')                       as abated,
  count(*) filter (where fc.outcome = 'ABATED' and (fc.disposal_ms is null or fc.disposal_ms < p.d30_ms)) as abated_prev,
  count(*) filter (where fc.outcome is null)                          as pending,
  count(*) filter (where fc.filingdate < p.d30_ms and (fc.outcome is null or fc.disposal_ms >= p.d30_ms)) as pending_prev,
  count(*) filter (where fc.outcome is null and fc.ctype = 'ST')      as pending_st,
  count(*) filter (where fc.ctype = 'ST' and fc.filingdate < p.d30_ms and (fc.outcome is null or fc.disposal_ms >= p.d30_ms)) as pending_st_prev,
  count(*) filter (where fc.outcome is null and fc.ctype = 'CMP')     as pending_cmp,
  count(*) filter (where fc.ctype = 'CMP' and fc.filingdate < p.d30_ms and (fc.outcome is null or fc.disposal_ms >= p.d30_ms)) as pending_cmp_prev
from fc, params p
"""

# 12 months ending with the reporting month: filings, disposals and the pending stock at
# the start of each month (the disposal-rate denominator).
SQL["monthly"] = f"""
with {PARAMS}, {FC},
months as (
  select generate_series(p.m_start - interval '11 months', p.m_start, interval '1 month') as m from params p
),
fx as (select fc.*, to_timestamp(fc.disposal_ms / 1000.0) at time zone 'Asia/Kolkata' as disposed_at from fc)
select to_char(m.m, 'YYYY-MM') as month,
  (select count(*) from fx where fx.filed_at >= m.m and fx.filed_at < m.m + interval '1 month')          as filings,
  (select count(*) from fx where fx.disposed_at >= m.m and fx.disposed_at < m.m + interval '1 month')    as disposals,
  (select count(*) from fx where fx.disposed_at >= m.m and fx.disposed_at < m.m + interval '1 month'
                              and fx.natureofdisposal = 'CONTESTED')                                      as contested,
  (select count(*) from fx where fx.disposed_at >= m.m and fx.disposed_at < m.m + interval '1 month'
                              and fx.natureofdisposal = 'UNCONTESTED')                                    as uncontested,
  (select count(*) from fx where fx.filed_at < m.m and (fx.outcome is null or fx.disposed_at >= m.m)) as pending_at_start
from months m
order by 1 desc
"""

# Hearing statistics for the reporting month and the month before it.
SQL["hearings"] = f"""
with {PARAMS}, {HH},
mm as (select p.m_start as m from params p union all select p.pm_start from params p),
hc as (
  select h.*, to_timestamp(h.starttime / 1000.0) at time zone 'Asia/Kolkata' as ts
  from dristi_hearing h where h.status = 'COMPLETED' and h.starttime > 0
),
dates as (
  select distinct filingnumber, (to_timestamp(starttime / 1000.0) at time zone 'Asia/Kolkata')::date as d
  from hh where status = 'COMPLETED'
),
gaps as (
  select filingnumber, d, d - lag(d) over (partition by filingnumber order by d) as gap_days from dates
)
select to_char(mm.m, 'YYYY-MM') as month,
  (select count(*) from hc where hc.ts >= mm.m and hc.ts < mm.m + interval '1 month')                         as hearings,
  (select count(distinct hc.ts::date) from hc where hc.ts >= mm.m and hc.ts < mm.m + interval '1 month')      as sitting_days,
  (select round((percentile_cont(0.5) within group (order by hc.hearingdurationinmillis) / 60000.0)::numeric, 2) from hc
     where hc.ts >= mm.m and hc.ts < mm.m + interval '1 month' and hc.hearingdurationinmillis > 0)            as median_duration_min,
  (select round(percentile_cont(0.5) within group (order by gap_days)::numeric, 1) from gaps
     where gaps.gap_days > 0 and gaps.d >= mm.m::date and gaps.d < (mm.m + interval '1 month')::date)          as median_gap_days
from mm
order by 1 desc
"""

SQL["process"] = f"""
with {PARAMS},
t as (
  select tasktype, status, createdtime, lastmodifiedtime,
         (tasktype = 'NOTICE'  and status = 'DELIVERED')
      or (tasktype = 'SUMMONS' and status in ('DELIVERED','EXECUTED'))
      or (tasktype = 'WARRANT' and status = 'EXECUTED') as served
  from dristi_task where tasktype in ('NOTICE','SUMMONS','WARRANT')
)
select tasktype,
  count(*)                                                        as issued,
  count(*) filter (where createdtime < p.d30_ms)                  as issued_prev,
  count(*) filter (where served)                                  as served,
  count(*) filter (where served and lastmodifiedtime < p.d30_ms)  as served_prev
from t, params p group by 1
"""

# ---------------------------------------------------------------------------
# Diagnostic pages
# ---------------------------------------------------------------------------

# Pending cases (not in LPR) with no order, hearing, process or application for 60+ days
# (counted from filing if there has been none) and no future hearing scheduled.
SQL["silent"] = f"""
with {PARAMS}, {FC}, {HH},
act as (
  select filingnumber, max(ms) as last_ms from (
    select filingnumber, createdtime as ms from dristi_orders where status = 'PUBLISHED'
    union all select filingnumber, starttime from hh where status = 'COMPLETED'
    union all select filingnumber, createdtime from dristi_task
    union all select filingnumber, createdtime from dristi_application
  ) x group by 1
),
nxt as (select filingnumber, min(starttime) as next_ms from hh, params p where status = 'SCHEDULED' and starttime > p.now_ms group by 1),
s as (
  select {CASE_COLS}, greatest(fc.filingdate, coalesce(a.last_ms, 0)) as last_ms
  from fc
  left join act a on a.filingnumber = fc.filingnumber
  left join nxt n on n.filingnumber = fc.filingnumber
  where fc.outcome is null and coalesce(fc.lifecyclestatus, '') <> 'LPR' and n.next_ms is null
)
select s.*, floor((p.now_ms - s.last_ms) / 86400000.0)::int as days_silent
from s, params p
where p.now_ms - s.last_ms > 60 * 86400000::bigint
order by days_silent desc
"""

# Median gap between successive hearing dates (completed + scheduled) for pending cases.
SQL["gaps"] = f"""
with {PARAMS}, {FC}, {HH},
dates as (
  select distinct filingnumber, (to_timestamp(starttime / 1000.0) at time zone 'Asia/Kolkata')::date as d from hh
),
gaps as (select filingnumber, d - lag(d) over (partition by filingnumber order by d) as gap_days from dates),
cm as (
  select filingnumber, count(*) + 1 as hearing_dates,
         percentile_cont(0.5) within group (order by gap_days) as median_gap
  from gaps where gap_days is not null group by 1
)
select {CASE_COLS}, cm.hearing_dates, round(cm.median_gap::numeric, 1) as median_gap_days
from cm join fc on fc.filingnumber = cm.filingnumber
where fc.outcome is null
order by cm.median_gap desc
"""

# Cases at Cognizance stage for 90+ days since registration, with no cognizance order yet.
SQL["cognizance"] = f"""
with {PARAMS}, {FC},
cog_done as (select distinct filingnumber from ord where t = 'TAKE_COGNIZANCE'),
dca as (
  select filingnumber, true as dca_pending from dristi_application
  where applicationtype = 'DELAY_CONDONATION' and status in ('PENDINGAPPROVAL','PENDINGREVIEW','PENDINGPAYMENT','DRAFT_IN_PROGRESS')
  group by 1
),
notice as (
  select filingnumber, bool_or(status = 'DELIVERED') as served
  from dristi_task where tasktype = 'NOTICE' group by 1
)
select {CASE_COLS},
  floor((p.now_ms - coalesce(fc.registrationdate, fc.filingdate)) / 86400000.0)::int as days_pending,
  case
    when d.dca_pending then 'Delay condonation application pending'
    when n.filingnumber is null then 'No notice issued'
    when not n.served then 'Notice issued, not yet served'
    else 'Notice served'
  end as reason
from fc
cross join params p
left join cog_done cd on cd.filingnumber = fc.filingnumber
left join dca d on d.filingnumber = fc.filingnumber
left join notice n on n.filingnumber = fc.filingnumber
where fc.stage = 'Cognizance' and fc.outcome is null and cd.filingnumber is null
  and p.now_ms - coalesce(fc.registrationdate, fc.filingdate) > 90 * 86400000::bigint
order by days_pending desc
"""

# Pending cases with more than 5 completed delay-condonation hearings.
SQL["dca"] = f"""
with {PARAMS}, {FC}, {HH},
dh as (
  select filingnumber, count(*) as dca_hearings, max(starttime) as last_dca_ms from hh
  where status = 'COMPLETED' and hearingtype in ('DELAY_CONDONATION_HEARING','DELAY_CONDONATION_AND_ADMISSION')
  group by 1
),
da as (
  select filingnumber, count(*) as dca_applications from dristi_application
  where applicationtype = 'DELAY_CONDONATION' and status not in ('DRAFT_IN_PROGRESS','DELETED')
  group by 1
)
select {CASE_COLS}, dh.dca_hearings, coalesce(da.dca_applications, 0) as dca_applications, dh.last_dca_ms
from dh join fc on fc.filingnumber = dh.filingnumber
left join da on da.filingnumber = dh.filingnumber
where fc.outcome is null and dh.dca_hearings > 5
order by dh.dca_hearings desc, da.dca_applications desc nulls last
"""

# Every warrant pushed to the police through the iCOPS integration.
SQL["icops_warrants"] = """
select i.process_number, i.task_number, i.delivery_status, i.booking_date, i.received_date,
       coalesce(i.task_details->'respondentDetails'->'address'->'geoLocationDetails'->'policeStation'->>'name', 'UNKNOWN') as police_station,
       coalesce(i.task_details->'respondentDetails'->'address'->'geoLocationDetails'->'policeStation'->>'district', '—') as district,
       t.filingnumber, c.courtcasenumber, c.casetitle, c.stage
from dristi_kerala_icops i
left join dristi_task t on t.tasknumber = i.task_number
left join dristi_cases c on c.filingnumber = t.filingnumber
where i.task_type = 'WARRANT'
"""

# Cases with 5+ warrant orders. One warrant order can create several tasks (one per
# delivery channel), so warrants are counted by order id. "Executed" = task status EXECUTED
# or iCOPS delivery status DELIVERED / DELIVERED_ICOPS. latest_status = recorded status of
# the most recently created warrant task.
SQL["repeat_warrants"] = f"""
with {FC},
wt as (
  select t.filingnumber, coalesce(t.orderid, t.tasknumber) as warrant_id, t.status, t.createdtime,
         (t.status = 'EXECUTED' or coalesce(i.delivery_status, '') in ('DELIVERED','DELIVERED_ICOPS')) as executed
  from dristi_task t
  left join dristi_kerala_icops i on i.task_number = t.tasknumber
  where t.tasktype = 'WARRANT'
),
latest as (
  select distinct on (filingnumber) filingnumber, status as latest_status
  from wt order by filingnumber, createdtime desc
)
select {CASE_COLS},
  count(distinct wt.warrant_id)                                     as total_warrants,
  count(distinct wt.warrant_id) filter (where wt.executed)          as executed,
  round(((max(wt.createdtime) - min(wt.createdtime)) / 86400000.0)::numeric, 0) as span_days,
  l.latest_status
from wt join fc on fc.filingnumber = wt.filingnumber
join latest l on l.filingnumber = wt.filingnumber
group by fc.filingnumber, fc.courtcasenumber, fc.cmpnumber, fc.casetitle, fc.stage, fc.status, fc.outcome, l.latest_status
having count(distinct wt.warrant_id) >= 5
order by total_warrants desc
"""

# Summons / notices / warrants whose hearing date (in the last 180 days) passed while the
# process was still awaiting fee payment or court dispatch.
SQL["process_failures"] = f"""
with {PARAMS},
t as (
  select t.*, (t.taskdetails->'caseDetails'->>'hearingDate')::bigint as hearing_ms,
         t.taskdetails->'deliveryChannels'->>'channelName' as channel
  from dristi_task t
  where t.tasktype in ('SUMMONS','NOTICE','WARRANT')
    and t.status in ('PENDING_PAYMENT','EXPIRED','ISSUE_SUMMON','ISSUE_NOTICE','ISSUE_WARRANT')
    and (t.taskdetails->'caseDetails'->>'hearingDate') ~ '^[0-9]+$'
)
select t.tasknumber, t.filingnumber, c.courtcasenumber, c.casetitle, t.tasktype, t.status, t.channel,
       t.createdtime, t.lastmodifiedtime, t.hearing_ms,
       case when t.status = 'PENDING_PAYMENT' then 'Pending payment'
            when t.status = 'EXPIRED' then 'Expired'
            else 'Issued, not sent' end as failure_point
from t
cross join params p
left join dristi_cases c on c.filingnumber = t.filingnumber
where t.hearing_ms < p.now_ms and t.hearing_ms >= p.now_ms - 180 * 86400000::bigint
order by t.hearing_ms desc
"""

# Monthly cohorts of newly cognised cases (first TAKE_COGNIZANCE order): "clean" = bail was
# granted (ACCEPT_BAIL order, the accused's first recorded appearance) with no warrant /
# proclamation / attachment order and at most one summons order.
SQL["clean_summons"] = f"""
with {PARAMS}, {ORD},
cog as (select filingnumber, min(createdtime) as cog_ms from ord where t = 'TAKE_COGNIZANCE' group by 1),
summ as (select filingnumber, count(distinct id) as summons_orders from ord where t = 'SUMMONS' group by 1),
war as (select filingnumber, min(createdtime) as first_warrant_ms from ord where t in ('WARRANT','PROCLAMATION','ATTACHMENT') group by 1),
appear as (select filingnumber, min(createdtime) as appear_ms from ord where t = 'ACCEPT_BAIL' group by 1),
k as (
  select cog.filingnumber, to_timestamp(cog.cog_ms / 1000.0) at time zone 'Asia/Kolkata' as cog_at,
         coalesce(s.summons_orders, 0) as summons_orders, w.first_warrant_ms, a.appear_ms
  from cog
  left join summ s on s.filingnumber = cog.filingnumber
  left join war w on w.filingnumber = cog.filingnumber
  left join appear a on a.filingnumber = cog.filingnumber and a.appear_ms >= cog.cog_ms
)
select to_char(date_trunc('month', k.cog_at), 'YYYY-MM') as month,
  count(*)                                                                                  as cognised,
  count(*) filter (where k.appear_ms is not null and k.first_warrant_ms is null and k.summons_orders <= 1) as clean,
  count(*) filter (where k.first_warrant_ms is not null)                                    as warrant_issued
from k, params p
where k.cog_at >= p.m_start - interval '11 months' and k.cog_at < p.m_end
group by 1 order by 1 desc
"""

# Every case referred to ADR (REFERRAL_CASE_TO_ADR order): days from the referral to the
# disposal order (or to today while the case is pending) and completed hearings since.
SQL["mediation"] = f"""
with {PARAMS}, {FC}, {HH},
ref as (select filingnumber, min(createdtime) as ref_ms from ord where t = 'REFERRAL_CASE_TO_ADR' group by 1),
hs as (
  select r.filingnumber, count(distinct hh.hearingid) as med_hearings
  from ref r join hh on hh.filingnumber = r.filingnumber
  where hh.status = 'COMPLETED' and hh.starttime >= r.ref_ms
  group by 1
)
select {CASE_COLS}, r.ref_ms, coalesce(hs.med_hearings, 0) as med_hearings, fc.disposal_ms,
  (fc.outcome is null) as still_in_mediation,
  floor((case when fc.outcome is null then p.now_ms else fc.disposal_ms end - r.ref_ms) / 86400000.0)::int as days_in_mediation
from ref r
join fc on fc.filingnumber = r.filingnumber
cross join params p
left join hs on hs.filingnumber = r.filingnumber
order by days_in_mediation desc nulls last
"""

# Cases where bail was granted: hearings from the first BAIL hearing (or the grant hearing)
# up to the grant, and the days that took.
SQL["bail"] = f"""
with {FC}, {HH},
g as (select filingnumber, min(createdtime) as grant_ms from ord where t = 'ACCEPT_BAIL' group by 1),
b as (
  select g.filingnumber, g.grant_ms,
         least(coalesce(min(hh.starttime) filter (where hh.hearingtype = 'BAIL' and hh.status = 'COMPLETED'
                                                   and hh.starttime <= g.grant_ms + 86400000), g.grant_ms), g.grant_ms) as start_ms
  from g left join hh on hh.filingnumber = g.filingnumber
  group by 1, 2
)
select {CASE_COLS},
  greatest(1, (select count(*) from hh where hh.filingnumber = b.filingnumber and hh.status = 'COMPLETED'
                 and hh.starttime >= b.start_ms - 43200000 and hh.starttime <= b.grant_ms + 43200000)) as bail_hearings,
  round(((b.grant_ms - b.start_ms) / 86400000.0)::numeric, 1) as days_to_bail,
  b.grant_ms
from b join fc on fc.filingnumber = b.filingnumber
order by bail_hearings desc, days_to_bail desc
"""

# Same complainant + accused with more than one pending case at the same trial stage.
SQL["joint"] = f"""
with {FC},
tc as (
  select fc.filingnumber, fc.stage,
         upper(trim(regexp_replace(split_part(regexp_replace(fc.casetitle, '\\s+vs\\.{{0,1}}\\s+', ' vs ', 'i'), ' vs ', 1), '\\s+', ' ', 'g'))) as complainant,
         upper(trim(regexp_replace(split_part(regexp_replace(fc.casetitle, '\\s+vs\\.{{0,1}}\\s+', ' vs ', 'i'), ' vs ', 2), '\\s+', ' ', 'g'))) as accused
  from fc
  where fc.outcome is null
    and fc.stage in ('Complainant Evidence','Examination of Accused','Defense Evidence','Arguments')
    and fc.casetitle ~* '\\svs\\.{{0,1}}\\s'
)
select complainant, accused, stage, count(*) as cases, string_agg(filingnumber, ', ' order by filingnumber) as filing_numbers
from tc group by 1, 2, 3 having count(*) > 1
order by cases desc, complainant
"""

# One row per (advocate, case) for active vakalats.
SQL["advocates"] = f"""
with {FC}, {HH},
rep as (
  select distinct r.case_id, a.id as advocate_id,
         coalesce(nullif(trim(a.additionaldetails->>'username'), ''), a.barregistrationnumber) as advocate,
         a.barregistrationnumber
  from dristi_case_representatives r join dristi_advocate a on a.id = r.advocateid
  where r.isactive
),
ts as (
  select filingnumber, min(starttime) as trial_start_ms from hh
  where status = 'COMPLETED' and hearingtype in ('EVIDENCE_COMPLAINANT','EVIDENCE_ACCUSED','EXAMINATION_UNDER_S351_BNSS','ARGUMENTS')
  group by 1
)
select rep.advocate_id, rep.advocate, rep.barregistrationnumber, {CASE_COLS},
       fc.filingdate, fc.disposal_ms, ts.trial_start_ms
from rep join fc on fc.id = rep.case_id
left join ts on ts.filingnumber = fc.filingnumber
"""

# First ACCEPT_BAIL order (the accused's first recorded appearance) vs the first completed
# PLEA hearing.
SQL["plea"] = f"""
with {FC}, {HH},
ap as (select filingnumber, min(createdtime) as appear_ms from ord where t = 'ACCEPT_BAIL' group by 1),
pl as (select filingnumber, min(starttime) as plea_ms from hh where hearingtype = 'PLEA' and status = 'COMPLETED' group by 1)
select {CASE_COLS}, ap.appear_ms, pl.plea_ms,
  ((to_timestamp(pl.plea_ms / 1000.0) at time zone 'Asia/Kolkata')::date
   - (to_timestamp(ap.appear_ms / 1000.0) at time zone 'Asia/Kolkata')::date) as days_to_plea
from fc join ap on ap.filingnumber = fc.filingnumber join pl on pl.filingnumber = fc.filingnumber
order by days_to_plea desc
"""

# Institutional ("REPRESENTATIVE") complainants. Their registered address is stored in
# plain text; individual complainants' addresses are encrypted and cannot be used.
SQL["institutional"] = f"""
with {PARAMS}, {FC}
select {CASE_COLS}, fc.filingdate, fc.filed_at >= p.m_start and fc.filed_at < p.m_end as filed_in_month,
       d->>'complainantCompanyName' as company,
       d->'addressCompanyDetails'->>'district' as district,
       d->'addressCompanyDetails'->>'state' as state
from fc
cross join params p
cross join lateral jsonb_array_elements(case when jsonb_typeof(fc.additionaldetails->'complainantDetails'->'formdata') = 'array'
                                            then fc.additionaldetails->'complainantDetails'->'formdata' else '[]'::jsonb end) f
cross join lateral (select f->'data' as d) z
where d->'complainantType'->>'code' = 'REPRESENTATIVE'
"""

# LPR: cases currently in the Long Pending Register (lifecyclestatus = LPR) and cases moved
# out of it (MOVE_CASE_OUT_OF_LONG_PENDING_REGISTER order).
SQL["lpr"] = f"""
with {FC},
mi as (select filingnumber, min(createdtime) as in_ms from ord where t = 'MOVE_CASE_TO_LONG_PENDING_REGISTER' group by 1),
mo as (select filingnumber, max(createdtime) as out_ms from ord where t = 'MOVE_CASE_OUT_OF_LONG_PENDING_REGISTER' group by 1),
x as (
  select {CASE_COLS}, fc.lprnumber, fc.lifecyclestatus, mi.in_ms, mo.out_ms,
    case when fc.lifecyclestatus = 'LPR' then 'In LPR'
         when mo.out_ms is not null then 'Revived from LPR' end as lpr_status
  from fc
  left join mi on mi.filingnumber = fc.filingnumber
  left join mo on mo.filingnumber = fc.filingnumber
)
select * from x where lpr_status is not null
order by lpr_status, lprnumber
"""

# Compact event history for any case shown in a table (for the per-row "Download" buttons).
SQL["history"] = f"""
with {HH}
select filingnumber, starttime as ms, 'Hearing' as kind, hearingtype as detail, status as extra from hh
union all
select o.filingnumber, o.createdtime, 'Order',
       coalesce(o.ordertype, (select string_agg(ci->>'orderType', ' + ') from jsonb_array_elements(
                case when jsonb_typeof(o.compositeitems) = 'array' then o.compositeitems else '[]'::jsonb end) ci), 'PROCEEDINGS'),
       left(regexp_replace(regexp_replace(coalesce(o.itemtext, ''), '<[^>]+>|&nbsp;', ' ', 'g'), '\\s+', ' ', 'g'), 160)
from dristi_orders o where o.status = 'PUBLISHED'
union all
select filingnumber, createdtime, 'Process', tasktype, status from dristi_task
where tasktype in ('SUMMONS','NOTICE','WARRANT','PROCLAMATION','ATTACHMENT')
union all
select filingnumber, createdtime, 'Application', applicationtype, status from dristi_application
where status not in ('DRAFT_IN_PROGRESS','DELETED')
"""

# Every disposed case (the register behind "View cases" on the main page).
SQL["disposed"] = f"""
with {FC}
select {CASE_COLS}, fc.natureofdisposal, fc.disposal_ms, fc.disposal_order_type
from fc where fc.outcome is not null
order by fc.disposal_ms desc nulls last
"""

# Basic details for every filed case (used to label case lists in downloads).
SQL["case_index"] = f"""
with {FC}
select {CASE_COLS} from fc
"""
