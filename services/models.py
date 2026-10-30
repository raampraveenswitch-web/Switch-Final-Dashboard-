"""Plain data containers shared across services."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd


class WorkbookError(Exception):
    """Raised when a workbook cannot be used. Messages never contain cell values."""


@dataclass
class SheetData:
    name: str
    df: pd.DataFrame
    header_row: int | None
    empty: bool
    original_columns: list[str]


@dataclass
class ColumnProfile:
    name: str
    inferred_type: str
    non_null: int
    missing: int
    unique: int
    min_value: str = ""
    max_value: str = ""


@dataclass
class SheetProfile:
    name: str
    rows: int
    columns: int
    duplicates: int
    empty: bool
    header_row: int | None
    column_profiles: list[ColumnProfile] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class DQIssue:
    sheet: str
    field: str
    count: int
    message: str
    severity: str = "warning"      # info | warning | error


@dataclass
class Classification:
    dataset: str | None
    hits: int
    confidence: str                 # high | low | none | manual | ignored
    mapping: dict[str, str]
    warnings: list[str] = field(default_factory=list)
    source: str = "auto"


@dataclass
class WorkbookModel:
    source_name: str
    fingerprint: str
    loaded_at: datetime
    sheets: dict[str, SheetData]
    profiles: list[SheetProfile]
    classifications: dict[str, Classification]
    datasets: dict[str, pd.DataFrame]
    dataset_sheets: dict[str, list[str]]
    issues: list[DQIssue]
    relationships: list[dict]
    warnings: list[str]
