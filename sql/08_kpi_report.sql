-- =====================================================================
-- KPI scorecard: the headline numbers for the dashboard and report.
-- TTM = trailing twelve months ending on the as-of date.
-- =====================================================================
SET search_path TO hr;

WITH p AS (SELECT as_of_date, as_of_date - INTERVAL '12 months' AS ttm_start FROM vw_params),
active AS (SELECT * FROM employees WHERE employment_status = 'Active'),
wf AS (
    SELECT SUM(exits) AS exits, SUM(voluntary_exits) AS vol_exits, SUM(hires) AS hires
    FROM vw_monthly_workforce, p WHERE month_start > p.ttm_start
),
avg_hc AS (
    SELECT AVG(hc) AS avg_hc FROM (
        SELECT month_start, SUM(headcount_start + headcount_end) / 2.0 AS hc
        FROM vw_monthly_workforce, p WHERE month_start > p.ttm_start GROUP BY month_start) x
),
att AS (
    SELECT 100.0 * SUM(days_present) / SUM(scheduled_days) AS attendance_rate,
           100.0 * SUM(sick_leave_days + unplanned_absence_days) / SUM(scheduled_days) AS absenteeism_rate
    FROM attendance_monthly, p WHERE month > p.ttm_start
),
perf AS (
    SELECT AVG(performance_rating) AS avg_rating,
           100.0 * AVG((performance_rating >= 4)::int) AS high_perf_pct
    FROM performance_reviews WHERE review_year = 2025
)
SELECT 'Active headcount'                AS kpi, (SELECT COUNT(*) FROM active)::text AS value
UNION ALL SELECT 'New hires (TTM)',        hires::text FROM wf
UNION ALL SELECT 'Exits (TTM)',            exits::text FROM wf
UNION ALL SELECT 'Attrition rate (TTM, %)', ROUND(100.0 * exits / avg_hc, 1)::text FROM wf, avg_hc
UNION ALL SELECT 'Voluntary attrition (TTM, %)', ROUND(100.0 * vol_exits / avg_hc, 1)::text FROM wf, avg_hc
UNION ALL SELECT 'Average tenure, active (yrs)', ROUND(AVG(tenure_years), 1)::text FROM active
UNION ALL SELECT 'Average age, active',    ROUND(AVG(age), 1)::text FROM active
UNION ALL SELECT 'Female share, active (%)', ROUND(100.0 * AVG((gender = 'Female')::int), 1)::text FROM active
UNION ALL SELECT 'Median annual salary (INR)', (PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY annual_salary))::numeric(12,0)::text FROM active
UNION ALL SELECT 'Annual payroll run-rate (INR Cr)', ROUND(SUM(annual_salary) / 1e7, 2)::text FROM active
UNION ALL SELECT 'Attendance rate (TTM, %)', ROUND(attendance_rate, 2)::text FROM att
UNION ALL SELECT 'Absenteeism rate (TTM, %)', ROUND(absenteeism_rate, 2)::text FROM att
UNION ALL SELECT 'Average performance rating (2025)', ROUND(avg_rating, 2)::text FROM perf
UNION ALL SELECT 'High performers, rated 4-5 (2025, %)', ROUND(high_perf_pct, 1)::text FROM perf
UNION ALL SELECT 'Employees on overtime (%)', ROUND(100.0 * AVG((overtime = 'Yes')::int), 1)::text FROM active;
