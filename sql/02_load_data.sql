-- =====================================================================
-- Load the CSVs in /data. Run with psql from the repository root:
--   psql -d hr_analytics -f sql/02_load_data.sql
-- (\copy reads files on the client, so no server file access is needed.)
-- =====================================================================
SET search_path TO hr;

\copy departments        FROM 'data/departments.csv'        WITH (FORMAT csv, HEADER true)
\copy employees          FROM 'data/employees.csv'          WITH (FORMAT csv, HEADER true, NULL '')
\copy salary_history     FROM 'data/salary_history.csv'     WITH (FORMAT csv, HEADER true)
\copy performance_reviews FROM 'data/performance_reviews.csv' WITH (FORMAT csv, HEADER true)
\copy attendance_monthly FROM 'data/attendance_monthly.csv' WITH (FORMAT csv, HEADER true)

ANALYZE;

SELECT 'departments' AS table_name, COUNT(*) FROM departments
UNION ALL SELECT 'employees', COUNT(*) FROM employees
UNION ALL SELECT 'salary_history', COUNT(*) FROM salary_history
UNION ALL SELECT 'performance_reviews', COUNT(*) FROM performance_reviews
UNION ALL SELECT 'attendance_monthly', COUNT(*) FROM attendance_monthly;
