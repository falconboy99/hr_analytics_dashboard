-- =====================================================================
-- Attrition analysis: how many people leave, who, when and why.
-- Attrition rate = exits in period / average headcount in period.
-- =====================================================================
SET search_path TO hr;

-- 5.1 Annual attrition rate (total and voluntary), company level.
--     The current year is partial, so its rates are annualised (x 12 / months covered).
WITH yearly AS (
    SELECT EXTRACT(YEAR FROM month_start)::int AS year,
           month_start,
           SUM(headcount_start) AS hc_start, SUM(headcount_end) AS hc_end,
           SUM(exits) AS exits, SUM(voluntary_exits) AS vol_exits
    FROM vw_monthly_workforce
    GROUP BY 1, 2
)
SELECT year,
       COUNT(*)                                                       AS months_covered,
       SUM(exits)                                                     AS exits,
       SUM(vol_exits)                                                 AS voluntary_exits,
       ROUND(AVG((hc_start + hc_end) / 2.0), 0)                       AS avg_headcount,
       ROUND(100.0 * SUM(exits)     / AVG((hc_start + hc_end) / 2.0) * 12 / COUNT(*), 1) AS attrition_rate_pct,
       ROUND(100.0 * SUM(vol_exits) / AVG((hc_start + hc_end) / 2.0) * 12 / COUNT(*), 1) AS voluntary_rate_pct
FROM yearly
WHERE year >= 2018
GROUP BY year ORDER BY year;

-- 5.2 Trailing-12-month attrition rate by department
WITH ttm AS (
    SELECT department,
           SUM(exits)                               AS exits,
           AVG((headcount_start + headcount_end) / 2.0) AS avg_hc
    FROM vw_monthly_workforce
    WHERE month_start >  (SELECT as_of_date FROM vw_params) - INTERVAL '12 months'
    GROUP BY department
)
SELECT department, exits, ROUND(avg_hc, 0) AS avg_headcount,
       ROUND(100.0 * exits / avg_hc, 1) AS ttm_attrition_rate_pct
FROM ttm ORDER BY ttm_attrition_rate_pct DESC;

-- 5.3 Exit reasons (last 24 months)
SELECT termination_type, termination_reason,
       COUNT(*) AS exits,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct_of_exits
FROM employees
WHERE termination_date > (SELECT as_of_date FROM vw_params) - INTERVAL '24 months'
GROUP BY termination_type, termination_reason
ORDER BY exits DESC;

-- 5.4 Attrition drivers: leaver share by factor, all employees ever hired.
--     (Share of the people in each group who have left.)
SELECT 'Overtime' AS factor, overtime AS value, COUNT(*) AS employees,
       ROUND(100.0 * AVG(is_leaver), 1) AS leaver_pct
FROM vw_employee GROUP BY overtime
UNION ALL
SELECT 'Job satisfaction', job_satisfaction::text, COUNT(*), ROUND(100.0 * AVG(is_leaver), 1)
FROM vw_employee GROUP BY job_satisfaction
UNION ALL
SELECT 'Work-life balance', work_life_balance::text, COUNT(*), ROUND(100.0 * AVG(is_leaver), 1)
FROM vw_employee GROUP BY work_life_balance
UNION ALL
SELECT 'Job level', job_level::text, COUNT(*), ROUND(100.0 * AVG(is_leaver), 1)
FROM vw_employee GROUP BY job_level
UNION ALL
SELECT 'Commute', commute_band, COUNT(*), ROUND(100.0 * AVG(is_leaver), 1)
FROM vw_employee GROUP BY commute_band
UNION ALL
SELECT 'Recruitment source', recruitment_source, COUNT(*), ROUND(100.0 * AVG(is_leaver), 1)
FROM vw_employee GROUP BY recruitment_source
UNION ALL
SELECT 'Work mode', work_mode, COUNT(*), ROUND(100.0 * AVG(is_leaver), 1)
FROM vw_employee GROUP BY work_mode
ORDER BY factor, value;

-- 5.5 Early attrition: share of exits that happen in the first year
SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE tenure_years < 1) / COUNT(*), 1) AS first_year_exit_pct,
       ROUND(AVG(tenure_years), 2)                                          AS avg_tenure_at_exit
FROM employees WHERE attrition = 'Yes';

-- 5.6 Hiring cohort retention: % of each hire-year cohort still employed after 1, 2, 3 years
SELECT EXTRACT(YEAR FROM hire_date)::int AS hire_year,
       COUNT(*) AS hired,
       ROUND(100.0 * COUNT(*) FILTER (WHERE termination_date IS NULL OR termination_date > hire_date + INTERVAL '1 year')  / COUNT(*), 1) AS retained_1y_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE termination_date IS NULL OR termination_date > hire_date + INTERVAL '2 years') / COUNT(*), 1) AS retained_2y_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE termination_date IS NULL OR termination_date > hire_date + INTERVAL '3 years') / COUNT(*), 1) AS retained_3y_pct
FROM employees
WHERE hire_date <= (SELECT as_of_date FROM vw_params) - INTERVAL '3 years'
GROUP BY 1 ORDER BY 1;

-- 5.7 Regretted attrition: voluntary leavers whose last rating was 4 or 5 (last 24 months)
SELECT department,
       COUNT(*) FILTER (WHERE termination_type = 'Voluntary' AND latest_performance_rating >= 4) AS regretted_exits,
       COUNT(*)                                                                                   AS all_exits,
       ROUND(100.0 * COUNT(*) FILTER (WHERE termination_type = 'Voluntary' AND latest_performance_rating >= 4)
             / NULLIF(COUNT(*), 0), 1)                                                            AS regretted_pct
FROM employees
WHERE termination_date > (SELECT as_of_date FROM vw_params) - INTERVAL '24 months'
GROUP BY department ORDER BY regretted_exits DESC;

-- 5.8 Simple flight-risk score for active employees (0-100), using the drivers in 5.4
SELECT employee_id, first_name || ' ' || last_name AS name, department, job_role,
       LEAST(100,
             (CASE overtime WHEN 'Yes' THEN 25 ELSE 0 END)
           + (4 - job_satisfaction) * 12
           + (4 - work_life_balance) * 6
           + (CASE WHEN job_level <= 2 THEN 10 ELSE 0 END)
           + (CASE WHEN distance_from_home_km > 25 THEN 8 ELSE 0 END)
           + (CASE WHEN years_since_last_promotion >= 3 THEN 8 ELSE 0 END)
       ) AS flight_risk_score
FROM employees
WHERE employment_status = 'Active'
ORDER BY flight_risk_score DESC
LIMIT 50;
