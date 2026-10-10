-- =====================================================================
-- Employee analytics: who works here today, and how the workforce has grown.
-- =====================================================================
SET search_path TO hr;

-- 4.1 Active headcount by department, with share of total and average tenure
SELECT department,
       COUNT(*)                                             AS headcount,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)   AS pct_of_workforce,
       ROUND(AVG(tenure_years), 1)                          AS avg_tenure_years,
       ROUND(AVG(age), 1)                                   AS avg_age
FROM vw_employee
WHERE is_active = 1
GROUP BY department
ORDER BY headcount DESC;

-- 4.2 Gender mix by department (active)
SELECT department,
       COUNT(*) FILTER (WHERE gender = 'Female')                                  AS female,
       COUNT(*) FILTER (WHERE gender = 'Male')                                    AS male,
       COUNT(*) FILTER (WHERE gender = 'Non-binary')                              AS non_binary,
       ROUND(100.0 * COUNT(*) FILTER (WHERE gender = 'Female') / COUNT(*), 1)     AS female_pct
FROM vw_employee
WHERE is_active = 1
GROUP BY department
ORDER BY female_pct DESC;

-- 4.3 Age and tenure distribution (active)
SELECT age_band, COUNT(*) AS headcount
FROM vw_employee WHERE is_active = 1
GROUP BY age_band ORDER BY age_band;

SELECT tenure_band, COUNT(*) AS headcount
FROM vw_employee WHERE is_active = 1
GROUP BY tenure_band
ORDER BY MIN(tenure_years);

-- 4.4 Headcount by location and work mode (active)
SELECT location,
       COUNT(*) FILTER (WHERE work_mode = 'On-site') AS on_site,
       COUNT(*) FILTER (WHERE work_mode = 'Hybrid')  AS hybrid,
       COUNT(*) FILTER (WHERE work_mode = 'Remote')  AS remote,
       COUNT(*)                                      AS total
FROM vw_employee WHERE is_active = 1
GROUP BY location ORDER BY total DESC;

-- 4.5 Workforce growth: year-end headcount, hires, exits and net change
SELECT EXTRACT(YEAR FROM month_start)::int                         AS year,
       SUM(headcount_end) FILTER (WHERE EXTRACT(MONTH FROM month_start) = 12
                                   OR month_start = date_trunc('month', (SELECT as_of_date FROM vw_params)))
                                                                    AS closing_headcount,
       SUM(hires)                                                   AS hires,
       SUM(exits)                                                   AS exits,
       SUM(hires) - SUM(exits)                                      AS net_change
FROM vw_monthly_workforce
GROUP BY 1 ORDER BY 1;

-- 4.6 Performance distribution, latest completed review cycle (2025)
SELECT performance_rating,
       COUNT(*)                                            AS employees,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)  AS pct,
       ROUND(AVG(goals_achieved_pct), 1)                   AS avg_goals_achieved_pct,
       ROUND(AVG(training_hours), 1)                       AS avg_training_hours
FROM performance_reviews
WHERE review_year = 2025
GROUP BY performance_rating ORDER BY performance_rating DESC;

-- 4.7 Average performance rating by department and year (trend)
SELECT e.department, r.review_year, ROUND(AVG(r.performance_rating), 2) AS avg_rating
FROM performance_reviews r JOIN employees e USING (employee_id)
GROUP BY e.department, r.review_year
ORDER BY e.department, r.review_year;

-- 4.8 High performers at risk: rated 4-5 in 2025, still active, low satisfaction or overdue promotion
SELECT e.employee_id, e.first_name || ' ' || e.last_name AS name, e.department, e.job_role,
       r.performance_rating, e.job_satisfaction, e.years_since_last_promotion, e.overtime
FROM employees e
JOIN performance_reviews r ON r.employee_id = e.employee_id AND r.review_year = 2025
WHERE e.employment_status = 'Active'
  AND r.performance_rating >= 4
  AND (e.job_satisfaction <= 2 OR e.years_since_last_promotion >= 3)
ORDER BY r.performance_rating DESC, e.job_satisfaction, e.years_since_last_promotion DESC;
