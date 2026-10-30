"""Central data-loading service. ``Store`` is plain Python (testable without Streamlit); every page
reads the same Store via ``get_store()`` so all pages show the same state."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from config import DEFAULT_REFRESH_SECONDS, DEFAULT_SETTINGS, DataState
from services.dataset_builder import build_model
from services.excel_loader import read_workbook, read_workbook_path
from services.log import get_logger
from services.models import WorkbookError, WorkbookModel
from services.refresh import ChangeDetector, stat_fingerprint

log = get_logger()


@dataclass
class Store:
    model: WorkbookModel | None = None
    settings: dict = field(default_factory=lambda: dict(DEFAULT_SETTINGS))
    overrides: dict = field(default_factory=dict)
    failure: str = ""                    # latest rejected file message (kept until next success)
    failed_name: str = ""
    last_refresh_ok: datetime | None = None
    last_attempt: datetime | None = None
    loading: bool = False
    monitor_path: str = ""
    monitor_on: bool = False
    refresh_seconds: int = DEFAULT_REFRESH_SECONDS
    detector: ChangeDetector = field(default_factory=ChangeDetector)
    last_upload_id: str | None = None
    watch_status: str = ""

    # ---------------------------------------------------------------- state
    @property
    def state(self) -> DataState:
        if self.loading:
            return DataState.LOADING
        if self.model is None:
            return DataState.INVALID_FILE if self.failure else DataState.NO_FILE
        ds = self.model.datasets
        if not ds:
            return DataState.NO_SUPPORTED_DATA
        core = {"employee", "recruitment", "training", "performance"}
        return DataState.READY if core <= set(ds) else DataState.PARTIAL_DATA

    @property
    def has_data(self) -> bool:
        return self.model is not None and bool(self.model.datasets)

    # ------------------------------------------------------------ ingestion
    def _accept(self, sheets, fp, name) -> None:
        # Overrides belong to the previous workbook; a new file starts from auto-detection.
        self.overrides = {}
        self.model = build_model(sheets, name, fp, self.settings, self.overrides)
        self.failure, self.failed_name = "", ""
        self.last_refresh_ok = datetime.now()
        log.info("loaded workbook name=%s sheets=%d datasets=%s", name, len(sheets), sorted(self.model.datasets))

    def _reject(self, name: str, exc: Exception) -> None:
        self.failure, self.failed_name = str(exc), name
        log.warning("workbook rejected name=%s reason=%s", name, type(exc).__name__)

    def ingest_bytes(self, data: bytes, name: str) -> bool:
        self.loading, self.last_attempt = True, datetime.now()
        try:
            sheets, fp = read_workbook(data, name)
            self._accept(sheets, fp, name)
            return True
        except WorkbookError as exc:
            self._reject(name, exc)       # last valid model (if any) is preserved, never replaced by demo data
            return False
        finally:
            self.loading = False

    def ingest_path(self, path: str) -> bool:
        self.loading, self.last_attempt, self.watch_status = True, datetime.now(), ""
        before = stat_fingerprint(path)          # taken before the read: a save during the read is caught by the next poll
        try:
            sheets, fp, name = read_workbook_path(path)
            self._accept(sheets, fp, name)
            self.detector.mark_loaded(path, content_hash=fp, fingerprint=before)
            return True
        except WorkbookError as exc:
            self._reject(Path(path).name or "file", exc)
            self.detector.mark_loaded(path, fingerprint=before)   # do not retry the same rejected version every poll
            return False
        except OSError:
            # Exists but unreadable right now (Excel or OneDrive holds it). Keep the last valid model and do NOT
            # mark it loaded, so the next poll retries automatically once the file is free.
            self.watch_status = "locked"
            return False
        finally:
            self.loading = False

    def rebuild(self) -> None:
        """Re-run mapping/cleaning on the already-loaded sheets (after mapping/settings changes)."""
        if self.model:
            m = self.model
            self.model = build_model(m.sheets, m.source_name, m.fingerprint, self.settings, self.overrides)
            self.model.loaded_at = m.loaded_at
            log.info("rebuilt model name=%s", m.source_name)

    # ------------------------------------------------------------- watching
    def poll(self) -> str:
        """One polling step for the monitored path. Returns the detector verdict."""
        if not (self.monitor_on and self.monitor_path):
            return "off"
        verdict = self.detector.check(self.monitor_path)
        if verdict == "changed":
            ok = self.ingest_path(self.monitor_path)
            if not ok and self.watch_status == "locked":
                return "locked"                  # no rerun loop: the next poll simply tries again
            self.watch_status = "reloaded" if ok else "rejected"
            return self.watch_status
        self.watch_status = verdict
        return verdict


def get_store() -> Store:
    import streamlit as st
    if "store" not in st.session_state:
        st.session_state["store"] = Store()
    return st.session_state["store"]
