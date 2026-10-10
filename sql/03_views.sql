-- =====================================================================
-- Reusable views. Everything downstream (analysis queries, Power BI,
-- the HTML dashboard export) reads from these.
-- =====================================================================
SET search_path TO hr;

-- Reporting date for the dataset. Change it here and every view follows.
CREATE OR REPLACE VIEW vw_params AS
SELECT DATE '2026-09-30' AS as_of_date;

-- One row per employee with derived bands used for slicing.
CREATE OR REPLACE VIEW vw_employee AS
SELECT
    e.*,
    CASE WHEN e.age < 25 THEN '18-24'
         WHEN e.age < 35 THEN '25-34'
         WHEN e.age < 45 THEN '35-44'
         WHEN e.age < 55 THEN '45-54'
         ELSE '55+' END                                      AS age_band,
    CASE WHEN e.tenure_years < 1 THEN '< 1 yr'
         WHEN e.tenure_years < 3 THEN '1-3 yrs'
         WHEN e.tenure_years < 5 THEN '3-5 yrs'
         WHEN e.tenure_years < 10 THEN '5-10 yrs'
         ELSE '10+ yrs' END                                  AS tenure_band,
    CASE WHEN e.annual_salary < 600000  THEN '< 6 L'
         WHEN e.annual_salary < 1000000 THEN '6-10 L'
         WHEN e.annual_salary < 1500000 THEN '10-15 L'
         WHEN e.annual_salary < 2500000 THEN '15-25 L'
         ELSE '25 L+' END                                    AS salary_band,
    CASE WHEN e.distance_from_home_km > 25 THEN 'Long (>25 km)'
         WHEN e.distance_from_home_km > 10 THEN 'Medium (11-25 km)'
         ELSE 'Short (<=10 km)' END                          AS commute_band,
    (e.attrition = 'Yes')::int                               AS is_leaver,
    (e.employment_status = 'Active')::int                    AS is_active
FROM employees e;

-- Month-end headcount, hires and exits per department (2016-01 .. as_of).
CREATE OR REPLACE VIEW vw_monthly_workforce AS
WITH months AS (
    SELECT generate_series(DATE '2016-01-01',
                           date_trunc('month', (SELECT as_of_date FROM vw_params))::date,
                           INTERVAL '1 month')::date AS month_start
)
SELECT
    m.month_start,
    (m.month_start + INTERVAL '1 month - 1 day')::date                       AS month_end,
    d.department_name                                                        AS department,
    COUNT(*) FILTER (WHERE e.hire_date <= (m.month_start + INTERVAL '1 month - 1 day')
                       AND (e.termination_date IS NULL
                            OR e.termination_date > (m.month_start + INTERVAL '1 month - 1 day'))) AS headcount_end,
    COUNT(*) FILTER (WHERE e.hire_date < m.month_start
                       AND (e.termination_date IS NULL OR e.termination_date >= m.month_start)) AS headcount_start,
    COUNT(*) FILTER (WHERE date_trunc('month', e.hire_date) = m.month_start)        AS hires,
    COUNT(*) FILTER (WHERE date_trunc('month', e.termination_date) = m.month_start) AS exits,
    COUNT(*) FILTER (WHERE date_trunc('month', e.termination_date) = m.month_start
                       AND e.termination_type = 'Voluntary')                         AS voluntary_exits
FROM months m
CROSS JOIN departments d
LEFT JOIN employees e ON e.department_id = d.department_id
GROUP BY m.month_start, d.department_name;

-- Attendance with rates per employee-month.
CREATE OR REPLACE VIEW vw_attendance AS
SELECT
    a.*,
    e.department,
    e.location,
    e.work_mode,
    (a.planned_leave_days + a.sick_leave_days + a.unplanned_absence_days) AS total_absence_days,
    ROUND(100.0 * a.days_present / NULLIF(a.scheduled_days, 0), 2)         AS attendance_rate_pct,
    ROUND(100.0 * (a.sick_leave_days + a.unplanned_absence_days)
                / NULLIF(a.scheduled_days, 0), 2)                          AS absenteeism_rate_pct
FROM attendance_monthly a
JOIN employees e USING (employee_id);

-- Current salary vs. the median for the same department and level (compa-ratio).
CREATE OR REPLACE VIEW vw_salary_position AS
WITH active AS (
    SELECT * FROM employees WHERE employment_status = 'Active'
), bands AS (
    SELECT department, job_level,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY annual_salary) AS band_median
    FROM active GROUP BY department, job_level
)
SELECT a.employee_id, a.department, a.job_level, a.gender, a.annual_salary,
       b.band_median,
       ROUND((a.annual_salary / b.band_median)::numeric, 3) AS compa_ratio
FROM active a JOIN bands b USING (department, job_level);
