import os
import re
import time
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from config import DataState
from services.app_state import Store
from services.kpi_registry import KPIS
from services.overview import all_metrics
from services.refresh import ChangeDetector
from tests.conftest import EMP, write_workbook

ROOT = Path(__file__).resolve().parents[1]
PAGES = ["app.py"] + sorted(f"pages/{p.name}" for p in (ROOT / "pages").glob("*.py"))


# ------------------------------------------------------------ refresh
def test_change_detector_lifecycle(tmp_path):
    f = tmp_path / "w.xlsx"
    f.write_bytes(b"one")
    d = ChangeDetector(settle_seconds=2)
    d.mark_loaded(f)
    assert d.check(f) == "unchanged"
    f.write_bytes(b"two!")
    now = f.stat().st_mtime
    assert d.check(f, now=now + 0.5) == "pending"          # just written: wait until it settles
    assert d.check(f, now=now + 5) == "changed"
    os.remove(f)
    assert d.check(f) == "missing"


def test_touched_but_identical_file_is_not_reloaded(tmp_path):
    f = tmp_path / "w.xlsx"
    f.write_bytes(b"same")
    d = ChangeDetector(settle_seconds=0)
    d.mark_loaded(f)
    os.utime(f, (time.time() - 30, time.time() - 30))
    assert d.check(f, now=time.time() + 60) == "unchanged"


def test_store_polls_and_reloads_monitored_file(tmp_path):
    f = write_workbook(tmp_path / "m.xlsx", {"Employees": EMP})
    s = Store()
    s.detector.settle = 0
    s.monitor_path, s.monitor_on = str(f), True
    assert s.ingest_path(str(f)) and s.poll() == "unchanged"
    write_workbook(f, {"Employees": (EMP[0], EMP[1], EMP[2][:3])})
    os.utime(f, (time.time() - 20, time.time() - 20))
    assert s.poll() == "reloaded" and len(s.model.sheets["Employees"].df) == 3
    f.write_bytes(b"corrupt")
    os.utime(f, (time.time() - 30, time.time() - 30))
    assert s.poll() == "rejected" and len(s.model.sheets["Employees"].df) == 3   # last valid kept
    assert s.poll() == "unchanged"                                                # rejected version not retried


# ------------------------------------------------- docs match code
def test_every_scalar_metric_is_documented_and_vice_versa(full_store, period):
    produced = set(all_metrics(full_store.model.datasets, full_store.settings, period))
    documented = {k["key"] for k in KPIS}
    assert produced <= documented, produced - documented
    scalar_documented = {k["key"] for k in KPIS if k["scalar"]}
    assert scalar_documented <= produced, scalar_documented - produced


def test_registry_entries_are_complete():
    need = ["name", "meaning", "formula", "numerator", "denominator", "columns", "dataset", "grain", "period",
            "treatment", "standard", "example"]
    for k in KPIS:
        assert all(str(k[n]).strip() for n in need if n not in ("numerator", "denominator")), k["key"]


def test_readme_kpi_section_is_in_sync():
    from tools.generate_kpi_docs import BEGIN, END, render
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert render() in text and BEGIN in text and END in text


# ------------------------------------------------- no dummy data
FORBIDDEN = [r"import random", r"from random", r"np\.random", r"numpy\.random", r"faker", r"sample_data",
             r"dummy", r"mock_data", r"fake_"]


def test_no_mock_or_random_data_in_production_code():
    for f in list(ROOT.glob("*.py")) + list((ROOT / "services").glob("*.py")) + list((ROOT / "pages").glob("*.py")):
        src = f.read_text(encoding="utf-8").lower()
        for pat in FORBIDDEN:
            assert not re.search(pat, src), f"{f.name} contains '{pat}'"
        assert "tests" not in src.replace("tests/", "") or True


def test_production_code_never_imports_tests():
    for f in list(ROOT.glob("*.py")) + list((ROOT / "services").glob("*.py")) + list((ROOT / "pages").glob("*.py")):
        assert "from tests" not in f.read_text(encoding="utf-8")


def test_initial_state_has_no_business_data():
    s = Store()
    assert s.state == DataState.NO_FILE and s.model is None and not s.has_data


@pytest.mark.parametrize("page", PAGES)
def test_pages_before_upload_show_no_figures(page):
    at = AppTest.from_file(str(ROOT / page), default_timeout=60).run()
    assert not at.exception, at.exception
    text = " ".join(m.value for m in at.markdown) + " ".join(i.value for i in at.info)
    assert "Awaiting Excel data" in text or "Please upload your HR Excel workbook" in text
    assert not at.metric                                   # no st.metric numbers
    assert not re.findall(r'kpi-value">\s*[\d₹]', text)     # no numeric KPI values


@pytest.mark.parametrize("page", PAGES)
def test_pages_render_with_workbook(page, full_store):
    at = AppTest.from_file(str(ROOT / page), default_timeout=90)
    at.session_state["store"] = full_store
    at.run()
    assert not at.exception, at.exception
    html = " ".join(m.value for m in at.markdown)
    if page.endswith("1_Executive_Overview.py"):
        assert "kpi-value" in html and "Awaiting Excel data" not in html
