// =====================================================================
// Power Query (M) for the HR Analytics Dashboard.
// In Power BI Desktop: Home > Transform data > New Source > Blank Query,
// open Advanced Editor and paste each query below as its own query,
// named exactly as in the comment above it. Set DataFolder first.
// =====================================================================

// ---- Query: DataFolder (Home > Manage Parameters > New, type Text) ----
// "C:\path\to\hr-analytics-dashboard\data\"

// ---- Query: Employees ----
let
    Source   = Csv.Document(File.Contents(DataFolder & "employees.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Headers  = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed    = Table.TransformColumnTypes(Headers, {
        {"employee_id", type text}, {"first_name", type text}, {"last_name", type text}, {"gender", type text},
        {"date_of_birth", type date}, {"age", Int64.Type}, {"marital_status", type text}, {"education", type text},
        {"education_field", type text}, {"department_id", Int64.Type}, {"department", type text}, {"job_role", type text},
        {"job_level", Int64.Type}, {"location", type text}, {"work_mode", type text}, {"distance_from_home_km", Int64.Type},
        {"recruitment_source", type text}, {"hire_date", type date}, {"termination_date", type date},
        {"employment_status", type text}, {"attrition", type text}, {"termination_type", type text},
        {"termination_reason", type text}, {"tenure_years", type number}, {"years_since_last_promotion", type number},
        {"annual_salary", Currency.Type}, {"overtime", type text}, {"job_satisfaction", Int64.Type},
        {"environment_satisfaction", Int64.Type}, {"work_life_balance", Int64.Type},
        {"relationship_satisfaction", Int64.Type}, {"latest_performance_rating", Int64.Type}}, "en-IN"),
    FullName = Table.AddColumn(Typed, "employee_name", each [first_name] & " " & [last_name], type text),
    AgeBand  = Table.AddColumn(FullName, "age_band", each
                 if [age] < 25 then "< 25" else if [age] < 35 then "25-34" else if [age] < 45 then "35-44"
                 else if [age] < 55 then "45-54" else "55+", type text),
    Tenure   = Table.AddColumn(AgeBand, "tenure_band", each
                 if [tenure_years] < 1 then "< 1 yr" else if [tenure_years] < 3 then "1-3 yrs"
                 else if [tenure_years] < 5 then "3-5 yrs" else if [tenure_years] < 10 then "5-10 yrs" else "10+ yrs", type text),
    SalBand  = Table.AddColumn(Tenure, "salary_band", each
                 if [annual_salary] < 600000 then "< 6 L" else if [annual_salary] < 1000000 then "6-10 L"
                 else if [annual_salary] < 1500000 then "10-15 L" else if [annual_salary] < 2500000 then "15-25 L" else "25 L+", type text)
in
    SalBand

// ---- Query: Attendance ----
let
    Source  = Csv.Document(File.Contents(DataFolder & "attendance_monthly.csv"), [Delimiter = ",", Encoding = 65001]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed   = Table.TransformColumnTypes(Headers, {
        {"employee_id", type text}, {"month", type date}, {"scheduled_days", Int64.Type}, {"days_present", Int64.Type},
        {"planned_leave_days", Int64.Type}, {"sick_leave_days", Int64.Type}, {"unplanned_absence_days", Int64.Type},
        {"late_arrivals", Int64.Type}, {"overtime_hours", type number}, {"remote_days", Int64.Type}})
in
    Typed

// ---- Query: SalaryHistory ----
let
    Source  = Csv.Document(File.Contents(DataFolder & "salary_history.csv"), [Delimiter = ",", Encoding = 65001]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed   = Table.TransformColumnTypes(Headers, {
        {"employee_id", type text}, {"effective_date", type date}, {"annual_salary", Currency.Type},
        {"increment_pct", type number}, {"change_reason", type text}, {"job_level", Int64.Type}})
in
    Typed

// ---- Query: PerformanceReviews ----
let
    Source  = Csv.Document(File.Contents(DataFolder & "performance_reviews.csv"), [Delimiter = ",", Encoding = 65001]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed   = Table.TransformColumnTypes(Headers, {
        {"employee_id", type text}, {"review_year", Int64.Type}, {"performance_rating", Int64.Type},
        {"goals_achieved_pct", type number}, {"training_hours", Int64.Type}, {"rating_band", type text}})
in
    Typed

// ---- Query: Departments ----
let
    Source  = Csv.Document(File.Contents(DataFolder & "departments.csv"), [Delimiter = ",", Encoding = 65001]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed   = Table.TransformColumnTypes(Headers, {{"department_id", Int64.Type}, {"department_name", type text}, {"cost_center", type text}})
in
    Typed

// ---- Query: Date ----
let
    StartDate = #date(2016, 1, 1),
    EndDate   = #date(2026, 12, 31),
    Dates     = List.Dates(StartDate, Duration.Days(EndDate - StartDate) + 1, #duration(1, 0, 0, 0)),
    AsTable   = Table.FromList(Dates, Splitter.SplitByNothing(), {"Date"}),
    Typed     = Table.TransformColumnTypes(AsTable, {{"Date", type date}}),
    Year      = Table.AddColumn(Typed, "Year", each Date.Year([Date]), Int64.Type),
    MonthNo   = Table.AddColumn(Year, "Month No", each Date.Month([Date]), Int64.Type),
    MonthName = Table.AddColumn(MonthNo, "Month", each Date.ToText([Date], "MMM"), type text),
    MonthStart= Table.AddColumn(MonthName, "Month Start", each Date.StartOfMonth([Date]), type date),
    YearMonth = Table.AddColumn(MonthStart, "Year-Month", each Date.ToText([Date], "MMM yyyy"), type text),
    Quarter   = Table.AddColumn(YearMonth, "Quarter", each "Q" & Text.From(Date.QuarterOfYear([Date])), type text)
in
    Quarter
