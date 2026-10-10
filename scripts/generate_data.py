"""
Generate a realistic synthetic HR dataset for the HR Analytics Dashboard.

Outputs (in ../data):
    departments.csv          8 departments
    employees.csv            one row per employee ever hired (2016-01 .. 2026-09)
    salary_history.csv       hire salary, yearly increments and promotions
    performance_reviews.csv  yearly ratings 2021-2025
    attendance_monthly.csv   monthly attendance per active employee, 2025-01 .. 2026-09

The data is fictional. Attrition, pay and attendance are driven by a small
set of known factors (overtime, satisfaction, pay vs. market, commute, level,
department) so that the analysis has real patterns to find.

Usage:  python scripts/generate_data.py [--seed 42] [--employees 2200]
"""
import argparse
import calendar
import csv
import math
import os
import random
from datetime import date, timedelta

SNAPSHOT = date(2026, 9, 30)
ATT_START = date(2025, 1, 1)

DEPARTMENTS = [
    # id, name, headcount weight, attrition multiplier, salary multiplier, roles by level 1..5
    (1, "Engineering", 0.27, 1.00, 1.25,
     ["Associate Software Engineer", "Software Engineer", "Senior Software Engineer", "Engineering Manager", "Director of Engineering"]),
    (2, "Sales", 0.17, 1.45, 1.00,
     ["Sales Associate", "Sales Executive", "Account Manager", "Sales Manager", "Head of Sales"]),
    (3, "Customer Support", 0.15, 1.60, 0.72,
     ["Support Associate", "Support Specialist", "Senior Support Specialist", "Support Lead", "Head of Support"]),
    (4, "Operations", 0.12, 1.05, 0.88,
     ["Operations Associate", "Operations Analyst", "Senior Operations Analyst", "Operations Manager", "Director of Operations"]),
    (5, "Marketing", 0.08, 1.10, 1.00,
     ["Marketing Associate", "Marketing Specialist", "Senior Marketing Specialist", "Marketing Manager", "Head of Marketing"]),
    (6, "Product", 0.08, 0.90, 1.30,
     ["Product Analyst", "Associate Product Manager", "Product Manager", "Senior Product Manager", "Director of Product"]),
    (7, "Finance", 0.07, 0.70, 1.05,
     ["Finance Associate", "Accountant", "Financial Analyst", "Finance Manager", "Head of Finance"]),
    (8, "Human Resources", 0.06, 0.85, 0.92,
     ["HR Associate", "HR Generalist", "HR Business Partner", "HR Manager", "Head of HR"]),
]

LOCATIONS = [("Bengaluru", 0.34), ("Hyderabad", 0.20), ("Pune", 0.18), ("Gurugram", 0.16), ("Chennai", 0.12)]
EDUCATION = [("High School", 0.05), ("Diploma", 0.08), ("Bachelor's", 0.58), ("Master's", 0.26), ("PhD", 0.03)]
EDU_FIELD = ["Engineering", "Commerce", "Science", "Management", "Arts", "Other"]
MARITAL = [("Single", 0.42), ("Married", 0.52), ("Divorced", 0.06)]
RECRUIT = [("Referral", 0.24), ("Job Portal", 0.33), ("LinkedIn", 0.21), ("Campus", 0.12), ("Agency", 0.10)]

# Unplanned absence propensity by department (shift work and customer-facing roles run higher).
ABSENCE_MULT = {"Customer Support": 1.45, "Sales": 1.2, "Operations": 1.15, "Engineering": 0.95,
                "Marketing": 1.0, "Product": 0.85, "Finance": 0.8, "Human Resources": 0.9}

# Annual base pay (INR) at level 1..5 before department multiplier.
LEVEL_BASE = [420_000, 750_000, 1_250_000, 2_100_000, 3_600_000]

FIRST_M = ["Aarav", "Vihaan", "Arjun", "Rohan", "Karthik", "Siddharth", "Rahul", "Aditya", "Nikhil", "Pranav",
           "Varun", "Harsh", "Akash", "Manish", "Suresh", "Rajesh", "Vikram", "Ankit", "Deepak", "Gaurav",
           "Imran", "Farhan", "Joseph", "Daniel", "Abhishek", "Kunal", "Yash", "Tarun", "Naveen", "Sameer"]
FIRST_F = ["Ananya", "Diya", "Priya", "Sneha", "Kavya", "Isha", "Neha", "Pooja", "Riya", "Shreya",
           "Aditi", "Meera", "Divya", "Lakshmi", "Nisha", "Swati", "Anjali", "Tanvi", "Sana", "Ayesha",
           "Fatima", "Mary", "Sarah", "Nandini", "Bhavna", "Kritika", "Simran", "Pallavi", "Madhuri", "Revathi"]
LAST = ["Sharma", "Verma", "Iyer", "Reddy", "Nair", "Patel", "Gupta", "Singh", "Kumar", "Rao",
        "Menon", "Joshi", "Desai", "Kulkarni", "Chatterjee", "Banerjee", "Das", "Mehta", "Shah", "Pillai",
        "Khan", "Ahmed", "Fernandes", "D'Souza", "Agarwal", "Bose", "Mishra", "Pandey", "Saxena", "Krishnan"]

VOLUNTARY_REASONS = [("Better Opportunity", 0.30), ("Compensation", 0.20), ("Career Growth", 0.17),
                     ("Work-Life Balance", 0.13), ("Relocation", 0.08), ("Manager Relationship", 0.07),
                     ("Higher Studies", 0.05)]
INVOLUNTARY_REASONS = [("Performance", 0.65), ("Restructuring", 0.25), ("Policy Violation", 0.10)]


def wchoice(rng, pairs):
    r = rng.random() * sum(w for _, w in pairs)
    for v, w in pairs:
        r -= w
        if r <= 0:
            return v
    return pairs[-1][0]


def add_months(d, n):
    m = d.month - 1 + n
    y = d.year + m // 12
    m = m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def working_days(y, m):
    n = calendar.monthrange(y, m)[1]
    return sum(1 for d in range(1, n + 1) if date(y, m, d).weekday() < 5)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def generate(seed, n_emp, out_dir):
    rng = random.Random(seed)
    os.makedirs(out_dir, exist_ok=True)

    # Hiring grows over time: weight each month by a gentle growth curve.
    months = []
    d = date(2016, 1, 1)
    while d <= date(2026, 9, 1):
        months.append(d)
        d = add_months(d, 1)
    m_weights = [1.0 + 0.11 * i / 12 for i in range(len(months))]
    # 2023 hiring freeze dip, 2025-26 expansion
    m_weights = [w * (0.55 if mm.year == 2023 else 1.25 if mm.year >= 2025 else 1.0) for w, mm in zip(m_weights, months)]

    employees, salaries, reviews, attendance = [], [], [], []

    for i in range(n_emp):
        emp_id = f"EMP{10001 + i}"
        dept = wchoice(rng, [(dd, dd[2]) for dd in DEPARTMENTS])
        dept_id, dept_name, _, dept_attr, dept_sal, roles = dept
        gender = wchoice(rng, [("Male", 0.58), ("Female", 0.40), ("Non-binary", 0.02)])
        if dept_name in ("Human Resources", "Marketing"):
            gender = wchoice(rng, [("Male", 0.40), ("Female", 0.58), ("Non-binary", 0.02)])
        first = rng.choice(FIRST_F if gender == "Female" else FIRST_M if gender == "Male" else FIRST_F + FIRST_M)
        last = rng.choice(LAST)

        hire_month = wchoice(rng, list(zip(months, m_weights)))
        hire = hire_month + timedelta(days=rng.randint(0, 27))
        if hire > SNAPSHOT:
            hire = SNAPSHOT - timedelta(days=rng.randint(1, 20))

        level = wchoice(rng, [(1, 0.34), (2, 0.31), (3, 0.21), (4, 0.10), (5, 0.04)])
        age_at_hire = clamp(int(rng.gauss(22 + level * 4.2, 3.5)), 20, 58)
        dob = hire - timedelta(days=int(age_at_hire * 365.25) + rng.randint(0, 364))
        education = wchoice(rng, EDUCATION)
        if level >= 4 and education in ("High School", "Diploma"):
            education = "Bachelor's"
        edu_field = "Engineering" if dept_name in ("Engineering", "Product") and rng.random() < 0.75 else rng.choice(EDU_FIELD)
        marital = wchoice(rng, MARITAL) if age_at_hire > 25 else wchoice(rng, [("Single", 0.85), ("Married", 0.15)])
        location = wchoice(rng, LOCATIONS)
        work_mode = wchoice(rng, [("Hybrid", 0.55), ("On-site", 0.33), ("Remote", 0.12)])
        if dept_name == "Customer Support":
            work_mode = wchoice(rng, [("On-site", 0.70), ("Hybrid", 0.30)])
        distance = 0 if work_mode == "Remote" else clamp(int(rng.lognormvariate(2.3, 0.6)), 1, 60)
        recruit = wchoice(rng, RECRUIT)

        # Latent traits
        ability = rng.gauss(0, 1)
        engagement = rng.gauss(0, 1)
        overtime = rng.random() < (0.38 if dept_name in ("Engineering", "Customer Support", "Sales") else 0.22)
        if overtime:
            engagement -= 0.45
        job_sat = clamp(int(round(2.6 + 0.85 * engagement + rng.gauss(0, 0.5))), 1, 4)
        env_sat = clamp(int(round(2.7 + 0.6 * engagement + rng.gauss(0, 0.7))), 1, 4)
        wlb = clamp(int(round(2.8 + 0.5 * engagement - (0.7 if overtime else 0) + rng.gauss(0, 0.6))), 1, 4)
        rel_sat = clamp(int(round(2.8 + 0.4 * engagement + rng.gauss(0, 0.8))), 1, 4)

        # Hiring pay: compa-ratio vs market band; women hired slightly lower on average (an issue for HR to find).
        compa = rng.gauss(1.0, 0.09) - (0.035 if gender == "Female" else 0)
        salary = LEVEL_BASE[level - 1] * dept_sal * compa
        if location in ("Bengaluru", "Gurugram"):
            salary *= 1.06
        salary = round(salary / 1000) * 1000
        salaries.append([emp_id, hire.isoformat(), salary, 0.0, "Hire", level])

        # Attrition hazard (annual)
        h = 0.085 * dept_attr
        h *= {1: 2.3, 2: 1.35, 3: 0.85, 4: 0.55}[job_sat]
        h *= 1.9 if overtime else 1.0
        h *= {1: 1.5, 2: 1.1, 3: 0.9, 4: 0.8}[wlb]
        h *= {1: 1.35, 2: 1.15, 3: 0.85, 4: 0.7, 5: 0.6}[level]
        h *= 1.35 if age_at_hire < 26 else 1.0
        h *= 1.3 if distance > 25 else 1.0
        h *= 1.45 if compa < 0.92 else 0.85 if compa > 1.08 else 1.0
        h *= 0.75 if recruit == "Referral" else 1.0
        h *= 0.8 if work_mode == "Remote" else 1.0
        h *= 1.15 if marital == "Single" else 1.0

        # Walk year by year: reviews, increments, promotions, exit.
        term = None
        term_type = term_reason = None
        last_promo = hire
        cur = hire
        perf_hist = []
        while True:
            # months until next anniversary-ish checkpoint
            nxt = min(add_months(cur, 12), SNAPSHOT + timedelta(days=1))
            span_years = (nxt - cur).days / 365.25
            p_exit = 1 - math.exp(-h * span_years)
            # first-year honeymoon is shorter for bad fits: bump early exits
            if cur == hire:
                p_exit *= 1.25
            if rng.random() < p_exit:
                term = cur + timedelta(days=rng.randint(15, max(16, (nxt - cur).days - 1)))
                if term > SNAPSHOT:
                    term = None
                break
            if nxt > SNAPSHOT:
                break
            cur = nxt

        end = term or SNAPSHOT
        # Yearly reviews (calendar year-end) and April increments
        for yr in range(max(hire.year, 2016), end.year + 1):
            review_date = date(yr, 12, 31)
            if review_date > end or (review_date - hire).days < 120:
                continue
            raw = 3.1 + 0.75 * ability + 0.25 * engagement + rng.gauss(0, 0.55)
            rating = clamp(int(round(raw)), 1, 5)
            perf_hist.append((yr, rating))
            if yr >= 2021:
                goals = clamp(round(rng.gauss(55 + rating * 9, 7), 1), 10, 120)
                training = clamp(int(rng.gauss(18 + 4 * (rating >= 4), 8)), 0, 80)
                reviews.append([emp_id, yr, rating, goals, training,
                                "Exceeds" if rating >= 4 else "Meets" if rating == 3 else "Below"])
            inc_date = date(yr + 1, 4, 1)
            if inc_date <= end:
                pct = {1: 0.0, 2: 0.03, 3: 0.07, 4: 0.10, 5: 0.13}[rating] + rng.gauss(0, 0.012)
                pct = max(pct, 0)
                promoted = (rating >= 4 and level < 5 and (inc_date - last_promo).days > 730
                            and rng.random() < (0.45 if rating == 5 else 0.28))
                if promoted:
                    level += 1
                    last_promo = inc_date
                    pct += 0.15 + rng.random() * 0.06
                salary = round(salary * (1 + pct) / 1000) * 1000
                salaries.append([emp_id, inc_date.isoformat(), salary, round(pct * 100, 1),
                                 "Promotion" if promoted else "Annual Increment", level])

        if term:
            last_rating = perf_hist[-1][1] if perf_hist else 3
            invol_p = 0.55 if last_rating <= 2 else 0.08
            if rng.random() < invol_p:
                term_type, term_reason = "Involuntary", wchoice(rng, INVOLUNTARY_REASONS)
                if last_rating > 2 and term_reason == "Performance":
                    term_reason = "Restructuring"
            else:
                term_type = "Voluntary"
                weights = dict(VOLUNTARY_REASONS)
                if compa < 0.92:
                    weights["Compensation"] *= 2.2
                if overtime or wlb <= 2:
                    weights["Work-Life Balance"] *= 2.2
                if (end - last_promo).days > 3 * 365:
                    weights["Career Growth"] *= 2.0
                term_reason = wchoice(rng, list(weights.items()))

        cur_sal = salary
        age_now = (end - dob).days // 365
        tenure_years = round((end - hire).days / 365.25, 2)
        years_since_promo = round((end - last_promo).days / 365.25, 1)
        last_rating = perf_hist[-1][1] if perf_hist else None
        role = roles[level - 1]

        employees.append({
            "employee_id": emp_id, "first_name": first, "last_name": last, "gender": gender,
            "date_of_birth": dob.isoformat(), "age": age_now, "marital_status": marital,
            "education": education, "education_field": edu_field,
            "department_id": dept_id, "department": dept_name, "job_role": role, "job_level": level,
            "location": location, "work_mode": work_mode, "distance_from_home_km": distance,
            "recruitment_source": recruit, "hire_date": hire.isoformat(),
            "termination_date": term.isoformat() if term else "",
            "employment_status": "Terminated" if term else "Active",
            "attrition": "Yes" if term else "No",
            "termination_type": term_type or "", "termination_reason": term_reason or "",
            "tenure_years": tenure_years, "years_since_last_promotion": years_since_promo,
            "annual_salary": cur_sal, "overtime": "Yes" if overtime else "No",
            "job_satisfaction": job_sat, "environment_satisfaction": env_sat,
            "work_life_balance": wlb, "relationship_satisfaction": rel_sat,
            "latest_performance_rating": last_rating if last_rating is not None else "",
        })

        # Monthly attendance for months the employee was active (fully or partly).
        m = ATT_START
        months_to_exit = None
        while m <= date(2026, 9, 1):
            m_end = date(m.year, m.month, calendar.monthrange(m.year, m.month)[1])
            if hire > m_end or (term and term < m):
                m = add_months(m, 1)
                continue
            wd = working_days(m.year, m.month)
            # pro-rate partial months
            first_day = max(m, hire)
            last_day = min(m_end, term) if term else m_end
            frac = ((last_day - first_day).days + 1) / ((m_end - m).days + 1)
            sched = max(1, round(wd * frac))
            if term:
                months_to_exit = (term.year - m.year) * 12 + term.month - m.month
            disengaged = months_to_exit is not None and months_to_exit <= 3
            unpl_rate = (0.016 + 0.012 * (4 - job_sat) / 3 + (0.02 if disengaged else 0)
                         + (0.006 if m.month in (1, 7, 8) else 0)) * ABSENCE_MULT[dept_name]
            unplanned = sum(1 for _ in range(sched) if rng.random() < unpl_rate)
            planned = sum(1 for _ in range(sched) if rng.random() < (0.07 if m.month in (5, 10, 12) else 0.045))
            sick = sum(1 for _ in range(sched) if rng.random() < (0.025 if m.month in (7, 8, 12, 1) else 0.012))
            absent = unplanned + planned + sick
            present = max(0, sched - absent)
            late = sum(1 for _ in range(present) if rng.random() < (0.05 + (0.04 if distance > 25 else 0) + (0.03 if disengaged else 0)))
            ot_hours = round(max(0, rng.gauss(16 if overtime else 2.5, 5 if overtime else 2)) * frac, 1)
            remote_days = 0
            if work_mode == "Remote":
                remote_days = present
            elif work_mode == "Hybrid":
                remote_days = min(present, int(round(present * rng.uniform(0.3, 0.5))))
            attendance.append([emp_id, m.isoformat(), sched, present, planned, sick, unplanned, late,
                               ot_hours, remote_days])
            m = add_months(m, 1)

    # --- write files ---
    with open(os.path.join(out_dir, "departments.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["department_id", "department_name", "cost_center"])
        for dd in DEPARTMENTS:
            w.writerow([dd[0], dd[1], f"CC-{100 + dd[0] * 10}"])

    with open(os.path.join(out_dir, "employees.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(employees[0].keys()))
        w.writeheader()
        w.writerows(employees)

    with open(os.path.join(out_dir, "salary_history.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["employee_id", "effective_date", "annual_salary", "increment_pct", "change_reason", "job_level"])
        w.writerows(salaries)

    with open(os.path.join(out_dir, "performance_reviews.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["employee_id", "review_year", "performance_rating", "goals_achieved_pct", "training_hours", "rating_band"])
        w.writerows(reviews)

    with open(os.path.join(out_dir, "attendance_monthly.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["employee_id", "month", "scheduled_days", "days_present", "planned_leave_days",
                    "sick_leave_days", "unplanned_absence_days", "late_arrivals", "overtime_hours", "remote_days"])
        w.writerows(attendance)

    print(f"employees={len(employees)} salary_rows={len(salaries)} reviews={len(reviews)} attendance_rows={len(attendance)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--employees", type=int, default=2200)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data"))
    a = ap.parse_args()
    generate(a.seed, a.employees, a.out)
