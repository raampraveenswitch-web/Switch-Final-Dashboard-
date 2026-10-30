import streamlit as st

from services import metrics as M
from services import ui
from services.insights import performance_insights

store = ui.page_setup("Performance", "Performance Management (PMS)", "🏆")
ui.gate(store, ["Performance-eligible employees", "Completed reviews", "PMS completion rate", "High performers",
                "Average rating", "Goal achievement rate"], needs=("performance",))
ctx = ui.context(store, with_period=False)
p = ctx.ds["performance"]
S = ctx.settings
if "cycle" in p.columns and p["cycle"].notna().any():
    cycles = sorted(p["cycle"].dropna().unique())
    with ui.header_slot(store, "period"):           # the review cycle takes the Period pill on this page
        pick = st.selectbox("Review cycle", cycles, index=len(cycles) - 1,
                            help="Rates are calculated for one cycle at a time so employees are not double-counted.")
    cur = p[p["cycle"] == pick]
else:
    cur = p
    pick = "All rows (no cycle column)"
cur = ui.filters(cur, {"function": "Function", "department": "Department", "level": "Level"}, "pms")

ui.kpi_cards([(m, None) for m in (M.pms_eligible(cur), M.pms_completed(cur), M.pms_completion(cur),
                                  M.pms_high_performers(cur, S), M.pms_avg_rating(cur), M.pms_goal_rate(cur), M.pms_idp(cur))])

# ---- distribution · status donut · by function · focus ----------------------
a, b, c, d = ui.row()
bx = ui.panel(a, "Rating Distribution", f"Employees by rating · cycle {pick}"
              + (f" · scale max {S['rating_scale_max']}" if S.get("rating_scale_max") is not None else ""))
dd = M.pms_rating_dist(cur)
if dd is not None:
    dd = dd.copy()
    dd["Rating"] = dd["Rating"].astype(str)
    ui.combo(bx, dd, "Rating", ["Employees"], line="Employees", line_name="Trend")
else:
    ui.unavailable(bx, "rating column not found.")

bx = ui.panel(b, "PMS Cycle Progress", "Employees by review status")
dd = M.pms_status_counts(cur)
if dd is not None:
    dd = dd.assign(**{"Review status": dd["Review status"].astype(str).str.replace("_", " ").str.capitalize()})
ui.donut(bx, dd, "Review status", "Employees", center="Employees") if dd is not None else ui.unavailable(bx, "review status column not found.")

bx = ui.panel(c, "Performance by Function", "Average rating; small groups hidden")
dd, n = M.small_group_filter(M.pms_by(cur, "function"), "Rated employees")
ui.bar(bx, dd, "Average rating", dd.columns[0], orient="h", fmt=".2f", height=300) if dd is not None and len(dd) \
    else ui.unavailable(bx, "function column not found or groups too small.")
ui.suppressed_note(bx, n)

ui.focus(ui.panel(d, "Performance Initiatives & Focus", icon="target"), performance_insights(cur, S), "performance")

# ---- detail rows ---------------------------------------------------------------
a, b, c, d = ui.row((1, 1, 1, 1))
bx = ui.card("Rating Trend", "Average rating per cycle", parent=a)
tr = M.pms_trend(p)
ui.line(bx, tr, "Cycle", ["Average rating"], height=ui.DETAIL_CHART_H) if tr is not None else ui.unavailable(bx, "rating with a cycle or review date not found.")
for holder, (title, col) in zip((b, c), (("Performance by Level", "level"), ("Performance by Age Group", "age_group"))):
    bx = ui.card(title, "Average rating; small groups hidden", parent=holder)
    dd, n = M.small_group_filter(M.pms_by(cur, col), "Rated employees")
    ui.bar(bx, dd, "Average rating", dd.columns[0], orient="h", fmt=".2f", height=ui.DETAIL_CHART_H) if dd is not None and len(dd) \
        else ui.unavailable(bx, f"{col.replace('_', ' ')} column not found or groups too small.")
    ui.suppressed_note(bx, n)
bx = ui.card("Top Talent / High Performers", "Counts by function (aggregated)", parent=d, icon="star")
if "function" in cur.columns and "employee_id" in cur.columns:
    mask, src = M._hp_mask(cur, S)
    if mask is not None:
        dd = cur[mask].groupby(cur["function"].fillna("Not recorded"))["employee_id"].nunique().rename_axis("Function").reset_index(name="High performers")
        dd, n = M.small_group_filter(dd, "High performers")
        ui.bar(bx, dd, "High performers", "Function", orient="h", height=265)
        bx.caption(f"Definition: {src}.")
        ui.suppressed_note(bx, n)
    else:
        ui.unavailable(bx, "no high-performer flag and no approved rating threshold configured.")
else:
    ui.unavailable(bx, "function or employee ID column not found.")

a, b = ui.row((1, 1))
ui.unavailable(ui.card("Strengths and Development Needs", parent=a), "no competency/strength fields are mapped.")
ui.unavailable(ui.card("Succession Planning, HiPo and Critical Roles", parent=b),
               "no successor/critical-role fields are mapped. HiPo status is used only when a formal flag column exists.")
