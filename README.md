# SWITCH Mobility — Automated HR Analytics Dashboard

A local, confidential, Excel-driven HR dashboard (Streamlit · pandas · openpyxl · Plotly).
Upload a workbook with any number of worksheets; every sheet is inspected, mapped to HR datasets and
turned into Executive, Recruitment, Employees, Training, Performance (PMS), Turnover, Employee Relations
and Data Explorer pages.

**Zero dummy data.** Before a workbook is loaded the app shows the branded shell and *"Please upload your
HR Excel workbook to view analytics."* — no figures. Every number afterwards is calculated from the
uploaded workbook; unavailable metrics say **Not available** with the reason (never 0).

## Quick start

```bash
python -m venv .venv && .venv\Scripts\activate      # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```
Opens at `http://localhost:8501`, bound to localhost only (`.streamlit/config.toml`), telemetry off.
Run the tests with `pytest`.

The SWITCH logo ships at `assets/switch_logo.png` (transparent PNG). If it is missing the app shows a text wordmark.
Brand colours (sampled from the logo): Blue `#01439E`, Green `#218455`; charts add Teal `#1FA5A6` and tints of these.

## Landing page

`streamlit run app.py` opens a landing page in the style of the SWITCH website: logo bar, teal→blue rule, a full-width
hero photo with *SWITCH to smarter HR Analytics · Move Better, Drive Smarter*, and a **Continue to Dashboard** button
(opens the HR Overview). Quick-link tiles below open each dashboard and the Downloads page.

**Hero photo:** replace `assets/hero.jpg` with your full-resolution image (a 3840 px-wide JPG is ideal; `.png` and
`.webp` also work — name it `hero.*`). It fills the width and is cropped to fit, so keep the vehicles near the centre.

## Dashboard layout

Every page follows the SWITCH Recruitment Dashboard format:

1. **Header bar** — SWITCH logo │ `<Page> Dashboard` with the tagline *Move Better, Drive Smarter*, and filter pills: *Last Updated*, *Year*, *Period* (Q1–Q4, H1, H2, Full year, Last 12 months), *Location*, and a
   filter button (custom date range + page filters such as department, function, priority).
2. **Icon sidebar** — page navigation, data source upload, file monitoring, workbook status.
3. **KPI row** — six icon cards with ▲/▼ change vs the previous comparable period (green = better, red = worse,
   blue = neutral). Extra KPIs appear in a compact strip below.
4. **Four-panel row** — trend (bars + labelled line) · donut with total · funnel / ranking · *Initiatives & Focus*
   checklist (rule-based insights plus your own focus items, editable per page for the session).
5. **Detail rows** — equal-height cards with breakdowns, tables and items that need extra data.

## Downloads (PowerPoint and PDF)

Open **Downloads** in the sidebar. Choose the Year, Period and Location in the header, then for any dashboard click
**Prepare files** → **PowerPoint** / **PDF**. The **Complete HR Analytics Pack** puts every available dashboard in one
deck/PDF (cover, contents, a section per dashboard); a ZIP with all separate files is also available.

* PowerPoint decks use **native, editable charts** (click a chart → *Edit Data* in PowerPoint); 16:9 widescreen.
* PDFs are print-ready 16:9 pages with the same layout.
* Each export: cover → key metrics (with ▲/▼ vs the previous period) → two charts per slide → table (where relevant)
  → Initiatives & Focus + data notes (what could not be shown and why). Your own focus items are included.
* Exports use the same metric functions as the screens (`services/report_data.py`), so the numbers always match.
  Page-level filters (department etc.) are not applied; Performance uses the latest review cycle.
* Built with python-pptx and matplotlib — no Office, browser or internet connection needed.

The default period is the latest quarter in the workbook (or the previous quarter when the latest is under half covered).
Quarter comparisons are against the previous calendar quarter; *Full year* compares with the same span last year.

## Project structure

```
app.py                      home: workbook status and detected datasets
pages/1_Executive_Overview.py … 8_Data_Explorer.py
services/
  excel_loader.py           safe read of every sheet, header detection, content fingerprint
  workbook_inspector.py     profiles (types, missing, duplicates, date ranges), ID relationships
  column_mapping.py         alias-based mapping + sheet classification (configurable in config.py)
  data_cleaning.py          typing, status normalisation, validation (reports every exclusion)
  dataset_builder.py        raw sheets -> clean datasets (combines same-type sheets, never joins rows)
  metrics.py                all KPI functions (return Metric or "unavailable + reason")
  kpi_registry.py           documentation of every KPI (source of the section below)
  insights.py               rule-based insights (each shows its rule)
  app_state.py              central Store + DataState (NO_FILE … NO_SUPPORTED_DATA)
  refresh.py                file-change detection (mtime/size + settle time + content hash)
  ui.py                     shared shell, sidebar, KPI cards, charts, gates
tools/generate_kpi_docs.py  regenerates the KPI section from the registry
tests/                      pytest suite (fictional fixtures live only here)
```

## How the workbook is read

1. The file is read fully into memory (the file handle is released immediately); macros are never executed
   and only cell values are read. Save the workbook in Excel so formula results are cached.
2. **Every** worksheet is parsed. Blank rows/columns are dropped, title rows above the header are skipped,
   duplicate column names are made unique, original names are kept for audit.
3. Each sheet is classified (employee, recruitment, training, performance, relations) from its column
   names via the aliases in `config.FIELDS`. Unfamiliar sheets are kept for review, not discarded.
   One matching column = *low confidence* warning; ambiguous mappings are flagged.
4. Mapping and dataset type can be overridden in **Data Explorer → Mapping**.
5. Sheets of the same type are concatenated with a `source_sheet` column and a warning (they are assumed to
   share the same record grain). Different datasets are **never row-joined**; they are linked only through
   distinct Employee ID sets (e.g. participation = trained IDs ∩ active employee IDs), so rows cannot multiply.
6. Identifiers stay text. Dates use day-first parsing for text dates (`config.DAYFIRST`); real Excel dates are exact.

### Data states
`NO_FILE` · `LOADING` · `READY` (employee, recruitment, training and performance data found) ·
`PARTIAL_DATA` · `INVALID_FILE` · `NO_SUPPORTED_DATA`. All pages read the same `Store`, so they always agree.

### Replacing a workbook
Uploading a new valid file replaces the active dataset and recalculates everything (manual mappings of the
old file are cleared). If the new file fails validation, the app shows a warning naming the rejected file and
**keeps the last valid workbook, clearly labelled**; if there is no earlier valid workbook, no figures are shown.

## Automatic refresh

Streamlit does **not** notice edits to files on disk, and refreshing the browser only re-runs the script on
data already loaded. This app adds its own mechanism: in the sidebar, enter a local path and switch on
*Monitor this file*. A timed fragment checks the file every N seconds (≥ 5; default 30) with a single `stat`
call. When the modification time/size changes the app waits until the file has been idle for 3 seconds (so a
half-written save is never read), confirms the content really changed (SHA-256), validates it, rebuilds all
metrics and redraws every page. Touching a file without changing it causes no reload. A rejected version is
not retried until the file changes again. **Save in Excel (Ctrl+S)** to trigger it. Monitoring only works while
the app is running; it cannot refresh while the app is closed. *Load / refresh now* is the manual fallback.

## Reporting period

The sidebar period defaults to the **latest 12 months** of dates found in the workbook (or all of it if shorter),
ending at the latest date found. Snapshot metrics (headcount, open requisitions, tenure) are as of the period end.
Change-versus-previous is shown only when the preceding equal-length window lies inside the data range.

## Confidentiality

* Everything runs locally; no external APIs, telemetry, cloud storage or web fonts. Server binds to `localhost`.
* Logs (`logs/app.log`) contain only counts, file/sheet names and states — never cell values or IDs.
* Dashboards show aggregates only; groups smaller than `MIN_GROUP_SIZE` (5) are hidden. Raw preview is opt-in,
  limited to a few rows, with identifier and personal-data columns masked.
* `.gitignore` excludes workbooks, CSVs, logs and secrets. Never commit HR data.
* Access control is the operating system's: keep the workbook in a folder only authorised people can read, back it
  up under your normal HR data policy, and do not expose the port beyond localhost. This app has no user accounts;
  anyone who can open the browser session on the machine can see the data.

## Business definitions that need approval

The data cannot supply these, so they start **empty** (Data Explorer → Business definitions): recruitment funnel
stage order, high-performer rating threshold (used only without a formal flag column), official rating-scale
maximum, PMS completion target, approved training budget. Dependent metrics show *Not available* until set.
Status wording (e.g. which statuses mean "filled") follows editable keyword rules in `config.STATUS_RULES`; the
**status audit** in Data Explorer shows how each raw value was treated.

## Not implemented / limits (so the docs match the code)

* Not calculated, and shown as such: hiring quality, skills & competencies, learning paths, training-needs table,
  strengths/development needs, succession/critical roles, new-hire retention cohort rate, retention-risk indicators
  (deliberately never provided).
* Multi-row headers and merged data cells are not reconstructed; fix the sheet or use the mapping override.
* PMS rates are computed per selected cycle (one row per employee per cycle assumed).
* Attrition is not annualised; it covers the selected period only.
* Excel serial numbers stored as plain numbers (not date-formatted) are not auto-converted to dates.

## Insight rules

| Insight | Rule |
|---|---|
| Positions filled up/down | last two consecutive calendar months in the data |
| Lowest funnel conversion | minimum stage-to-next conversion across the configured stages |
| Highest department attrition | max rate among departments with average headcount ≥ 5 |
| Outcome data missing | training hours present and no score column mapped |
| PMS completion vs target | compared only with a configured target; otherwise reported as "no target configured" |
| Data-quality warnings | sum of warning counts in the validation log |

Insights are descriptive; correlations are not presented as causes and no individual-level recommendations are made.

## KPI Definitions and Calculation Formulas

<!-- KPI-DOCS:BEGIN -->

_Generated from `services/kpi_registry.py` — do not edit by hand. All examples use fictional numbers and are not workbook data._

### Recruitment

**Default treatment of missing/duplicate/invalid records:** Rows without Requisition ID are excluded; exact duplicate rows removed (configurable); invalid/negative durations excluded and counted in Data Quality; missing values are never treated as zero.

#### Total requisitions  (`rec_requisitions`)

1. **Business meaning:** Requisitions opened in the period.
2. **Formula:** `COUNT DISTINCT requisition_id with open date in period`
3. **Numerator:** Distinct requisitions
4. **Denominator:** —
5. **Required columns:** Requisition ID; Open date (optional)
6. **Source:** Sheet(s) classified as 'recruitment' (see Data Explorer)
7. **Aggregation level / grain:** Requisition
8. **Reporting period:** Open date in selected period (all records if no open date)
9. **Missing/duplicate/invalid handling:** Rows without Requisition ID are excluded; exact duplicate rows removed (configurable); invalid/negative durations excluded and counted in Data Quality; missing values are never treated as zero.
10. **Definition status:** Standard
11. **Example (fictional):** Example: 12 distinct IDs opened in the period → 12

#### Positions filled  (`rec_filled`)

1. **Business meaning:** Requisitions whose normalised status is 'filled'.
2. **Formula:** `COUNT DISTINCT requisition_id WHERE status_norm = filled`
3. **Numerator:** Filled requisitions
4. **Denominator:** —
5. **Required columns:** Requisition ID; Status; Filled date/Open date
6. **Source:** Sheet(s) classified as 'recruitment' (see Data Explorer)
7. **Aggregation level / grain:** Requisition
8. **Reporting period:** Filled date in period (else open date)
9. **Missing/duplicate/invalid handling:** Rows without Requisition ID are excluded; exact duplicate rows removed (configurable); invalid/negative durations excluded and counted in Data Quality; missing values are never treated as zero.
10. **Definition status:** Requires approved business definition (status wording → 'filled' rules in config.STATUS_RULES)
11. **Example (fictional):** Example: 8 of 12 requisitions have status 'Closed – joined' → 8

#### New hires (recruitment)  (`rec_new_hires`)

1. **Business meaning:** Requisitions with a filled / offer-accepted date in the period.
2. **Formula:** `COUNT DISTINCT requisition_id WHERE filled_date in period`
3. **Numerator:** Requisitions with filled date
4. **Denominator:** —
5. **Required columns:** Requisition ID; Filled date
6. **Source:** Sheet(s) classified as 'recruitment' (see Data Explorer)
7. **Aggregation level / grain:** Requisition (one hire per requisition assumed)
8. **Reporting period:** Filled date in period
9. **Missing/duplicate/invalid handling:** Rows without Requisition ID are excluded; exact duplicate rows removed (configurable); invalid/negative durations excluded and counted in Data Quality; missing values are never treated as zero.
10. **Definition status:** Requires approved business definition
11. **Example (fictional):** Example: 7 filled dates in period → 7

#### Average time to hire  (`rec_time_to_hire`)

1. **Business meaning:** Mean days from requisition opening to filled date.
2. **Formula:** `Σ(filled_date − open_date) ÷ valid hires`
3. **Numerator:** Sum of valid durations (days)
4. **Denominator:** Number of valid hires
5. **Required columns:** Requisition ID; Open date; Filled date
6. **Source:** Sheet(s) classified as 'recruitment' (see Data Explorer)
7. **Aggregation level / grain:** Requisition
8. **Reporting period:** Filled date in period
9. **Missing/duplicate/invalid handling:** Rows without Requisition ID are excluded; exact duplicate rows removed (configurable); invalid/negative durations excluded and counted in Data Quality; missing values are never treated as zero.
10. **Definition status:** Requires approved business definition (start/end dates)
11. **Example (fictional):** Example: durations 30, 40, 50 days → 120 ÷ 3 = 40 days

#### Offer acceptance rate  (`rec_offer_acceptance`)

1. **Business meaning:** Share of decided offers that were accepted.
2. **Formula:** `Accepted ÷ (Accepted + Rejected + Declined) × 100`
3. **Numerator:** Accepted offers
4. **Denominator:** Offers with a recorded outcome
5. **Required columns:** Offer status (Candidate ID optional for de-duplication)
6. **Source:** Sheet(s) classified as 'recruitment' (see Data Explorer)
7. **Aggregation level / grain:** Offer (one row per offer/candidate)
8. **Reporting period:** Requisition open date in period (else filled date; all records if neither is mapped)
9. **Missing/duplicate/invalid handling:** Rows without Requisition ID are excluded; exact duplicate rows removed (configurable); invalid/negative durations excluded and counted in Data Quality; missing values are never treated as zero.
10. **Definition status:** Standard
11. **Example (fictional):** Example: 9 accepted, 3 declined → 9 ÷ 12 = 75.0%

#### Cost per hire  (`rec_cost_per_hire`)

1. **Business meaning:** Recruitment cost per filled requisition.
2. **Formula:** `Σ cost of filled requisitions ÷ number of filled requisitions with recorded cost`
3. **Numerator:** Recruitment cost (first value per requisition)
4. **Denominator:** Filled requisitions with recorded cost
5. **Required columns:** Requisition ID; Status; Recruitment cost
6. **Source:** Sheet(s) classified as 'recruitment' (see Data Explorer)
7. **Aggregation level / grain:** Requisition (cost recorded once per requisition)
8. **Reporting period:** Filled/open date in period
9. **Missing/duplicate/invalid handling:** Rows without Requisition ID are excluded; exact duplicate rows removed (configurable); invalid/negative durations excluded and counted in Data Quality; missing values are never treated as zero.
10. **Definition status:** Requires approved business definition (which costs are attributable)
11. **Example (fictional):** Example: costs 20,000 and 40,000 over 2 hires → 30,000 per hire

#### Open requisition ageing  (`rec_open_ageing`)

1. **Business meaning:** Average age of requisitions still open.
2. **Formula:** `Σ(reporting date − open date) ÷ open requisitions`
3. **Numerator:** Sum of days open
4. **Denominator:** Open requisitions
5. **Required columns:** Status; Open date
6. **Source:** Sheet(s) classified as 'recruitment' (see Data Explorer)
7. **Aggregation level / grain:** Requisition
8. **Reporting period:** Reporting date = end of selected period
9. **Missing/duplicate/invalid handling:** Rows without Requisition ID are excluded; exact duplicate rows removed (configurable); invalid/negative durations excluded and counted in Data Quality; missing values are never treated as zero.
10. **Definition status:** Standard
11. **Example (fictional):** Example: 10 and 30 days open → 20 days

#### Open requisitions  (`rec_open_count`)

1. **Business meaning:** Requisitions with normalised status 'open' opened on or before the reporting date.
2. **Formula:** `COUNT DISTINCT requisition_id WHERE status_norm = open AND open_date ≤ as-of`
3. **Numerator:** Open requisitions
4. **Denominator:** —
5. **Required columns:** Requisition ID; Status; Open date
6. **Source:** Sheet(s) classified as 'recruitment' (see Data Explorer)
7. **Aggregation level / grain:** Requisition
8. **Reporting period:** Reporting date = end of selected period
9. **Missing/duplicate/invalid handling:** Rows without Requisition ID are excluded; exact duplicate rows removed (configurable); invalid/negative durations excluded and counted in Data Quality; missing values are never treated as zero.
10. **Definition status:** Requires approved business definition
11. **Example (fictional):** Example: 9 open → 9

#### Requisitions by dimension / top roles  (`rec_by`)

1. **Business meaning:** Distinct requisitions (all or filled) per department, function, location, job title, gender.
2. **Formula:** `COUNT DISTINCT requisition_id GROUPED BY dimension`
3. **Numerator:** Requisitions in group
4. **Denominator:** —
5. **Required columns:** Requisition ID; dimension; Status (filled only)
6. **Source:** Sheet(s) classified as 'recruitment' (see Data Explorer)
7. **Aggregation level / grain:** Requisition
8. **Reporting period:** Open or filled date in period
9. **Missing/duplicate/invalid handling:** Rows without Requisition ID are excluded; exact duplicate rows removed (configurable); invalid/negative durations excluded and counted in Data Quality; missing values are never treated as zero.
10. **Definition status:** Standard
11. **Example (fictional):** Example: 5 filled 'Engineer' roles

#### Source-of-hire share  (`rec_source_share`)

1. **Business meaning:** Share of hires by sourcing channel.
2. **Formula:** `Hires from source ÷ hires with a valid source × 100`
3. **Numerator:** Hires from source
4. **Denominator:** Hires with valid source
5. **Required columns:** Requisition ID; Status; Source
6. **Source:** Sheet(s) classified as 'recruitment' (see Data Explorer)
7. **Aggregation level / grain:** Requisition
8. **Reporting period:** Filled/open date in period
9. **Missing/duplicate/invalid handling:** Rows without Requisition ID are excluded; exact duplicate rows removed (configurable); invalid/negative durations excluded and counted in Data Quality; missing values are never treated as zero.
10. **Definition status:** Standard
11. **Example (fictional):** Example: 6 of 10 hires from referrals → 60%

#### Hiring funnel conversion  (`rec_funnel_conversion`)

1. **Business meaning:** Progression between configured stages.
2. **Formula:** `Reached(next stage) ÷ Reached(stage) × 100, where Reached(stage) = records at that stage or later`
3. **Numerator:** Records reaching next stage
4. **Denominator:** Records reaching current stage
5. **Required columns:** Stage (Candidate ID optional); funnel order setting
6. **Source:** Sheet(s) classified as 'recruitment' (see Data Explorer)
7. **Aggregation level / grain:** Candidate/application
8. **Reporting period:** All records
9. **Missing/duplicate/invalid handling:** Rows without Requisition ID are excluded; exact duplicate rows removed (configurable); invalid/negative durations excluded and counted in Data Quality; missing values are never treated as zero.
10. **Definition status:** Requires approved business definition (stage order)
11. **Example (fictional):** Example: 40 reach Screening, 20 reach Interview → 50%

#### Recruitment monthly trend  (`rec_monthly_trend`)

1. **Business meaning:** Requisitions opened, positions filled and average time to hire by month.
2. **Formula:** `COUNT DISTINCT requisition_id GROUPED BY month(open_date | filled_date); mean days GROUPED BY month(filled_date)`
3. **Numerator:** —
4. **Denominator:** —
5. **Required columns:** Requisition ID; Open date; Filled date
6. **Source:** Sheet(s) classified as 'recruitment' (see Data Explorer)
7. **Aggregation level / grain:** Requisition × month
8. **Reporting period:** Calendar month
9. **Missing/duplicate/invalid handling:** Rows without Requisition ID are excluded; exact duplicate rows removed (configurable); invalid/negative durations excluded and counted in Data Quality; missing values are never treated as zero.
10. **Definition status:** Standard
11. **Example (fictional):** Example: 3 opened in March → bar of 3

### Employees and turnover

**Default treatment of missing/duplicate/invalid records:** Employees with no valid date of joining are excluded from date-based counts; distinct Employee IDs are counted (repeated IDs flagged); invalid dates excluded and counted.

#### Total headcount  (`emp_headcount`)

1. **Business meaning:** Employees active on the as-of date.
2. **Formula:** `COUNT DISTINCT employee_id WHERE hire_date ≤ as-of AND (exit_date empty OR exit_date > as-of)`
3. **Numerator:** Active employees
4. **Denominator:** —
5. **Required columns:** Employee ID; Date of joining; Date of exit (optional)
6. **Source:** Sheet(s) classified as 'employee' (see Data Explorer)
7. **Aggregation level / grain:** Employee
8. **Reporting period:** As-of date = end of selected period
9. **Missing/duplicate/invalid handling:** Employees with no valid date of joining are excluded from date-based counts; distinct Employee IDs are counted (repeated IDs flagged); invalid dates excluded and counted.
10. **Definition status:** Standard
11. **Example (fictional):** Example: 100 joined, 10 exited before the date → 90

#### New hires  (`emp_new_hires`)

1. **Business meaning:** Employees whose joining date falls in the period.
2. **Formula:** `COUNT DISTINCT employee_id WHERE hire_date in period`
3. **Numerator:** Employees joined
4. **Denominator:** —
5. **Required columns:** Date of joining
6. **Source:** Sheet(s) classified as 'employee' (see Data Explorer)
7. **Aggregation level / grain:** Employee
8. **Reporting period:** Joining date in period
9. **Missing/duplicate/invalid handling:** Employees with no valid date of joining are excluded from date-based counts; distinct Employee IDs are counted (repeated IDs flagged); invalid dates excluded and counted.
10. **Definition status:** Standard
11. **Example (fictional):** Example: 6 joining dates → 6

#### Employee exits  (`emp_exits`)

1. **Business meaning:** Employees whose exit date falls in the period.
2. **Formula:** `COUNT DISTINCT employee_id WHERE exit_date in period`
3. **Numerator:** Employees exited
4. **Denominator:** —
5. **Required columns:** Date of exit
6. **Source:** Sheet(s) classified as 'employee' (see Data Explorer)
7. **Aggregation level / grain:** Employee
8. **Reporting period:** Exit date in period
9. **Missing/duplicate/invalid handling:** Employees with no valid date of joining are excluded from date-based counts; distinct Employee IDs are counted (repeated IDs flagged); invalid dates excluded and counted.
10. **Definition status:** Standard
11. **Example (fictional):** Example: 4 exit dates → 4

#### Attrition rate  (`emp_attrition`)

1. **Business meaning:** Exits relative to average headcount (not annualised).
2. **Formula:** `Exits ÷ ((opening + closing headcount) ÷ 2) × 100`
3. **Numerator:** Exits in period
4. **Denominator:** Average of opening headcount (day before period start) and closing headcount (period end)
5. **Required columns:** Date of joining; Date of exit
6. **Source:** Sheet(s) classified as 'employee' (see Data Explorer)
7. **Aggregation level / grain:** Employee
8. **Reporting period:** Selected period
9. **Missing/duplicate/invalid handling:** Employees with no valid date of joining are excluded from date-based counts; distinct Employee IDs are counted (repeated IDs flagged); invalid dates excluded and counted.
10. **Definition status:** Requires approved business definition (average-headcount method: opening/closing)
11. **Example (fictional):** Example: 5 exits, opening 95, closing 105 → 5 ÷ 100 = 5.0%

#### Average tenure  (`emp_tenure`)

1. **Business meaning:** Mean years of service of active employees.
2. **Formula:** `Σ((as-of − hire_date) ÷ 365.25) ÷ active employees`
3. **Numerator:** Sum of tenure years
4. **Denominator:** Active employees with valid tenure
5. **Required columns:** Date of joining
6. **Source:** Sheet(s) classified as 'employee' (see Data Explorer)
7. **Aggregation level / grain:** Employee
8. **Reporting period:** As-of date
9. **Missing/duplicate/invalid handling:** Employees with no valid date of joining are excluded from date-based counts; distinct Employee IDs are counted (repeated IDs flagged); invalid dates excluded and counted.
10. **Definition status:** Standard
11. **Example (fictional):** Example: tenures 1, 2, 6 yrs → 3.0 yrs

#### Employee distribution  (`emp_distribution`)

1. **Business meaning:** Share of active employees by category (function, type, gender, …).
2. **Formula:** `Employees in category ÷ active employees × 100`
3. **Numerator:** Employees in category
4. **Denominator:** Active employees
5. **Required columns:** Date of joining + the category column
6. **Source:** Sheet(s) classified as 'employee' (see Data Explorer)
7. **Aggregation level / grain:** Employee
8. **Reporting period:** As-of date
9. **Missing/duplicate/invalid handling:** Employees with no valid date of joining are excluded from date-based counts; distinct Employee IDs are counted (repeated IDs flagged); invalid dates excluded and counted.
10. **Definition status:** Standard
11. **Example (fictional):** Example: 30 of 120 in Finance → 25%

#### Tenure distribution  (`emp_tenure_bands`)

1. **Business meaning:** Active employees by configured tenure band (<1, 1–3, 3–5, 5–10, 10+ yrs).
2. **Formula:** `Employees in band ÷ active employees × 100`
3. **Numerator:** Employees in band
4. **Denominator:** Active employees
5. **Required columns:** Date of joining
6. **Source:** Sheet(s) classified as 'employee' (see Data Explorer)
7. **Aggregation level / grain:** Employee
8. **Reporting period:** As-of date
9. **Missing/duplicate/invalid handling:** Employees with no valid date of joining are excluded from date-based counts; distinct Employee IDs are counted (repeated IDs flagged); invalid dates excluded and counted.
10. **Definition status:** Band edges are configuration (config.TENURE_BANDS_YEARS)
11. **Example (fictional):** Example: 12 of 60 in 1–3 yrs → 20%

#### Headcount trend  (`emp_headcount_trend`)

1. **Business meaning:** Month-end headcount.
2. **Formula:** `Headcount formula evaluated at each month end`
3. **Numerator:** —
4. **Denominator:** —
5. **Required columns:** Date of joining; Date of exit (optional)
6. **Source:** Sheet(s) classified as 'employee' (see Data Explorer)
7. **Aggregation level / grain:** Employee × month-end
8. **Reporting period:** Selected period
9. **Missing/duplicate/invalid handling:** Employees with no valid date of joining are excluded from date-based counts; distinct Employee IDs are counted (repeated IDs flagged); invalid dates excluded and counted.
10. **Definition status:** Standard
11. **Example (fictional):** Example: month-end values 90, 93, 91

#### Attrition by dimension  (`emp_attrition_by`)

1. **Business meaning:** Attrition rate per department/type/location; groups with average headcount < minimum size are suppressed.
2. **Formula:** `Exits in group ÷ average group headcount × 100`
3. **Numerator:** Exits in group
4. **Denominator:** Average group headcount
5. **Required columns:** Date of joining; Date of exit; dimension column
6. **Source:** Sheet(s) classified as 'employee' (see Data Explorer)
7. **Aggregation level / grain:** Employee
8. **Reporting period:** Selected period
9. **Missing/duplicate/invalid handling:** Employees with no valid date of joining are excluded from date-based counts; distinct Employee IDs are counted (repeated IDs flagged); invalid dates excluded and counted.
10. **Definition status:** Requires approved business definition
11. **Example (fictional):** Example: 2 exits ÷ 20 average → 10%

#### Voluntary vs involuntary exits  (`emp_exit_mix`)

1. **Business meaning:** Exit counts by normalised exit type.
2. **Formula:** `COUNT exits GROUPED BY exit_type_norm`
3. **Numerator:** Exits in type
4. **Denominator:** —
5. **Required columns:** Date of exit; Exit type
6. **Source:** Sheet(s) classified as 'employee' (see Data Explorer)
7. **Aggregation level / grain:** Employee
8. **Reporting period:** Selected period
9. **Missing/duplicate/invalid handling:** Employees with no valid date of joining are excluded from date-based counts; distinct Employee IDs are counted (repeated IDs flagged); invalid dates excluded and counted.
10. **Definition status:** Requires approved business definition (voluntary/involuntary wording rules)
11. **Example (fictional):** Example: 6 voluntary, 2 involuntary

#### Exits trend  (`emp_exits_trend`)

1. **Business meaning:** Exits per month or quarter.
2. **Formula:** `COUNT DISTINCT employee_id GROUPED BY period(exit_date)`
3. **Numerator:** Exits in period
4. **Denominator:** —
5. **Required columns:** Date of exit
6. **Source:** Sheet(s) classified as 'employee' (see Data Explorer)
7. **Aggregation level / grain:** Employee × period
8. **Reporting period:** Selected period
9. **Missing/duplicate/invalid handling:** Employees with no valid date of joining are excluded from date-based counts; distinct Employee IDs are counted (repeated IDs flagged); invalid dates excluded and counted.
10. **Definition status:** Standard
11. **Example (fictional):** Example: 2 exits in March

#### Exit reasons  (`emp_exit_reasons`)

1. **Business meaning:** Exit counts by recorded reason.
2. **Formula:** `COUNT exits GROUPED BY exit_reason`
3. **Numerator:** Exits with reason
4. **Denominator:** —
5. **Required columns:** Date of exit; Exit reason
6. **Source:** Sheet(s) classified as 'employee' (see Data Explorer)
7. **Aggregation level / grain:** Employee
8. **Reporting period:** Selected period
9. **Missing/duplicate/invalid handling:** Employees with no valid date of joining are excluded from date-based counts; distinct Employee IDs are counted (repeated IDs flagged); invalid dates excluded and counted.
10. **Definition status:** Standard
11. **Example (fictional):** Example: 3 exits cite 'Better opportunity'

#### Exits by tenure band  (`emp_exit_tenure`)

1. **Business meaning:** Exits grouped by tenure at exit (counts, not rates).
2. **Formula:** `COUNT exits GROUPED BY band((exit_date − hire_date) ÷ 365.25)`
3. **Numerator:** Exits in band
4. **Denominator:** —
5. **Required columns:** Date of joining; Date of exit
6. **Source:** Sheet(s) classified as 'employee' (see Data Explorer)
7. **Aggregation level / grain:** Employee
8. **Reporting period:** Selected period
9. **Missing/duplicate/invalid handling:** Employees with no valid date of joining are excluded from date-based counts; distinct Employee IDs are counted (repeated IDs flagged); invalid dates excluded and counted.
10. **Definition status:** Standard
11. **Example (fictional):** Example: 4 exits at <1 yr

### Training

**Default treatment of missing/duplicate/invalid records:** Non-numeric/negative hours and costs are excluded; exact duplicate attendance rows removed (configurable); unavailable (not 0) if the column is missing.

#### Total training hours  (`trn_hours`)

1. **Business meaning:** Sum of recorded hours.
2. **Formula:** `Σ hours over attendance/completion records`
3. **Numerator:** Sum of hours
4. **Denominator:** —
5. **Required columns:** Training hours (Date optional)
6. **Source:** Sheet(s) classified as 'training' (see Data Explorer)
7. **Aggregation level / grain:** One row per attendance record (hours per participant)
8. **Reporting period:** Training date in period
9. **Missing/duplicate/invalid handling:** Non-numeric/negative hours and costs are excluded; exact duplicate attendance rows removed (configurable); unavailable (not 0) if the column is missing.
10. **Definition status:** Requires approved business definition (record grain)
11. **Example (fictional):** Example: 3 records × 8 h → 24 h

#### Employees trained  (`trn_employees`)

1. **Business meaning:** Distinct participants.
2. **Formula:** `COUNT DISTINCT employee_id (status 'completed' only when a status column exists)`
3. **Numerator:** Distinct participants
4. **Denominator:** —
5. **Required columns:** Employee ID; Completion status (optional)
6. **Source:** Sheet(s) classified as 'training' (see Data Explorer)
7. **Aggregation level / grain:** Employee
8. **Reporting period:** Training date in period
9. **Missing/duplicate/invalid handling:** Non-numeric/negative hours and costs are excluded; exact duplicate attendance rows removed (configurable); unavailable (not 0) if the column is missing.
10. **Definition status:** Requires approved business definition (participation definition)
11. **Example (fictional):** Example: 40 attendance rows for 25 people → 25

#### Training participation rate  (`trn_participation`)

1. **Business meaning:** Eligible employees who were trained.
2. **Formula:** `Distinct trained eligible employees ÷ eligible employees × 100`
3. **Numerator:** Trained ∩ eligible
4. **Denominator:** Eligible employees (active on as-of date in the employee sheet)
5. **Required columns:** Training: Employee ID; Employee sheet: Employee ID, Date of joining
6. **Source:** Sheet(s) classified as 'training' (see Data Explorer)
7. **Aggregation level / grain:** Employee
8. **Reporting period:** Training date in period; eligibility at period end
9. **Missing/duplicate/invalid handling:** Non-numeric/negative hours and costs are excluded; exact duplicate attendance rows removed (configurable); unavailable (not 0) if the column is missing.
10. **Definition status:** Requires approved business definition (eligible population)
11. **Example (fictional):** Example: 60 of 80 → 75%

#### Average training hours per employee  (`trn_avg_hours`)

1. **Business meaning:** Training hours spread over eligible employees.
2. **Formula:** `Σ hours ÷ eligible employees`
3. **Numerator:** Σ hours
4. **Denominator:** Eligible employees
5. **Required columns:** Hours; Employee sheet
6. **Source:** Sheet(s) classified as 'training' (see Data Explorer)
7. **Aggregation level / grain:** Employee
8. **Reporting period:** Training date in period
9. **Missing/duplicate/invalid handling:** Non-numeric/negative hours and costs are excluded; exact duplicate attendance rows removed (configurable); unavailable (not 0) if the column is missing.
10. **Definition status:** Requires approved business definition
11. **Example (fictional):** Example: 400 h ÷ 80 → 5.0 h

#### Certification rate  (`trn_cert_rate`)

1. **Business meaning:** Employees certified among those with a recorded certification outcome.
2. **Formula:** `Employees with certification = yes ÷ employees with a yes/no certification value × 100`
3. **Numerator:** Certified employees
4. **Denominator:** Employees with recorded certification flag
5. **Required columns:** Employee ID; Certification
6. **Source:** Sheet(s) classified as 'training' (see Data Explorer)
7. **Aggregation level / grain:** Employee
8. **Reporting period:** Training date in period
9. **Missing/duplicate/invalid handling:** Non-numeric/negative hours and costs are excluded; exact duplicate attendance rows removed (configurable); unavailable (not 0) if the column is missing.
10. **Definition status:** Requires approved business definition (who is required to certify)
11. **Example (fictional):** Example: 18 of 24 → 75%

#### Training effectiveness  (`trn_effectiveness`)

1. **Business meaning:** Average post − pre score improvement, else average assessment score. Attendance is never used.
2. **Formula:** `mean(post_score − pre_score) | mean(assessment_score)`
3. **Numerator:** Σ score change | Σ score
4. **Denominator:** Records with scores
5. **Required columns:** Pre/Post score or Assessment score
6. **Source:** Sheet(s) classified as 'training' (see Data Explorer)
7. **Aggregation level / grain:** Record
8. **Reporting period:** Training date in period
9. **Missing/duplicate/invalid handling:** Non-numeric/negative hours and costs are excluded; exact duplicate attendance rows removed (configurable); unavailable (not 0) if the column is missing.
10. **Definition status:** Requires approved business definition (evaluation instrument)
11. **Example (fictional):** Example: +10, +20 → +15.0 pts

#### Total training cost  (`trn_cost`)

1. **Business meaning:** Sum of recorded cost.
2. **Formula:** `Σ cost`
3. **Numerator:** Σ cost
4. **Denominator:** —
5. **Required columns:** Training cost
6. **Source:** Sheet(s) classified as 'training' (see Data Explorer)
7. **Aggregation level / grain:** Record
8. **Reporting period:** Training date in period
9. **Missing/duplicate/invalid handling:** Non-numeric/negative hours and costs are excluded; exact duplicate attendance rows removed (configurable); unavailable (not 0) if the column is missing.
10. **Definition status:** Standard
11. **Example (fictional):** Example: 10,000 + 5,000 → 15,000

#### Training cost per employee  (`trn_cost_per_employee`)

1. **Business meaning:** Cost over eligible employees.
2. **Formula:** `Σ cost ÷ eligible employees`
3. **Numerator:** Σ cost
4. **Denominator:** Eligible employees
5. **Required columns:** Training cost; Employee sheet
6. **Source:** Sheet(s) classified as 'training' (see Data Explorer)
7. **Aggregation level / grain:** Employee
8. **Reporting period:** Training date in period
9. **Missing/duplicate/invalid handling:** Non-numeric/negative hours and costs are excluded; exact duplicate attendance rows removed (configurable); unavailable (not 0) if the column is missing.
10. **Definition status:** Requires approved business definition
11. **Example (fictional):** Example: 150,000 ÷ 100 → 1,500

#### Budget utilisation  (`trn_budget_util`)

1. **Business meaning:** Actual spend against approved budget.
2. **Formula:** `Σ cost ÷ approved budget × 100`
3. **Numerator:** Σ cost
4. **Denominator:** Approved budget (user-entered, else sum of budget column)
5. **Required columns:** Training cost; Budget (or setting)
6. **Source:** Sheet(s) classified as 'training' (see Data Explorer)
7. **Aggregation level / grain:** Record
8. **Reporting period:** Training date in period
9. **Missing/duplicate/invalid handling:** Non-numeric/negative hours and costs are excluded; exact duplicate attendance rows removed (configurable); unavailable (not 0) if the column is missing.
10. **Definition status:** Requires approved business definition (approved budget)
11. **Example (fictional):** Example: 60,000 ÷ 80,000 → 75%

#### Training by category / mode / location / programme  (`trn_breakdown`)

1. **Business meaning:** Hours and distinct participants by dimension.
2. **Formula:** `Σ hours; COUNT DISTINCT employee_id GROUPED BY dimension`
3. **Numerator:** —
4. **Denominator:** —
5. **Required columns:** Hours; dimension column
6. **Source:** Sheet(s) classified as 'training' (see Data Explorer)
7. **Aggregation level / grain:** Record
8. **Reporting period:** Training date in period
9. **Missing/duplicate/invalid handling:** Non-numeric/negative hours and costs are excluded; exact duplicate attendance rows removed (configurable); unavailable (not 0) if the column is missing.
10. **Definition status:** Standard
11. **Example (fictional):** Example: 'Online' 40 h

#### Training effectiveness by group  (`trn_effect_by`)

1. **Business meaning:** Mean score improvement (post − pre) or mean assessment score per programme/category.
2. **Formula:** `mean(post − pre) | mean(assessment_score) GROUPED BY dimension`
3. **Numerator:** Σ score change
4. **Denominator:** Records with scores
5. **Required columns:** Scores; dimension
6. **Source:** Sheet(s) classified as 'training' (see Data Explorer)
7. **Aggregation level / grain:** Record
8. **Reporting period:** Training date in period
9. **Missing/duplicate/invalid handling:** Non-numeric/negative hours and costs are excluded; exact duplicate attendance rows removed (configurable); unavailable (not 0) if the column is missing.
10. **Definition status:** Requires approved business definition
11. **Example (fictional):** Example: +12 pts for 'Safety'

#### Training completion status mix  (`trn_completion_mix`)

1. **Business meaning:** Records by normalised completion status.
2. **Formula:** `COUNT records GROUPED BY completion_status_norm`
3. **Numerator:** Records in status
4. **Denominator:** —
5. **Required columns:** Completion status
6. **Source:** Sheet(s) classified as 'training' (see Data Explorer)
7. **Aggregation level / grain:** Record
8. **Reporting period:** Training date in period
9. **Missing/duplicate/invalid handling:** Non-numeric/negative hours and costs are excluded; exact duplicate attendance rows removed (configurable); unavailable (not 0) if the column is missing.
10. **Definition status:** Requires approved business definition
11. **Example (fictional):** Example: 80 completed, 5 not completed

#### Training monthly trend  (`trn_monthly`)

1. **Business meaning:** Hours and distinct participants by month.
2. **Formula:** `Σ hours; COUNT DISTINCT employee_id GROUPED BY month(date)`
3. **Numerator:** —
4. **Denominator:** —
5. **Required columns:** Training date; Hours; Employee ID
6. **Source:** Sheet(s) classified as 'training' (see Data Explorer)
7. **Aggregation level / grain:** Record × month
8. **Reporting period:** Calendar month
9. **Missing/duplicate/invalid handling:** Non-numeric/negative hours and costs are excluded; exact duplicate attendance rows removed (configurable); unavailable (not 0) if the column is missing.
10. **Definition status:** Standard
11. **Example (fictional):** Example: March 120 h

### Performance management (PMS)

**Default treatment of missing/duplicate/invalid records:** Ratings outside the configured scale (if set) excluded; one row per employee per cycle assumed (select a cycle when several exist); missing ratings excluded.

#### Performance-eligible employees  (`pms_eligible`)

1. **Business meaning:** Distinct employees in the performance data (selected cycle).
2. **Formula:** `COUNT DISTINCT employee_id`
3. **Numerator:** Distinct employees
4. **Denominator:** —
5. **Required columns:** Employee ID
6. **Source:** Sheet(s) classified as 'performance' (see Data Explorer)
7. **Aggregation level / grain:** Employee
8. **Reporting period:** Selected cycle
9. **Missing/duplicate/invalid handling:** Ratings outside the configured scale (if set) excluded; one row per employee per cycle assumed (select a cycle when several exist); missing ratings excluded.
10. **Definition status:** Requires approved business definition (eligibility rules)
11. **Example (fictional):** Example: 150 listed → 150

#### Completed reviews  (`pms_completed`)

1. **Business meaning:** Employees whose normalised review status is 'completed'.
2. **Formula:** `COUNT DISTINCT employee_id WHERE review_status_norm = completed`
3. **Numerator:** Completed
4. **Denominator:** —
5. **Required columns:** Employee ID; Review status
6. **Source:** Sheet(s) classified as 'performance' (see Data Explorer)
7. **Aggregation level / grain:** Employee
8. **Reporting period:** Selected cycle
9. **Missing/duplicate/invalid handling:** Ratings outside the configured scale (if set) excluded; one row per employee per cycle assumed (select a cycle when several exist); missing ratings excluded.
10. **Definition status:** Requires approved business definition
11. **Example (fictional):** Example: 120 completed → 120

#### PMS completion rate  (`pms_completion`)

1. **Business meaning:** Completed ÷ eligible.
2. **Formula:** `Completed reviews ÷ eligible employees × 100`
3. **Numerator:** Completed reviews
4. **Denominator:** Eligible employees
5. **Required columns:** Employee ID; Review status
6. **Source:** Sheet(s) classified as 'performance' (see Data Explorer)
7. **Aggregation level / grain:** Employee
8. **Reporting period:** Selected cycle
9. **Missing/duplicate/invalid handling:** Ratings outside the configured scale (if set) excluded; one row per employee per cycle assumed (select a cycle when several exist); missing ratings excluded.
10. **Definition status:** Standard
11. **Example (fictional):** Example: 120 ÷ 150 → 80%

#### Average performance rating  (`pms_avg_rating`)

1. **Business meaning:** Mean of numeric ratings on the workbook's own scale.
2. **Formula:** `Σ valid ratings ÷ count of valid ratings`
3. **Numerator:** Σ ratings
4. **Denominator:** Valid ratings
5. **Required columns:** Rating
6. **Source:** Sheet(s) classified as 'performance' (see Data Explorer)
7. **Aggregation level / grain:** Rating record
8. **Reporting period:** Selected cycle
9. **Missing/duplicate/invalid handling:** Ratings outside the configured scale (if set) excluded; one row per employee per cycle assumed (select a cycle when several exist); missing ratings excluded.
10. **Definition status:** Standard
11. **Example (fictional):** Example: 3, 4, 5 → 4.00

#### High performers  (`pms_high_performers`)

1. **Business meaning:** Employees flagged as high performers in the workbook, or with rating ≥ approved threshold.
2. **Formula:** `COUNT DISTINCT employee_id WHERE flag = yes | rating ≥ threshold`
3. **Numerator:** High performers
4. **Denominator:** —
5. **Required columns:** High-performer flag or Rating + threshold setting
6. **Source:** Sheet(s) classified as 'performance' (see Data Explorer)
7. **Aggregation level / grain:** Employee
8. **Reporting period:** Selected cycle
9. **Missing/duplicate/invalid handling:** Ratings outside the configured scale (if set) excluded; one row per employee per cycle assumed (select a cycle when several exist); missing ratings excluded.
10. **Definition status:** Requires approved business definition (threshold)
11. **Example (fictional):** Example: threshold 4.5 → 12 employees

#### High-performer share  (`pms_high_pct`)

1. **Business meaning:** High performers ÷ eligible.
2. **Formula:** `High performers ÷ eligible employees × 100`
3. **Numerator:** High performers
4. **Denominator:** Eligible employees
5. **Required columns:** as above
6. **Source:** Sheet(s) classified as 'performance' (see Data Explorer)
7. **Aggregation level / grain:** Employee
8. **Reporting period:** Selected cycle
9. **Missing/duplicate/invalid handling:** Ratings outside the configured scale (if set) excluded; one row per employee per cycle assumed (select a cycle when several exist); missing ratings excluded.
10. **Definition status:** Requires approved business definition
11. **Example (fictional):** Example: 12 ÷ 150 → 8%

#### Goal achievement rate  (`pms_goal_rate`)

1. **Business meaning:** Achieved goals ÷ assessable goals.
2. **Formula:** `Σ goals achieved ÷ Σ goals set × 100 (rows with goals set > 0 and achieved ≤ set)`
3. **Numerator:** Σ goals achieved
4. **Denominator:** Σ goals set
5. **Required columns:** Goals set; Goals achieved
6. **Source:** Sheet(s) classified as 'performance' (see Data Explorer)
7. **Aggregation level / grain:** Employee
8. **Reporting period:** Selected cycle
9. **Missing/duplicate/invalid handling:** Ratings outside the configured scale (if set) excluded; one row per employee per cycle assumed (select a cycle when several exist); missing ratings excluded.
10. **Definition status:** Requires approved business definition
11. **Example (fictional):** Example: 36 ÷ 48 → 75%

#### IDPs created  (`pms_idp`)

1. **Business meaning:** Employees with an IDP (yes/no column), else sum of an IDP count column.
2. **Formula:** `COUNT DISTINCT employee_id WHERE idp = yes | Σ idp`
3. **Numerator:** IDPs
4. **Denominator:** Eligible employees (coverage shown in detail)
5. **Required columns:** IDP
6. **Source:** Sheet(s) classified as 'performance' (see Data Explorer)
7. **Aggregation level / grain:** Employee
8. **Reporting period:** Selected cycle
9. **Missing/duplicate/invalid handling:** Ratings outside the configured scale (if set) excluded; one row per employee per cycle assumed (select a cycle when several exist); missing ratings excluded.
10. **Definition status:** Requires approved business definition
11. **Example (fictional):** Example: 90 of 150 → 90 (60% coverage)

#### Rating distribution  (`pms_rating_dist`)

1. **Business meaning:** Employees by rating value.
2. **Formula:** `COUNT DISTINCT employee_id GROUPED BY rating`
3. **Numerator:** Employees at rating
4. **Denominator:** Rated employees
5. **Required columns:** Employee ID; Rating
6. **Source:** Sheet(s) classified as 'performance' (see Data Explorer)
7. **Aggregation level / grain:** Employee
8. **Reporting period:** Selected cycle
9. **Missing/duplicate/invalid handling:** Ratings outside the configured scale (if set) excluded; one row per employee per cycle assumed (select a cycle when several exist); missing ratings excluded.
10. **Definition status:** Standard
11. **Example (fictional):** Example: 40 at rating 3

#### Rating by function/level/age group  (`pms_by`)

1. **Business meaning:** Average rating per group; groups below minimum size suppressed.
2. **Formula:** `mean(rating) GROUPED BY dimension`
3. **Numerator:** Σ ratings
4. **Denominator:** Rated employees in group
5. **Required columns:** Rating; dimension
6. **Source:** Sheet(s) classified as 'performance' (see Data Explorer)
7. **Aggregation level / grain:** Employee
8. **Reporting period:** Selected cycle
9. **Missing/duplicate/invalid handling:** Ratings outside the configured scale (if set) excluded; one row per employee per cycle assumed (select a cycle when several exist); missing ratings excluded.
10. **Definition status:** Standard
11. **Example (fictional):** Example: 3.6 for 25 employees

#### PMS cycle progress  (`pms_status_counts`)

1. **Business meaning:** Employees by normalised review status (overall or by dimension).
2. **Formula:** `COUNT DISTINCT employee_id GROUPED BY review_status_norm [, dimension]`
3. **Numerator:** Employees in status
4. **Denominator:** —
5. **Required columns:** Employee ID; Review status
6. **Source:** Sheet(s) classified as 'performance' (see Data Explorer)
7. **Aggregation level / grain:** Employee
8. **Reporting period:** Selected cycle
9. **Missing/duplicate/invalid handling:** Ratings outside the configured scale (if set) excluded; one row per employee per cycle assumed (select a cycle when several exist); missing ratings excluded.
10. **Definition status:** Requires approved business definition
11. **Example (fictional):** Example: 120 completed, 30 pending

#### Rating trend  (`pms_trend`)

1. **Business meaning:** Average rating per cycle (or review quarter).
2. **Formula:** `mean(rating) GROUPED BY cycle | quarter(review_date)`
3. **Numerator:** Σ ratings
4. **Denominator:** Ratings in cycle
5. **Required columns:** Rating; Cycle or Review date
6. **Source:** Sheet(s) classified as 'performance' (see Data Explorer)
7. **Aggregation level / grain:** Rating record
8. **Reporting period:** Each cycle
9. **Missing/duplicate/invalid handling:** Ratings outside the configured scale (if set) excluded; one row per employee per cycle assumed (select a cycle when several exist); missing ratings excluded.
10. **Definition status:** Standard
11. **Example (fictional):** Example: 3.4 then 3.6

### Employee relations and engagement

**Default treatment of missing/duplicate/invalid records:** Cases without Case ID excluded; invalid dates excluded; groups below the minimum size are suppressed in aggregate views.

#### Cases raised  (`rel_cases`)

1. **Business meaning:** Distinct cases opened in the period.
2. **Formula:** `COUNT DISTINCT case_id WHERE open_date in period`
3. **Numerator:** Cases
4. **Denominator:** —
5. **Required columns:** Case ID; Open date
6. **Source:** Sheet(s) classified as 'relations' (see Data Explorer)
7. **Aggregation level / grain:** Case
8. **Reporting period:** Open date in period
9. **Missing/duplicate/invalid handling:** Cases without Case ID excluded; invalid dates excluded; groups below the minimum size are suppressed in aggregate views.
10. **Definition status:** Standard
11. **Example (fictional):** Example: 14 → 14

#### Open cases  (`rel_open`)

1. **Business meaning:** Cases with normalised status 'open'.
2. **Formula:** `COUNT DISTINCT case_id WHERE status_norm = open`
3. **Numerator:** Open cases
4. **Denominator:** —
5. **Required columns:** Case ID; Status
6. **Source:** Sheet(s) classified as 'relations' (see Data Explorer)
7. **Aggregation level / grain:** Case
8. **Reporting period:** Open date in period
9. **Missing/duplicate/invalid handling:** Cases without Case ID excluded; invalid dates excluded; groups below the minimum size are suppressed in aggregate views.
10. **Definition status:** Requires approved business definition
11. **Example (fictional):** Example: 4

#### Closed cases  (`rel_closed`)

1. **Business meaning:** Cases with normalised status 'closed'.
2. **Formula:** `COUNT DISTINCT case_id WHERE status_norm = closed`
3. **Numerator:** Closed cases
4. **Denominator:** —
5. **Required columns:** Case ID; Status
6. **Source:** Sheet(s) classified as 'relations' (see Data Explorer)
7. **Aggregation level / grain:** Case
8. **Reporting period:** Open date in period
9. **Missing/duplicate/invalid handling:** Cases without Case ID excluded; invalid dates excluded; groups below the minimum size are suppressed in aggregate views.
10. **Definition status:** Requires approved business definition
11. **Example (fictional):** Example: 9

#### Pending cases  (`rel_pending`)

1. **Business meaning:** Cases with normalised status 'pending'.
2. **Formula:** `COUNT DISTINCT case_id WHERE status_norm = pending`
3. **Numerator:** Pending cases
4. **Denominator:** —
5. **Required columns:** Case ID; Status
6. **Source:** Sheet(s) classified as 'relations' (see Data Explorer)
7. **Aggregation level / grain:** Case
8. **Reporting period:** Open date in period
9. **Missing/duplicate/invalid handling:** Cases without Case ID excluded; invalid dates excluded; groups below the minimum size are suppressed in aggregate views.
10. **Definition status:** Requires approved business definition
11. **Example (fictional):** Example: 1

#### Case resolution rate  (`rel_resolution_rate`)

1. **Business meaning:** Closed share of cases opened in the period (cohort = opened in period).
2. **Formula:** `Closed cases in cohort ÷ cases in cohort × 100`
3. **Numerator:** Closed cases
4. **Denominator:** Cases opened in period
5. **Required columns:** Case ID; Status; Open date
6. **Source:** Sheet(s) classified as 'relations' (see Data Explorer)
7. **Aggregation level / grain:** Case
8. **Reporting period:** Open date in period
9. **Missing/duplicate/invalid handling:** Cases without Case ID excluded; invalid dates excluded; groups below the minimum size are suppressed in aggregate views.
10. **Definition status:** Requires approved business definition (cohort definition)
11. **Example (fictional):** Example: 9 ÷ 14 → 64.3%

#### Average resolution time  (`rel_resolution_days`)

1. **Business meaning:** Mean days from opening to closing.
2. **Formula:** `Σ(close_date − open_date) ÷ closed cases with both dates`
3. **Numerator:** Σ days
4. **Denominator:** Closed cases with valid dates
5. **Required columns:** Open date; Close date
6. **Source:** Sheet(s) classified as 'relations' (see Data Explorer)
7. **Aggregation level / grain:** Case
8. **Reporting period:** Open date in period
9. **Missing/duplicate/invalid handling:** Cases without Case ID excluded; invalid dates excluded; groups below the minimum size are suppressed in aggregate views.
10. **Definition status:** Standard
11. **Example (fictional):** Example: 5, 15 days → 10 days

#### Average engagement score  (`rel_engagement`)

1. **Business meaning:** Mean of valid scores on the survey's own scale.
2. **Formula:** `Σ valid scores ÷ count of valid scores`
3. **Numerator:** Σ scores
4. **Denominator:** Valid scores
5. **Required columns:** Engagement score
6. **Source:** Sheet(s) classified as 'relations' (see Data Explorer)
7. **Aggregation level / grain:** Response
8. **Reporting period:** All records
9. **Missing/duplicate/invalid handling:** Cases without Case ID excluded; invalid dates excluded; groups below the minimum size are suppressed in aggregate views.
10. **Definition status:** Requires approved business definition (scale and aggregation)
11. **Example (fictional):** Example: 3.5, 4.5 → 4.00

#### Survey response rate  (`rel_response_rate`)

1. **Business meaning:** Respondents ÷ invitees.
2. **Formula:** `Σ responded ÷ Σ invited × 100 (rows with invited > 0 and responded ≤ invited)`
3. **Numerator:** Respondents
4. **Denominator:** Invitees
5. **Required columns:** Invited; Responded
6. **Source:** Sheet(s) classified as 'relations' (see Data Explorer)
7. **Aggregation level / grain:** Survey group
8. **Reporting period:** All records
9. **Missing/duplicate/invalid handling:** Cases without Case ID excluded; invalid dates excluded; groups below the minimum size are suppressed in aggregate views.
10. **Definition status:** Standard
11. **Example (fictional):** Example: 80 ÷ 100 → 80%

#### Cases trend  (`rel_monthly`)

1. **Business meaning:** Cases opened per month.
2. **Formula:** `COUNT DISTINCT case_id GROUPED BY month(open_date)`
3. **Numerator:** Cases
4. **Denominator:** —
5. **Required columns:** Case ID; Open date
6. **Source:** Sheet(s) classified as 'relations' (see Data Explorer)
7. **Aggregation level / grain:** Case × month
8. **Reporting period:** Open date in period
9. **Missing/duplicate/invalid handling:** Cases without Case ID excluded; invalid dates excluded; groups below the minimum size are suppressed in aggregate views.
10. **Definition status:** Standard
11. **Example (fictional):** Example: 3 cases in March

#### Cases by category  (`rel_categories`)

1. **Business meaning:** Distinct cases per issue category; small groups suppressed.
2. **Formula:** `COUNT DISTINCT case_id GROUPED BY category`
3. **Numerator:** Cases in category
4. **Denominator:** —
5. **Required columns:** Case ID; Issue category
6. **Source:** Sheet(s) classified as 'relations' (see Data Explorer)
7. **Aggregation level / grain:** Case
8. **Reporting period:** Open date in period
9. **Missing/duplicate/invalid handling:** Cases without Case ID excluded; invalid dates excluded; groups below the minimum size are suppressed in aggregate views.
10. **Definition status:** Standard
11. **Example (fictional):** Example: 6 'Workplace conduct'

### Comparison and change

**Default treatment of missing/duplicate/invalid records:** Shown only if the previous period lies fully inside the observed data range and the previous value exists.

#### Absolute change  (`chg_abs`)

1. **Business meaning:** Current − previous period.
2. **Formula:** `Current − Previous`
3. **Numerator:** Current
4. **Denominator:** —
5. **Required columns:** Any period metric
6. **Source:** Any metric above
7. **Aggregation level / grain:** —
8. **Reporting period:** Current vs immediately preceding equal-length period
9. **Missing/duplicate/invalid handling:** Shown only if the previous period lies fully inside the observed data range and the previous value exists.
10. **Definition status:** Standard
11. **Example (fictional):** Example: 12 − 10 = +2

#### Percentage change  (`chg_pct`)

1. **Business meaning:** Relative change; undefined when previous = 0.
2. **Formula:** `(Current − Previous) ÷ Previous × 100`
3. **Numerator:** Current − Previous
4. **Denominator:** Previous
5. **Required columns:** Any count/amount metric
6. **Source:** Any metric above
7. **Aggregation level / grain:** —
8. **Reporting period:** as above
9. **Missing/duplicate/invalid handling:** Shown only if the previous period lies fully inside the observed data range and the previous value exists.
10. **Definition status:** Standard
11. **Example (fictional):** Example: (12 − 10) ÷ 10 = +20%

#### Percentage-point change  (`chg_pp`)

1. **Business meaning:** Difference of two rates (used for % KPIs).
2. **Formula:** `Current rate − Previous rate`
3. **Numerator:** Current rate
4. **Denominator:** —
5. **Required columns:** Any rate metric
6. **Source:** Any metric above
7. **Aggregation level / grain:** —
8. **Reporting period:** as above
9. **Missing/duplicate/invalid handling:** Shown only if the previous period lies fully inside the observed data range and the previous value exists.
10. **Definition status:** Standard
11. **Example (fictional):** Example: 55% − 50% = +5 pp

<!-- KPI-DOCS:END -->
