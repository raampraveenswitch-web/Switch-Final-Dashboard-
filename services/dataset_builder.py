"""Turns raw sheets into a WorkbookModel: profile -> classify -> map -> clean -> combine."""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from config import DEFAULT_SETTINGS, FIELDS
from services.column_mapping import classify_sheet, manual_classification
from services.data_cleaning import clean_frame
from services.models import DQIssue, SheetData, WorkbookModel
from services.workbook_inspector import find_relationships, profile_sheet


def build_model(sheets: dict[str, SheetData], source_name: str, fingerprint: str,
                settings: dict | None = None, overrides: dict | None = None) -> WorkbookModel:
    settings = {**DEFAULT_SETTINGS, **(settings or {})}
    overrides = overrides or {}
    profiles = [profile_sheet(sd) for sd in sheets.values()]
    classifications, issues, warnings = {}, [], []
    parts: dict[str, list[pd.DataFrame]] = {}
    used: dict[str, list[str]] = {}
    for name, sd in sheets.items():
        cols = list(sd.df.columns)
        if name in overrides:
            o = overrides[name]
            cl = manual_classification(cols, o.get("dataset"), o.get("mapping", {}))
        else:
            cl = classify_sheet(cols, sd.empty)
        classifications[name] = cl
        warnings += [f"[{name}] {w}" for w in cl.warnings if "empty" not in w.lower()]
        if sd.empty or cl.dataset is None:
            continue
        frame, iss = clean_frame(sd.df, cl.mapping, cl.dataset, name, settings)
        issues += iss
        parts.setdefault(cl.dataset, []).append(frame)
        used.setdefault(cl.dataset, []).append(name)
    datasets = {}
    for ds, frames in parts.items():
        datasets[ds] = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]
        if len(frames) > 1:
            warnings.append(f"{len(frames)} sheets ({', '.join(used[ds])}) were combined as '{ds}' data. "
                            "They are assumed to share the same record grain; verify in Data Explorer.")
            cols = [set(f.columns) - {"source_sheet"} for f in frames]
            if any(c != cols[0] for c in cols):
                warnings.append(f"Sheets combined as '{ds}' map different columns; metrics needing a "
                                "missing column will ignore rows from sheets that lack it.")
    return WorkbookModel(source_name, fingerprint, datetime.now(), sheets, profiles, classifications,
                         datasets, used, issues, find_relationships(datasets), warnings)


def mapped_field_labels(dataset: str, mapping: dict[str, str]) -> dict[str, str]:
    return {FIELDS[dataset][f]["label"]: c for f, c in mapping.items()}
