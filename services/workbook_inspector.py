"""Workbook profiling: types, missing values, duplicates, date ranges, relationships."""
from __future__ import annotations

import warnings

import pandas as pd
from pandas.api.types import is_datetime64_any_dtype, is_numeric_dtype

from config import DAYFIRST, FIELDS
from services.column_mapping import norm
from services.models import ColumnProfile, SheetData, SheetProfile

_ID_HINTS = ("id", "code", "number", "no", "empid", "ecode")


def _looks_like_id_name(name: str) -> bool:
    n = norm(name)
    return n.endswith(_ID_HINTS) or n.startswith(("emp", "req")) and any(h in n for h in _ID_HINTS)


def _try_dates(s: pd.Series) -> pd.Series:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            return pd.to_datetime(s, errors="coerce", dayfirst=DAYFIRST, format="mixed")
        except (TypeError, ValueError):
            return pd.to_datetime(s, errors="coerce", dayfirst=DAYFIRST)


def infer_type(name: str, s: pd.Series) -> str:
    nn = s.dropna()
    if nn.empty:
        return "empty"
    if is_datetime64_any_dtype(s):
        return "date"
    if is_numeric_dtype(s):
        return "identifier" if _looks_like_id_name(name) else "number"
    as_str = nn.astype(str)
    if as_str.str.contains(r"[-/.:]", regex=True).mean() > 0.8 and len(nn) >= 1:
        if _try_dates(nn).notna().mean() >= 0.8:
            return "date"
    if _looks_like_id_name(name):
        return "identifier"
    uniq = nn.nunique()
    if uniq <= max(20, 0.05 * len(nn)):
        return "category"
    return "identifier" if uniq / len(nn) > 0.9 and as_str.str.len().max() < 25 else "text"


def profile_sheet(sd: SheetData) -> SheetProfile:
    if sd.empty:
        warns = ["Sheet has no data rows."]
        if sd.df.attrs.get("read_error"):
            warns.append("Sheet could not be read.")
        return SheetProfile(sd.name, 0, 0, 0, True, sd.header_row, [], warns)
    df = sd.df
    cols = []
    warns = []
    for c in df.columns:
        s = df[c]
        t = infer_type(c, s)
        lo = hi = ""
        if t == "date":
            d = s if is_datetime64_any_dtype(s) else _try_dates(s.dropna())
            if d.notna().any():
                lo, hi = str(d.min().date()), str(d.max().date())
        elif t == "number":
            lo, hi = str(s.min()), str(s.max())
        cols.append(ColumnProfile(c, t, int(s.notna().sum()), int(s.isna().sum()), int(s.nunique()), lo, hi))
        if s.isna().mean() > 0.5:
            warns.append(f"Column '{c}' is more than 50% empty.")
    dups = int(df.duplicated().sum())
    if dups:
        warns.append(f"{dups} exact duplicate row(s).")
    if sd.header_row:
        warns.append(f"Header detected on row {sd.header_row + 1}; rows above were treated as titles.")
    return SheetProfile(sd.name, len(df), df.shape[1], dups, False, sd.header_row, cols, warns)


def find_relationships(datasets: dict[str, pd.DataFrame]) -> list[dict]:
    """Report identifier overlap between datasets. Datasets are NEVER row-joined; only distinct-ID
    sets are compared, so no relationship can multiply rows."""
    out = []
    names = [n for n, d in datasets.items() if "employee_id" in d.columns]
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            ia = set(datasets[a]["employee_id"].dropna())
            ib = set(datasets[b]["employee_id"].dropna())
            if not ia or not ib:
                continue
            both = len(ia & ib)
            out.append({"from": a, "to": b, "key": "employee_id", "ids_in_from": len(ia),
                        "ids_in_to": len(ib), "ids_in_both": both,
                        "share_of_smaller_matched_pct": round(100 * both / min(len(ia), len(ib)), 1)})
    return out


def has_field(ds: str, field: str) -> bool:
    return field in FIELDS.get(ds, {})
