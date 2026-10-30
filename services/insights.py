"""Rule-based insights. Each insight carries the rule that produced it; none are hard-coded text about
the workforce. Targets are never invented: a missing target is reported as 'not configured'."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from config import MIN_GROUP_SIZE
from services import metrics as M


@dataclass(frozen=True)
class Insight:
    text: str
    rule: str
    kind: str = "insight"            # insight | attention | action
    action: str = ""


AGEING_DAYS = 90      # descriptive cut for "long-open" requisitions (shown in the rule text; not a target)


def recruitment_insights(r, order, p=None, as_of=None) -> list[Insight]:
    out = []
    if r is not None and p is not None:
        s = M.rec_source_share(r, p)
        if s is not None and len(s):
            top = s.iloc[0]
            out.append(Insight(f"{top['Source']} is the leading source of hire ({top['Share %']:.0f}% of "
                               f"{s['Hires'].sum():.0f} hires in the period).",
                               "Largest share of filled requisitions with a recorded source in the period."))
        tth = M.rec_time_to_hire(r, p)
        if tth.available:
            out.append(Insight(f"Average time to hire is {tth.value:.0f} days in the period.",
                               "Mean days from requisition open to filled, for requisitions filled in the period."))
    if r is not None and as_of is not None:
        o = M.rec_open_positions(r, as_of)
        if o is not None and len(o):
            n = int((o["days_open"] > AGEING_DAYS).sum())
            if n:
                out.append(Insight(f"{n} of {len(o)} open requisitions have been open for more than {AGEING_DAYS} days.",
                                   f"Open requisitions with days open > {AGEING_DAYS} as of {as_of:%d %b %Y}.", "attention",
                                   "Prioritise, re-scope or close long-open requisitions with hiring managers."))
    t = M.rec_monthly(r) if r is not None else None
    if t is not None and "Positions filled" in t and len(t) >= 2:
        a, b = t.iloc[-2], t.iloc[-1]
        if (b["Month"] - a["Month"]).days <= 31 and pd.notna(a["Positions filled"]) and pd.notna(b["Positions filled"]):
            d = b["Positions filled"] - a["Positions filled"]
            word = "rose" if d > 0 else "fell" if d < 0 else "was unchanged"
            out.append(Insight(f"Positions filled {word} from {a['Positions filled']:.0f} in {a['Month']:%b %Y} to "
                               f"{b['Positions filled']:.0f} in {b['Month']:%b %Y}.",
                               "Compare the last two consecutive calendar months in the data."))
    f, _ = M.rec_funnel(r, order) if r is not None else (None, "")
    if f is not None:
        c = f.dropna(subset=["Conversion to next %"])
        if len(c) >= 2:
            lo = c.loc[c["Conversion to next %"].idxmin()]
            out.append(Insight(f"Lowest funnel conversion is after '{lo['Stage']}' ({lo['Conversion to next %']:.1f}%).",
                               "Minimum stage-to-next-stage conversion across configured stages.", "attention",
                               "Review this stage's process with Talent Acquisition."))
    return out


def employee_insights(e, p) -> list[Insight]:
    out = []
    t = M.emp_attrition_by(e, "department", p) if e is not None and "department" in e.columns else None
    t, _ = M.small_group_filter(t, "Average headcount")
    if t is not None and t["Attrition rate %"].notna().any():
        hi = t.loc[t["Attrition rate %"].idxmax()]
        out.append(Insight(f"Highest aggregate attrition: {hi['Department']} at {hi['Attrition rate %']:.1f}% "
                           f"({hi['Exits']:.0f} exits).",
                           f"Highest department attrition rate among departments with average headcount ≥ {MIN_GROUP_SIZE}.",
                           "attention", "Discuss drivers with leadership; correlation does not imply cause."))
    return out


def training_insights(t, settings) -> list[Insight]:
    out = []
    if t is not None and "hours" in t.columns and not M.trn_effectiveness(t).available:
        out.append(Insight("Training hours are recorded but no assessment/pre-post scores exist, so effectiveness "
                           "cannot be measured.", "Hours present AND no score columns mapped.", "attention",
                           "Agree an evaluation measure (e.g. post-training assessment) with L&D."))
    return out


def performance_insights(pf, settings) -> list[Insight]:
    out = []
    c = M.pms_completion(pf) if pf is not None else None
    if c is not None and c.available:
        tgt = settings.get("pms_completion_target")
        if tgt is None:
            out.append(Insight(f"PMS completion is {c.value:.1f}%. No completion target is configured.",
                               "Target comparison requires an approved target (Data Explorer → Business definitions).",
                               "attention", "Confirm the approved PMS completion target."))
        elif c.value < float(tgt):
            out.append(Insight(f"PMS completion ({c.value:.1f}%) is below the configured target ({float(tgt):.1f}%).",
                               "Completion rate < configured target.", "attention", "Follow up on pending reviews by function."))
        else:
            out.append(Insight(f"PMS completion ({c.value:.1f}%) meets the configured target ({float(tgt):.1f}%).",
                               "Completion rate ≥ configured target."))
    return out


def data_quality_insights(model) -> list[Insight]:
    out = []
    n = sum(i.count for i in model.issues if i.severity == "warning")
    if n:
        out.append(Insight(f"{n} record-level data-quality warnings were found across the workbook.",
                           "Sum of warning counts in the data-quality log.", "attention",
                           "Review the Data Explorer → Data quality section."))
    return out


def relations_insights(c, p) -> list[Insight]:
    out = []
    if c is None:
        return out
    t, _ = M.small_group_filter(M.rel_categories(c, "case_category", p), "Cases")
    if t is not None and len(t) and t["Cases"].sum():
        top = t.loc[t["Cases"].idxmax()]
        out.append(Insight(f"'{top['Category']}' is the most common case category "
                           f"({top['Cases'] / t['Cases'].sum() * 100:.0f}% of cases in groups shown).",
                           f"Largest issue category among groups with ≥ {MIN_GROUP_SIZE} cases."))
    rr = M.rel_resolution_rate(c, p)
    pend = M.rel_pending(c, p)
    if rr.available:
        out.append(Insight(f"Case resolution rate for cases opened in the period is {rr.value:.1f}% ({rr.detail}).",
                           "Closed cases ÷ cases opened in the period."))
    if pend.available and pend.value:
        out.append(Insight(f"{pend.value:.0f} case(s) opened in the period are pending.",
                           "Count of cases with status 'pending' opened in the period.", "attention",
                           "Review pending cases with the ER team and agree closure dates."))
    return out


def turnover_insights(e, p) -> list[Insight]:
    out = list(employee_insights(e, p)) if e is not None and p is not None else []
    if e is None or p is None:
        return out
    r, _ = M.small_group_filter(M.emp_exit_reasons(e, p), "Exits")
    if r is not None and len(r):
        top = r.iloc[0]
        out.append(Insight(f"Most frequent exit reason: '{top['Exit reason']}' ({top['Exits']:.0f} exits).",
                           f"Largest exit-reason group with ≥ {MIN_GROUP_SIZE} exits in the period.", "attention",
                           "Use exit-interview themes to plan retention actions."))
    mix = M.emp_exit_mix(e, p)
    if mix is not None and "voluntary" in set(mix["Category"]):
        v = mix.loc[mix["Category"] == "voluntary", "Exits"].sum() / mix["Exits"].sum() * 100
        out.append(Insight(f"{v:.0f}% of exits in the period were voluntary.",
                           "Voluntary exits ÷ all exits with an exit record in the period."))
    return out
