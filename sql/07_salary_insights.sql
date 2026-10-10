-- =====================================================================
-- Salary insights (annual salary in INR).
-- =====================================================================
SET search_path TO hr;

-- 7.1 Salary distribution by department (active employees)
SELECT department,
       COUNT(*)                                                                 AS headcount,
       ROUND(AVG(annual_salary))                                                AS avg_salary,
       PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY annual_salary)::numeric(12,0) AS p25,
       PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY annual_salary)::numeric(12,0) AS median,
       PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY annual_salary)::numeric(12,0) AS p75,
       SUM(annual_salary)                                                       AS total_payroll
FROM employees WHERE employment_status = 'Active'
GROUP BY department ORDER BY median DESC;

-- 7.2 Pay by job level
SELECT job_level, COUNT(*) AS headcount,
       MIN(annual_salary) AS min_salary,
       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY annual_salary)::numeric(12,0) AS median_salary,
       MAX(annual_salary) AS max_salary
FROM employees WHERE employment_status = 'Active'
GROUP BY job_level ORDER BY job_level;

-- 7.3 Gender pay gap: raw (company-wide median) and adjusted (same department and level)
WITH raw AS (
    SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY annual_salary) FILTER (WHERE gender = 'Male')   AS male_med,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY annual_salary) FILTER (WHERE gender = 'Female') AS female_med
    FROM employees WHERE employment_status = 'Active'
)
SELECT 'Raw median gap' AS measure, ROUND((100.0 * (male_med - female_med) / male_med)::numeric, 1) AS gap_pct FROM raw
UNION ALL
SELECT 'Adjusted gap (avg compa-ratio, M minus F)',
       ROUND(100.0 * (AVG(compa_ratio) FILTER (WHERE gender = 'Male')
                    - AVG(compa_ratio) FILTER (WHERE gender = 'Female')), 1)
FROM vw_salary_position;

-- 7.4 Adjusted gender gap by department
SELECT department,
       ROUND(AVG(compa_ratio) FILTER (WHERE gender = 'Male'), 3)   AS male_compa,
       ROUND(AVG(compa_ratio) FILTER (WHERE gender = 'Female'), 3) AS female_compa,
       ROUND(100.0 * (AVG(compa_ratio) FILTER (WHERE gender = 'Male')
                    - AVG(compa_ratio) FILTER (WHERE gender = 'Female')), 1) AS gap_pts
FROM vw_salary_position
GROUP BY department ORDER BY gap_pts DESC;

-- 7.5 Average increment by performance rating (April cycles)
SELECT EXTRACT(YEAR FROM s.effective_date)::int AS cycle_year,
       r.performance_rating,
       COUNT(*) AS employees,
       ROUND(AVG(s.increment_pct), 1) AS avg_increment_pct,
       ROUND(100.0 * AVG((s.change_reason = 'Promotion')::int), 1) AS promoted_pct
FROM salary_history s
JOIN performance_reviews r
  ON r.employee_id = s.employee_id AND r.review_year = EXTRACT(YEAR FROM s.effective_date) - 1
WHERE s.change_reason <> 'Hire' AND s.effective_date >= DATE '2022-04-01'
GROUP BY 1, 2 ORDER BY 1, 2;

-- 7.6 Payroll trend: total annual salary cost of the workforce at each year-end
SELECT y.year_end,
       SUM(sh.annual_salary) AS payroll_run_rate,
       COUNT(*)              AS headcount,
       ROUND(AVG(sh.annual_salary)) AS avg_salary
FROM (SELECT make_date(y, 12, 31) AS year_end FROM generate_series(2018, 2025) y
      UNION ALL SELECT as_of_date FROM vw_params) y
JOIN employees e
  ON e.hire_date <= y.year_end AND (e.termination_date IS NULL OR e.termination_date > y.year_end)
JOIN LATERAL (
    SELECT annual_salary FROM salary_history s
    WHERE s.employee_id = e.employee_id AND s.effective_date <= y.year_end
    ORDER BY s.effective_date DESC LIMIT 1
) sh ON true
GROUP BY y.year_end ORDER BY y.year_end;

-- 7.7 Underpaid and at risk: active employees below 0.90 compa-ratio
SELECT p.department, COUNT(*) AS below_band,
       ROUND(100.0 * COUNT(*) / MAX(t.n), 1) AS pct_of_dept,
       SUM(ROUND(p.band_median * 0.95 - p.annual_salary)) AS cost_to_lift_to_095
FROM vw_salary_position p
JOIN (SELECT department, COUNT(*) AS n FROM vw_salary_position GROUP BY department) t USING (department)
WHERE p.compa_ratio < 0.90
GROUP BY p.department ORDER BY below_band DESC;

-- 7.8 Does pay position predict leaving? Leaver share by compa-ratio band at exit/snapshot
WITH band AS (
    SELECT department, job_level,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY annual_salary) AS med
    FROM employees GROUP BY department, job_level
)
SELECT CASE WHEN e.annual_salary / b.med < 0.92 THEN '1. Below 0.92'
            WHEN e.annual_salary / b.med <= 1.08 THEN '2. 0.92-1.08'
            ELSE '3. Above 1.08' END AS compa_band,
       COUNT(*) AS employees,
       ROUND(100.0 * AVG((e.attrition = 'Yes')::int), 1) AS leaver_pct
FROM employees e JOIN band b USING (department, job_level)
GROUP BY 1 ORDER BY 1;
