"""Alias-based column mapping and sheet classification (configurable, auditable)."""
from __future__ import annotations

import re

from config import FIELDS, SIGNATURES
from services.models import Classification

EXACT_BASE, CONTAINS_BASE = 100, 50


def norm(name: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def match_columns(columns: list[str], dataset: str) -> tuple[dict[str, str], list[str]]:
    """Map canonical fields of ``dataset`` to workbook columns. Returns (mapping, ambiguity warnings)."""
    cands: list[tuple[int, str, str]] = []
    for fld, spec in FIELDS[dataset].items():
        for col in columns:
            n = norm(col)
            best = 0
            for rank, alias in enumerate(spec["aliases"]):
                a = norm(alias)
                if n == a:
                    best = max(best, EXACT_BASE - rank)
                elif len(a) >= 6 and a in n:
                    best = max(best, CONTAINS_BASE - rank)
            if best:
                cands.append((best, fld, col))
    cands.sort(key=lambda t: -t[0])
    mapping: dict[str, str] = {}
    used: set[str] = set()
    for _, fld, col in cands:
        if fld not in mapping and col not in used:
            mapping[fld] = col
            used.add(col)
    warns = []
    for fld in mapping:
        top = max(s for s, f, _ in cands if f == fld)
        tied = sorted({c for s, f, c in cands if f == fld and s >= top - 0 and (top < 60 or s >= 60)})
        exact = sorted({c for s, f, c in cands if f == fld and s >= 60})
        if len(exact) > 1 or (top < 60 and len(tied) > 1):
            warns.append(f"Ambiguous mapping for '{FIELDS[dataset][fld]['label']}': candidates "
                         f"{', '.join(exact or tied)}. Using '{mapping[fld]}'. Review in Data Explorer.")
    return mapping, warns


def classify_sheet(columns: list[str], empty: bool = False) -> Classification:
    if empty or not columns:
        return Classification(None, 0, "none", {}, ["Sheet is empty."])
    scored = []
    for ds in FIELDS:
        mapping, warns = match_columns(columns, ds)
        hits = sum(1 for f in SIGNATURES[ds] if f in mapping)
        scored.append((hits, len(mapping), ds, mapping, warns))
    scored.sort(key=lambda t: (-t[0], -t[1]))
    hits, _, ds, mapping, warns = scored[0]
    if hits == 0:
        return Classification(None, 0, "none", {}, ["No recognised HR columns; sheet kept for review only."])
    warns = list(warns)
    if len(scored) > 1 and scored[1][0] == hits:
        warns.append(f"Sheet also resembles '{scored[1][2]}' data equally well; classified as '{ds}'. "
                     "Override in Data Explorer if wrong.")
    conf = "high" if hits >= 2 else "low"
    if conf == "low":
        warns.append("Only one identifying column matched; classification confidence is low.")
    return Classification(ds, hits, conf, mapping, warns)


def manual_classification(columns: list[str], dataset: str | None, mapping: dict[str, str | None]) -> Classification:
    if dataset is None:
        return Classification(None, 0, "ignored", {}, [], "manual")
    clean = {k: v for k, v in mapping.items() if v and v in columns}
    return Classification(dataset, 0, "manual", clean, [], "manual")
