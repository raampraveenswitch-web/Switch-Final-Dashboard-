"""Orchestration: period bounds and one-shot calculation of every scalar KPI."""
from __future__ import annotations

import pandas as pd

from services import metrics as M

_DATE_FIELDS = {"employee": ["hire_date", "exit_date"], "recruitment": ["open_date", "filled_date"],
                "training": ["date"], "performance": ["review_date"], "relations": ["open_date", "close_date"]}


def data_bounds(datasets: dict[str, pd.DataFrame]) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    lo, hi = [], []
    for ds, cols in _DATE_FIELDS.items():
        d = datasets.get(ds)
        if d is None:
            continue
        for c in cols:
            if c in d.columns and d[c].notna().any():
                lo.append(d[c].min())
                hi.append(d[c].max())
    return (min(lo).normalize(), max(hi).normalize()) if lo else None


def comparable(period: M.Period | None, bounds) -> bool:
    """A previous-period comparison is only shown when the previous window lies inside the observed data range."""
    return bool(period and bounds and period.previous().start >= bounds[0])


def all_metrics(ds: dict[str, pd.DataFrame], settings: dict, period: M.Period | None) -> dict[str, M.Metric]:
    as_of = period.end if period else pd.Timestamp.today().normalize()
    r, e, t, p, c = (ds.get(k) for k in ("recruitment", "employee", "training", "performance", "relations"))
    out: list[M.Metric] = []
    if r is not None:
        out += [M.rec_requisitions(r, period), M.rec_filled(r, period), M.rec_new_hires(r, period),
                M.rec_time_to_hire(r, period), M.rec_open_count(r, as_of), M.rec_offer_acceptance(r, period), M.rec_cost_per_hire(r, period),
                M.rec_open_ageing(r, as_of)]
    if e is not None:
        out += [M.emp_headcount(e, as_of), M.emp_new_hires(e, period), M.emp_exits(e, period),
                M.emp_attrition(e, period), M.emp_tenure(e, as_of)]
    if t is not None:
        out += [M.trn_hours(t, period), M.trn_employees(t, period), M.trn_participation(t, e, period, as_of),
                M.trn_avg_hours(t, e, period, as_of), M.trn_cert_rate(t, period), M.trn_effectiveness(t, period),
                M.trn_cost(t, period), M.trn_cost_per_employee(t, e, period, as_of),
                M.trn_budget_util(t, period, settings)]
    if p is not None:
        out += [M.pms_eligible(p), M.pms_completed(p), M.pms_completion(p), M.pms_avg_rating(p),
                M.pms_high_performers(p, settings), M.pms_high_pct(p, settings), M.pms_goal_rate(p), M.pms_idp(p)]
    if c is not None:
        out += [M.rel_cases(c, period), M.rel_open(c, period), M.rel_closed(c, period), M.rel_pending(c, period),
                M.rel_resolution_rate(c, period), M.rel_resolution_days(c, period), M.rel_engagement(c),
                M.rel_response_rate(c)]
    return {m.key: m for m in out}
