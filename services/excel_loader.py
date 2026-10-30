"""Safe, read-only Excel ingestion. Every worksheet is read; macros are never executed."""
from __future__ import annotations

import hashlib
import io
import warnings
from pathlib import Path

import pandas as pd

from config import ALLOWED_EXTENSIONS, HEADER_SCAN_ROWS
from services.models import SheetData, WorkbookError


def fingerprint_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _unique_names(values: list) -> list[str]:
    seen: dict[str, int] = {}
    names = []
    for i, v in enumerate(values):
        base = str(v).strip() if v is not None and not (isinstance(v, float) and pd.isna(v)) else ""
        base = " ".join(base.split()) or f"Unnamed_{i + 1}"
        n = seen.get(base, 0) + 1
        seen[base] = n
        names.append(base if n == 1 else f"{base} ({n})")
    return names


def detect_header_row(raw: pd.DataFrame) -> int:
    """Find the header row, skipping title/blank rows above it.

    A header row is the first row in the scan window that is (nearly) as wide as the widest row,
    mostly text, and has distinct labels.
    """
    window = raw.head(HEADER_SCAN_ROWS)
    widths = window.notna().sum(axis=1)
    max_width = int(widths.max()) if len(widths) else 0
    for i in range(len(window)):
        row = window.iloc[i].dropna()
        if len(row) == 0 or len(row) < max(1, 0.6 * max_width):
            continue
        text_share = sum(isinstance(v, str) for v in row) / len(row)
        distinct = row.astype(str).nunique() / len(row)
        if text_share >= 0.6 and distinct >= 0.9:
            return i
    return 0


def _parse_sheet(xl: pd.ExcelFile, name: str) -> SheetData:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        raw = xl.parse(name, header=None, dtype=object)
    raw = raw.dropna(how="all").dropna(axis=1, how="all").reset_index(drop=True)
    if raw.empty:
        return SheetData(name, pd.DataFrame(), None, True, [])
    h = detect_header_row(raw)
    cols = _unique_names(list(raw.iloc[h]))
    body = raw.iloc[h + 1:].copy()
    body.columns = cols
    body = body.dropna(how="all").reset_index(drop=True).infer_objects()
    return SheetData(name, body, h, body.empty, cols)


def read_workbook(data: bytes, filename: str) -> tuple[dict[str, SheetData], str]:
    """Return ({sheet name: SheetData}, content fingerprint). Raises WorkbookError on failure."""
    if Path(filename).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise WorkbookError(f"Unsupported file type. Use one of: {', '.join(ALLOWED_EXTENSIONS)}.")
    if not data:
        raise WorkbookError("The file is empty.")
    try:
        xl = pd.ExcelFile(io.BytesIO(data), engine="openpyxl")
        names = list(xl.sheet_names)
    except Exception as exc:  # corrupt, password-protected, wrong format ...
        raise WorkbookError(f"The workbook could not be opened ({type(exc).__name__}).") from None
    if not names:
        raise WorkbookError("The workbook contains no worksheets.")
    sheets = {}
    for n in names:
        try:
            sheets[n] = _parse_sheet(xl, n)
        except Exception as exc:
            sheets[n] = SheetData(n, pd.DataFrame(), None, True, [])
            sheets[n].original_columns = []
            sheets[n].df.attrs["read_error"] = type(exc).__name__
    return sheets, fingerprint_bytes(data)


def read_workbook_path(path: str | Path) -> tuple[dict[str, SheetData], str, str]:
    p = Path(path).expanduser()
    if not p.is_file():
        raise WorkbookError("The file path does not exist or is not a file.")
    data = p.read_bytes()          # read fully, then release the file handle immediately
    sheets, fp = read_workbook(data, p.name)
    return sheets, fp, p.name
