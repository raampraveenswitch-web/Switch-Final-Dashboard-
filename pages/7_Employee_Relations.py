import streamlit as st

from services import metrics as M
from services import ui
from services.insights import relations_insights

store = ui.page_setup("Employee Relations", "Engagement & Case Management", "🤝")
ui.gate(store, ["Cases raised", "Open cases", "Closed cases", "Case resolution rate", "Average resolution time",
                "Engagement score"], needs=("relations",))
ctx = ui.context(store)
c = ui.filters(ctx.ds["relations"], {"department": "Department", "case_category": "Category"}, "rel")
ui.kpi_cards([ctx.cmp(lambda q: M.rel_cases(c, q)), ctx.cmp(lambda q: M.rel_open(c, q)), ctx.cmp(lambda q: M.rel_closed(c, q)),
              ctx.cmp(lambda q: M.rel_resolution_rate(c, q)), ctx.cmp(lambda q: M.rel_resolution_days(c, q)),
              (M.rel_engagement(c), None)],
             secondary=[ctx.cmp(lambda q: M.rel_pending(c, q)), (M.rel_response_rate(c), None)])

# ---- trend · donut · by department · focus -----------------------------------
a, b, c3, d = ui.row()
bx = ui.panel(a, "Cases Trend", "Cases opened per month in the selected year")
tr = M.rel_monthly(c, ctx.window) if ctx.window else None
ui.combo(bx, tr, "Month", ["Cases"], line="Cases", line_name="Trend") if tr is not None else ui.unavailable(bx, "case ID and open date not found.")

bx = ui.panel(b, "Issue Categories", "Cases in the period; small groups hidden")
dd, n = M.small_group_filter(M.rel_categories(c, "case_category", ctx.period), "Cases")
ui.donut(bx, dd, "Category", "Cases", center="Cases") if dd is not None and len(dd) else ui.unavailable(bx, "issue category column not found or groups too small.")
ui.suppressed_note(bx, n)

bx = ui.panel(c3, "Cases by Department", "Distinct cases; small groups hidden")
dd, n = M.small_group_filter(M.rel_categories(c, "department", ctx.period), "Cases")
ui.bar(bx, dd, "Cases", "Category", orient="h", height=300) if dd is not None and len(dd) else ui.unavailable(bx, "department column not found or groups too small.")
ui.suppressed_note(bx, n)

ui.focus(ui.panel(d, "ER Initiatives & Focus", icon="target"), relations_insights(c, ctx.period), "relations")

# ---- detail row ------------------------------------------------------------------
a, b = ui.row((1, 1))
bx = ui.card("Cases by Location", "Distinct cases; small groups hidden", parent=a)
dd, n = M.small_group_filter(M.rel_categories(c, "location", ctx.period), "Cases")
ui.bar(bx, dd, "Cases", "Category", orient="h", height=ui.DETAIL_CHART_H) if dd is not None and len(dd) else ui.unavailable(bx, "location column not found or groups too small.")
ui.suppressed_note(bx, n)
bx = ui.card("Case Status", "Cases opened in the period by status", parent=b)
if "status_norm" in c.columns and "case_id" in c.columns:
    s, _ = M._scope(c, ctx.period, "open_date")
    dd = s.dropna(subset=["case_id"]).drop_duplicates("case_id")["status_norm"].fillna("Not recorded").str.title() \
        .value_counts().rename_axis("Status").reset_index(name="Cases")
    ui.donut(bx, dd, "Status", "Cases", height=ui.DETAIL_CHART_H, center="Cases") if len(dd) else ui.unavailable(bx, "no cases in the period.")
else:
    ui.unavailable(bx, "case status column not found.")
st.caption("Only aggregated counts are shown. Groups with fewer than the minimum group size are hidden; individual cases are never listed.")
