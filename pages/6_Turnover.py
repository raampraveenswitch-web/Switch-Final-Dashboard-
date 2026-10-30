import pandas as pd
import streamlit as st

from services import metrics as M
from services import ui
from services.insights import turnover_insights

store = ui.page_setup("Turnover", "Retention & Attrition", "🔁")
ui.gate(store, ["Opening headcount", "Closing headcount", "Employee exits", "Attrition rate",
                "Voluntary exits (share)", "Average tenure"], needs=("employee",))
ctx = ui.context(store)
e = ui.filters(ctx.ds["employee"], {"department": "Department", "function": "Function",
                                     "employee_type": "Employee type"}, "turn")
P = ctx.period
if P is None:
    st.warning("No dates found in the workbook, so period-based turnover cannot be calculated.")
    st.stop()
op = M.emp_headcount(e, P.start - pd.Timedelta(days=1))
op = M.Metric("op", "Opening headcount", op.value, "count", op.reason, f"Day before {P.start:%d %b %Y}")
cl = M.emp_headcount(e, P.end)
cl = M.Metric("cl", "Closing headcount", cl.value, "count", cl.reason, f"As of {P.end:%d %b %Y}")
mix = M.emp_exit_mix(e, P)
vol = None
if mix is not None and "voluntary" in set(mix["Category"]):
    tot = mix["Exits"].sum()
    vol = M.Metric("vol", "Voluntary exits (share)", mix.loc[mix["Category"] == "voluntary", "Exits"].sum() / tot * 100, "pct",
                   detail=f"{tot} exits with exit-type data (incl. unclassified)")
ui.kpi_cards([(op, None), (cl, None), ctx.cmp(lambda q: M.emp_exits(e, q)), ctx.cmp(lambda q: M.emp_attrition(e, q)),
              (vol or M._na("vol", "Voluntary exits (share)", "pct", "Not available — exit type column not found or no exits."), None),
              ctx.cmp(lambda q: M.emp_tenure(e, ctx.asof(q)))])

# ---- trend · donut · tenure · focus ------------------------------------------
a, b, c, d = ui.row()
bx = ui.panel(a, "Exit Trend", "Exits by month in the selected year, with month-end headcount")
ex = M.emp_exits_trend(e, ctx.window, "M") if ctx.window else None
hc = M.emp_headcount_trend(e, ctx.window) if ctx.window else None
if ex is not None:
    ex = ex.assign(Month=pd.to_datetime(ex["Period"].astype(str)).dt.to_period("M").dt.to_timestamp())
    if hc is not None:
        hc = hc.assign(Month=hc["Month end"].dt.to_period("M").dt.to_timestamp())
        ex = hc[["Month", "Headcount"]].merge(ex[["Month", "Exits"]], on="Month", how="left").fillna({"Exits": 0})
    ui.combo(bx, ex, "Month", ["Exits"], line="Headcount" if "Headcount" in ex else None, line_secondary=True)
else:
    ui.unavailable(bx, "no exits with dates in the selected year.")

bx = ui.panel(b, "Voluntary vs Involuntary", "Exits in the period")
if mix is not None:
    mix = mix.assign(Category=mix["Category"].astype(str).str.replace("_", " ").str.capitalize())
ui.donut(bx, mix, "Category", "Exits", center="Exits") if mix is not None else ui.unavailable(bx, "exit type column not found or no exits.")

bx = ui.panel(c, "Exits by Tenure", "Tenure at exit, period exits")
dd = M.emp_exit_tenure(e, P)
ui.bar(bx, dd, "Tenure at exit", "Exits", height=300) if dd is not None else ui.unavailable(bx, "joining and exit dates not found.")

ui.focus(ui.panel(d, "Retention Initiatives & Focus", icon="target"), turnover_insights(e, P), "turnover")
st.caption("Attrition = exits ÷ average of opening and closing headcount for the selected period (not annualised). "
           "Patterns shown are descriptive; they do not establish causes.")

# ---- detail rows ---------------------------------------------------------------
a, b, c, d = ui.row((1, 1, 1, 1))
for holder, (title, col) in zip((a, b, c, d), (("Attrition by Department", "department"), ("Attrition by Function", "function"),
                                                ("Attrition by Employee Type", "employee_type"), ("Attrition by Location", "location"))):
    bx = ui.card(title, "Rate %; small groups hidden", parent=holder)
    dd, n = M.small_group_filter(M.emp_attrition_by(e, col, P), "Average headcount")
    ui.bar(bx, dd, "Attrition rate %", dd.columns[0], orient="h", fmt=".1f", height=ui.DETAIL_CHART_H) if dd is not None and len(dd) \
        else ui.unavailable(bx, f"{col.replace('_', ' ')} column not found or groups too small.")
    ui.suppressed_note(bx, n)

a, b, c = ui.row((1.2, 1, 1))
bx = ui.card("Exit Reasons", "Counts; small groups hidden", parent=a)
dd, n = M.small_group_filter(M.emp_exit_reasons(e, P), "Exits")
ui.bar(bx, dd, "Exits", "Exit reason", orient="h", height=ui.DETAIL_CHART_H) if dd is not None and len(dd) else ui.unavailable(bx, "exit reason column not found or groups too small.")
ui.suppressed_note(bx, n)
ui.unavailable(ui.card("New-Hire Retention", parent=b),
               "not calculated: this version does not implement a cohort retention rule (it needs an approved cohort and rehire definition).")
ui.unavailable(ui.card("Retention Risk Indicators", parent=c),
               "intentionally not provided: no individual predictions or unsupported risk scores are generated.")
