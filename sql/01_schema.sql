-- =====================================================================
-- HR Analytics Dashboard : schema (PostgreSQL 13+)
-- Run from the repository root:
--   psql -d hr_analytics -f sql/01_schema.sql
-- =====================================================================

DROP SCHEMA IF EXISTS hr CASCADE;
CREATE SCHEMA hr;
SET search_path TO hr;

CREATE TABLE departments (
    department_id    SMALLINT     PRIMARY KEY,
    department_name  VARCHAR(50)  NOT NULL UNIQUE,
    cost_center      VARCHAR(10)  NOT NULL
);

CREATE TABLE employees (
    employee_id                 VARCHAR(10)  PRIMARY KEY,
    first_name                  VARCHAR(40)  NOT NULL,
    last_name                   VARCHAR(40)  NOT NULL,
    gender                      VARCHAR(12)  NOT NULL,
    date_of_birth               DATE         NOT NULL,
    age                         SMALLINT     NOT NULL,          -- at snapshot or at exit
    marital_status              VARCHAR(10),
    education                   VARCHAR(20),
    education_field             VARCHAR(20),
    department_id               SMALLINT     NOT NULL REFERENCES departments,
    department                  VARCHAR(50)  NOT NULL,
    job_role                    VARCHAR(60)  NOT NULL,
    job_level                   SMALLINT     NOT NULL CHECK (job_level BETWEEN 1 AND 5),
    location                    VARCHAR(20)  NOT NULL,
    work_mode                   VARCHAR(10)  NOT NULL,
    distance_from_home_km       SMALLINT,
    recruitment_source          VARCHAR(20),
    hire_date                   DATE         NOT NULL,
    termination_date            DATE,
    employment_status           VARCHAR(10)  NOT NULL CHECK (employment_status IN ('Active','Terminated')),
    attrition                   VARCHAR(3)   NOT NULL CHECK (attrition IN ('Yes','No')),
    termination_type            VARCHAR(12),
    termination_reason          VARCHAR(30),
    tenure_years                NUMERIC(5,2) NOT NULL,
    years_since_last_promotion  NUMERIC(4,1),
    annual_salary               NUMERIC(12,0) NOT NULL,          -- INR, current or last drawn
    overtime                    VARCHAR(3)   NOT NULL,
    job_satisfaction            SMALLINT     CHECK (job_satisfaction BETWEEN 1 AND 4),
    environment_satisfaction    SMALLINT     CHECK (environment_satisfaction BETWEEN 1 AND 4),
    work_life_balance           SMALLINT     CHECK (work_life_balance BETWEEN 1 AND 4),
    relationship_satisfaction   SMALLINT     CHECK (relationship_satisfaction BETWEEN 1 AND 4),
    latest_performance_rating   SMALLINT     CHECK (latest_performance_rating BETWEEN 1 AND 5),
    CHECK (termination_date IS NULL OR termination_date >= hire_date)
);

CREATE TABLE salary_history (
    employee_id     VARCHAR(10)   NOT NULL REFERENCES employees,
    effective_date  DATE          NOT NULL,
    annual_salary   NUMERIC(12,0) NOT NULL,
    increment_pct   NUMERIC(5,1)  NOT NULL,
    change_reason   VARCHAR(20)   NOT NULL,   -- Hire | Annual Increment | Promotion
    job_level       SMALLINT      NOT NULL,
    PRIMARY KEY (employee_id, effective_date)
);

CREATE TABLE performance_reviews (
    employee_id         VARCHAR(10)  NOT NULL REFERENCES employees,
    review_year         SMALLINT     NOT NULL,
    performance_rating  SMALLINT     NOT NULL CHECK (performance_rating BETWEEN 1 AND 5),
    goals_achieved_pct  NUMERIC(5,1),
    training_hours      SMALLINT,
    rating_band         VARCHAR(10),
    PRIMARY KEY (employee_id, review_year)
);

CREATE TABLE attendance_monthly (
    employee_id             VARCHAR(10)  NOT NULL REFERENCES employees,
    month                   DATE         NOT NULL,   -- first day of month
    scheduled_days          SMALLINT     NOT NULL,
    days_present            SMALLINT     NOT NULL,
    planned_leave_days      SMALLINT     NOT NULL,
    sick_leave_days         SMALLINT     NOT NULL,
    unplanned_absence_days  SMALLINT     NOT NULL,
    late_arrivals           SMALLINT     NOT NULL,
    overtime_hours          NUMERIC(5,1) NOT NULL,
    remote_days             SMALLINT     NOT NULL,
    PRIMARY KEY (employee_id, month)
);

CREATE INDEX ix_emp_dept     ON employees (department_id);
CREATE INDEX ix_emp_dates    ON employees (hire_date, termination_date);
CREATE INDEX ix_att_month    ON attendance_monthly (month);
CREATE INDEX ix_sal_date     ON salary_history (effective_date);
