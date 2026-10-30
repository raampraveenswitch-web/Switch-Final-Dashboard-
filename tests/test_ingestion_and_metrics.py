import pandas as pd
import pytest

from config import DataState
from services import metrics as M
from services.app_state import Store
from services.excel_loader import read_workbook
from services.models import WorkbookError
from tests.conftest import EMP, TRN, write_workbook, D


def test_every_sheet_is_read_and_classified(full_store):
    m = full_store.model
    assert set(m.sheets) == {"Employees", "Hiring", "L&D", "PMS 2024", "ER", "Misc", "Notes"}
    cl = {n: c.dataset for n, c in m.classifications.items()}
    assert cl["Employees"] == "employee" and cl["Hiring"] == "recruitment" and cl["L&D"] == "training"
    assert cl["PMS 2024"] == "performance" and cl["ER"] == "relations"
    assert cl["Misc"] is None and cl["Notes"] is None          # irrelevant / empty sheets create no data
    assert full_store.state == DataState.READY


def test_title_rows_are_skipped(full_workbook):
    sheets, _ = read_workbook(full_workbook.read_bytes(), "x.xlsx")
    assert sheets["L&D"].header_row == 2 and "Training Hours" in sheets["L&D"].df.columns
    assert len(sheets["L&D"].df) == 5


def test_empty_sheet_makes_no_records(full_store):
    assert full_store.model.sheets["Notes"].empty
    assert all("Notes" not in set(d["source_sheet"]) for d in full_store.model.datasets.values())


def test_employee_metrics_from_actual_contents(full_store, period):
    e = full_store.model.datasets["employee"]
    assert M.emp_headcount(e, period.end).value == 8
    assert M.emp_new_hires(e, period).value == 3
    assert M.emp_exits(e, period).value == 2
    assert M.emp_attrition(e, period).value == pytest.approx(2 / 7.5 * 100)


def test_recruitment_metrics(full_store, period):
    r = full_store.model.datasets["recruitment"]
    assert M.rec_requisitions(r, period).value == 5
    assert M.rec_filled(r, period).value == 2
    assert M.rec_time_to_hire(r, period).value == 45
    assert M.rec_offer_acceptance(r, period).value == pytest.approx(200 / 3)
    assert M.rec_cost_per_hire(r, period).value == 2000
    assert M.rec_open_count(r, period.end).value == 2
    assert M.rec_open_ageing(r, period.end).value == 44.5


def test_training_metrics(full_store, period):
    t, e = full_store.model.datasets["training"], full_store.model.datasets["employee"]
    assert M.trn_hours(t, period).value == 28
    assert M.trn_employees(t, period).value == 3
    assert M.trn_participation(t, e, period, period.end).value == pytest.approx(37.5)
    assert M.trn_avg_hours(t, e, period, period.end).value == pytest.approx(3.5)
    assert M.trn_cert_rate(t, period).value == 50
    assert M.trn_effectiveness(t, period).value == 75


def test_performance_and_relations(full_store):
    p, c = full_store.model.datasets["performance"], full_store.model.datasets["relations"]
    assert M.pms_completion(p).value == 75 and M.pms_avg_rating(p).value == 4
    assert M.pms_goal_rate(p).value == pytest.approx(10 / 13 * 100) and M.pms_idp(p).value == 2
    hp = M.pms_high_performers(p, {"high_perf_threshold": None})
    assert not hp.available and "threshold" in hp.reason          # never guessed
    assert M.pms_high_performers(p, {"high_perf_threshold": 5}).value == 1
    assert (M.rel_cases(c).value, M.rel_open(c).value, M.rel_closed(c).value, M.rel_pending(c).value) == (4, 1, 2, 1)
    assert M.rel_resolution_rate(c).value == 50 and M.rel_resolution_days(c).value == 15


def test_missing_columns_are_unavailable_not_zero(tmp_path, period):
    emp_no_exit = (EMP[0], ["Employee ID", "Date of Joining"], [[r[0], r[2]] for r in EMP[2]])
    trn_no_cost = (TRN[0], TRN[1], TRN[2])
    p = write_workbook(tmp_path / "a.xlsx", {"E": emp_no_exit, "T": trn_no_cost})
    s = Store()
    assert s.ingest_bytes(p.read_bytes(), "a.xlsx")
    e, t = s.model.datasets["employee"], s.model.datasets["training"]
    a = M.emp_attrition(e, period)
    assert a.value is None and "Date of exit" in a.reason
    c = M.trn_cost(t, period)
    assert c.value is None and "training cost data not found" in c.reason
    assert s.state == DataState.PARTIAL_DATA


def test_no_previous_period_no_fabricated_change():
    cur, prev = M.Metric("k", "x", 5.0), M.Metric("k", "x", None)
    assert M.change_text(cur, prev, True) == "" and M.change_text(cur, M.Metric("k", "x", 4.0), False) == ""
    assert M.pct_change(5, 0) is None
    assert M.change_text(M.Metric("k", "r", 55.0, "pct"), M.Metric("k", "r", 50.0, "pct"), True, "p").startswith("+5.0 pp")


def test_failed_upload_has_no_fallback():
    s = Store()
    assert not s.ingest_bytes(b"not an excel file", "bad.xlsx")
    assert s.state == DataState.INVALID_FILE and s.model is None
    assert not s.ingest_bytes(b"x", "bad.csv") and s.model is None


def test_unsupported_workbook(tmp_path):
    p = write_workbook(tmp_path / "x.xlsx", {"Misc": (([], ["Colour", "Shape"], [["red", "square"]]))})
    s = Store()
    assert s.ingest_bytes(p.read_bytes(), "x.xlsx") and s.state == DataState.NO_SUPPORTED_DATA


def test_replacing_workbook_recalculates_and_failure_keeps_last_valid(full_store, tmp_path):
    first = M.emp_headcount(full_store.model.datasets["employee"], pd.Timestamp("2024-03-31")).value
    smaller = (EMP[0], EMP[1], EMP[2][:4])
    p = write_workbook(tmp_path / "new.xlsx", {"Employees": smaller})
    assert full_store.ingest_bytes(p.read_bytes(), "new.xlsx")
    assert "recruitment" not in full_store.model.datasets             # nothing stale from the old workbook
    assert M.emp_headcount(full_store.model.datasets["employee"], pd.Timestamp("2024-03-31")).value != first
    assert not full_store.ingest_bytes(b"junk", "broken.xlsx")
    assert full_store.model.source_name == "new.xlsx" and full_store.failure and full_store.failed_name == "broken.xlsx"


def test_small_groups_suppressed():
    t = pd.DataFrame({"g": ["a", "b"], "n": [2, 9]})
    out, hidden = M.small_group_filter(t, "n")
    assert list(out["g"]) == ["b"] and hidden == 1


def test_invalid_values_are_reported_not_dropped(tmp_path):
    rows = [["E1", D(2024, 1, 1), "not a date"], ["E2", D(2024, 1, 2), None]]
    p = write_workbook(tmp_path / "w.xlsx", {"E": ([], ["Employee ID", "Date of Joining", "Date of Exit"], rows)})
    s = Store()
    s.ingest_bytes(p.read_bytes(), "w.xlsx")
    assert len(s.model.datasets["employee"]) == 2
    assert any("not valid dates" in i.message for i in s.model.issues)
