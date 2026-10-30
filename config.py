"""Central configuration.

This module contains ONLY technical defaults, column aliases and UI settings.
It must never contain business values (headcounts, targets, thresholds, costs).
Anything the business has to approve (high-performer threshold, funnel order,
targets, budgets) is a user setting that starts as ``None`` / empty.
"""
from __future__ import annotations

from enum import Enum
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
LOGO_PATH = ASSETS_DIR / "switch_logo.png"
CSS_PATH = ASSETS_DIR / "styles.css"
LOG_DIR = BASE_DIR / "logs"

APP_NAME = "SWITCH Mobility · HR Analytics"
TAGLINE = "Move Better, Drive Smarter"
# SWITCH logo colours (sampled from the logo) plus a chart teal and tints of the same family.
BRAND_BLUE = "#01439E"
BRAND_GREEN = "#218455"
BRAND_TEAL = "#1FA5A6"
PALETTE = [BRAND_BLUE, BRAND_TEAL, "#5B8BD9", "#7FCFCB", BRAND_GREEN, "#A9C1E8", "#0B2F6B", "#9BD3B5"]


class DataState(str, Enum):
    NO_FILE = "NO_FILE"
    LOADING = "LOADING"
    READY = "READY"
    PARTIAL_DATA = "PARTIAL_DATA"
    INVALID_FILE = "INVALID_FILE"
    NO_SUPPORTED_DATA = "NO_SUPPORTED_DATA"


# ---- ingestion / refresh -------------------------------------------------
ALLOWED_EXTENSIONS = (".xlsx", ".xlsm")
HEADER_SCAN_ROWS = 15
DAYFIRST = True                 # dd/mm/yyyy text dates (India); Excel date cells are unaffected
DEFAULT_REFRESH_SECONDS = 10
MIN_REFRESH_SECONDS = 5
SETTLE_SECONDS = 3              # a file must be unmodified this long before it is reloaded

# ---- confidentiality -----------------------------------------------------
MIN_GROUP_SIZE = 5              # groups smaller than this are suppressed in aggregate views
SENSITIVE_NAME_TOKENS = ("name", "email", "mail", "phone", "mobile", "contact", "aadhaar",
                         "aadhar", "pan", "address", "dob", "birth", "salary", "ctc", "bank")
PREVIEW_ROWS = 25

# ---- presentation --------------------------------------------------------
CURRENCY_SYMBOL = "₹"
TENURE_BANDS_YEARS = [(0, 1, "<1 yr"), (1, 3, "1–3 yrs"), (3, 5, "3–5 yrs"),
                      (5, 10, "5–10 yrs"), (10, None, "10+ yrs")]

# User-adjustable settings. ``None`` / empty means "not configured" (never a made-up default).
DEFAULT_SETTINGS = {
    "dedupe_exact_rows": True,       # technical rule: drop rows identical in every column
    "funnel_order": [],              # ordered recruitment stages, approved by TA
    "high_perf_threshold": None,     # rating >= threshold counts as high performer
    "rating_scale_max": None,        # official top of rating scale (for validation only)
    "pms_completion_target": None,   # approved target, if any
    "training_budget": None,         # approved total training budget, if not in workbook
}


def _f(label: str, kind: str, *aliases: str) -> dict:
    return {"label": label, "kind": kind, "aliases": list(aliases)}


# kind: id | date | number | category | status | flag | text
FIELDS: dict[str, dict[str, dict]] = {
    "employee": {
        "employee_id": _f("Employee ID", "id", "employee id", "emp id", "emp code", "employee code",
                          "employee number", "emp no", "empid", "staff id", "personnel number", "ecode"),
        "department": _f("Department", "category", "department", "dept", "division"),
        "function": _f("Function", "category", "function", "business function", "vertical"),
        "location": _f("Location", "category", "location", "work location", "city", "site", "plant"),
                "state": _f("State", "category", "state", "state / ut", "state/ut", "province"),
        "employee_type": _f("Employee type", "category", "employee type", "emp type", "employment type",
                            "worker type", "contract type", "employee category"),
        "gender": _f("Gender", "category", "gender", "sex"),
        "level": _f("Level / grade", "category", "level", "grade", "band", "job level", "employee level"),
        "hire_date": _f("Date of joining", "date", "date of joining", "doj", "joining date", "hire date",
                        "date of hire", "start date"),
        "exit_date": _f("Date of exit", "date", "date of exit", "exit date", "last working day", "lwd",
                        "resignation effective date", "termination date", "separation date", "date of leaving"),
        "exit_type": _f("Exit type", "status", "exit type", "separation type", "type of exit",
                        "attrition type", "voluntary involuntary"),
        "exit_reason": _f("Exit reason", "category", "exit reason", "reason for leaving", "reason for exit",
                          "separation reason", "reason of leaving"),
    },
    "recruitment": {
        "requisition_id": _f("Requisition ID", "id", "requisition id", "req id", "requisition number",
                             "req no", "job id", "position id", "job requisition id", "requisition code"),
        "candidate_id": _f("Candidate ID", "id", "candidate id", "applicant id", "application id"),
        "job_title": _f("Job title", "category", "job title", "position title", "position", "role",
                        "job role", "designation", "requisition title"),
        "department": _f("Department", "category", "department", "dept", "division"),
        "function": _f("Function", "category", "function", "business function", "vertical"),
        "location": _f("Location", "category", "location", "work location", "city", "site"),
        "priority": _f("Priority", "category", "priority", "urgency"),
        "recruiter": _f("Recruiter", "category", "recruiter", "talent acquisition spoc", "ta spoc", "recruiter name"),
        "hiring_manager": _f("Hiring manager", "category", "hiring manager", "requester", "requestor"),
        "status": _f("Requisition status", "status", "requisition status", "position status", "req status", "status"),
        "open_date": _f("Requisition open date", "date", "requisition open date", "open date", "date opened",
                        "requisition date", "opening date", "created date", "raised date", "date of requisition"),
        "filled_date": _f("Filled / offer accepted date", "date", "filled date", "date filled",
                          "offer accepted date", "closure date", "closed date", "date closed", "position filled date"),
        "source": _f("Source of hire", "category", "source of hire", "hiring source", "sourcing channel",
                     "source", "channel"),
        "cost": _f("Recruitment cost", "number", "cost per hire", "recruitment cost", "hiring cost",
                   "agency fee", "total cost", "cost"),
        "offer_status": _f("Offer status", "status", "offer status", "offer outcome", "offer decision"),
        "stage": _f("Recruitment stage", "category", "recruitment stage", "current stage", "pipeline stage",
                    "hiring stage", "stage"),
        "gender": _f("Gender", "category", "gender", "sex"),
    },
    "training": {
        "employee_id": _f("Employee ID", "id", "employee id", "emp id", "emp code", "employee code",
                          "employee number", "emp no", "empid", "staff id"),
        "program": _f("Training programme", "category", "training program", "training programme", "program",
                      "programme", "training name", "course name", "course", "training title", "training"),
        "category": _f("Training category", "category", "training category", "training type", "competency area",
                       "category", "type"),
        "delivery_mode": _f("Delivery mode", "category", "delivery mode", "mode of delivery", "training mode",
                            "mode of training", "mode", "format"),
        "location": _f("Location", "category", "location", "work location", "city", "site"),
        "department": _f("Department", "category", "department", "dept", "division"),
        "hours": _f("Training hours", "number", "training hours", "learning hours", "duration hours",
                    "duration in hours", "no of hours", "hours", "hrs"),
        "date": _f("Training date", "date", "training date", "training start date", "program date",
                   "completion date", "start date", "date"),
        "cost": _f("Training cost", "number", "training cost", "program cost", "total cost", "fee", "cost"),
        "budget": _f("Training budget", "number", "training budget", "approved budget", "budget"),
        "completion_status": _f("Completion status", "status", "completion status", "attendance status",
                                "training status", "status"),
        "certification": _f("Certification", "flag", "certification completed", "certification status",
                            "certified", "certificate", "certification"),
        "pre_score": _f("Pre-training score", "number", "pre score", "pre assessment", "pre training score"),
        "post_score": _f("Post-training score", "number", "post score", "post assessment", "post training score"),
        "assessment_score": _f("Assessment score", "number", "assessment score", "test score",
                               "evaluation score", "effectiveness score", "score"),
    },
    "performance": {
        "employee_id": _f("Employee ID", "id", "employee id", "emp id", "emp code", "employee code",
                          "employee number", "emp no", "empid", "staff id"),
        "department": _f("Department", "category", "department", "dept", "division"),
        "function": _f("Function", "category", "function", "business function", "vertical"),
        "location": _f("Location", "category", "location", "work location", "city", "site"),
        "level": _f("Level / grade", "category", "level", "grade", "band", "job level", "employee level"),
        "age_group": _f("Age group", "category", "age group", "age band", "age bracket"),
        "rating": _f("Performance rating", "number", "performance rating", "final rating", "overall rating",
                     "pms rating", "appraisal rating", "rating"),
        "review_status": _f("Review status", "status", "review status", "pms status", "appraisal status",
                            "review completion status", "status"),
        "cycle": _f("Review cycle", "category", "review cycle", "appraisal cycle", "performance cycle",
                    "financial year", "cycle"),
        "review_date": _f("Review date", "date", "review date", "appraisal date", "review completed date"),
        "goals_total": _f("Goals set", "number", "total goals", "goals set", "number of goals", "goals count"),
        "goals_achieved": _f("Goals achieved", "number", "goals achieved", "goals met", "achieved goals",
                             "goals completed"),
        "high_performer_flag": _f("High-performer flag", "flag", "high performer flag", "high performer",
                                  "hipo", "high potential", "top talent"),
        "idp": _f("IDP created", "flag", "idp created", "individual development plan", "idp status", "idp"),
    },
    "relations": {
        "case_id": _f("Case ID", "id", "case id", "grievance id", "issue id", "ticket id", "case number"),
        "case_category": _f("Issue category", "category", "issue category", "case category", "issue type",
                            "grievance type", "nature of issue", "issue"),
        "status": _f("Case status", "status", "case status", "resolution status", "status"),
        "open_date": _f("Case open date", "date", "case open date", "date raised", "opened date",
                        "date reported", "open date", "raised on"),
        "close_date": _f("Case close date", "date", "case close date", "closed date", "date closed",
                         "resolution date", "closure date", "resolved date"),
        "department": _f("Department", "category", "department", "dept", "division"),
        "location": _f("Location", "category", "location", "work location", "city", "site"),
        "engagement_score": _f("Engagement score", "number", "engagement score", "engagement index",
                               "satisfaction score", "survey score", "enps"),
        "invited": _f("Survey invitees", "number", "survey invited", "total invited", "eligible participants",
                      "invited"),
        "responded": _f("Survey respondents", "number", "survey responded", "respondents", "responses",
                        "responded"),
    },
}

# Fields that identify what kind of data a sheet holds. One hit = low confidence, two = high.
SIGNATURES = {
    "employee": ["hire_date", "exit_date", "employee_type", "exit_type", "exit_reason"],
    "recruitment": ["requisition_id", "candidate_id", "open_date", "filled_date", "source", "offer_status",
                    "stage", "recruiter", "hiring_manager", "priority"],
    "training": ["program", "hours", "delivery_mode", "certification", "pre_score", "post_score",
                 "assessment_score", "budget"],
    "performance": ["rating", "goals_total", "goals_achieved", "high_performer_flag", "idp", "cycle"],
    "relations": ["case_id", "case_category", "engagement_score", "invited", "responded"],
}

DATASET_LABELS = {"employee": "Employees", "recruitment": "Recruitment", "training": "Training",
                  "performance": "Performance (PMS)", "relations": "Employee relations & engagement"}

# Keyword rules for status normalisation. Rules are evaluated in order; the first match wins,
# so negative phrases ("not completed") must come before positive ones. Unmatched -> "unclassified".
STATUS_RULES: dict[tuple[str, str], dict[str, list[str]]] = {
    ("recruitment", "status"): {
        "cancelled": ["cancel", "withdrawn", "dropped"],
        "on_hold": ["hold"],
        "open": ["open", "active", "in progress", "ongoing", "sourcing", "pending"],
        "filled": ["filled", "closed", "joined", "hired", "onboarded", "completed"],
    },
    ("recruitment", "offer_status"): {
        "declined": ["declin"],
        "rejected": ["reject"],
        "accepted": ["accept"],
    },
    ("employee", "exit_type"): {
        "involuntary": ["involuntary", "terminat", "dismiss", "retrench", "layoff", "absconded"],
        "voluntary": ["voluntary", "resign"],
    },
    ("training", "completion_status"): {
        "not_completed": ["not complet", "incomplete", "absent", "no show", "cancel", "fail", "dropped",
                          "pending", "registered", "enrolled", "in progress"],
        "completed": ["complet", "attended", "present", "passed", "done"],
    },
    ("performance", "review_status"): {
        "pending": ["not complet", "incomplete", "pending", "not started", "in progress", "open", "draft"],
        "completed": ["complet", "done", "closed", "submitted", "finali"],
    },
    ("relations", "status"): {
        "open": ["unresolved", "not resolved", "not closed", "open", "new", "progress", "ongoing", "investigat"],
        "pending": ["pend", "hold", "wait"],
        "closed": ["clos", "resolv", "complet"],
    },
}
