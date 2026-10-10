-- =====================================================================
-- Attendance analysis (monthly data, 2025-01 .. 2026-09).
-- Attendance rate  = days present / scheduled days
-- Absenteeism rate = (sick + unplanned absence days) / scheduled days
-- =====================================================================
SET search_path TO hr;

-- 6.1 Monthly company attendance trend
SELECT month,
       COUNT(DISTINCT employee_id)                                         AS employees,
       ROUND(100.0 * SUM(days_present) / SUM(scheduled_days), 2)           AS attendance_rate_pct,
       ROUND(100.0 * SUM(sick_leave_days + unplanned_absence_days)
                   / SUM(scheduled_days), 2)                               AS absenteeism_rate_pct,
       ROUND(AVG(overtime_hours), 1)                                       AS avg_overtime_hours,
       SUM(late_arrivals)                                                  AS late_arrivals
FROM attendance_monthly
GROUP BY month ORDER BY month;

-- 6.2 Attendance by department, trailing 12 months
SELECT department,
       ROUND(100.0 * SUM(days_present) / SUM(scheduled_days), 2)                           AS attendance_rate_pct,
       ROUND(100.0 * SUM(sick_leave_days + unplanned_absence_days) / SUM(scheduled_days), 2) AS absenteeism_rate_pct,
       ROUND(1.0 * SUM(unplanned_absence_days) / COUNT(DISTINCT employee_id), 2)           AS unplanned_days_per_employee,
       ROUND(AVG(overtime_hours), 1)                                                       AS avg_monthly_overtime_hours,
       ROUND(100.0 * SUM(late_arrivals) / SUM(days_present), 2)                            AS late_arrival_rate_pct
FROM vw_attendance
WHERE month > (SELECT as_of_date FROM vw_params) - INTERVAL '12 months'
GROUP BY department ORDER BY absenteeism_rate_pct DESC;

-- 6.3 Leave mix by type, trailing 12 months
SELECT SUM(planned_leave_days)      AS planned_leave_days,
       SUM(sick_leave_days)         AS sick_leave_days,
       SUM(unplanned_absence_days)  AS unplanned_absence_days,
       ROUND(100.0 * SUM(unplanned_absence_days)
             / NULLIF(SUM(planned_leave_days + sick_leave_days + unplanned_absence_days), 0), 1) AS unplanned_share_pct
FROM attendance_monthly
WHERE month > (SELECT as_of_date FROM vw_params) - INTERVAL '12 months';

-- 6.4 Bradford factor (S^2 x D) per active employee, trailing 12 months.
--     S = absence spells (approximated by months with unplanned or sick days), D = total unplanned+sick days.
WITH t AS (
    SELECT employee_id,
           COUNT(*) FILTER (WHERE sick_leave_days + unplanned_absence_days > 0) AS spells,
           SUM(sick_leave_days + unplanned_absence_days)                        AS days
    FROM attendance_monthly
    WHERE month > (SELECT as_of_date FROM vw_params) - INTERVAL '12 months'
    GROUP BY employee_id
)
SELECT e.employee_id, e.first_name || ' ' || e.last_name AS name, e.department,
       t.spells, t.days, t.spells * t.spells * t.days AS bradford_factor
FROM t JOIN employees e USING (employee_id)
WHERE e.employment_status = 'Active'
ORDER BY bradford_factor DESC
LIMIT 25;

-- 6.5 Absence before exit: leavers' absenteeism in their last 3 months vs. everyone else
WITH tagged AS (
    SELECT a.*,
           CASE WHEN e.termination_date IS NOT NULL
                 AND a.month >= date_trunc('month', e.termination_date) - INTERVAL '3 months'
                THEN 'Leaver, final 3 months' ELSE 'All other employee-months' END AS grp
    FROM attendance_monthly a JOIN employees e USING (employee_id)
)
SELECT grp,
       ROUND(100.0 * SUM(unplanned_absence_days) / SUM(scheduled_days), 2) AS unplanned_absence_rate_pct,
       ROUND(100.0 * SUM(late_arrivals) / NULLIF(SUM(days_present), 0), 2) AS late_arrival_rate_pct
FROM tagged GROUP BY grp;

-- 6.6 Work mode and attendance
SELECT work_mode,
       ROUND(100.0 * SUM(days_present) / SUM(scheduled_days), 2) AS attendance_rate_pct,
       ROUND(100.0 * SUM(remote_days) / NULLIF(SUM(days_present), 0), 1) AS remote_share_pct,
       ROUND(100.0 * SUM(late_arrivals) / NULLIF(SUM(days_present), 0), 2) AS late_arrival_rate_pct
FROM vw_attendance
GROUP BY work_mode ORDER BY attendance_rate_pct DESC;
