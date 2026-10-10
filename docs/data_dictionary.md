# Data dictionary

All files are in `data/`, UTF-8 CSV with a header row. The data is synthetic (see `scripts/generate_data.py`). Snapshot date: **30 September 2026**.

## employees.csv (2,200 rows, one per employee ever hired)

| Column | Type | Description |
|---|---|---|
| employee_id | text | Primary key, `EMP10001`… |
| first_name, last_name | text | Fictional names |
| gender | text | Female, Male, Non-binary |
| date_of_birth | date | |
| age | int | Age at snapshot (active) or at exit (leavers) |
| marital_status | text | Single, Married, Divorced |
| education | text | High School, Diploma, Bachelor's, Master's, PhD |
| education_field | text | Engineering, Commerce, Science, Management, Arts, Other |
| department_id, department | int, text | Foreign key to departments.csv |
| job_role | text | Role title for the current (or last) level |
| job_level | int | 1 (entry) to 5 (head of function) |
| location | text | Bengaluru, Hyderabad, Pune, Gurugram, Chennai |
| work_mode | text | On-site, Hybrid, Remote |
| distance_from_home_km | int | Commute distance; 0 for remote |
| recruitment_source | text | Referral, Job Portal, LinkedIn, Campus, Agency |
| hire_date | date | |
| termination_date | date | Blank if active |
| employment_status | text | Active, Terminated |
| attrition | text | Yes if the employee has left |
| termination_type | text | Voluntary, Involuntary (blank if active) |
| termination_reason | text | e.g. Better Opportunity, Compensation, Work-Life Balance, Performance |
| tenure_years | decimal | Years from hire to snapshot or exit |
| years_since_last_promotion | decimal | |
| annual_salary | int | Current (or last drawn) annual salary, INR |
| overtime | text | Yes if the employee regularly works overtime |
| job_satisfaction, environment_satisfaction, work_life_balance, relationship_satisfaction | int | Survey scores 1 (low) to 4 (high) |
| latest_performance_rating | int | 1–5, most recent year-end review (blank if none yet) |

## salary_history.csv (one row per pay change)

| Column | Description |
|---|---|
| employee_id | Foreign key |
| effective_date | Hire date, or 1 April for yearly increments |
| annual_salary | Salary from that date, INR |
| increment_pct | % change (0 for hire) |
| change_reason | Hire, Annual Increment, Promotion |
| job_level | Level from that date |

## performance_reviews.csv (one row per employee per year, 2021–2025)

| Column | Description |
|---|---|
| employee_id, review_year | Composite key |
| performance_rating | 1 (below) to 5 (outstanding) |
| goals_achieved_pct | % of annual goals met |
| training_hours | Training hours that year |
| rating_band | Below (1–2), Meets (3), Exceeds (4–5) |

## attendance_monthly.csv (one row per employee per month, Jan 2025 – Sep 2026)

| Column | Description |
|---|---|
| employee_id, month | Composite key; month is the first day of the month |
| scheduled_days | Working days the employee was scheduled (pro-rated for joiners and leavers) |
| days_present | Days worked |
| planned_leave_days | Pre-approved leave |
| sick_leave_days | Sick leave |
| unplanned_absence_days | Unapproved or same-day absence |
| late_arrivals | Days present with a late check-in |
| overtime_hours | Overtime hours in the month |
| remote_days | Days present worked remotely |

## departments.csv

| Column | Description |
|---|---|
| department_id | Primary key |
| department_name | |
| cost_center | Finance cost centre code |
