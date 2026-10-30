import pandas as pd
import streamlit as st

from services import metrics as M
from services import ui
from services.insights import (data_quality_insights, employee_insights, performance_insights,
                               recruitment_insights, training_insights)

LABELS = ["Total employees", "New hires", "Attrition rate", "Open requisitions", "Positions filled",
          "Average time to hire"]
store = ui.page_setup("HR Overview", "Executive Summary", "🧭")
ui.gate(store, LABELS)
ctx = ui.context(store)
ds, S = ctx.ds, ctx.settings
r, e, t, p, c = (ds.get(k) for k in ("recruitment", "employee", "training", "performance", "relations"))

# ---- KPI row (six headline cards + secondary strip) --------------------------
mt = ctx.metric
ui.kpi_cards([
    mt("employee", "Total employees", "count", lambda q: M.emp_headcount(e, ctx.asof(q))),
    mt("employee", "New hires", "count", lambda q: M.emp_new_hires(e, q)),
    mt("employee", "Attrition rate", "pct", lambda q: M.emp_attrition(e, q)),
    mt("recruitment", "Open requisitions", "count", lambda q: M.rec_open_count(r, ctx.asof(q))),
    mt("recruitment", "Positions filled", "count", lambda q: M.rec_filled(r, q)),
    mt("recruitment", "Average time to hire", "days", lambda q: M.rec_time_to_hire(r, q)),
], secondary=[
    mt("training", "Training hours", "hours", lambda q: M.trn_hours(t, q)),
    mt("training", "Employees trained", "count", lambda q: M.trn_employees(t, q)),
    mt("training", "Training participation", "pct", lambda q: M.trn_participation(t, e, q, ctx.asof(q))),
    ctx.static("performance", "Average performance rating", "score", lambda q: M.pms_avg_rating(p)),
    ctx.static("performance", "High performers", "count", lambda q: M.pms_high_performers(p, S)),
    ctx.static("performance", "Goal achievement rate", "pct", lambda q: M.pms_goal_rate(p)),
    ctx.static("relations", "Engagement score", "score", lambda q: M.rel_engagement(c)),
])

# ---- trend · donut · funnel · focus ------------------------------------------
a, b, c3, d = ui.row()
bx = ui.panel(a, "Workforce Trend", "Joiners and leavers by month, with month-end headcount")
if e is not None and ctx.window is not None:
    hc = M.emp_headcount_trend(e, ctx.window)
    parts = []
    if "hire_date" in e.columns:
        h = e[e["hire_date"].notna()]
        parts.append(h.groupby(h["hire_date"].dt.to_period("M")).size().rename("Joiners"))
    if "exit_date" in e.columns and e["exit_date"].notna().any():
        x = e[e["exit_date"].notna()]
        parts.append(x.groupby(x["exit_date"].dt.to_period("M")).size().rename("Leavers"))
    if hc is not None and parts:
        lc = pd.concat(parts, axis=1).fillna(0)
        lc.index = lc.index.to_timestamp()
        hc = hc.assign(Month=hc["Month end"].dt.to_period("M").dt.to_timestamp())
        tr = hc.merge(lc, left_on="Month", right_index=True, how="left").fillna({"Joiners": 0, "Leavers": 0})
        ui.combo(bx, tr, "Month", [k for k in ("Joiners", "Leavers") if k in tr], line="Headcount", line_secondary=True)
    else:
        ui.unavailable(bx, "employee dates of joining not found.")
else:
    ui.unavailable(bx, "employee data with dates of joining not found.")

bx = ui.panel(b, "Headcount by Function", "Active employees at period end")
dd = None
if e is not None:
    dd = next((x for x in (M.emp_distribution(e, k, ctx.asof()) for k in ("function", "department")) if x is not None), None)
ui.donut(bx, dd, dd.columns[0], "Employees", center="Employees") if dd is not None else ui.unavailable(bx, "no department/function column.")

bx = ui.panel(c3, "Recruitment Funnel", "Candidates reaching each stage")
f, note = M.rec_funnel(r, S["funnel_order"]) if r is not None else (None, "No recruitment data found.")
if f is not None:
    ui.funnel(bx, f["Stage"], f["Reached"])
elif r is not None and "stage" in r.columns:
    s = r["stage"].fillna("Not recorded").value_counts().rename_axis("Stage").reset_index(name="Records")
    ui.bar(bx, s, "Records", "Stage", orient="h", height=280)
    bx.caption("Showing records currently at each stage. " + note)
else:
    ui.unavailable(bx, note)

items = (recruitment_insights(r, S["funnel_order"], ctx.period, ctx.asof()) + employee_insights(e, ctx.period) + training_insights(t, S)
         + performance_insights(p, S) + data_quality_insights(store.model))
ui.focus(ui.panel(d, "HR Initiatives & Focus", icon="target"), items, "overview")

# ---- detail row ------------------------------------------------------------------
a, b, c3, d = ui.row((1, 1, 1, 1))
bx = ui.card("Recruitment Trend", "Requisitions opened vs positions filled", parent=a)
t_ = ctx.in_window(M.rec_monthly(r), "Month") if r is not None else None
if t_ is not None and "Positions filled" in t_:
    ui.combo(bx, t_, "Month", ["Positions filled", "Requisitions opened"], height=ui.DETAIL_CHART_H,
             bar_names={"Positions filled": "Hired", "Requisitions opened": "Requisitions"})
else:
    ui.unavailable(bx, "recruitment dates not found.")
bx = ui.card("Workforce Distribution", "By employee type", parent=b)
dd = M.emp_distribution(e, "employee_type", ctx.asof()) if e is not None else None
ui.donut(bx, dd, dd.columns[0], "Employees", height=ui.DETAIL_CHART_H) if dd is not None else ui.unavailable(bx, "employee type column not found.")
bx = ui.card("Source of Hire", "Hires in the period", parent=c3)
s = M.rec_source_share(r, ctx.period) if r is not None else None
ui.donut(bx, s, "Source", "Hires", height=ui.DETAIL_CHART_H) if s is not None else ui.unavailable(bx, "source-of-hire data not found.")
bx = ui.card("Training Hours by Category", "Hours in the period", parent=d)
g = M.trn_breakdown(t, "category", ctx.period) if t is not None else None
ui.bar(bx, g.head(6), "Training hours", g.columns[0], orient="h", fmt=",.0f", height=ui.DETAIL_CHART_H) if g is not None \
    else ui.unavailable(bx, "training category data not found.")

with st.expander("All insights with their rules"):
    ui.insights_panel(items)
