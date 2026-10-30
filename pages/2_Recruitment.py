import streamlit as st

from services import metrics as M
from services import ui
from services.insights import recruitment_insights

store = ui.page_setup("Recruitment", "Talent Acquisition", "🧲")
ui.gate(store, ["Total requisitions", "Positions filled", "Time to hire (avg.)", "Offer acceptance rate",
                "New hires", "Cost per hire"], needs=("recruitment",))
ctx = ui.context(store)
r = ui.filters(ctx.ds["recruitment"], {"department": "Department", "function": "Function",
                                       "priority": "Priority", "recruiter": "Recruiter"}, "rec")

# ---- KPI row ---------------------------------------------------------------
ui.kpi_cards([
    ctx.cmp(lambda q: M.rec_requisitions(r, q)), ctx.cmp(lambda q: M.rec_filled(r, q)),
    ctx.cmp(lambda q: M.rec_time_to_hire(r, q)), ctx.cmp(lambda q: M.rec_offer_acceptance(r, q)),
    ctx.cmp(lambda q: M.rec_new_hires(r, q)), ctx.cmp(lambda q: M.rec_cost_per_hire(r, q)),
    ctx.cmp(lambda q: M.rec_open_count(r, ctx.asof(q))), ctx.cmp(lambda q: M.rec_open_ageing(r, ctx.asof(q)))])

# ---- trend · donut · funnel · focus ------------------------------------------
trend = ctx.in_window(M.rec_monthly(r), "Month")
a, b, c, d = ui.row()
bx = ui.panel(a, "Hiring Trend", "Positions filled vs requisitions opened, by month")
if trend is not None and "Positions filled" in trend:
    ui.combo(bx, trend, "Month", ["Positions filled", "Requisitions opened"], line="Positions filled",
             bar_names={"Positions filled": "Hired", "Requisitions opened": "Requisitions"}, line_name="Hired (trend)")
else:
    ui.unavailable(bx, "requisition ID with open/filled dates not found.")

bx = ui.panel(b, "Hiring by Function", "Positions filled in the period")
fn = next((x for x in (M.rec_by(r, k, ctx.period, filled_only=True) for k in ("function", "department")) if x is not None), None)
ui.donut(bx, fn, fn.columns[0], "Requisitions", center="Positions Filled") if fn is not None \
    else ui.unavailable(bx, "no function/department column, or no filled requisitions in the period.")

bx = ui.panel(c, "Recruitment Funnel", "Candidates reaching each stage · % of first stage")
f, note = M.rec_funnel(r, ctx.settings["funnel_order"])
if f is not None:
    ui.funnel(bx, f["Stage"], f["Reached"])
    if note:
        bx.caption(note)
elif "stage" in r.columns:
    s = r["stage"].fillna("Not recorded").value_counts().rename_axis("Stage").reset_index(name="Records")
    ui.bar(bx, s, "Records", "Stage", orient="h", height=280)
    bx.caption("Showing records currently at each stage. " + note)
else:
    ui.unavailable(bx, note)

ui.focus(ui.panel(d, "Recruitment Initiatives & Focus", icon="target"),
         recruitment_insights(r, ctx.settings["funnel_order"], ctx.period, ctx.asof()), "recruitment")

# ---- detail rows ---------------------------------------------------------------
a, b, c, d = ui.row((1, 1, 1, 1))
bx = ui.card("Time-to-Hire Trend", "Average days from open to filled", parent=a)
ui.line(bx, trend, "Month", ["Avg time to hire (days)"], height=ui.DETAIL_CHART_H) if trend is not None and "Avg time to hire (days)" in trend \
    else ui.unavailable(bx, "open and filled dates not found.")
bx = ui.card("Source of Hire", "Share of hires with a valid source", parent=b)
s = M.rec_source_share(r, ctx.period)
ui.donut(bx, s, "Source", "Hires", height=ui.DETAIL_CHART_H, center="Hires") if s is not None else ui.unavailable(bx, "source and status columns not found, or no hires.")
bx = ui.card("Top Hiring Roles", "Filled requisitions by job title", parent=c)
t = M.rec_by(r, "job_title", ctx.period, filled_only=True)
ui.bar(bx, t.head(8), "Requisitions", t.columns[0], orient="h", height=ui.DETAIL_CHART_H) if t is not None else ui.unavailable(bx, "job title/status not found.")
bx = ui.card("Hiring by Location", "Requisitions opened in the period", parent=d)
t = M.rec_by(r, "location", ctx.period)
ui.bar(bx, t.head(8), "Requisitions", t.columns[0], orient="h", height=ui.DETAIL_CHART_H) if t is not None else ui.unavailable(bx, "location column not found.")

a, b, c = ui.row((1, 1, 2))
bx = ui.card("Diversity Hiring", "Hires by gender (aggregated; small groups hidden). Use only where permitted.", parent=a)
t = M.rec_by(r, "gender", ctx.period, filled_only=True)
t, n = M.small_group_filter(t, "Requisitions")
ui.donut(bx, t, t.columns[0], "Requisitions", height=ui.DETAIL_CHART_H) if t is not None and len(t) else ui.unavailable(bx, "gender column not found or groups too small.")
ui.suppressed_note(bx, n)
bx = ui.card("Hiring Quality", parent=b)
ui.unavailable(bx, "needs a post-hire outcome measure (e.g. first-year rating or retention) linked to each hire; none is mapped.")
bx = ui.card("Open Positions", "Requisitions with status 'open' as of period end, oldest first", parent=c, icon="work")
ui.table(bx, M.rec_open_positions(r, ctx.asof()), 265, "open", searchable=True)
