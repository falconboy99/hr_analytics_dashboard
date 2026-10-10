"""
Build the HR Analytics Report (PDF) from the CSVs in ../data.

Metric definitions match sql/08_kpi_report.sql and the dashboard:
  attrition rate = exits / average monthly headcount (annualised)
  attendance rate = days present / scheduled days
  absenteeism = (sick + unplanned days) / scheduled days
  compa-ratio = salary / median salary of active staff in same department and level

Usage:  python scripts/build_report.py      -> report/HR_Analytics_Report.pdf
Needs:  pandas, matplotlib, reportlab
"""
import os
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "report")
FIG = os.path.join(OUT, "figures")
AS_OF = pd.Timestamp("2026-09-30")
TTM_START = pd.Timestamp("2025-10-01")

INK, INK2, MUTED, GRID = "#111722", "#4b5466", "#7f8796", "#e4e7ed"
S = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": "#ccd2dc", "axes.labelcolor": INK2,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False, "axes.axisbelow": True, "axes.titlesize": 10,
    "axes.titleweight": "bold", "axes.titlecolor": INK, "axes.titlelocation": "left", "legend.frameon": False,
})


# ---------------------------------------------------------------- data
def load():
    e = pd.read_csv(os.path.join(DATA, "employees.csv"), parse_dates=["hire_date", "termination_date", "date_of_birth"])
    a = pd.read_csv(os.path.join(DATA, "attendance_monthly.csv"), parse_dates=["month"])
    s = pd.read_csv(os.path.join(DATA, "salary_history.csv"), parse_dates=["effective_date"])
    r = pd.read_csv(os.path.join(DATA, "performance_reviews.csv"))
    a = a.merge(e[["employee_id", "department", "work_mode"]], on="employee_id")
    return e, a, s, r


def month_starts(start, end):
    return pd.date_range(start, end, freq="MS")


def headcount_end(e, m_end):
    return ((e.hire_date <= m_end) & (e.termination_date.isna() | (e.termination_date > m_end))).sum()


def headcount_start(e, m_start):
    return ((e.hire_date < m_start) & (e.termination_date.isna() | (e.termination_date >= m_start))).sum()


def attrition(e, start, end, voluntary=False):
    months = month_starts(start, end)
    hc = np.mean([(headcount_start(e, m) + headcount_end(e, m + pd.offsets.MonthEnd(0))) / 2 for m in months])
    ex = e[(e.termination_date >= start) & (e.termination_date <= end)]
    if voluntary:
        ex = ex[ex.termination_type == "Voluntary"]
    return len(ex), hc, 100 * len(ex) / hc * 12 / len(months) if hc else np.nan


def fig_path(name):
    return os.path.join(FIG, name + ".png")


def save(fig, name):
    fig.tight_layout()
    fig.savefig(fig_path(name), dpi=200)
    plt.close(fig)


def hbar(ax, labels, values, color, fmt):
    y = np.arange(len(labels))[::-1]
    ax.barh(y, values, color=color, height=0.62)
    ax.set_yticks(y, labels)
    ax.grid(axis="y", visible=False)
    for yi, v in zip(y, values):
        ax.text(v, yi, " " + fmt(v), va="center", fontsize=8, color=INK2)
    ax.set_xlim(0, max(values) * 1.18)


# ---------------------------------------------------------------- analysis
def analyse(e, a, s, r):
    act = e[e.employment_status == "Active"].copy()
    k = {}
    k["active"] = len(act)
    k["hires_ttm"] = int(((e.hire_date >= TTM_START) & (e.hire_date <= AS_OF)).sum())
    k["exits_ttm"], k["avg_hc_ttm"], k["attr_ttm"] = attrition(e, TTM_START, AS_OF)
    k["vol_exits_ttm"], _, k["vol_attr_ttm"] = attrition(e, TTM_START, AS_OF, voluntary=True)
    _, _, k["attr_prev"] = attrition(e, TTM_START - pd.DateOffset(years=1), AS_OF - pd.DateOffset(years=1))
    k["tenure"] = act.tenure_years.mean()
    k["age"] = act.age.mean()
    k["female"] = 100 * (act.gender == "Female").mean()
    k["median_sal"] = act.annual_salary.median()
    k["payroll_cr"] = act.annual_salary.sum() / 1e7
    at = a[a.month >= TTM_START]
    k["att_rate"] = 100 * at.days_present.sum() / at.scheduled_days.sum()
    k["abs_rate"] = 100 * (at.sick_leave_days.sum() + at.unplanned_absence_days.sum()) / at.scheduled_days.sum()
    k["unpl_per_emp"] = at.unplanned_absence_days.sum() / len(at) * 12
    r25 = r[r.review_year == 2025]
    k["avg_rating"] = r25.performance_rating.mean()
    k["high_perf"] = 100 * (r25.performance_rating >= 4).mean()
    k["overtime"] = 100 * (act.overtime == "Yes").mean()

    band = act.groupby(["department", "job_level"]).annual_salary.median().rename("band_med")
    act = act.join(band, on=["department", "job_level"])
    act["compa"] = act.annual_salary / act.band_med
    k["gap_adj"] = 100 * (act[act.gender == "Male"].compa.mean() - act[act.gender == "Female"].compa.mean())
    m_med, f_med = act[act.gender == "Male"].annual_salary.median(), act[act.gender == "Female"].annual_salary.median()
    k["gap_raw"] = 100 * (m_med - f_med) / m_med
    k["below_090"] = int((act.compa < 0.9).sum())

    # department tables
    dept = []
    for d, g in e.groupby("department"):
        ex, hc, rate = attrition(g, TTM_START, AS_OF)
        ga = act[act.department == d]
        aa = at[at.department == d]
        dept.append(dict(department=d, headcount=len(ga), attr=rate, exits=ex,
                         median_sal=ga.annual_salary.median(), tenure=ga.tenure_years.mean(),
                         abs=100 * (aa.sick_leave_days.sum() + aa.unplanned_absence_days.sum()) / aa.scheduled_days.sum(),
                         ot=aa.overtime_hours.mean(),
                         gap=100 * (ga[ga.gender == "Male"].compa.mean() - ga[ga.gender == "Female"].compa.mean())))
    k["dept"] = pd.DataFrame(dept).sort_values("headcount", ascending=False)

    # yearly attrition
    yrs = []
    for y in range(2019, 2027):
        st, en = pd.Timestamp(y, 1, 1), min(pd.Timestamp(y, 12, 31), AS_OF)
        ex, hc, rate = attrition(e, st, en)
        _, _, vr = attrition(e, st, en, voluntary=True)
        hires = ((e.hire_date >= st) & (e.hire_date <= en)).sum()
        yrs.append(dict(year=y, exits=ex, hires=hires, rate=rate, vol=vr, hc_end=headcount_end(e, en)))
    k["years"] = pd.DataFrame(yrs)

    lv = e[e.attrition == "Yes"]
    k["first_year_exit"] = 100 * (lv.tenure_years < 1).mean()
    k["drivers"] = {
        "Overtime": e.groupby("overtime").attrition.apply(lambda x: 100 * (x == "Yes").mean()),
        "Job satisfaction": e.groupby("job_satisfaction").attrition.apply(lambda x: 100 * (x == "Yes").mean()),
        "Work-life balance": e.groupby("work_life_balance").attrition.apply(lambda x: 100 * (x == "Yes").mean()),
        "Job level": e.groupby("job_level").attrition.apply(lambda x: 100 * (x == "Yes").mean()),
    }
    rec = e[e.termination_date > AS_OF - pd.DateOffset(months=24)]
    k["reasons"] = rec.groupby(["termination_reason", "termination_type"]).size().unstack(fill_value=0)
    k["reasons"]["total"] = k["reasons"].sum(axis=1)
    k["reasons"] = k["reasons"].sort_values("total", ascending=False)
    vol = rec[rec.termination_type == "Voluntary"]
    k["regretted"] = int((vol.latest_performance_rating >= 4).sum())
    k["vol_24"] = len(vol)
    k["top_reason"] = vol.termination_reason.value_counts()

    # attendance monthly
    k["att_month"] = a.groupby("month").agg(sched=("scheduled_days", "sum"), present=("days_present", "sum"),
                                            planned=("planned_leave_days", "sum"), sick=("sick_leave_days", "sum"),
                                            unpl=("unplanned_absence_days", "sum"), n=("employee_id", "count"))
    leaver_last3 = a.merge(e[["employee_id", "termination_date"]], on="employee_id")
    flag = leaver_last3.termination_date.notna() & (
        leaver_last3.month >= leaver_last3.termination_date.dt.to_period("M").dt.to_timestamp() - pd.DateOffset(months=3))
    k["unpl_leaver"] = 100 * leaver_last3[flag].unplanned_absence_days.sum() / leaver_last3[flag].scheduled_days.sum()
    k["unpl_other"] = 100 * leaver_last3[~flag].unplanned_absence_days.sum() / leaver_last3[~flag].scheduled_days.sum()

    # increments by rating (April 2026)
    inc = s[(s.effective_date == "2026-04-01")].merge(r[r.review_year == 2025], on="employee_id")
    k["inc_by_rating"] = inc.groupby("performance_rating").increment_pct.mean()
    k["level_sal"] = act.groupby("job_level").annual_salary.describe(percentiles=[.25, .5, .75])
    k["act"] = act
    return k


# ---------------------------------------------------------------- charts
def charts(e, a, k):
    os.makedirs(FIG, exist_ok=True)
    # headcount trend
    ms = month_starts("2019-01-01", "2026-09-01")
    hc = [headcount_end(e, m + pd.offsets.MonthEnd(0)) for m in ms]
    fig, ax = plt.subplots(figsize=(7.2, 2.6))
    ax.plot(ms, hc, color=S[0], lw=2)
    ax.fill_between(ms, hc, min(hc) * 0.9, color=S[0], alpha=0.12)
    ax.set_ylim(min(hc) * 0.9, max(hc) * 1.06)
    ax.set_title("Month-end headcount, Jan 2019 – Sep 2026")
    ax.annotate(f"{hc[-1]:,}", (ms[-1], hc[-1]), xytext=(-6, 6), textcoords="offset points", ha="right", fontsize=8, color=INK)
    save(fig, "headcount")

    # hires vs exits & attrition rate
    y = k["years"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.2, 2.6))
    x = np.arange(len(y))
    a1.bar(x - 0.2, y.hires, 0.38, color=S[0], label="Hires")
    a1.bar(x + 0.2, y.exits, 0.38, color=S[1], label="Exits")
    a1.set_xticks(x, [str(v) if v < 2026 else "2026\nYTD" for v in y.year], fontsize=7.5)
    a1.grid(axis="x", visible=False)
    a1.legend(loc="upper left", fontsize=8)
    a1.set_title("Hires and exits by year")
    a2.bar(x, y.rate, 0.6, color=S[1])
    for xi, v in zip(x, y.rate):
        a2.text(xi, v + 0.3, f"{v:.1f}", ha="center", fontsize=7.5, color=INK2)
    a2.set_xticks(x, [str(v) if v < 2026 else "2026*" for v in y.year], fontsize=7.5)
    a2.grid(axis="x", visible=False)
    a2.set_ylim(0, y.rate.max() * 1.2)
    a2.set_title("Attrition rate by year (%)")
    save(fig, "years")

    # attrition by dept + reasons
    d = k["dept"].sort_values("attr", ascending=False)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.2, 2.9))
    hbar(a1, d.department, d.attr, S[1], lambda v: f"{v:.1f}%")
    a1.axvline(k["attr_ttm"], color=INK2, lw=1, ls="--")
    a1.set_title("Attrition by department, TTM (%)")
    rs = k["reasons"]
    yy = np.arange(len(rs))[::-1]
    vol = rs.get("Voluntary", 0)
    inv = rs.get("Involuntary", 0)
    a2.barh(yy, vol, color=S[1], height=0.62, label="Voluntary")
    a2.barh(yy, inv, left=vol, color=S[6], height=0.62, label="Involuntary")
    a2.set_yticks(yy, rs.index)
    a2.grid(axis="y", visible=False)
    a2.legend(loc="lower right", fontsize=7.5)
    a2.set_title("Exit reasons, last 24 mo")
    save(fig, "attrition")

    # drivers
    fig, axs = plt.subplots(1, 4, figsize=(7.2, 2.1), sharey=True)
    for ax, (name, ser) in zip(axs, k["drivers"].items()):
        labels = [str(i) if name != "Job level" else f"L{i}" for i in ser.index]
        ax.bar(labels, ser.values, color=S[1], width=0.6)
        ax.set_title(name, fontsize=8.5)
        ax.grid(axis="x", visible=False)
        ax.set_ylim(0, 100)
        for i, v in enumerate(ser.values):
            ax.text(i, v + 2, f"{v:.0f}", ha="center", fontsize=7, color=INK2)
    axs[0].set_ylabel("% who left")
    save(fig, "drivers")

    # attendance
    am = k["att_month"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.2, 2.6))
    a1.plot(am.index, 100 * am.present / am.sched, color=S[0], lw=2, marker="o", ms=3)
    a1.set_title("Attendance rate by month (%)")
    a1.tick_params(axis="x", labelsize=7, rotation=0)
    a1.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%b %y"))
    a1.xaxis.set_major_locator(matplotlib.dates.MonthLocator(bymonth=[1, 4, 7, 10]))
    bottom = np.zeros(len(am))
    for col, lab, c in [("planned", "Planned", S[0]), ("sick", "Sick", S[3]), ("unpl", "Unplanned", S[1])]:
        v = (am[col] / am.n).values
        a2.bar(am.index, v, width=22, bottom=bottom, color=c, label=lab)
        bottom += v
    a2.set_title("Leave days per employee per month")
    a2.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%b %y"))
    a2.xaxis.set_major_locator(matplotlib.dates.MonthLocator(bymonth=[1, 4, 7, 10]))
    a2.tick_params(axis="x", labelsize=7)
    a2.grid(axis="x", visible=False)
    a2.legend(fontsize=7, loc="upper left", ncol=3)
    a2.set_ylim(0, bottom.max() * 1.25)
    save(fig, "attendance")

    d = k["dept"].sort_values("abs", ascending=False)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.2, 2.6))
    hbar(a1, d.department, d["abs"], S[3], lambda v: f"{v:.1f}%")
    a1.set_title("Absenteeism by department, TTM")
    d2 = k["dept"].sort_values("ot", ascending=False)
    hbar(a2, d2.department, d2.ot, S[0], lambda v: f"{v:.1f} h")
    a2.set_title("Overtime h / employee / mo")
    save(fig, "attendance_dept")

    # salary
    d = k["dept"].sort_values("median_sal", ascending=False)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.2, 2.7))
    hbar(a1, d.department, d.median_sal / 1e5, S[0], lambda v: f"₹{v:.1f} L")
    a1.set_title("Median salary by department (₹ lakh)")
    act = k["act"]
    depts = sorted(act.department.unique())
    yy = np.arange(len(depts))[::-1]
    fc = [act[(act.department == x) & (act.gender == "Female")].compa.mean() for x in depts]
    mc = [act[(act.department == x) & (act.gender == "Male")].compa.mean() for x in depts]
    a2.barh(yy + 0.19, fc, 0.36, color=S[0], label="Women")
    a2.barh(yy - 0.19, mc, 0.36, color=S[2], label="Men")
    a2.axvline(1, color=INK2, lw=1, ls="--")
    a2.set_xlim(0.85, 1.2)
    a2.set_yticks(yy, depts)
    a2.grid(axis="y", visible=False)
    a2.legend(fontsize=7.5, loc="lower right")
    a2.set_title("Compa-ratio by gender")
    save(fig, "salary")

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.2, 2.4))
    ls = k["level_sal"]
    x = np.arange(len(ls))
    a1.bar(x, (ls["75%"] - ls["25%"]) / 1e5, bottom=ls["25%"] / 1e5, color=S[0], alpha=0.35, width=0.55, label="P25–P75")
    a1.scatter(x, ls["50%"] / 1e5, marker="_", s=380, color=S[0], linewidths=2.5, label="Median", zorder=3)
    a1.set_xticks(x, [f"L{i}" for i in ls.index])
    a1.grid(axis="x", visible=False)
    a1.legend(fontsize=7.5, loc="upper left")
    a1.set_title("Salary range by job level (₹ lakh)")
    ib = k["inc_by_rating"]
    a2.bar([f"{i}" for i in ib.index], ib.values, color=S[2], width=0.6)
    for i, v in enumerate(ib.values):
        a2.text(i, v + 0.3, f"{v:.1f}%", ha="center", fontsize=7.5, color=INK2)
    a2.set_ylim(0, ib.max() * 1.2)
    a2.grid(axis="x", visible=False)
    a2.set_xlabel("2025 performance rating")
    a2.set_title("April 2026 increment by rating (%)")
    save(fig, "salary_level")


# ---------------------------------------------------------------- PDF
def register_fonts():
    # DejaVu ships with matplotlib and includes the rupee sign, which the built-in PDF fonts lack.
    fdir = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")
    pdfmetrics.registerFont(TTFont("Sans", os.path.join(fdir, "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("Sans-Bold", os.path.join(fdir, "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFontFamily("Sans", normal="Sans", bold="Sans-Bold", italic="Sans", boldItalic="Sans-Bold")


def build_pdf(k):
    register_fonts()
    ss = getSampleStyleSheet()
    H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontName="Sans-Bold", fontSize=20, leading=24, textColor=INK, spaceAfter=4)
    H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontName="Sans-Bold", fontSize=13.5, leading=17, textColor=INK, spaceBefore=4, spaceAfter=6)
    H3 = ParagraphStyle("H3", parent=ss["Heading3"], fontName="Sans-Bold", fontSize=10.5, leading=13, textColor=INK, spaceBefore=6, spaceAfter=3)
    B = ParagraphStyle("B", parent=ss["BodyText"], fontName="Sans", fontSize=9.5, leading=13.5, textColor=INK, alignment=TA_LEFT, spaceAfter=5)
    SM = ParagraphStyle("SM", parent=B, fontSize=8, leading=10.5, textColor=MUTED)
    BL = ParagraphStyle("BL", parent=B, leftIndent=12, bulletIndent=2, spaceAfter=3)

    def bullets(items):
        return [Paragraph(t, BL, bulletText="•") for t in items]

    def img(name, w=180):
        im = Image(fig_path(name))
        ratio = im.imageHeight / im.imageWidth
        im.drawWidth, im.drawHeight = w * mm, w * mm * ratio
        return im

    def table(rows, widths, num_cols=()):
        t = Table(rows, colWidths=[w * mm for w in widths], hAlign="LEFT")
        st = [("FONT", (0, 0), (-1, 0), "Sans-Bold", 8), ("FONT", (0, 1), (-1, -1), "Sans", 8.5),
              ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor(INK2)), ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor(INK)),
              ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.HexColor("#ccd2dc")),
              ("LINEBELOW", (0, 1), (-1, -1), 0.4, colors.HexColor(GRID)),
              ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5)]
        for c in num_cols:
            st.append(("ALIGN", (c, 0), (c, -1), "RIGHT"))
        t.setStyle(TableStyle(st))
        return t

    d = k["dept"]
    top_attr = d.sort_values("attr", ascending=False).iloc[0]
    low_attr = d.sort_values("attr").iloc[0]
    dr = k["drivers"]
    ot_ratio = dr["Overtime"]["Yes"] / dr["Overtime"]["No"]
    tr = k["top_reason"]
    vol24 = k["vol_24"]
    am = k["att_month"]
    cs = d.sort_values("abs", ascending=False).iloc[0]

    story = []
    story += [Paragraph("HR Analytics Report", H1),
              Paragraph(f"Workforce, attrition, attendance and pay · data as of 30 September 2026 · prepared {date.today():%d %B %Y}", SM),
              Spacer(1, 8)]

    story.append(Paragraph("Executive summary", H2))
    story.append(Paragraph(
        f"The company employs <b>{k['active']:,}</b> people across 8 departments and 5 Indian cities, up from "
        f"{int(k['years'].iloc[-2].hc_end):,} at the end of 2025. Over the last twelve months it hired {k['hires_ttm']} people and lost "
        f"{k['exits_ttm']}, an attrition rate of <b>{k['attr_ttm']:.1f}%</b> ({k['vol_attr_ttm']:.1f}% voluntary), "
        f"{'up' if k['attr_ttm'] > k['attr_prev'] else 'down'} from {k['attr_prev']:.1f}% a year earlier. "
        f"Growth is real but expensive: almost one in two leavers goes within the first year, and attrition is concentrated in "
        f"customer-facing teams and among people working regular overtime.", B))

    kpi_rows = [["KPI", "Value", "KPI", "Value"],
                ["Active headcount", f"{k['active']:,}", "Attendance rate (TTM)", f"{k['att_rate']:.1f}%"],
                ["Attrition rate (TTM)", f"{k['attr_ttm']:.1f}%", "Absenteeism rate (TTM)", f"{k['abs_rate']:.2f}%"],
                ["Voluntary attrition (TTM)", f"{k['vol_attr_ttm']:.1f}%", "Unplanned absence / employee / yr", f"{k['unpl_per_emp']:.1f} days"],
                ["New hires (TTM)", f"{k['hires_ttm']}", "Average rating (2025)", f"{k['avg_rating']:.2f} / 5"],
                ["Average tenure", f"{k['tenure']:.1f} yrs", "Rated 4 or 5 (2025)", f"{k['high_perf']:.0f}%"],
                ["Median salary", f"₹{k['median_sal'] / 1e5:.1f} L", "Women in workforce", f"{k['female']:.0f}%"],
                ["Annual payroll", f"₹{k['payroll_cr']:.1f} Cr", "Adjusted gender pay gap", f"{k['gap_adj']:.1f} pts"]]
    story.append(table(kpi_rows, [52, 30, 58, 30], num_cols=(1, 3)))
    story.append(Spacer(1, 8))
    story.append(Paragraph("Key findings", H3))
    story += bullets([
        f"<b>{top_attr.department}</b> has the highest attrition at {top_attr.attr:.1f}% (TTM), against {low_attr.attr:.1f}% in {low_attr.department}.",
        f"Employees on regular overtime have left at <b>{ot_ratio:.1f}×</b> the rate of those without it ({dr['Overtime']['Yes']:.0f}% vs {dr['Overtime']['No']:.0f}%).",
        f"Job satisfaction is the strongest single signal: {dr['Job satisfaction'][1]:.0f}% of people who scored 1 have left, against {dr['Job satisfaction'][4]:.0f}% of those who scored 4.",
        f"<b>{k['first_year_exit']:.0f}%</b> of all leavers went within their first year.",
        f"The top voluntary exit reasons in the last two years are {tr.index[0].lower()} ({100 * tr.iloc[0] / vol24:.0f}%), "
        f"{tr.index[1].lower()} ({100 * tr.iloc[1] / vol24:.0f}%) and {tr.index[2].lower()} ({100 * tr.iloc[2] / vol24:.0f}%). "
        f"{k['regretted']} of the {vol24} voluntary leavers were rated 4 or 5.",
        f"At the same department and level, men are paid <b>{k['gap_adj']:.1f} points</b> above women on compa-ratio. "
        + (f"The company-wide median shows almost no gap ({k['gap_raw']:+.1f}%), which hides the like-for-like difference."
           if abs(k['gap_raw']) < 1.5 else f"The raw company-wide median gap is {k['gap_raw']:.1f}%."),
        f"Leavers' unplanned absence rises to {k['unpl_leaver']:.1f}% of scheduled days in their final three months, versus {k['unpl_other']:.1f}% for everyone else, giving HR an early-warning signal.",
    ])
    story.append(PageBreak())

    # Workforce
    story.append(Paragraph("1. Employee analytics", H2))
    story.append(Paragraph(
        f"Headcount has grown steadily since 2019, with a pause in 2023 when hiring slowed, and an expansion through 2025 and 2026. "
        f"The average active employee is {k['age']:.0f} years old with {k['tenure']:.1f} years of service. "
        f"Engineering is the largest function; women make up {k['female']:.0f}% of the workforce overall.", B))
    story.append(img("headcount"))
    story.append(Spacer(1, 4))
    rows = [["Department", "Headcount", "Avg tenure", "Median salary", "TTM attrition", "Absenteeism"]]
    for _, x in d.iterrows():
        rows.append([x.department, f"{x.headcount}", f"{x.tenure:.1f} yrs", f"₹{x.median_sal / 1e5:.1f} L", f"{x.attr:.1f}%", f"{x['abs']:.2f}%"])
    rows.append(["Company", f"{k['active']:,}", f"{k['tenure']:.1f} yrs", f"₹{k['median_sal'] / 1e5:.1f} L", f"{k['attr_ttm']:.1f}%", f"{k['abs_rate']:.2f}%"])
    t = table(rows, [42, 24, 24, 30, 28, 26], num_cols=(1, 2, 3, 4, 5))
    t.setStyle(TableStyle([("FONT", (0, -1), (-1, -1), "Sans-Bold", 8.5), ("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.HexColor("#ccd2dc"))]))
    story.append(t)
    story.append(Spacer(1, 6))
    r25 = k["act"].latest_performance_rating.value_counts(normalize=True).sort_index() * 100
    story.append(Paragraph(
        "Performance: in the 2025 cycle the average rating was "
        f"{k['avg_rating']:.2f} and {k['high_perf']:.0f}% of employees were rated 4 or 5. "
        f"Among active staff the spread is " + ", ".join(f"{int(i)}: {v:.0f}%" for i, v in r25.items()) + ".", B))
    story.append(PageBreak())

    # Attrition
    story.append(Paragraph("2. Attrition analysis", H2))
    story.append(Paragraph(
        "Attrition rate is exits divided by average monthly headcount, annualised for the partial year 2026. "
        f"The company has held between {k['years'].rate.min():.0f}% and {k['years'].rate.max():.0f}% a year since 2019, "
        "which is high for a business of this size, while hiring has outpaced exits every year except 2023.", B))
    story.append(img("years"))
    story.append(img("attrition"))
    story.append(Paragraph(
        "The dashed line marks the company average. Customer-facing and operational teams lose people fastest, and most exits are "
        "voluntary: people leave for a better opportunity, pay, or work-life balance.", B))
    story.append(Paragraph("What predicts leaving", H3))
    story.append(img("drivers"))
    story.append(Paragraph(
        "Each bar is the share of everyone hired since 2016 in that group who has since left. Overtime, low job satisfaction and poor "
        "work-life balance each roughly double the chance of leaving. Junior levels (L1–L2) leave far more than senior ones.", B))
    story.append(PageBreak())

    # Attendance
    story.append(Paragraph("3. Attendance analysis", H2))
    best = am.index[(am.present / am.sched).argmax()]
    worst = am.index[(am.present / am.sched).argmin()]
    story.append(Paragraph(
        f"Over the last twelve months employees were present on <b>{k['att_rate']:.1f}%</b> of scheduled days. "
        f"Absenteeism (sick plus unplanned days) was {k['abs_rate']:.2f}%, or about {k['unpl_per_emp']:.1f} unplanned days per employee per year. "
        f"Attendance dips in December–January and in the July–August monsoon months, when sick leave rises; the low point in the "
        f"period was {worst:%b %Y} and the high point {best:%b %Y}.", B))
    story.append(img("attendance"))
    story.append(img("attendance_dept"))
    story.append(Paragraph(
        f"{cs.department} has the highest absenteeism at {cs['abs']:.1f}%, which tracks with its shift-based, on-site work and its "
        f"attrition. Engineering runs the most overtime. Unplanned absence among leavers climbs to {k['unpl_leaver']:.1f}% in their last three "
        f"months (vs {k['unpl_other']:.1f}% otherwise), so a rising absence pattern is worth a manager conversation.", B))
    story.append(PageBreak())

    # Salary
    story.append(Paragraph("4. Salary insights", H2))
    story.append(Paragraph(
        f"The median annual salary is <b>₹{k['median_sal'] / 1e5:.1f} lakh</b> and the payroll run-rate is ₹{k['payroll_cr']:.1f} crore a year. "
        "Pay rises steeply with level, and Engineering and Product pay the most at every level.", B))
    story.append(img("salary"))
    story.append(Paragraph(
        "Compa-ratio compares each salary with the median for the same department and level (1.00 means at the median). "
        f"Women sit below men in almost every department. The adjusted gap of {k['gap_adj']:.1f} points is mostly set at hiring, "
        f"since increments are tied to ratings. {k['below_090']} active employees ({100 * k['below_090'] / k['active']:.0f}%) are paid below 0.90 of their band median.", B))
    story.append(img("salary_level"))
    story.append(Paragraph(
        f"Increments follow performance closely: a rating of 5 earned {k['inc_by_rating'][5]:.1f}% against {k['inc_by_rating'][2]:.1f}% for a rating of 2 in April 2026, "
        "including promotions. The pay process rewards performance; the gap comes from starting salaries.", B))
    story.append(PageBreak())

    # Recommendations
    story.append(Paragraph("5. Recommendations", H2))
    story += bullets([
        f"<b>Fix first-year attrition.</b> {k['first_year_exit']:.0f}% of leavers go in year one. Add 30/60/90-day check-ins, buddy programmes and a structured "
        "onboarding plan, starting with Customer Support and Sales.",
        f"<b>Cap and rotate overtime.</b> People on regular overtime leave at {ot_ratio:.1f}× the rate of others. Track overtime hours per team monthly and add "
        "headcount where overtime is structural.",
        "<b>Act on engagement scores.</b> Use the flight-risk watchlist in the dashboard (overtime, satisfaction, work-life balance, level, commute, time since "
        "promotion) for monthly stay interviews with high-scoring employees, prioritising those rated 4 or 5.",
        f"<b>Close the gender pay gap at hire.</b> Set offer ranges by band and audit offers against them. Lifting everyone below 0.95 compa-ratio "
        "is costed in sql/07_salary_insights.sql (query 7.7).",
        "<b>Review compensation for customer-facing roles.</b> Compensation is a top-three exit reason; benchmark Support and Sales pay against the market.",
        "<b>Use absence as an early warning.</b> Flag employees whose unplanned absence doubles over a quarter for a manager check-in.",
        "<b>Report monthly.</b> Track the KPI set in this report (sql/08_kpi_report.sql) every month with targets: attrition below 14%, first-year exits below 30% "
        "of leavers, absenteeism below 4% and an adjusted pay gap below 2 points.",
    ])
    story.append(Spacer(1, 8))
    story.append(Paragraph("Data and method", H2))
    story.append(Paragraph(
        "This analysis uses a synthetic dataset generated for this project (scripts/generate_data.py, seed 42). It contains 2,200 employees hired "
        "between January 2016 and September 2026, their salary history and yearly performance reviews, and 21 months of attendance "
        "(January 2025 to September 2026). Names and figures are fictional, but the generator builds in realistic relationships between "
        "overtime, satisfaction, pay position, level and attrition, so the methods carry over directly to real HRIS data.", B))
    defs = [["Metric", "Definition"],
            ["Attrition rate", "Exits in period ÷ average of month-start and month-end headcount, annualised"],
            ["TTM", "Trailing twelve months, Oct 2025 – Sep 2026"],
            ["Attendance rate", "Days present ÷ scheduled working days"],
            ["Absenteeism rate", "(Sick leave + unplanned absence days) ÷ scheduled days"],
            ["Compa-ratio", "Salary ÷ median salary of active staff in same department and level"],
            ["Adjusted pay gap", "Average male compa-ratio − average female compa-ratio, in points"],
            ["Regretted exit", "Voluntary leaver whose last performance rating was 4 or 5"]]
    story.append(table(defs, [38, 132]))

    def on_page(c, doc):
        c.saveState()
        c.setFont("Sans", 7.5)
        c.setFillColor(colors.HexColor(MUTED))
        c.drawString(15 * mm, 10 * mm, "HR Analytics Report · synthetic data · as of 30 Sep 2026")
        c.drawRightString(195 * mm, 10 * mm, f"Page {doc.page}")
        c.restoreState()

    doc = SimpleDocTemplate(os.path.join(OUT, "HR_Analytics_Report.pdf"), pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=15 * mm, bottomMargin=16 * mm, title="HR Analytics Report", author="HR Analytics")
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)


def main():
    os.makedirs(OUT, exist_ok=True)
    e, a, s, r = load()
    k = analyse(e, a, s, r)
    charts(e, a, k)
    build_pdf(k)
    print(f"report/HR_Analytics_Report.pdf written · active={k['active']} attr_ttm={k['attr_ttm']:.1f} att={k['att_rate']:.2f} gap={k['gap_adj']:.1f}")


if __name__ == "__main__":
    main()
