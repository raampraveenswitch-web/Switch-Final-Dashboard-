"""Reusable KPI functions. Every function:
  * takes already-cleaned canonical frames (see data_cleaning.py),
  * returns a ``Metric`` (or a DataFrame for breakdowns) and never fabricates a value,
  * returns an *unavailable* Metric with a reason when columns/data are missing.
Definitions are documented in services/kpi_registry.py (single source for the README)."""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from config import CURRENCY_SYMBOL, FIELDS, MIN_GROUP_SIZE, TENURE_BANDS_YEARS


@dataclass(frozen=True)
class Period:
    start: pd.Timestamp
    end: pd.Timestamp

    def previous(self) -> "Period":
        span = self.end - self.start + pd.Timedelta(days=1)
        return Period(self.start - span, self.start - pd.Timedelta(days=1))

    def label(self) -> str:
        return f"{self.start:%d %b %Y} – {self.end:%d %b %Y}"


@dataclass(frozen=True)
class Metric:
    key: str
    label: str
    value: float | None = None
    unit: str = "count"          # count | pct | days | hours | years | currency | score | pts
    reason: str = ""
    detail: str = ""

    @property
    def available(self) -> bool:
        return self.value is not None

    def display(self) -> str:
        if self.value is None:
            return "Not available"
        v, u = self.value, self.unit
        return {"pct": f"{v:.1f}%", "days": f"{v:.1f} days", "hours": f"{v:,.1f} h", "years": f"{v:.1f} yrs",
                "currency": f"{CURRENCY_SYMBOL}{v:,.0f}", "score": f"{v:.2f}", "pts": f"{v:+.1f} pts"
                }.get(u, f"{v:,.0f}")


def _na(key, label, unit, reason):
    return Metric(key, label, None, unit, reason)


def _ok(key, label, value, unit="count", detail=""):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return _na(key, label, unit, "No valid records in the selected scope.")
    return Metric(key, label, float(value), unit, "", detail)


def _missing(ds: str, df: pd.DataFrame | None, *fields: str) -> str | None:
    if df is None:
        return f"Not available — no {ds} data found in the workbook."
    miss = [FIELDS[ds][f]["label"] for f in fields if f not in df.columns]
    return ("Not available — required column(s) not found: " + ", ".join(miss) + ".") if miss else None


def _div(n, d):
    return None if d in (0, None) or n is None else n / d


def _between(s: pd.Series, p: Period | None) -> pd.Series:
    return pd.Series(True, index=s.index) if p is None else (s >= p.start) & (s <= p.end + pd.Timedelta(days=1) - pd.Timedelta(seconds=1))


def _scope(df: pd.DataFrame, p: Period | None, *prefer: str) -> tuple[pd.DataFrame, str]:
    for c in prefer:
        if c in df.columns and p is not None:
            return df[_between(df[c], p)], ""
    return df, ("" if p is None else "No date column mapped: period filter not applied.")


def _ids(df: pd.DataFrame, col: str = "employee_id") -> set:
    return set(df[col].dropna()) if col in df.columns else set()


def _req_level(df: pd.DataFrame) -> pd.DataFrame:
    return df.dropna(subset=["requisition_id"]).drop_duplicates("requisition_id", keep="first")


# ===================================================================== change
def absolute_change(cur, prev):
    return None if cur is None or prev is None else cur - prev


def pct_change(cur, prev):
    return None if cur is None or prev in (None, 0) else (cur - prev) / prev * 100


def pp_change(cur, prev):
    return None if cur is None or prev is None else cur - prev


def change_text(cur: Metric, prev: Metric | None, comparable: bool, prev_label: str = "") -> str:
    """Human-readable change vs previous period, or '' when it would be misleading."""
    if not comparable or prev is None or not cur.available or not prev.available:
        return ""
    if cur.unit == "pct":
        d = pp_change(cur.value, prev.value)
        return f"{d:+.1f} pp vs previous period ({prev_label})" if d is not None else ""
    d, pc = absolute_change(cur.value, prev.value), pct_change(cur.value, prev.value)
    if d is None:
        return ""
    return f"{d:+,.1f} ({pc:+.1f}%) vs previous period ({prev_label})" if pc is not None else \
        f"{d:+,.1f} vs previous period ({prev_label}; % change undefined)"


# ============================================================== recruitment
def rec_requisitions(df, p=None):
    m = _missing("recruitment", df, "requisition_id")
    if m:
        return _na("rec_requisitions", "Total requisitions", "count", m)
    s, note = _scope(df, p, "open_date")
    return _ok("rec_requisitions", "Total requisitions", s["requisition_id"].nunique(), detail=note)


def rec_filled(df, p=None):
    m = _missing("recruitment", df, "requisition_id", "status")
    if m:
        return _na("rec_filled", "Positions filled", "count", m)
    s, note = _scope(df, p, "filled_date", "open_date")
    r = _req_level(s)
    return _ok("rec_filled", "Positions filled", (r["status_norm"] == "filled").sum(), detail=note)


def rec_new_hires(df, p=None):
    m = _missing("recruitment", df, "requisition_id", "filled_date")
    if m:
        return _na("rec_new_hires", "New hires (recruitment)", "count", m)
    s = df[_between(df["filled_date"], p)]
    return _ok("rec_new_hires", "New hires (recruitment)", s["requisition_id"].nunique())


def _tth_values(df, p):
    s = df[_between(df["filled_date"], p)]
    r = _req_level(s)
    d = (r["filled_date"] - r["open_date"]).dt.days
    return d[d >= 0].dropna(), int(d.isna().sum() + (d < 0).sum())


def rec_time_to_hire(df, p=None):
    m = _missing("recruitment", df, "requisition_id", "open_date", "filled_date")
    if m:
        return _na("rec_time_to_hire", "Average time to hire", "days", m)
    d, excl = _tth_values(df, p)
    return _ok("rec_time_to_hire", "Average time to hire", d.mean() if len(d) else None, "days",
               f"{len(d)} valid hires; {excl} excluded (missing/negative dates)")


def rec_offer_acceptance(df, p=None):
    m = _missing("recruitment", df, "offer_status")
    if m:
        return _na("rec_offer_acceptance", "Offer acceptance rate", "pct", m)
    s, note = _scope(df, p, "open_date", "filled_date")   # declined offers have no filled date, so scope by open date
    if "candidate_id" in s.columns:
        s = s.drop_duplicates(["requisition_id", "candidate_id"]) if "requisition_id" in s.columns \
            else s.drop_duplicates("candidate_id")
    o = s["offer_status_norm"]
    acc, den = (o == "accepted").sum(), o.isin(["accepted", "rejected", "declined"]).sum()
    return _ok("rec_offer_acceptance", "Offer acceptance rate",
               None if den == 0 else acc / den * 100, "pct", f"{acc} of {den} offers with a recorded outcome. {note}".strip())


def rec_cost_per_hire(df, p=None):
    m = _missing("recruitment", df, "requisition_id", "status", "cost")
    if m:
        return _na("rec_cost_per_hire", "Cost per hire", "currency", m)
    s, _ = _scope(df, p, "filled_date", "open_date")
    r = s.dropna(subset=["requisition_id"])
    r = r.groupby("requisition_id").agg(cost=("cost", "first"), st=("status_norm", "first"))
    r = r[(r["st"] == "filled") & r["cost"].notna()]
    return _ok("rec_cost_per_hire", "Cost per hire", _div(r["cost"].sum(), len(r)), "currency",
               f"{len(r)} filled requisitions with recorded cost")


def rec_source_share(df, p=None) -> pd.DataFrame | None:
    if _missing("recruitment", df, "requisition_id", "status", "source"):
        return None
    s, _ = _scope(df, p, "filled_date", "open_date")
    r = _req_level(s)
    r = r[(r["status_norm"] == "filled") & r["source"].notna()]
    if r.empty:
        return None
    t = r["source"].value_counts().rename_axis("Source").reset_index(name="Hires")
    t["Share %"] = t["Hires"] / t["Hires"].sum() * 100
    return t


def rec_funnel(df, order: list[str]) -> tuple[pd.DataFrame | None, str]:
    """Cumulative 'reached stage' counts and conversion to next stage."""
    if _missing("recruitment", df, "stage"):
        return None, "Recruitment stage column not found."
    if not order:
        return None, "Funnel order not configured. Set the ordered stages in Data Explorer → Business definitions."
    key = "candidate_id" if "candidate_id" in df.columns else None
    base = df.dropna(subset=[key]).drop_duplicates(key) if key else df
    idx = {s.strip().lower(): i for i, s in enumerate(order)}
    pos = base["stage"].astype("string").str.strip().str.lower().map(idx)
    unmapped = int((base["stage"].notna() & pos.isna()).sum())
    reached = [int((pos >= i).sum()) for i in range(len(order))]
    t = pd.DataFrame({"Stage": order, "Reached": reached})
    t["Conversion to next %"] = [None if reached[i] == 0 or i == len(order) - 1 else reached[i + 1] / reached[i] * 100
                                 for i in range(len(order))]
    note = f"{unmapped} record(s) have a stage that is not in the configured order and are excluded." if unmapped else ""
    return t, note


def rec_open_positions(df, as_of: pd.Timestamp) -> pd.DataFrame | None:
    if _missing("recruitment", df, "status", "open_date"):
        return None
    r = _req_level(df) if "requisition_id" in df.columns else df
    r = r[(r["status_norm"] == "open") & (r["open_date"] <= as_of)].copy()
    r["days_open"] = (as_of - r["open_date"]).dt.days
    cols = [c for c in ["requisition_id", "job_title", "department", "function", "location", "priority",
                        "days_open", "recruiter", "hiring_manager", "status"] if c in r.columns]
    return r[cols].sort_values("days_open", ascending=False)


def rec_open_ageing(df, as_of):
    t = rec_open_positions(df, as_of)
    m = _missing("recruitment", df, "status", "open_date")
    if m:
        return _na("rec_open_ageing", "Average open-requisition age", "days", m)
    return _ok("rec_open_ageing", "Average open-requisition age", t["days_open"].mean() if len(t) else None, "days",
               f"{len(t)} open requisitions as of {as_of:%d %b %Y}")


def rec_open_count(df, as_of):
    t = rec_open_positions(df, as_of)
    m = _missing("recruitment", df, "status", "open_date")
    if m:
        return _na("rec_open_count", "Open requisitions", "count", m)
    return _ok("rec_open_count", "Open requisitions", len(t), detail=f"As of {as_of:%d %b %Y}")


def rec_by(df, col, p=None, filled_only=False) -> pd.DataFrame | None:
    """Distinct requisitions per category (all, or filled only)."""
    if col not in df.columns or "requisition_id" not in df.columns:
        return None
    s, _ = _scope(df, p, "filled_date" if filled_only else "open_date", "open_date")
    r = _req_level(s)
    if filled_only:
        if "status_norm" not in r.columns:
            return None
        r = r[r["status_norm"] == "filled"]
    if r.empty:
        return None
    lab = FIELDS["recruitment"][col]["label"]
    return r[col].fillna("Not recorded").value_counts().rename_axis(lab).reset_index(name="Requisitions")


def rec_monthly(df) -> pd.DataFrame | None:
    frames = {}
    if "open_date" in df.columns and "requisition_id" in df.columns:
        r = _req_level(df).dropna(subset=["open_date"])
        frames["Requisitions opened"] = r.groupby(r["open_date"].dt.to_period("M"))["requisition_id"].nunique()
    if "filled_date" in df.columns and "requisition_id" in df.columns:
        r = _req_level(df).dropna(subset=["filled_date"])
        frames["Positions filled"] = r.groupby(r["filled_date"].dt.to_period("M"))["requisition_id"].nunique()
        if "open_date" in df.columns:
            r = r.assign(d=(r["filled_date"] - r["open_date"]).dt.days)
            r = r[r["d"] >= 0]
            frames["Avg time to hire (days)"] = r.groupby(r["filled_date"].dt.to_period("M"))["d"].mean()
    if not frames:
        return None
    t = pd.DataFrame(frames).sort_index()
    t.index = t.index.to_timestamp()
    return t.rename_axis("Month").reset_index()


# ================================================================ employees
def _active(df, on):
    a = df[df["hire_date"] <= on]
    return a[a["exit_date"].isna() | (a["exit_date"] > on)] if "exit_date" in a.columns else a


def _count(df):
    return df["employee_id"].nunique() if "employee_id" in df.columns else len(df)


def emp_headcount(df, on):
    m = _missing("employee", df, "hire_date")
    if m:
        return _na("emp_headcount", "Total employees", "count", m)
    return _ok("emp_headcount", "Total employees", _count(_active(df, on)), detail=f"Active on {on:%d %b %Y}")


def emp_new_hires(df, p=None):
    m = _missing("employee", df, "hire_date")
    if m:
        return _na("emp_new_hires", "New hires", "count", m)
    return _ok("emp_new_hires", "New hires", _count(df[_between(df["hire_date"], p)]))


def _exits_df(df, p):
    return df[df["exit_date"].notna() & _between(df["exit_date"], p)]


def emp_exits(df, p=None):
    m = _missing("employee", df, "exit_date")
    if m:
        return _na("emp_exits", "Employee exits", "count", m)
    return _ok("emp_exits", "Employee exits", _count(_exits_df(df, p)))


def _avg_headcount(df, p):
    o = _count(_active(df, p.start - pd.Timedelta(days=1)))
    c = _count(_active(df, p.end))
    return o, c, (o + c) / 2


def emp_attrition(df, p):
    m = _missing("employee", df, "hire_date", "exit_date")
    if m:
        return _na("emp_attrition", "Attrition rate", "pct", m)
    if p is None:
        return _na("emp_attrition", "Attrition rate", "pct", "Not available — no reporting period.")
    o, c, avg = _avg_headcount(df, p)
    ex = _count(_exits_df(df, p))
    return _ok("emp_attrition", "Attrition rate", None if avg == 0 else ex / avg * 100, "pct",
               f"{ex} exits ÷ average headcount {avg:,.1f} (opening {o}, closing {c}); not annualised")


def _tenure_years(df, on):
    a = _active(df, on)
    t = (on - a["hire_date"]).dt.days / 365.25
    return a.assign(tenure_years=t)[t >= 0]


def emp_tenure(df, on):
    m = _missing("employee", df, "hire_date")
    if m:
        return _na("emp_tenure", "Average tenure", "years", m)
    t = _tenure_years(df, on)
    return _ok("emp_tenure", "Average tenure", t["tenure_years"].mean() if len(t) else None, "years",
               f"{len(t)} active employees")


def _band(years: pd.Series) -> pd.Series:
    labels = pd.Series(pd.NA, index=years.index, dtype="object")
    for lo, hi, name in TENURE_BANDS_YEARS:
        mask = (years >= lo) & (years < hi) if hi is not None else (years >= lo)
        labels[mask] = name
    return labels


def emp_tenure_bands(df, on) -> pd.DataFrame | None:
    if _missing("employee", df, "hire_date"):
        return None
    t = _tenure_years(df, on)
    if t.empty:
        return None
    b = _band(t["tenure_years"])
    order = [n for _, _, n in TENURE_BANDS_YEARS]
    c = b.value_counts().reindex(order, fill_value=0).rename_axis("Tenure band").reset_index(name="Employees")
    c["Share %"] = c["Employees"] / c["Employees"].sum() * 100
    return c


def emp_distribution(df, col, on) -> pd.DataFrame | None:
    if _missing("employee", df, "hire_date") or col not in df.columns:
        return None
    a = _active(df, on)
    if a.empty:
        return None
    k = a[col].fillna("Not recorded")
    g = (a.assign(_k=k).groupby("_k").apply(_count, include_groups=False)
         .rename_axis(FIELDS["employee"][col]["label"]).reset_index(name="Employees"))
    g["Share %"] = g["Employees"] / g["Employees"].sum() * 100
    return g.sort_values("Employees", ascending=False)


def emp_headcount_trend(df, p: Period) -> pd.DataFrame | None:
    if _missing("employee", df, "hire_date"):
        return None
    ends = pd.date_range(p.start, p.end, freq="ME")
    if len(ends) == 0:
        ends = pd.DatetimeIndex([p.end])
    return pd.DataFrame({"Month end": ends, "Headcount": [_count(_active(df, e)) for e in ends]})


def emp_attrition_by(df, col, p) -> pd.DataFrame | None:
    if _missing("employee", df, "hire_date", "exit_date") or col not in df.columns or p is None:
        return None
    rows = []
    for k, g in df.assign(_k=df[col].fillna("Not recorded")).groupby("_k"):
        o, c, avg = _avg_headcount(g, p)
        ex = _count(_exits_df(g, p))
        rows.append({FIELDS["employee"][col]["label"]: k, "Exits": ex, "Average headcount": avg,
                     "Attrition rate %": None if avg == 0 else ex / avg * 100})
    return pd.DataFrame(rows) if rows else None


def emp_exit_mix(df, p, col="exit_type_norm") -> pd.DataFrame | None:
    if col not in df.columns or "exit_date" not in df.columns:
        return None
    e = _exits_df(df, p)
    if e.empty:
        return None
    return e[col].fillna("Not recorded").value_counts().rename_axis("Category").reset_index(name="Exits")


def emp_exit_reasons(df, p) -> pd.DataFrame | None:
    if "exit_reason" not in df.columns or "exit_date" not in df.columns:
        return None
    e = _exits_df(df, p)
    if e.empty:
        return None
    return e["exit_reason"].fillna("Not recorded").value_counts().rename_axis("Exit reason").reset_index(name="Exits")


def emp_exit_tenure(df, p) -> pd.DataFrame | None:
    if _missing("employee", df, "hire_date", "exit_date"):
        return None
    e = _exits_df(df, p)
    yrs = (e["exit_date"] - e["hire_date"]).dt.days / 365.25
    yrs = yrs[yrs >= 0]
    if yrs.empty:
        return None
    order = [n for _, _, n in TENURE_BANDS_YEARS]
    return _band(yrs).value_counts().reindex(order, fill_value=0).rename_axis("Tenure at exit").reset_index(name="Exits")


def emp_exits_trend(df, p, freq="M") -> pd.DataFrame | None:
    if _missing("employee", df, "exit_date"):
        return None
    e = _exits_df(df, p)
    if e.empty:
        return None
    g = e.groupby(e["exit_date"].dt.to_period(freq))["employee_id" if "employee_id" in e.columns else "exit_date"]
    t = (g.nunique() if "employee_id" in e.columns else g.count()).rename("Exits")
    t.index = t.index.astype(str)
    return t.rename_axis("Period").reset_index()


# ================================================================== training
def _eligible_employees(emp: pd.DataFrame | None, on) -> tuple[set | None, str]:
    if emp is None or "employee_id" not in emp.columns:
        return None, "Employee dataset with Employee ID not found (needed as denominator)."
    if "hire_date" in emp.columns and on is not None:
        return _ids(_active(emp, on)), f"active on {on:%d %b %Y}"
    return _ids(emp), "all distinct employees in the employee sheet"


def _participants(df):
    if "completion_status_norm" in df.columns:
        return df[df["completion_status_norm"] == "completed"]
    return df


def trn_hours(df, p=None):
    m = _missing("training", df, "hours")
    if m:
        return _na("trn_hours", "Total training hours", "hours", m)
    s, note = _scope(df, p, "date")
    return _ok("trn_hours", "Total training hours", s["hours"].sum() if s["hours"].notna().any() else None, "hours", note)


def trn_employees(df, p=None):
    m = _missing("training", df, "employee_id")
    if m:
        return _na("trn_employees", "Employees trained", "count", m)
    s, note = _scope(df, p, "date")
    return _ok("trn_employees", "Employees trained", _participants(s)["employee_id"].nunique(), detail=note)


def trn_participation(df, emp, p, on):
    m = _missing("training", df, "employee_id")
    if m:
        return _na("trn_participation", "Training participation rate", "pct", m)
    el, why = _eligible_employees(emp, on)
    if el is None:
        return _na("trn_participation", "Training participation rate", "pct", "Not available — " + why)
    s, _ = _scope(df, p, "date")
    tr = _ids(_participants(s)) & el
    rate = len(tr) / len(el) * 100 if el else None
    return _ok("trn_participation", "Training participation rate", rate, "pct",
               f"{len(tr)} of {len(el)} eligible employees ({why})")


def trn_avg_hours(df, emp, p, on):
    m = _missing("training", df, "hours")
    if m:
        return _na("trn_avg_hours", "Avg training hours per employee", "hours", m)
    el, why = _eligible_employees(emp, on)
    if el is None:
        return _na("trn_avg_hours", "Avg training hours per employee", "hours", "Not available — " + why)
    s, _ = _scope(df, p, "date")
    return _ok("trn_avg_hours", "Avg training hours per employee", _div(s["hours"].sum(), len(el)), "hours",
               f"{len(el)} eligible employees ({why})")


def trn_cert_rate(df, p=None):
    m = _missing("training", df, "employee_id", "certification")
    if m:
        return _na("trn_cert_rate", "Certification rate", "pct", m)
    s, _ = _scope(df, p, "date")
    s = s.dropna(subset=["employee_id"])
    s = s[s["certification"].notna()]
    per = s.groupby("employee_id")["certification"].max()
    return _ok("trn_cert_rate", "Certification rate", None if per.empty else per.astype(bool).mean() * 100, "pct",
               f"{int(per.astype(bool).sum())} of {len(per)} employees with a recorded certification requirement")


def trn_effectiveness(df, p=None):
    s, _ = _scope(df, p, "date")
    if {"pre_score", "post_score"} <= set(df.columns):
        d = (s["post_score"] - s["pre_score"]).dropna()
        return _ok("trn_effectiveness", "Training effectiveness", d.mean() if len(d) else None, "pts",
                   f"Average post − pre score across {len(d)} paired records")
    if "assessment_score" in df.columns:
        d = s["assessment_score"].dropna()
        return _ok("trn_effectiveness", "Training effectiveness", d.mean() if len(d) else None, "score",
                   f"Average assessment score across {len(d)} records")
    return _na("trn_effectiveness", "Training effectiveness", "score",
               "Not available — no assessment or pre/post score columns found (attendance is not effectiveness).")


def trn_cost(df, p=None):
    m = _missing("training", df, "cost")
    if m:
        return _na("trn_cost", "Total training cost", "currency", "Not available — training cost data not found.")
    s, _ = _scope(df, p, "date")
    return _ok("trn_cost", "Total training cost", s["cost"].sum() if s["cost"].notna().any() else None, "currency")


def trn_cost_per_employee(df, emp, p, on):
    c = trn_cost(df, p)
    if not c.available:
        return _na("trn_cost_per_employee", "Training cost per employee", "currency", c.reason)
    el, why = _eligible_employees(emp, on)
    if el is None:
        return _na("trn_cost_per_employee", "Training cost per employee", "currency", "Not available — " + why)
    return _ok("trn_cost_per_employee", "Training cost per employee", _div(c.value, len(el)), "currency",
               f"{len(el)} eligible employees ({why})")


def trn_budget_util(df, p, settings):
    c = trn_cost(df, p)
    if not c.available:
        return _na("trn_budget_util", "Budget utilisation", "pct", c.reason)
    s, _ = _scope(df, p, "date")
    if settings.get("training_budget") is not None:
        budget, src = float(settings["training_budget"]), "approved budget entered in Data Explorer"
    elif "budget" in df.columns and s["budget"].notna().any():
        budget, src = s["budget"].sum(), "sum of workbook budget column"
    else:
        return _na("trn_budget_util", "Budget utilisation", "pct",
                   "Not available — no budget column and no approved budget configured.")
    return _ok("trn_budget_util", "Budget utilisation", None if budget == 0 else c.value / budget * 100, "pct", src)


def trn_breakdown(df, col, p=None) -> pd.DataFrame | None:
    if col not in df.columns or "hours" not in df.columns:
        return None
    s, _ = _scope(df, p, "date")
    s = s.assign(_k=s[col].fillna("Not recorded"))
    g = s.groupby("_k").agg(hours=("hours", "sum"))
    if "employee_id" in s.columns:
        g["participants"] = _participants(s).groupby("_k")["employee_id"].nunique()
    g = g.rename_axis(FIELDS["training"][col]["label"]).reset_index().rename(
        columns={"hours": "Training hours", "participants": "Employees trained"})
    return g.sort_values("Training hours", ascending=False)


def trn_effect_by(df, col, p=None) -> pd.DataFrame | None:
    """Mean score improvement (post − pre) or mean assessment score per group. Never based on attendance."""
    if col not in df.columns:
        return None
    s, _ = _scope(df, p, "date")
    if {"pre_score", "post_score"} <= set(df.columns):
        v, name = s["post_score"] - s["pre_score"], "Avg improvement (pts)"
    elif "assessment_score" in df.columns:
        v, name = s["assessment_score"], "Avg assessment score"
    else:
        return None
    g = pd.DataFrame({"k": s[col].fillna("Not recorded"), "v": v}).dropna().groupby("k")["v"].agg(["mean", "count"])
    g = g.rename_axis(FIELDS["training"][col]["label"]).reset_index().rename(columns={"mean": name, "count": "Records"})
    return g if len(g) else None


def trn_completion_mix(df, p=None) -> pd.DataFrame | None:
    if "completion_status_norm" not in df.columns:
        return None
    s, _ = _scope(df, p, "date")
    return s["completion_status_norm"].fillna("Not recorded").value_counts().rename_axis("Status").reset_index(name="Records")


def trn_monthly(df, p=None) -> pd.DataFrame | None:
    if "date" not in df.columns:
        return None
    s, _ = _scope(df, p, "date")
    s = s.dropna(subset=["date"])
    if s.empty:
        return None
    g = s.groupby(s["date"].dt.to_period("M"))
    t = pd.DataFrame(index=sorted(g.groups))
    if "hours" in s.columns:
        t["Training hours"] = g["hours"].sum()
    if "employee_id" in s.columns:
        t["Employees trained"] = _participants(s).groupby(s["date"].dt.to_period("M"))["employee_id"].nunique()
    t.index = t.index.to_timestamp()
    return t.rename_axis("Month").reset_index()


# ============================================================== performance
def _pe(df):  # one row per employee when ids exist
    return df.dropna(subset=["employee_id"]).drop_duplicates("employee_id") if "employee_id" in df.columns else df


def pms_eligible(df):
    m = _missing("performance", df, "employee_id")
    if m:
        return _na("pms_eligible", "Performance-eligible employees", "count", m)
    return _ok("pms_eligible", "Performance-eligible employees", df["employee_id"].nunique(),
               detail="Distinct employees listed in the performance sheet/cycle")


def pms_completed(df):
    m = _missing("performance", df, "employee_id", "review_status")
    if m:
        return _na("pms_completed", "Completed reviews", "count", m)
    return _ok("pms_completed", "Completed reviews", df.loc[df["review_status_norm"] == "completed", "employee_id"].nunique())


def pms_completion(df):
    m = _missing("performance", df, "employee_id", "review_status")
    if m:
        return _na("pms_completion", "PMS completion rate", "pct", m)
    e, c = df["employee_id"].nunique(), pms_completed(df).value
    return _ok("pms_completion", "PMS completion rate", None if not e else c / e * 100, "pct", f"{c:.0f} of {e} eligible")


def pms_avg_rating(df):
    m = _missing("performance", df, "rating")
    if m:
        return _na("pms_avg_rating", "Average performance rating", "score", m)
    r = df["rating"].dropna()
    return _ok("pms_avg_rating", "Average performance rating", r.mean() if len(r) else None, "score", f"{len(r)} valid ratings")


def _hp_mask(df, settings):
    if "high_performer_flag" in df.columns:
        return df["high_performer_flag"].fillna(False).astype(bool), "formal high-performer flag in workbook"
    thr = settings.get("high_perf_threshold")
    if "rating" in df.columns and thr is not None:
        return (df["rating"] >= float(thr)).fillna(False), f"rating ≥ {thr} (approved threshold entered in Data Explorer)"
    return None, ""


def pms_high_performers(df, settings):
    mask, src = _hp_mask(df, settings) if "employee_id" in df.columns else (None, "")
    if mask is None:
        return _na("pms_high_performers", "High performers", "count",
                   "Not available — no high-performer flag column and no approved rating threshold configured.")
    return _ok("pms_high_performers", "High performers", df.loc[mask, "employee_id"].nunique(), detail=src)


def pms_high_pct(df, settings):
    h = pms_high_performers(df, settings)
    if not h.available:
        return _na("pms_high_pct", "High-performer share", "pct", h.reason)
    e = df["employee_id"].nunique()
    return _ok("pms_high_pct", "High-performer share", None if not e else h.value / e * 100, "pct", h.detail)


def pms_goal_rate(df):
    m = _missing("performance", df, "goals_total", "goals_achieved")
    if m:
        return _na("pms_goal_rate", "Goal achievement rate", "pct", m)
    v = df.dropna(subset=["goals_total", "goals_achieved"])
    v = v[(v["goals_total"] > 0) & (v["goals_achieved"] <= v["goals_total"])]
    tot = v["goals_total"].sum()
    rate = v["goals_achieved"].sum() / tot * 100 if tot else None
    return _ok("pms_goal_rate", "Goal achievement rate", rate, "pct", f"{len(v)} employees with assessable goals")


def pms_idp(df):
    m = _missing("performance", df, "employee_id", "idp")
    if m:
        return _na("pms_idp", "IDPs created", "count", m)
    if df["idp"].notna().mean() >= 0.5:
        n = df.loc[df["idp"].fillna(False).astype(bool), "employee_id"].nunique()
        e = df["employee_id"].nunique()
        return _ok("pms_idp", "IDPs created", n, detail=f"{n / e * 100:.1f}% of {e} eligible employees" if e else "")
    n = df["idp_raw"].sum()
    return _ok("pms_idp", "IDPs created", n if pd.notna(n) else None, detail="Sum of IDP count column")


def pms_rating_dist(df) -> pd.DataFrame | None:
    if "rating" not in df.columns or df["rating"].dropna().empty:
        return None
    t = _pe(df)["rating"].dropna().value_counts().sort_index().rename_axis("Rating").reset_index(name="Employees")
    t["Share %"] = t["Employees"] / t["Employees"].sum() * 100
    return t


def pms_by(df, col) -> pd.DataFrame | None:
    if col not in df.columns or "rating" not in df.columns:
        return None
    g = _pe(df).assign(_k=lambda d: d[col].fillna("Not recorded")).groupby("_k")["rating"].agg(["mean", "count"])
    g = g.rename_axis(FIELDS["performance"][col]["label"]).reset_index()
    return g.rename(columns={"mean": "Average rating", "count": "Rated employees"})


def pms_trend(df) -> pd.DataFrame | None:
    if "rating" not in df.columns:
        return None
    if "cycle" in df.columns:
        g = df.groupby("cycle")["rating"].agg(["mean", "count"])
    elif "review_date" in df.columns:
        d = df.dropna(subset=["review_date"])
        g = d.groupby(d["review_date"].dt.to_period("Q").astype(str))["rating"].agg(["mean", "count"])
    else:
        return None
    g = g.sort_index().rename_axis("Cycle").reset_index().rename(columns={"mean": "Average rating", "count": "Ratings"})
    return g if len(g) else None


def pms_status_counts(df, col=None) -> pd.DataFrame | None:
    if "review_status_norm" not in df.columns:
        return None
    d = _pe(df)
    if col and col in d.columns:
        t = d.assign(g=d[col].fillna("Not recorded"), s=d["review_status_norm"].fillna("Not recorded"))
        return t.groupby(["g", "s"]).size().rename("Employees").reset_index().rename(
            columns={"g": FIELDS["performance"][col]["label"], "s": "Review status"})
    return d["review_status_norm"].fillna("Not recorded").value_counts().rename_axis("Review status").reset_index(name="Employees")


# ============================================================ relations
def rel_cases(df, p=None):
    m = _missing("relations", df, "case_id")
    if m:
        return _na("rel_cases", "Cases raised", "count", m)
    s, note = _scope(df, p, "open_date")
    return _ok("rel_cases", "Cases raised", s["case_id"].nunique(), detail=note)


def _case_count(df, status, key, label, p):
    m = _missing("relations", df, "case_id", "status")
    if m:
        return _na(key, label, "count", m)
    s, _ = _scope(df, p, "open_date")
    return _ok(key, label, s.loc[s["status_norm"] == status, "case_id"].nunique())


def rel_open(df, p=None):
    return _case_count(df, "open", "rel_open", "Open cases", p)


def rel_closed(df, p=None):
    return _case_count(df, "closed", "rel_closed", "Closed cases", p)


def rel_pending(df, p=None):
    return _case_count(df, "pending", "rel_pending", "Pending cases", p)


def rel_resolution_rate(df, p=None):
    m = _missing("relations", df, "case_id", "status")
    if m:
        return _na("rel_resolution_rate", "Case resolution rate", "pct", m)
    s, _ = _scope(df, p, "open_date")
    n = s["case_id"].nunique()
    c = s.loc[s["status_norm"] == "closed", "case_id"].nunique()
    return _ok("rel_resolution_rate", "Case resolution rate", None if n == 0 else c / n * 100, "pct",
               f"{c} of {n} cases opened in period are closed")


def rel_resolution_days(df, p=None):
    m = _missing("relations", df, "case_id", "open_date", "close_date")
    if m:
        return _na("rel_resolution_days", "Average resolution time", "days", m)
    s, _ = _scope(df, p, "open_date")
    d = (s["close_date"] - s["open_date"]).dt.days
    d = d[d >= 0]
    return _ok("rel_resolution_days", "Average resolution time", d.mean() if len(d) else None, "days", f"{len(d)} closed cases")


def rel_engagement(df):
    m = _missing("relations", df, "engagement_score")
    if m:
        return _na("rel_engagement", "Average engagement score", "score", m)
    v = df["engagement_score"].dropna()
    return _ok("rel_engagement", "Average engagement score", v.mean() if len(v) else None, "score", f"{len(v)} responses")


def rel_response_rate(df):
    m = _missing("relations", df, "invited", "responded")
    if m:
        return _na("rel_response_rate", "Survey response rate", "pct", m)
    v = df.dropna(subset=["invited", "responded"])
    v = v[(v["invited"] > 0) & (v["responded"] <= v["invited"])]
    return _ok("rel_response_rate", "Survey response rate", None if v.empty else v["responded"].sum() / v["invited"].sum() * 100, "pct")


def rel_categories(df, col="case_category", p=None) -> pd.DataFrame | None:
    if col not in df.columns or "case_id" not in df.columns:
        return None
    s, _ = _scope(df, p, "open_date")
    g = s.assign(_k=s[col].fillna("Not recorded")).groupby("_k")["case_id"].nunique()
    return g.rename_axis("Category").reset_index(name="Cases").sort_values("Cases", ascending=False)


def rel_monthly(df, p=None) -> pd.DataFrame | None:
    if "open_date" not in df.columns or "case_id" not in df.columns:
        return None
    s, _ = _scope(df, p, "open_date")
    s = s.dropna(subset=["open_date"])
    if s.empty:
        return None
    t = s.groupby(s["open_date"].dt.to_period("M"))["case_id"].nunique().rename("Cases")
    t.index = t.index.to_timestamp()
    return t.rename_axis("Month").reset_index()


def small_group_filter(t: pd.DataFrame | None, count_col: str, min_n: int = MIN_GROUP_SIZE) -> tuple[pd.DataFrame | None, int]:
    """Suppress groups below the minimum size. Returns (table, number suppressed)."""
    if t is None or count_col not in t.columns:
        return t, 0
    keep = t[count_col] >= min_n
    return t[keep], int((~keep).sum())
