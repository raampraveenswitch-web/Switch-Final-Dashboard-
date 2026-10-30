"""Type cleaning, status normalisation and validation. Never drops rows silently:
every exclusion is reported as a DQIssue."""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from pandas.api.types import is_datetime64_any_dtype, is_numeric_dtype

from config import DAYFIRST, FIELDS, STATUS_RULES
from services.models import DQIssue

_TRUE = {"yes", "y", "true", "1", "completed", "created", "done", "available"}
_FALSE = {"no", "n", "false", "0", "pending", "not created", "not done", "na"}
_NONNEG = {"hours", "cost", "budget", "goals_total", "goals_achieved", "invited", "responded"}


def to_datetime(s: pd.Series) -> pd.Series:
    if is_datetime64_any_dtype(s):
        return s
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            return pd.to_datetime(s, errors="coerce", dayfirst=DAYFIRST, format="mixed")
        except (TypeError, ValueError):
            return pd.to_datetime(s, errors="coerce", dayfirst=DAYFIRST)


def to_number(s: pd.Series) -> pd.Series:
    if is_numeric_dtype(s):
        return pd.to_numeric(s, errors="coerce")
    t = (s.astype("string").str.replace(r"[₹$€£,\s]", "", regex=True)
         .str.replace(r"^\((.*)\)$", r"-\1", regex=True))
    return pd.to_numeric(t, errors="coerce")


def to_flag(s: pd.Series) -> pd.Series:
    t = s.astype("string").str.strip().str.lower()
    out = pd.Series(pd.NA, index=s.index, dtype="boolean")
    out[t.isin(_TRUE)] = True
    out[t.isin(_FALSE)] = False
    return out


def normalise_status(value, rules: dict[str, list[str]]) -> str | None:
    if value is None or (isinstance(value, float) and np.isnan(value)) or pd.isna(value):
        return None
    t = str(value).strip().lower()
    if not t:
        return None
    for label, keys in rules.items():
        if any(k in t for k in keys):
            return label
    return "unclassified"


def clean_frame(raw: pd.DataFrame, mapping: dict[str, str], dataset: str, sheet: str,
                settings: dict, today: pd.Timestamp | None = None) -> tuple[pd.DataFrame, list[DQIssue]]:
    """Return a canonical-column frame for one sheet plus the issues found."""
    today = today or pd.Timestamp.today().normalize()
    issues: list[DQIssue] = []
    work = raw
    if settings.get("dedupe_exact_rows", True):
        dup = int(work.duplicated().sum())
        if dup:
            issues.append(DQIssue(sheet, "(all)", dup, f"{dup} exact duplicate row(s) removed "
                                  "(rule: dedupe_exact_rows). Disable in Data Explorer if rows are legitimately identical.",
                                  "warning"))
            work = work.drop_duplicates()
    out = pd.DataFrame(index=work.index)
    for fld, col in mapping.items():
        if col not in work.columns:
            continue
        spec = FIELDS[dataset][fld]
        s, kind = work[col], spec["kind"]
        label = spec["label"]
        if kind == "id":
            v = s.astype("string").str.strip()
            v = v.mask(v.isin(["", "nan", "None", "<NA>"]))
            if is_numeric_dtype(s):
                v = v.str.replace(r"\.0$", "", regex=True)
            miss = int(v.isna().sum())
            if miss:
                issues.append(DQIssue(sheet, label, miss, f"{miss} record(s) have no {label}; they are "
                                      "excluded from distinct-ID counts.", "warning"))
            out[fld] = v
        elif kind == "date":
            d = to_datetime(s)
            bad = int((s.notna() & d.isna()).sum())
            if bad:
                issues.append(DQIssue(sheet, label, bad, f"{bad} value(s) are not valid dates and are "
                                      "excluded from date-based metrics.", "warning"))
            fut = int((d > today).sum())
            if fut and fld not in ("exit_date",):
                issues.append(DQIssue(sheet, label, fut, f"{fut} date(s) are in the future.", "info"))
            out[fld] = d
        elif kind == "number":
            n = to_number(s)
            bad = int((s.notna() & n.isna()).sum())
            if bad:
                issues.append(DQIssue(sheet, label, bad, f"{bad} non-numeric value(s) ignored.", "warning"))
            if fld in _NONNEG:
                neg = int((n < 0).sum())
                if neg:
                    issues.append(DQIssue(sheet, label, neg, f"{neg} negative value(s) excluded.", "warning"))
                    n = n.mask(n < 0)
            cap = settings.get("rating_scale_max")
            if fld == "rating" and cap is not None:
                over = int(((n > cap) | (n < 0)).sum())
                if over:
                    issues.append(DQIssue(sheet, label, over, f"{over} rating(s) outside 0–{cap} excluded.", "warning"))
                    n = n.mask((n > cap) | (n < 0))
            out[fld] = n
        elif kind == "flag":
            f = to_flag(s)
            unparsed = int((s.notna() & f.isna()).sum())
            if unparsed:
                issues.append(DQIssue(sheet, label, unparsed, f"{unparsed} value(s) are not yes/no style flags "
                                      "(kept as unknown).", "info"))
            out[fld] = f
            out[fld + "_raw"] = pd.to_numeric(s, errors="coerce")
        elif kind == "status":
            txt = s.astype("string").str.strip()
            out[fld] = txt
            rules = STATUS_RULES.get((dataset, fld), {})
            out[fld + "_norm"] = txt.map(lambda v: normalise_status(v, rules))
            unc = int((out[fld + "_norm"] == "unclassified").sum())
            if unc:
                issues.append(DQIssue(sheet, label, unc, f"{unc} status value(s) did not match any rule "
                                      "and are 'unclassified'. See the status audit in Data Explorer.", "warning"))
        else:
            v = s.astype("string").str.strip()
            out[fld] = v.mask(v.isin(["", "nan", "None", "<NA>"]))
    # cross-field checks
    if dataset == "recruitment" and {"open_date", "filled_date"} <= set(out.columns):
        neg = int((out["filled_date"] < out["open_date"]).sum())
        if neg:
            issues.append(DQIssue(sheet, "Filled date", neg, f"{neg} record(s) have a filled date before the "
                                  "open date; excluded from time-to-hire.", "warning"))
    if dataset == "employee" and {"hire_date", "exit_date"} <= set(out.columns):
        neg = int((out["exit_date"] < out["hire_date"]).sum())
        if neg:
            issues.append(DQIssue(sheet, "Date of exit", neg, f"{neg} record(s) exit before joining; "
                                  "excluded from tenure.", "warning"))
    if dataset == "employee" and "employee_id" in out.columns:
        d = int(out["employee_id"].dropna().duplicated().sum())
        if d:
            issues.append(DQIssue(sheet, "Employee ID", d, f"{d} repeated Employee ID(s). Metrics count "
                                  "distinct IDs; check for conflicting records.", "warning"))
    out["source_sheet"] = sheet
    return out, issues
