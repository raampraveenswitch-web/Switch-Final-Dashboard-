"""Test fixtures. Fictional values live ONLY here — never in production code."""
import sys
from datetime import datetime
from pathlib import Path

import pytest
from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
D = datetime


def write_workbook(path, sheets: dict):
    """sheets: name -> (title_rows, header, rows)."""
    wb = Workbook()
    wb.remove(wb.active)
    for name, (titles, header, rows) in sheets.items():
        ws = wb.create_sheet(name)
        for t in titles:
            ws.append([t])
        if header:
            ws.append(header)
        for r in rows:
            ws.append(r)
    wb.save(path)
    return path


EMP = (["Employee Master — fictional test data"],
       ["Employee ID", "Department", "Date of Joining", "Date of Exit", "Exit Type"],
       [["E01", "Sales", D(2020, 1, 1), None, None], ["E02", "Sales", D(2021, 6, 15), None, None],
        ["E03", "Sales", D(2022, 3, 1), D(2024, 2, 10), "Resignation"], ["E04", "Ops", D(2019, 5, 1), None, None],
        ["E05", "Ops", D(2023, 2, 1), None, None], ["E06", "Ops", D(2023, 7, 1), D(2024, 3, 20), "Terminated"],
        ["E07", "Ops", D(2024, 1, 10), None, None], ["E08", "Sales", D(2024, 2, 5), None, None],
        ["E09", "Sales", D(2018, 1, 1), None, None], ["E10", "Ops", D(2024, 3, 1), None, None]])
REC = ([], ["Req ID", "Job Title", "Department", "Status", "Requisition Open Date", "Filled Date", "Source",
            "Offer Status", "Cost per Hire"],
       [["R1", "Engineer", "Sales", "Filled", D(2024, 1, 2), D(2024, 2, 1), "Referral", "Accepted", 1000],
        ["R2", "Analyst", "Ops", "Filled", D(2024, 1, 10), D(2024, 3, 10), "Portal", "Accepted", 3000],
        ["R3", "Manager", "Ops", "Open", D(2024, 2, 1), None, "Portal", "Declined", None],
        ["R4", "Engineer", "Sales", "Open", D(2024, 3, 1), None, None, None, None],
        ["R5", "Clerk", "Ops", "Cancelled", D(2024, 1, 5), None, None, None, None]])
TRN = (["Training log", "fictional"],
       ["Employee ID", "Training Program", "Training Category", "Delivery Mode", "Training Hours", "Training Date",
        "Completion Status", "Certification", "Assessment Score"],
       [["E01", "Safety", "Compliance", "Classroom", 8, D(2024, 1, 15), "Completed", "Yes", 80],
        ["E02", "Safety", "Compliance", "Classroom", 8, D(2024, 1, 15), "Completed", "No", 60],
        ["E04", "Excel", "Skills", "Online", 4, D(2024, 2, 10), "Completed", None, 90],
        ["E05", "Excel", "Skills", "Online", 4, D(2024, 2, 10), "Not completed", None, None],
        ["E01", "Excel", "Skills", "Online", 4, D(2024, 2, 11), "Completed", None, 70]])
PMS = ([], ["Employee ID", "Function", "Performance Rating", "Review Status", "Goals Set", "Goals Achieved", "IDP Created"],
       [["E01", "Sales", 4, "Completed", 5, 4, "Yes"], ["E02", "Sales", 3, "Completed", 4, 2, "No"],
        ["E04", "Ops", 5, "Completed", 4, 4, "Yes"], ["E05", "Ops", None, "Pending", None, None, "No"]])
REL = ([], ["Case ID", "Issue Category", "Case Status", "Case Open Date", "Case Close Date"],
       [["C1", "Conduct", "Closed", D(2024, 1, 5), D(2024, 1, 15)], ["C2", "Conduct", "Closed", D(2024, 2, 1), D(2024, 2, 21)],
        ["C3", "Pay", "Open", D(2024, 3, 1), None], ["C4", "Pay", "Pending", D(2024, 3, 5), None]])
MISC = ([], ["Colour", "Shape"], [["red", "square"]])
BLANK = ([], None, [])


@pytest.fixture
def full_workbook(tmp_path):
    return write_workbook(tmp_path / "hr.xlsx", {"Employees": EMP, "Hiring": REC, "L&D": TRN, "PMS 2024": PMS,
                                                 "ER": REL, "Misc": MISC, "Notes": BLANK})


@pytest.fixture
def full_store(full_workbook):
    from services.app_state import Store
    s = Store()
    assert s.ingest_bytes(full_workbook.read_bytes(), "hr.xlsx")
    return s


@pytest.fixture
def period():
    import pandas as pd
    from services.metrics import Period
    return Period(pd.Timestamp("2024-01-01"), pd.Timestamp("2024-03-31"))
