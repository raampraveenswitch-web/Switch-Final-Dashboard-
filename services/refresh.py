"""Detection of external changes to a monitored workbook.

Streamlit does NOT notice edits to a file on disk. The UI polls ``ChangeDetector.check`` from a
timed fragment; the detector compares (mtime, size), waits until the file has been quiet for
SETTLE_SECONDS (so half-written saves are never read), and only then confirms a change by content
hash. Unchanged files cost one ``stat`` call per poll — never a reload.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path

from config import SETTLE_SECONDS


@dataclass(frozen=True)
class Fingerprint:
    mtime_ns: int
    size: int


def stat_fingerprint(path: str | Path) -> Fingerprint | None:
    try:
        st = Path(path).expanduser().stat()
    except OSError:
        return None
    return Fingerprint(st.st_mtime_ns, st.st_size)


def clean_path(raw: str) -> str:
    """Windows 'Copy as path' wraps the path in double quotes; pasted paths often carry stray spaces."""
    return raw.strip().strip('"').strip("'").strip()


def sha256_file(path: str | Path) -> str | None:
    try:
        return hashlib.sha256(Path(path).expanduser().read_bytes()).hexdigest()
    except OSError:
        return None


class ChangeDetector:
    """Result of ``check``: 'unchanged' | 'pending' | 'changed' | 'missing'."""

    def __init__(self, settle_seconds: float = SETTLE_SECONDS):
        self.settle = settle_seconds
        self.loaded_fp: Fingerprint | None = None
        self.loaded_hash: str | None = None

    def mark_loaded(self, path: str | Path, content_hash: str | None = None,
                    fingerprint: Fingerprint | None = None) -> None:
        # ``fingerprint`` should be taken BEFORE the file is read, so a save made during the read is noticed later.
        self.loaded_fp = fingerprint or stat_fingerprint(path)
        self.loaded_hash = content_hash or sha256_file(path)

    def check(self, path: str | Path, now: float | None = None) -> str:
        fp = stat_fingerprint(path)
        if fp is None:
            return "missing"
        if fp == self.loaded_fp:
            return "unchanged"
        now = time.time() if now is None else now
        age = now - fp.mtime_ns / 1e9
        if 0 <= age < self.settle:                # still being written / just saved (future mtimes = clock skew: settled)
            return "pending"
        h = sha256_file(path)
        if h is None:
            return "locked"                       # exists but cannot be read now: open in Excel, OneDrive sync, antivirus
        if h == self.loaded_hash:
            self.loaded_fp = fp                   # touched but identical: no reload
            return "unchanged"
        return "changed"
