"""Streamlit-free presentation logic shared by the dashboards and the PPT/PDF exports:
reporting periods, previous-period comparison, change direction, value formatting and short labels."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from services import metrics as M
from services.overview import data_bounds

# ---------------------------------------------------------------- labels & direction
LOWER_IS_BETTER = {"rec_time_to_hire", "rec_cost_per_hire", "rec_open_ageing", "emp_exits", "emp_attrition",
                   "rel_open", "rel_pending", "rel_resolution_days"}
NEUTRAL = {"trn_cost", "trn_cost_per_employee", "rec_open_count", "rel_cases", "op", "cl"}
SHORT_LABEL = {"rec_new_hires": "New hires", "rec_time_to_hire": "Time to hire (avg.)",
               "rec_open_ageing": "Avg. open-req. age", "trn_avg_hours": "Avg. hours / employee",
               "rel_engagement": "Engagement score", "pms_avg_rating": "Average rating",
               "pms_eligible": "PMS-eligible employees", "trn_participation": "Participation rate",
               "trn_cost_per_employee": "Cost per employee", "rel_resolution_days": "Avg. resolution time",
               "rec_open_count": "Open requisitions", "trn_hours": "Training hours"}


def label(m: M.Metric) -> str:
    return SHORT_LABEL.get(m.key, m.label)


@dataclass(frozen=True)
class Delta:
    value: float            # absolute change (pp for percentages)
    pct: float | None       # relative change %, None when undefined
    unit: str
    tone: str               # good | bad | neutral
    vs: str                 # e.g. "last quarter"

    @property
    def text(self) -> str:
        if self.value == 0:
            return "No change"
        if self.unit == "pct":
            return f"{abs(self.value):.1f} pp"
        if self.pct is not None:
            return f"{abs(self.pct):.0f}%" if abs(self.pct) >= 10 else f"{abs(self.pct):.1f}%"
        return f"{abs(self.value):,.1f}"

    @property
    def up(self) -> bool:
        return self.value > 0


def make_delta(cur: M.Metric, prev: M.Metric | None, vs: str) -> Delta | None:
    if prev is None or not cur.available or not prev.available:
        return None
    d = cur.value - prev.value
    if cur.key in NEUTRAL or d == 0:
        tone = "neutral"
    else:
        tone = "good" if (d < 0) == (cur.key in LOWER_IS_BETTER) else "bad"
    return Delta(d, M.pct_change(cur.value, prev.value), cur.unit, tone, vs)


def num(v: float, dec: int = 1) -> str:
    s = f"{v:,.{dec}f}"
    return s[:-2] if dec == 1 and s.endswith(".0") else s


def fmt(m: M.Metric) -> str:
    if not m.available:
        return "Not available"
    v, u = m.value, m.unit
    if u == "pct":
        return f"{num(v)}%"
    if u == "days":
        return f"{v:,.0f} days" if abs(v) >= 10 else f"{num(v)} days"
    if u == "hours":
        return f"{num(v)} h"
    if u == "years":
        return f"{num(v)} yrs"
    return m.display()


# ---------------------------------------------------------------- periods
PERIODS = ["Q1", "Q2", "Q3", "Q4", "H1", "H2", "Full year", "Last 12 months"]
_START = {"Q1": 1, "Q2": 4, "Q3": 7, "Q4": 10, "H1": 1, "H2": 7, "Full year": 1}
_LEN = {"Q1": 3, "Q2": 3, "Q3": 3, "Q4": 3, "H1": 6, "H2": 6, "Full year": 12}
_VS = {3: "last quarter", 6: "previous half", 12: "same period last year"}


def default_selection(b) -> tuple[int, str]:
    """Latest quarter in the data, or the quarter before it when the latest is under half covered."""
    q_start = pd.Timestamp(b[1].year, 3 * ((b[1].month - 1) // 3) + 1, 1)
    dq = q_start if (b[1] - q_start).days >= 45 or q_start - pd.DateOffset(months=3) < b[0] \
        else q_start - pd.DateOffset(months=3)
    return dq.year, f"Q{(dq.month - 1) // 3 + 1}"


def year_options(b) -> list[int]:
    return list(range(b[1].year, b[0].year - 1, -1))


def period_options(year: int, b) -> list[str]:
    out = []
    for c in PERIODS:
        if c == "Last 12 months":
            out.append(c)
            continue
        s = pd.Timestamp(year, _START[c], 1)
        e = s + pd.DateOffset(months=_LEN[c]) - pd.Timedelta(days=1)
        if s <= b[1] and e >= b[0]:
            out.append(c)
    return out


def resolve(year: int, choice: str, b) -> tuple[M.Period, M.Period, str, M.Period]:
    """(period, previous period, 'vs …' label, trend window) for a Year + Period selection."""
    lo, hi = b
    if choice == "Last 12 months":
        p = M.Period(max(lo, hi - pd.Timedelta(days=364)), hi)
        return p, p.previous(), "previous 12 months", p
    start = pd.Timestamp(year, _START[choice], 1)
    n = _LEN[choice]
    end = start + pd.DateOffset(months=n) - pd.Timedelta(days=1)
    p = M.Period(max(start, lo), min(end, hi))
    off = pd.DateOffset(months=n)
    prev = M.Period(p.start - off, p.end - off)
    vs = _VS[n] if not (n == 12 and p.start == start and p.end == end) else "last year"
    win = M.Period(max(pd.Timestamp(year, 1, 1), lo), min(pd.Timestamp(year, 12, 31), hi))
    return p, prev, vs, win


def period_name(year: int | None, choice: str | None, p: M.Period | None) -> str:
    if p is None:
        return "All data"
    if choice in _START:
        return f"{choice} {year}" if choice != "Full year" else f"FY {year} (Jan–Dec)"
    return p.label()


def locations(ds: dict) -> list[str]:
    vals = set()
    for d in ds.values():
        if "location" in d.columns:
            vals |= set(d["location"].dropna().astype(str))
    return sorted(vals)


def apply_location(ds: dict, loc: str) -> dict:
    if not loc or loc == "All":
        return dict(ds)
    return {k: (d[d["location"].astype(str) == loc] if "location" in d.columns else d) for k, d in ds.items()}


# ---------------------------------------------------------------- context
@dataclass
class PeriodCtx:
    ds: dict
    settings: dict
    bounds: tuple | None
    period: M.Period | None
    prev: M.Period | None
    vs: str
    window: M.Period | None          # trend window (the selected year, or the selected range)
    label: str = ""                  # e.g. "Q3 2026"
    location: str = "All"

    @property
    def comparable(self) -> bool:
        return bool(self.prev and self.bounds and self.prev.start >= self.bounds[0])

    def asof(self, p: M.Period | None = None) -> pd.Timestamp:
        p = p or self.period
        return p.end if p else pd.Timestamp.today().normalize()

    def cmp(self, fn: Callable[[M.Period | None], M.Metric]) -> tuple[M.Metric, Delta | None]:
        cur = fn(self.period)
        if not (self.period and self.comparable) or not cur.available:
            return cur, None
        return cur, make_delta(cur, fn(self.prev), self.vs)

    def static(self, dataset: str, label: str, unit: str, fn) -> tuple[M.Metric, None]:
        """Metric that is not period-based: no previous-period comparison is shown."""
        if dataset not in self.ds:
            return M._na(label, label, unit, f"Not available — no {dataset} data found in the workbook."), None
        return fn(None), None

    def metric(self, dataset: str, label: str, unit: str, fn):
        if dataset not in self.ds:
            return M._na(label, label, unit, f"Not available — no {dataset} data found in the workbook."), None
        return self.cmp(fn)

    def in_window(self, df: pd.DataFrame | None, col: str) -> pd.DataFrame | None:
        """Rows of a monthly trend table that fall inside the trend window."""
        if df is None or self.window is None or col not in df.columns:
            return df
        d = df[(df[col] >= self.window.start.to_period("M").to_timestamp()) & (df[col] <= self.window.end)]
        return d if len(d) else None


def build_ctx(datasets: dict, settings: dict, year: int | None = None, choice: str | None = None,
              loc: str = "All") -> PeriodCtx:
    """Context without Streamlit (used by the exports and tests). Defaults to the dashboards' default period."""
    b = data_bounds(datasets)
    ds = apply_location(datasets, loc)
    if not b:
        return PeriodCtx(ds, settings, None, None, None, "", None, "All data", loc)
    if year is None or choice is None:
        year, choice = default_selection(b)
    p, prev, vs, win = resolve(year, choice, b)
    return PeriodCtx(ds, settings, b, p, prev, vs, win, period_name(year, choice, p), loc)
