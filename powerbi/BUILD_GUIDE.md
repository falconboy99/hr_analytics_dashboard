# Power BI build guide

This folder holds everything needed to rebuild the dashboard in Power BI Desktop: the Power Query scripts, the DAX measures, a report theme and the page-by-page layout. A `.pbix` file is binary and has to be saved from Power BI Desktop itself, so build it once with these steps and save it here as `HR_Analytics_Dashboard.pbix`.

| File | Purpose |
|---|---|
| `power_query.m` | Load and type the five CSVs, add age, tenure and salary bands, and create the `Date` table |
| `measures.dax` | All measures: headcount, attrition, attendance, salary and KPI cards |
| `hr_theme.json` | Colour palette and visual defaults (View > Themes > Browse for themes) |

## 1. Load the data (about 10 minutes)

1. Open Power BI Desktop and choose **Transform data**.
2. Create a text parameter called `DataFolder` that points to the repository's `data\` folder, with a trailing backslash.
3. For each query in `power_query.m`, create a **Blank Query**, paste the code into the Advanced Editor and rename the query (`Employees`, `Attendance`, `SalaryHistory`, `PerformanceReviews`, `Departments`, `Date`).
4. **Close & Apply**.
5. Select the `Date` table and choose **Mark as date table** on the `Date` column.

## 2. Model relationships

| From (one) | To (many) | Active |
|---|---|---|
| `Departments[department_id]` | `Employees[department_id]` | Yes |
| `Date[Date]` | `Employees[hire_date]` | Yes |
| `Date[Date]` | `Employees[termination_date]` | **No** (used by `USERELATIONSHIP` in `[Exits]`) |
| `Date[Date]` | `Attendance[month]` | Yes |
| `Employees[employee_id]` | `Attendance[employee_id]` | Yes |
| `Employees[employee_id]` | `SalaryHistory[employee_id]` | Yes |
| `Employees[employee_id]` | `PerformanceReviews[employee_id]` | Yes |

Set cross-filter direction to **Single** for all of them.

## 3. Measures

Create an empty table (**Enter data**, call it `_Measures`) and add each measure from `measures.dax`. Use these display formats:

* Percentages (`… %`): decimal number, 1 decimal place
* `Median Salary`, `Average Salary`, `Total Payroll (INR)`: currency, Indian rupee, 0 decimals
* `Average Compa-Ratio`: decimal, 2 places

## 4. Pages and visuals

Apply `hr_theme.json`, set the canvas to 16:9, and add these slicers to every page (sync them with **View > Sync slicers**): Department, Location, Gender, Work mode, plus a `Date[Year]` slicer on the Overview and Attrition pages.

### Page 1: Overview
* Cards: `Active Employees`, `Attrition Rate % (TTM)` (with `Attrition Change (pts)` as a subtitle), `Voluntary Attrition Rate %`, `Average Tenure (yrs)`, `Median Salary`, `Attendance Rate %`, `Average Performance Rating`, `Female Share %`
* Line chart: `Date[Month Start]` × `Headcount (Period End)`
* Clustered column: `Date[Year]` × `Attrition Rate %`
* Smart narrative visual for the "what stands out" summary

### Page 2: Employees
* Bar: `Employees[department]` × `Active Employees`
* Clustered column: `Date[Year]` × `New Hires`, `Exits`
* 100% stacked bar: department × `Active Employees`, legend `gender`
* Column: `PerformanceReviews[performance_rating]` × count (filter `review_year = 2025`)
* Columns: `age_band` and `tenure_band` × `Active Employees`
* Stacked column: `location` × `Active Employees`, legend `work_mode`

### Page 3: Attrition
* Bar: department × `Attrition Rate % (TTM)` (sort descending)
* Stacked bar: `termination_reason` × `Exits`, legend `termination_type` (relative date filter: last 24 months)
* Four small columns using `Leaver Share %` by `overtime`, `job_satisfaction`, `work_life_balance`, `job_level`
* Key influencers visual: analyse `attrition`, explain by satisfaction, overtime, level, commute, salary band
* Table: employee name, department, job role, rating, `Flight Risk Score` (top N = 25 by score, `employment_status = Active`)

### Page 4: Attendance
* Cards: `Attendance Rate %`, `Absenteeism Rate %`, `Unplanned Absence Days per Employee (annualised)`, `Late Arrival Rate %`, `Overtime Hours per Employee-Month`
* Line: `Date[Month Start]` × `Attendance Rate %`
* Stacked column: month × sums of planned, sick and unplanned leave days
* Bars: department × `Absenteeism Rate %`, department × `Overtime Hours per Employee-Month`
* Matrix heatmap: department × month with `Absenteeism Rate %` and conditional background colour

### Page 5: Salary
* Cards: `Median Salary`, `Total Payroll (INR Cr)`, `Gender Pay Gap (compa pts)`, `Average Increment %`
* Bar: department × `Median Salary`
* Box-and-whisker (AppSource) or clustered column of P25/median/P75 by `job_level`
* Clustered bar: department × `Average Compa-Ratio`, legend `gender`
* Column: `PerformanceReviews[performance_rating]` × `Average Increment %`
* Column: `salary_band` × `Active Employees`

## 5. Publish

Save as `powerbi/HR_Analytics_Dashboard.pbix`, export a PDF of the pages (**File > Export > PDF**), and optionally publish to the Power BI service with a scheduled refresh pointed at the CSV folder or the PostgreSQL views in `sql/03_views.sql`.

### Using PostgreSQL instead of CSVs
Load the database with the scripts in `sql/`, then in Power BI choose **Get data > PostgreSQL database** and import `hr.employees`, `hr.attendance_monthly`, `hr.salary_history`, `hr.performance_reviews` and `hr.departments`. The measures work unchanged.
