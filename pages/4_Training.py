import streamlit as st

from services import metrics as M
from services import ui
from services.insights import training_insights

store = ui.page_setup("Training", "Learning & Development", "🎓")
ui.gate(store, ["Total training hours", "Employees trained", "Training participation rate",
                "Average training hours per employee", "Certification rate", "Training effectiveness"], needs=("training",))
ctx = ui.context(store)
t = ui.filters(ctx.ds["training"], {"department": "Department", "category": "Category",
                                     "delivery_mode": "Delivery mode", "program": "Programme"}, "trn")
e, S = ctx.ds.get("employee"), ctx.settings
ui.kpi_cards([
    ctx.cmp(lambda q: M.trn_hours(t, q)), ctx.cmp(lambda q: M.trn_employees(t, q)),
    ctx.cmp(lambda q: M.trn_participation(t, e, q, ctx.asof(q))),
    ctx.cmp(lambda q: M.trn_avg_hours(t, e, q, ctx.asof(q))), ctx.cmp(lambda q: M.trn_cert_rate(t, q)),
    ctx.cmp(lambda q: M.trn_effectiveness(t, q)), ctx.cmp(lambda q: M.trn_cost(t, q)),
    ctx.cmp(lambda q: M.trn_cost_per_employee(t, e, q, ctx.asof(q))), ctx.cmp(lambda q: M.trn_budget_util(t, q, S))])

# ---- trend · donut · programmes · focus --------------------------------------
tr = M.trn_monthly(t, ctx.window)
a, b, c, d = ui.row()
bx = ui.panel(a, "Training Trend", "Training hours by month, with employees trained")
if tr is not None and "Training hours" in tr:
    ui.combo(bx, tr, "Month", ["Training hours"], line="Employees trained" if "Employees trained" in tr else None,
             line_secondary=True)
else:
    ui.unavailable(bx, "training date and hours not found.")

bx = ui.panel(b, "Training by Category", "Hours in the period")
g = M.trn_breakdown(t, "category", ctx.period)
ui.donut(bx, g, g.columns[0], "Training hours", center="Training Hours") if g is not None else ui.unavailable(bx, "category or hours column not found.")

bx = ui.panel(c, "Top Training Programmes", "By hours in the period")
g = M.trn_breakdown(t, "program", ctx.period)
ui.bar(bx, g.head(8), "Training hours", g.columns[0], orient="h", fmt=",.0f", height=300) if g is not None \
    else ui.unavailable(bx, "programme or hours column not found.")

ui.focus(ui.panel(d, "L&D Initiatives & Focus", icon="target"), training_insights(t, S), "training")

# ---- detail rows ---------------------------------------------------------------
a, b, c, d = ui.row((1, 1, 1, 1))
bx = ui.card("Delivery Mode", "Hours", parent=a)
g = M.trn_breakdown(t, "delivery_mode", ctx.period)
ui.donut(bx, g, g.columns[0], "Training hours", height=ui.DETAIL_CHART_H) if g is not None else ui.unavailable(bx, "delivery mode or hours column not found.")
bx = ui.card("Training by Location", "Hours", parent=b)
g = M.trn_breakdown(t, "location", ctx.period)
ui.bar(bx, g, "Training hours", g.columns[0], orient="h", fmt=",.0f", height=ui.DETAIL_CHART_H) if g is not None else ui.unavailable(bx, "location or hours column not found.")
bx = ui.card("Training Effectiveness", "From assessment or pre/post scores only", parent=c)
g = next((x for x in (M.trn_effect_by(t, k, ctx.period) for k in ("program", "category")) if x is not None), None)
ui.bar(bx, g, g.columns[1], g.columns[0], orient="h", fmt=".1f", height=ui.DETAIL_CHART_H) if g is not None \
    else ui.unavailable(bx, "no assessment or pre/post score columns found. Attendance is not treated as effectiveness.")
bx = ui.card("Training Cost by Category", parent=d, icon="rupee")
if "cost" in t.columns and "category" in t.columns:
    s, _ = M._scope(t, ctx.period, "date")
    g = s.assign(k=s["category"].fillna("Not recorded")).groupby("k")["cost"].sum().rename_axis("Category").reset_index(name="Cost")
    ui.bar(bx, g, "Cost", "Category", orient="h", fmt=",.0f", height=ui.DETAIL_CHART_H)
else:
    ui.unavailable(bx, "training cost data not found.")

a, b, c = ui.row((1, 1.4, 1))
bx = ui.card("Certification and Completion", "Completion status of training records", parent=a)
g = M.trn_completion_mix(t, ctx.period)
if g is not None:
    g = g.assign(Status=g["Status"].astype(str).str.replace("_", " ").str.capitalize())
ui.donut(bx, g, "Status", "Records", height=ui.DETAIL_CHART_H, center="Records") if g is not None else ui.unavailable(bx, "completion status column not found.")
bx = ui.card("Programme Detail", "Hours and participants by programme", parent=b, icon="table")
g = M.trn_breakdown(t, "program", ctx.period)
ui.table(bx, g.head(25).round(1) if g is not None else None, 255, "prog", searchable=True)
with c:
    ui.unavailable(ui.section("Learning-Path Progression"), "no learning-path fields are mapped.")
    ui.unavailable(ui.section("Training Needs Analysis"), "no priority / focus-area / planned-action fields are mapped.")
