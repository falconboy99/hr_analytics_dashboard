"""
Build the interactive HTML dashboard.

Reads the CSVs in ../data, packs a compact employee-level dataset plus
monthly attendance aggregates into JSON, and injects it into
dashboard/template.html to produce dashboard/index.html. All filtering
and KPI maths then run in the browser, so the page needs no server.

Usage:  python scripts/build_dashboard.py
"""
import csv
import json
import os
from collections import defaultdict

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA = os.path.join(ROOT, "data")
BASE_YEAR = 2016  # month index 0 = Jan 2016


def month_idx(iso):
    if not iso:
        return -1
    y, m = int(iso[:4]), int(iso[5:7])
    return (y - BASE_YEAR) * 12 + (m - 1)


def read(name):
    with open(os.path.join(DATA, name), newline="") as f:
        return list(csv.DictReader(f))


def main():
    emps = read("employees.csv")
    sal = read("salary_history.csv")
    att = read("attendance_monthly.csv")

    depts = sorted({e["department"] for e in emps})
    locs = sorted({e["location"] for e in emps})
    genders = ["Female", "Male", "Non-binary"]
    modes = ["On-site", "Hybrid", "Remote"]
    reasons = sorted({e["termination_reason"] for e in emps if e["termination_reason"]})
    sources = sorted({e["recruitment_source"] for e in emps})

    # Last April-2026 increment per employee (if they were in that cycle)
    last_inc = {}
    for s in sal:
        if s["effective_date"] == "2026-04-01":
            last_inc[s["employee_id"]] = float(s["increment_pct"])

    rows = []
    for e in emps:
        rows.append([
            e["employee_id"],
            f'{e["first_name"]} {e["last_name"]}',
            depts.index(e["department"]),
            locs.index(e["location"]),
            genders.index(e["gender"]),
            modes.index(e["work_mode"]),
            int(e["job_level"]),
            e["job_role"],
            int(e["age"]),
            month_idx(e["hire_date"]),
            month_idx(e["termination_date"]),
            {"": 0, "Voluntary": 1, "Involuntary": 2}[e["termination_type"]],
            reasons.index(e["termination_reason"]) if e["termination_reason"] else -1,
            float(e["tenure_years"]),
            int(float(e["annual_salary"])),
            1 if e["overtime"] == "Yes" else 0,
            int(e["job_satisfaction"]),
            int(e["work_life_balance"]),
            int(e["latest_performance_rating"]) if e["latest_performance_rating"] else 0,
            int(e["distance_from_home_km"]),
            float(e["years_since_last_promotion"]),
            last_inc.get(e["employee_id"], -1),
            sources.index(e["recruitment_source"]),
        ])

    # Attendance aggregated by month x department x location x gender x work mode
    emp_key = {e["employee_id"]: (depts.index(e["department"]), locs.index(e["location"]),
                                  genders.index(e["gender"]), modes.index(e["work_mode"])) for e in emps}
    agg = defaultdict(lambda: [0, 0, 0, 0, 0, 0, 0.0, 0])
    for a in att:
        k = (month_idx(a["month"]),) + emp_key[a["employee_id"]]
        v = agg[k]
        v[0] += int(a["scheduled_days"])
        v[1] += int(a["days_present"])
        v[2] += int(a["planned_leave_days"])
        v[3] += int(a["sick_leave_days"])
        v[4] += int(a["unplanned_absence_days"])
        v[5] += int(a["late_arrivals"])
        v[6] += float(a["overtime_hours"])
        v[7] += 1
    att_rows = [list(k) + v[:6] + [round(v[6], 1), v[7]] for k, v in sorted(agg.items())]

    payload = {
        "asOf": "2026-09-30",
        "asOfIdx": month_idx("2026-09-30"),
        "baseYear": BASE_YEAR,
        "depts": depts, "locs": locs, "genders": genders, "modes": modes,
        "reasons": reasons, "sources": sources,
        "empCols": ["id", "name", "dept", "loc", "gender", "mode", "level", "role", "age", "hire", "term",
                    "termType", "reason", "tenure", "salary", "ot", "jobSat", "wlb", "rating", "dist",
                    "yrsPromo", "lastInc", "source"],
        "emps": rows,
        "attCols": ["m", "dept", "loc", "gender", "mode", "sched", "present", "planned", "sick", "unplanned",
                    "late", "otHours", "empMonths"],
        "att": att_rows,
    }

    with open(os.path.join(ROOT, "dashboard", "template.html")) as f:
        tpl = f.read()
    out = tpl.replace("/*__HR_DATA__*/null", json.dumps(payload, separators=(",", ":")))
    with open(os.path.join(ROOT, "dashboard", "index.html"), "w") as f:
        f.write(out)
    print(f"dashboard/index.html written ({len(out) / 1024:.0f} KB, {len(rows)} employees, {len(att_rows)} attendance rows)")


if __name__ == "__main__":
    main()
