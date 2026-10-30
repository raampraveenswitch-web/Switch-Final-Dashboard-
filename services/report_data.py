"""Report content for the PPT/PDF downloads — one builder per dashboard.

Builders use exactly the same metric functions, periods and comparison rules as the dashboard pages
(services/metrics.py + services/presentation.py), so an exported deck always matches the screen.
Nothing here imports Streamlit."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from config import MIN_GROUP_SIZE
from services import metrics as M
from services import presentation as P
from services.insights import (Insight, data_quality_insights, employee_insights, performance_insights,
                               recruitment_insights, relations_insights, training_insights, turnover_insights)


@dataclass
class Chart:
    kind: str                                  # combo | bar | hbar | donut | line | funnel
    title: str
    subtitle: str = ""
    cats: list = field(default_factory=list)
    series: list = field(default_factory=list)  # [(name, [values])]
    line: tuple | None = None                   # (name, [values]) drawn as a labelled line
    secondary: bool = False                     # line on its own (right) axis
    center: str = ""                            # donut centre caption
    fmt: str = "int"                            # int | dec1 | dec2 | pct
    reason: str = ""                            # set when the chart is not available
    note: str = ""

    @property
    def ok(self) -> bool:
        return not self.reason and bool(self.cats) and bool(self.series)


@dataclass
class Report:
    key: str
    title: str                                  # "Recruitment Dashboard"
    area: str                                   # "Talent Acquisition"
    period: str                                 # "Q3 2026"
    period_range: str                           # "01 Jul 2026 – 30 Sep 2026"
    location: str
    source: str
    kpis: list = field(default_factory=list)    # [(Metric, Delta|None)] — first six are headline cards
    charts: list = field(default_factory=list)
    focus: list = field(default_factory=list)   # [Insight]
    table: tuple | None = None                  # (title, DataFrame)
    available: bool = True
    reason: str = ""
    generated: datetime = field(default_factory=datetime.now)

    @property
    def notes(self) -> list[tuple[str, str]]:
        return [(c.title, c.reason) for c in self.charts if not c.ok and c.reason]


DASHBOARDS = [  # key, title, area, needs, icon, description
    ("overview", "HR Overview", "Executive Summary", (), "dashboard",
     "Headline workforce, hiring and training KPIs with the organisation-wide trends."),
    ("recruitment", "Recruitment", "Talent Acquisition", ("recruitment",), "person_add",
     "Requisitions, hiring trend, function mix, funnel, sources and open positions."),
    ("employees", "Employees", "Workforce Overview", ("employee",), "groups",
     "Headcount trend, department mix, tenure and workforce composition."),
    ("training", "Training", "Learning & Development", ("training",), "school",
     "Training hours, participation, programmes, delivery, effectiveness and cost."),
    ("performance", "Performance", "Performance Management", ("performance",), "star",
     "Rating distribution, review progress, performance by function and level."),
    ("turnover", "Turnover", "Retention & Attrition", ("employee",), "exit",
     "Exits, attrition rates by group, exit reasons and tenure at exit."),
    ("relations", "Employee Relations", "Engagement & Case Management", ("relations",), "forum",
     "Case volumes, categories, resolution and engagement (aggregated)."),
]


# ------------------------------------------------------------------ chart helpers
def _cat_labels(s: pd.Series) -> list[str]:
    if pd.api.types.is_datetime64_any_dtype(s):
        fmt = "%b" if s.dt.year.nunique() == 1 else "%b %y"
        return [d.strftime(fmt) for d in s]
    return [str(x) for x in s]


def _vals(s) -> list:
    return [None if pd.isna(v) else float(v) for v in pd.to_numeric(pd.Series(s), errors="coerce")]


def na(kind: str, title: str, reason: str, subtitle: str = "") -> Chart:
    return Chart(kind, title, subtitle, reason=reason)


def combo(title, sub, df, x, bars, line=None, names=None, secondary=False, line_name=None) -> Chart:
    if df is None or not len(df):
        return na("combo", title, "no data for this chart in the selected period.", sub)
    names = names or {}
    ser = [(names.get(b, b), _vals(df[b])) for b in bars if b in df.columns]
    ln = (line_name or names.get(line, line), _vals(df[line])) if line and line in df.columns else None
    return Chart("combo", title, sub, _cat_labels(df[x]), ser, ln, secondary)


def bars(kind, title, sub, df, cat, val, top=10, fmt="int", reason="no data for this chart in the selected period.") -> Chart:
    if df is None or not len(df):
        return na(kind, title, reason, sub)
    d = df.sort_values(val, ascending=False) if kind == "hbar" else df
    note = ""
    if kind == "hbar" and len(d) > top:
        d = d.sort_values(val, ascending=False).head(top)
        note = f"Top {top} of {len(df)} shown."
    return Chart(kind, title, sub, _cat_labels(d[cat]), [(val, _vals(d[val]))], fmt=fmt, note=note)


def donut(title, sub, df, names, values, center="", top=6, reason="no data for this chart in the selected period.") -> Chart:
    if df is None or not len(df):
        return na("donut", title, reason, sub)
    d = df[[names, values]].copy()
    d[values] = pd.to_numeric(d[values], errors="coerce").fillna(0)
    d = d[d[values] > 0].sort_values(values, ascending=False)
    if d.empty:
        return na("donut", title, reason, sub)
    if len(d) > top:
        rest = d.iloc[top - 1:][values].sum()
        d = pd.concat([d.iloc[:top - 1], pd.DataFrame({names: ["Others"], values: [rest]})])
    return Chart("donut", title, sub, [str(x) for x in d[names]], [(values, _vals(d[values]))], center=center)


def line(title, sub, df, x, y, fmt="dec1") -> Chart:
    if df is None or not len(df) or y not in df.columns:
        return na("line", title, "no data for this chart.", sub)
    return Chart("line", title, sub, _cat_labels(df[x]), [(y, _vals(df[y]))], fmt=fmt)


def funnel_or_pipeline(r, order, title="Recruitment Funnel") -> Chart:
    f, note = M.rec_funnel(r, order)
    if f is not None:
        return Chart("funnel", title, "Candidates reaching each stage · % of first stage", list(f["Stage"]),
                     [("Reached", _vals(f["Reached"]))], note=note)
    if "stage" in r.columns:
        s = r["stage"].fillna("Not recorded").value_counts().rename_axis("Stage").reset_index(name="Records")
        return bars("hbar", "Hiring Pipeline by Stage", "Records currently at each stage (funnel order not configured)",
                    s, "Stage", "Records")
    return na("funnel", title, note)


def workforce_trend(e: pd.DataFrame, window: M.Period | None) -> pd.DataFrame | None:
    """Month-end headcount with joiners and leavers per month inside the window."""
    if e is None or window is None:
        return None
    hc = M.emp_headcount_trend(e, window)
    parts = []
    if "hire_date" in e.columns:
        h = e[e["hire_date"].notna()]
        parts.append(h.groupby(h["hire_date"].dt.to_period("M")).size().rename("Joiners"))
    if "exit_date" in e.columns and e["exit_date"].notna().any():
        x = e[e["exit_date"].notna()]
        parts.append(x.groupby(x["exit_date"].dt.to_period("M")).size().rename("Leavers"))
    if hc is None or not parts:
        return None
    lc = pd.concat(parts, axis=1).fillna(0)
    lc.index = lc.index.to_timestamp()
    hc = hc.assign(Month=hc["Month end"].dt.to_period("M").dt.to_timestamp())
    return hc.merge(lc, left_on="Month", right_index=True, how="left").fillna({"Joiners": 0, "Leavers": 0})


def _first(fns):
    return next((x for x in (f() for f in fns) if x is not None), None)


# ------------------------------------------------------------------ builders
def _base(key: str, ctx: P.PeriodCtx, source: str) -> Report:
    k, title, area, *_ = next(d for d in DASHBOARDS if d[0] == key)
    return Report(key, f"{title} Dashboard", area, ctx.label or "All data",
                  ctx.period.label() if ctx.period else "All data", ctx.location, source)


def _missing(rep: Report, needs: tuple) -> Report:
    rep.available = False
    rep.reason = f"No {' / '.join(needs)} data was found in the workbook."
    return rep


def build_overview(ctx: P.PeriodCtx, model=None) -> Report:
    rep = _base("overview", ctx, getattr(model, "source_name", ""))
    ds, S = ctx.ds, ctx.settings
    r, e, t, p, c = (ds.get(k) for k in ("recruitment", "employee", "training", "performance", "relations"))
    if not ds:
        return _missing(rep, ("HR",))
    mt = ctx.metric
    rep.kpis = [
        mt("employee", "Total employees", "count", lambda q: M.emp_headcount(e, ctx.asof(q))),
        mt("employee", "New hires", "count", lambda q: M.emp_new_hires(e, q)),
        mt("employee", "Attrition rate", "pct", lambda q: M.emp_attrition(e, q)),
        mt("recruitment", "Open requisitions", "count", lambda q: M.rec_open_count(r, ctx.asof(q))),
        mt("recruitment", "Positions filled", "count", lambda q: M.rec_filled(r, q)),
        mt("recruitment", "Average time to hire", "days", lambda q: M.rec_time_to_hire(r, q)),
        mt("training", "Training hours", "hours", lambda q: M.trn_hours(t, q)),
        mt("training", "Employees trained", "count", lambda q: M.trn_employees(t, q)),
        ctx.static("performance", "Average performance rating", "score", lambda q: M.pms_avg_rating(p)),
        ctx.static("relations", "Engagement score", "score", lambda q: M.rel_engagement(c)),
    ]
    wt = workforce_trend(e, ctx.window)
    rep.charts.append(combo("Workforce Trend", "Joiners and leavers by month, with month-end headcount", wt, "Month",
                            ["Joiners", "Leavers"], "Headcount", secondary=True) if wt is not None
                      else na("combo", "Workforce Trend", "employee dates of joining not found."))
    dd = _first([lambda k=k: M.emp_distribution(e, k, ctx.asof()) for k in ("function", "department")]) if e is not None else None
    rep.charts.append(donut("Headcount by Function", "Active employees at period end", dd, dd.columns[0] if dd is not None else "",
                            "Employees", "Employees", reason="no department/function column."))
    rep.charts.append(funnel_or_pipeline(r, S["funnel_order"]) if r is not None else na("funnel", "Recruitment Funnel", "no recruitment data."))
    tr = ctx.in_window(M.rec_monthly(r), "Month") if r is not None else None
    rep.charts.append(combo("Recruitment Trend", "Positions filled vs requisitions opened", tr, "Month",
                            ["Positions filled", "Requisitions opened"],
                            names={"Positions filled": "Hired", "Requisitions opened": "Requisitions"})
                      if tr is not None and "Positions filled" in tr else na("combo", "Recruitment Trend", "recruitment dates not found."))
    dd = M.emp_distribution(e, "employee_type", ctx.asof()) if e is not None else None
    rep.charts.append(donut("Workforce Distribution", "By employee type", dd, dd.columns[0] if dd is not None else "", "Employees",
                            reason="employee type column not found."))
    s = M.rec_source_share(r, ctx.period) if r is not None else None
    rep.charts.append(donut("Source of Hire", "Hires in the period", s, "Source", "Hires", "Hires", reason="source-of-hire data not found."))
    g = M.trn_breakdown(t, "category", ctx.period) if t is not None else None
    rep.charts.append(bars("hbar", "Training Hours by Category", "Hours in the period", g, g.columns[0] if g is not None else "",
                           "Training hours", reason="training category data not found."))
    rep.focus = (recruitment_insights(r, S["funnel_order"], ctx.period, ctx.asof()) + employee_insights(e, ctx.period)
                 + training_insights(t, S) + performance_insights(p, S) + (data_quality_insights(model) if model else []))
    return rep


def build_recruitment(ctx: P.PeriodCtx, model=None) -> Report:
    rep = _base("recruitment", ctx, getattr(model, "source_name", ""))
    r = ctx.ds.get("recruitment")
    if r is None:
        return _missing(rep, ("recruitment",))
    rep.kpis = [ctx.cmp(lambda q: M.rec_requisitions(r, q)), ctx.cmp(lambda q: M.rec_filled(r, q)),
                ctx.cmp(lambda q: M.rec_time_to_hire(r, q)), ctx.cmp(lambda q: M.rec_offer_acceptance(r, q)),
                ctx.cmp(lambda q: M.rec_new_hires(r, q)), ctx.cmp(lambda q: M.rec_cost_per_hire(r, q)),
                ctx.cmp(lambda q: M.rec_open_count(r, ctx.asof(q))), ctx.cmp(lambda q: M.rec_open_ageing(r, ctx.asof(q)))]
    tr = ctx.in_window(M.rec_monthly(r), "Month")
    rep.charts.append(combo("Hiring Trend", "Positions filled vs requisitions opened, by month", tr, "Month",
                            ["Positions filled", "Requisitions opened"], "Positions filled",
                            names={"Positions filled": "Hired", "Requisitions opened": "Requisitions"}, line_name="Hired (trend)")
                      if tr is not None and "Positions filled" in tr else na("combo", "Hiring Trend", "requisition dates not found."))
    fn = _first([lambda k=k: M.rec_by(r, k, ctx.period, filled_only=True) for k in ("function", "department")])
    rep.charts.append(donut("Hiring by Function", "Positions filled in the period", fn, fn.columns[0] if fn is not None else "",
                            "Requisitions", "Positions Filled", reason="no function/department column or no filled requisitions."))
    rep.charts.append(funnel_or_pipeline(r, ctx.settings["funnel_order"]))
    rep.charts.append(line("Time-to-Hire Trend", "Average days from open to filled", tr, "Month", "Avg time to hire (days)", "int")
                      if tr is not None else na("line", "Time-to-Hire Trend", "open and filled dates not found."))
    s = M.rec_source_share(r, ctx.period)
    rep.charts.append(donut("Source of Hire", "Share of hires with a valid source", s, "Source", "Hires", "Hires",
                            reason="source and status columns not found, or no hires."))
    tt = M.rec_by(r, "job_title", ctx.period, filled_only=True)
    rep.charts.append(bars("hbar", "Top Hiring Roles", "Filled requisitions by job title", tt, tt.columns[0] if tt is not None else "",
                           "Requisitions", top=8, reason="job title/status not found."))
    tt = M.rec_by(r, "location", ctx.period)
    rep.charts.append(bars("hbar", "Hiring by Location", "Requisitions opened in the period", tt, tt.columns[0] if tt is not None else "",
                           "Requisitions", top=8, reason="location column not found."))
    tt, _ = M.small_group_filter(M.rec_by(r, "gender", ctx.period, filled_only=True), "Requisitions")
    rep.charts.append(donut("Diversity Hiring", "Hires by gender (small groups hidden)", tt, tt.columns[0] if tt is not None and len(tt) else "",
                            "Requisitions", reason="gender column not found or groups too small."))
    op = M.rec_open_positions(r, ctx.asof())
    if op is not None and len(op):
        op = op.rename(columns={"requisition_id": "Req ID", "job_title": "Job title", "department": "Department",
                                "function": "Function", "location": "Location", "priority": "Priority",
                                "days_open": "Days open", "recruiter": "Recruiter"})
        keep = [c for c in ["Req ID", "Job title", "Department", "Location", "Priority", "Days open", "Recruiter"] if c in op]
        rep.table = (f"Open Positions — oldest first ({len(op)} open as of {ctx.asof():%d %b %Y})", op[keep].head(12))
    rep.focus = recruitment_insights(r, ctx.settings["funnel_order"], ctx.period, ctx.asof())
    return rep


def build_employees(ctx: P.PeriodCtx, model=None) -> Report:
    rep = _base("employees", ctx, getattr(model, "source_name", ""))
    e = ctx.ds.get("employee")
    if e is None:
        return _missing(rep, ("employee",))
    rel = ctx.ds.get("relations")
    on = ctx.asof()
    rep.kpis = [ctx.cmp(lambda q: M.emp_headcount(e, ctx.asof(q))), ctx.cmp(lambda q: M.emp_new_hires(e, q)),
                ctx.cmp(lambda q: M.emp_exits(e, q)), ctx.cmp(lambda q: M.emp_attrition(e, q)),
                ctx.cmp(lambda q: M.emp_tenure(e, ctx.asof(q))),
                ctx.static("relations", "Engagement score", "score", lambda q: M.rel_engagement(rel))]
    wt = workforce_trend(e, ctx.window)
    rep.charts.append(combo("Headcount Trend", "Joiners and leavers by month, with month-end headcount", wt, "Month",
                            ["Joiners", "Leavers"], "Headcount", secondary=True) if wt is not None
                      else na("combo", "Headcount Trend", "date of joining not found."))
    dd = _first([lambda k=k: M.emp_distribution(e, k, on) for k in ("department", "function")])
    rep.charts.append(donut("Headcount by Department", "Active employees at period end", dd, dd.columns[0] if dd is not None else "",
                            "Employees", "Employees", reason="department column not found."))
    dd = M.emp_tenure_bands(e, on)
    rep.charts.append(bars("bar", "Tenure Distribution", "Active employees by tenure band", dd, "Tenure band", "Employees",
                           reason="date of joining not found."))
    for title, col, kind in (("Distribution by Function", "function", "hbar"), ("Employee Type", "employee_type", "donut"),
                             ("Gender Mix", "gender", "donut"), ("Level / Grade", "level", "hbar")):
        dd = M.emp_distribution(e, col, on)
        if col in ("gender", "level"):
            dd, _ = M.small_group_filter(dd, "Employees")
        reason = f"{col.replace('_', ' ')} column not found or groups too small."
        cat = dd.columns[0] if dd is not None and len(dd) else ""
        rep.charts.append(donut(title, "Active employees at period end", dd if cat else None, cat, "Employees", reason=reason)
                          if kind == "donut" else bars("hbar", title, "Active employees at period end", dd if cat else None,
                                                       cat, "Employees", reason=reason))
    rep.focus = employee_insights(e, ctx.period)
    return rep


def build_training(ctx: P.PeriodCtx, model=None) -> Report:
    rep = _base("training", ctx, getattr(model, "source_name", ""))
    t = ctx.ds.get("training")
    if t is None:
        return _missing(rep, ("training",))
    e, S = ctx.ds.get("employee"), ctx.settings
    rep.kpis = [ctx.cmp(lambda q: M.trn_hours(t, q)), ctx.cmp(lambda q: M.trn_employees(t, q)),
                ctx.cmp(lambda q: M.trn_participation(t, e, q, ctx.asof(q))),
                ctx.cmp(lambda q: M.trn_avg_hours(t, e, q, ctx.asof(q))), ctx.cmp(lambda q: M.trn_cert_rate(t, q)),
                ctx.cmp(lambda q: M.trn_effectiveness(t, q)), ctx.cmp(lambda q: M.trn_cost(t, q)),
                ctx.cmp(lambda q: M.trn_cost_per_employee(t, e, q, ctx.asof(q))), ctx.cmp(lambda q: M.trn_budget_util(t, q, S))]
    tr = M.trn_monthly(t, ctx.window)
    rep.charts.append(combo("Training Trend", "Training hours by month, with employees trained", tr, "Month", ["Training hours"],
                            "Employees trained" if tr is not None and "Employees trained" in tr else None, secondary=True)
                      if tr is not None and "Training hours" in tr else na("combo", "Training Trend", "training date and hours not found."))
    for title, col, kind in (("Training by Category", "category", "donut"), ("Top Training Programmes", "program", "hbar"),
                             ("Delivery Mode", "delivery_mode", "donut"), ("Training by Location", "location", "hbar")):
        g = M.trn_breakdown(t, col, ctx.period)
        cat = g.columns[0] if g is not None else ""
        reason = f"{col.replace('_', ' ')} or hours column not found."
        rep.charts.append(donut(title, "Hours in the period", g, cat, "Training hours",
                                "Training Hours" if col == "category" else "", reason=reason)
                          if kind == "donut" else bars("hbar", title, "Hours in the period", g, cat, "Training hours", top=8, reason=reason))
    g = _first([lambda k=k: M.trn_effect_by(t, k, ctx.period) for k in ("program", "category")])
    rep.charts.append(bars("hbar", "Training Effectiveness", g.columns[1] if g is not None else "", g,
                           g.columns[0] if g is not None else "", g.columns[1] if g is not None else "", fmt="dec1",
                           reason="no assessment or pre/post score columns found (attendance is not treated as effectiveness)."))
    if "cost" in t.columns and "category" in t.columns:
        s, _ = M._scope(t, ctx.period, "date")
        g = s.assign(k=s["category"].fillna("Not recorded")).groupby("k")["cost"].sum().rename_axis("Category").reset_index(name="Cost")
        rep.charts.append(bars("hbar", "Training Cost by Category", "Cost in the period (₹)", g, "Category", "Cost"))
    else:
        rep.charts.append(na("hbar", "Training Cost by Category", "training cost data not found."))
    g = M.trn_completion_mix(t, ctx.period)
    if g is not None:
        g = g.assign(Status=g["Status"].astype(str).str.replace("_", " ").str.capitalize())
    rep.charts.append(donut("Certification and Completion", "Completion status of training records", g, "Status", "Records", "Records",
                            reason="completion status column not found."))
    g = M.trn_breakdown(t, "program", ctx.period)
    if g is not None and len(g):
        rep.table = ("Programme Detail — hours and participants", g.head(12).round(1))
    rep.focus = training_insights(t, S)
    return rep


def build_performance(ctx: P.PeriodCtx, model=None) -> Report:
    rep = _base("performance", ctx, getattr(model, "source_name", ""))
    p = ctx.ds.get("performance")
    if p is None:
        return _missing(rep, ("performance",))
    S = ctx.settings
    if "cycle" in p.columns and p["cycle"].notna().any():
        cyc = sorted(p["cycle"].dropna().unique())[-1]
        cur = p[p["cycle"] == cyc]
        rep.period, rep.period_range = f"Cycle {cyc}", f"Review cycle {cyc} (latest in the workbook)"
    else:
        cur = p
        rep.period, rep.period_range = "All reviews", "All review rows (no cycle column)"
    rep.kpis = [(m, None) for m in (M.pms_eligible(cur), M.pms_completed(cur), M.pms_completion(cur),
                                    M.pms_high_performers(cur, S), M.pms_avg_rating(cur), M.pms_goal_rate(cur), M.pms_idp(cur))]
    dd = M.pms_rating_dist(cur)
    if dd is not None:
        dd = dd.assign(Rating=dd["Rating"].map(lambda v: P.num(float(v))))
    rep.charts.append(bars("bar", "Rating Distribution", "Employees by rating", dd, "Rating", "Employees", reason="rating column not found."))
    dd = M.pms_status_counts(cur)
    if dd is not None:
        dd = dd.assign(**{"Review status": dd["Review status"].astype(str).str.replace("_", " ").str.capitalize()})
    rep.charts.append(donut("PMS Cycle Progress", "Employees by review status", dd, "Review status", "Employees", "Employees",
                            reason="review status column not found."))
    for title, col in (("Performance by Function", "function"), ("Performance by Level", "level"), ("Performance by Age Group", "age_group")):
        dd, _ = M.small_group_filter(M.pms_by(cur, col), "Rated employees")
        ok = dd is not None and len(dd)
        rep.charts.append(bars("hbar", title, "Average rating; small groups hidden", dd if ok else None, dd.columns[0] if ok else "",
                               "Average rating", fmt="dec2", reason=f"{col.replace('_', ' ')} column not found or groups too small."))
    tr = M.pms_trend(p)
    rep.charts.append(line("Rating Trend", "Average rating per cycle", tr, "Cycle", "Average rating", "dec2")
                      if tr is not None else na("line", "Rating Trend", "rating with a cycle or review date not found."))
    if "function" in cur.columns and "employee_id" in cur.columns:
        mask, src = M._hp_mask(cur, S)
        if mask is not None:
            dd = cur[mask].groupby(cur["function"].fillna("Not recorded"))["employee_id"].nunique() \
                .rename_axis("Function").reset_index(name="High performers")
            dd, _ = M.small_group_filter(dd, "High performers")
            rep.charts.append(bars("hbar", "High Performers by Function", f"Definition: {src}", dd if len(dd) else None,
                                   "Function", "High performers", reason="groups too small."))
        else:
            rep.charts.append(na("hbar", "High Performers by Function", "no high-performer flag and no approved rating threshold configured."))
    rep.focus = performance_insights(cur, S)
    return rep


def build_turnover(ctx: P.PeriodCtx, model=None) -> Report:
    rep = _base("turnover", ctx, getattr(model, "source_name", ""))
    e = ctx.ds.get("employee")
    if e is None:
        return _missing(rep, ("employee",))
    Pd = ctx.period
    if Pd is None:
        rep.available, rep.reason = False, "No dates found in the workbook, so period-based turnover cannot be calculated."
        return rep
    op = M.emp_headcount(e, Pd.start - pd.Timedelta(days=1))
    op = M.Metric("op", "Opening headcount", op.value, "count", op.reason, f"Day before {Pd.start:%d %b %Y}")
    cl = M.emp_headcount(e, Pd.end)
    cl = M.Metric("cl", "Closing headcount", cl.value, "count", cl.reason, f"As of {Pd.end:%d %b %Y}")
    mix = M.emp_exit_mix(e, Pd)
    vol = M._na("vol", "Voluntary exits (share)", "pct", "Not available — exit type column not found or no exits.")
    if mix is not None and "voluntary" in set(mix["Category"]):
        tot = mix["Exits"].sum()
        vol = M.Metric("vol", "Voluntary exits (share)", mix.loc[mix["Category"] == "voluntary", "Exits"].sum() / tot * 100, "pct")
    rep.kpis = [(op, None), (cl, None), ctx.cmp(lambda q: M.emp_exits(e, q)), ctx.cmp(lambda q: M.emp_attrition(e, q)),
                (vol, None), ctx.cmp(lambda q: M.emp_tenure(e, ctx.asof(q)))]
    ex = M.emp_exits_trend(e, ctx.window, "M") if ctx.window else None
    hc = M.emp_headcount_trend(e, ctx.window) if ctx.window else None
    if ex is not None:
        ex = ex.assign(Month=pd.to_datetime(ex["Period"].astype(str)).dt.to_period("M").dt.to_timestamp())
        if hc is not None:
            hc = hc.assign(Month=hc["Month end"].dt.to_period("M").dt.to_timestamp())
            ex = hc[["Month", "Headcount"]].merge(ex[["Month", "Exits"]], on="Month", how="left").fillna({"Exits": 0})
        rep.charts.append(combo("Exit Trend", "Exits by month, with month-end headcount", ex, "Month", ["Exits"],
                                "Headcount" if "Headcount" in ex else None, secondary=True))
    else:
        rep.charts.append(na("combo", "Exit Trend", "no exits with dates in the selected year."))
    if mix is not None:
        mix = mix.assign(Category=mix["Category"].astype(str).str.replace("_", " ").str.capitalize())
    rep.charts.append(donut("Voluntary vs Involuntary", "Exits in the period", mix, "Category", "Exits", "Exits",
                            reason="exit type column not found or no exits."))
    dd = M.emp_exit_tenure(e, Pd)
    rep.charts.append(bars("bar", "Exits by Tenure", "Tenure at exit, period exits", dd, "Tenure at exit", "Exits",
                           reason="joining and exit dates not found."))
    for title, col in (("Attrition by Department", "department"), ("Attrition by Function", "function"),
                       ("Attrition by Employee Type", "employee_type"), ("Attrition by Location", "location")):
        dd, _ = M.small_group_filter(M.emp_attrition_by(e, col, Pd), "Average headcount")
        ok = dd is not None and len(dd)
        rep.charts.append(bars("hbar", title, "Attrition rate %, small groups hidden", dd if ok else None,
                               dd.columns[0] if ok else "", "Attrition rate %", fmt="pct",
                               reason=f"{col.replace('_', ' ')} column not found or groups too small."))
    dd, _ = M.small_group_filter(M.emp_exit_reasons(e, Pd), "Exits")
    rep.charts.append(bars("hbar", "Exit Reasons", "Exits; small groups hidden", dd if dd is not None and len(dd) else None,
                           "Exit reason", "Exits", reason="exit reason column not found or groups too small."))
    rep.focus = turnover_insights(e, Pd)
    return rep


def build_relations(ctx: P.PeriodCtx, model=None) -> Report:
    rep = _base("relations", ctx, getattr(model, "source_name", ""))
    c = ctx.ds.get("relations")
    if c is None:
        return _missing(rep, ("relations",))
    rep.kpis = [ctx.cmp(lambda q: M.rel_cases(c, q)), ctx.cmp(lambda q: M.rel_open(c, q)), ctx.cmp(lambda q: M.rel_closed(c, q)),
                ctx.cmp(lambda q: M.rel_resolution_rate(c, q)), ctx.cmp(lambda q: M.rel_resolution_days(c, q)),
                (M.rel_engagement(c), None), ctx.cmp(lambda q: M.rel_pending(c, q)), (M.rel_response_rate(c), None)]
    tr = M.rel_monthly(c, ctx.window) if ctx.window else None
    rep.charts.append(combo("Cases Trend", "Cases opened per month", tr, "Month", ["Cases"], "Cases", line_name="Trend")
                      if tr is not None else na("combo", "Cases Trend", "case ID and open date not found."))
    for title, col, kind in (("Issue Categories", "case_category", "donut"), ("Cases by Department", "department", "hbar"),
                             ("Cases by Location", "location", "hbar")):
        dd, _ = M.small_group_filter(M.rel_categories(c, col, ctx.period), "Cases")
        ok = dd is not None and len(dd)
        reason = f"{col.replace('_', ' ')} column not found or groups too small."
        rep.charts.append(donut(title, "Cases in the period; small groups hidden", dd if ok else None, "Category", "Cases", "Cases", reason=reason)
                          if kind == "donut" else bars("hbar", title, "Distinct cases; small groups hidden", dd if ok else None,
                                                       "Category", "Cases", reason=reason))
    if "status_norm" in c.columns and "case_id" in c.columns:
        s, _ = M._scope(c, ctx.period, "open_date")
        dd = s.dropna(subset=["case_id"]).drop_duplicates("case_id")["status_norm"].fillna("Not recorded").astype(str).str.title() \
            .value_counts().rename_axis("Status").reset_index(name="Cases")
        rep.charts.append(donut("Case Status", "Cases opened in the period", dd if len(dd) else None, "Status", "Cases", "Cases"))
    rep.focus = relations_insights(c, ctx.period)
    return rep


BUILDERS = {"overview": build_overview, "recruitment": build_recruitment, "employees": build_employees,
            "training": build_training, "performance": build_performance, "turnover": build_turnover,
            "relations": build_relations}


def build(key: str, ctx: P.PeriodCtx, model=None) -> Report:
    return BUILDERS[key](ctx, model)


def availability(datasets: dict, key: str) -> tuple[bool, str]:
    needs = next(d[3] for d in DASHBOARDS if d[0] == key)
    if not needs:
        return bool(datasets), "Ready" if datasets else "No HR data"
    ok = any(n in datasets for n in needs)
    return ok, "Ready" if ok else f"Needs {' / '.join(needs)} data"


MIN_GROUP_NOTE = f"Groups with fewer than {MIN_GROUP_SIZE} people are hidden for confidentiality."
