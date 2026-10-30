"""Shared Streamlit UI in the SWITCH dashboard format.

Every page uses the same frame:
  * header bar   — SWITCH logo | page title + tagline, and filter "pills"
                   (Last updated · Year · Period · Location · more filters)
  * icon sidebar — page navigation, data source, monitoring, status
  * KPI row      — six icon cards with change arrows vs the previous period
  * panel rows   — equal-height cards: trend · donut · funnel/ranking · initiatives & focus, then detail rows
Period, comparison and formatting rules live in services/presentation.py (shared with the PPT/PDF exports).
"""
from __future__ import annotations

import base64
import hashlib
import html
from functools import lru_cache

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import (BRAND_BLUE, BRAND_GREEN, BRAND_TEAL, CSS_PATH, LOGO_PATH, MIN_REFRESH_SECONDS, PALETTE,
                    PREVIEW_ROWS, SENSITIVE_NAME_TOKENS, TAGLINE, DataState)
from services import metrics as M
from services import presentation as P
from services.app_state import Store, get_store
from services.refresh import clean_path
from services.insights import Insight
from services.overview import data_bounds
from services.presentation import Delta, fmt, label  # noqa: F401  (re-exported for pages)

FONT = "Segoe UI, system-ui, Arial, sans-serif"
INK, MUTED, GRID = "#0F1F3D", "#5E6B85", "#E6EBF3"
AWAITING = "Awaiting Excel data"
PANEL_H = 445          # four-panel row card height (all four line up)
DETAIL_H = 400         # detail-row card height
CHART_H = 335          # chart height inside a panel card
DETAIL_CHART_H = 295   # chart height inside a detail card

# ------------------------------------------------------------------ navigation
NAV = [("app.py", "Home", ":material/home:"),
       ("pages/1_Executive_Overview.py", "Overview", ":material/dashboard:"),
       ("pages/2_Recruitment.py", "Recruitment", ":material/person_search:"),
       ("pages/3_Employees.py", "Employees", ":material/groups:"),
       ("pages/4_Training.py", "Training", ":material/school:"),
       ("pages/5_Performance.py", "Performance", ":material/trending_up:"),
       ("pages/6_Turnover.py", "Turnover", ":material/sync:"),
       ("pages/7_Employee_Relations.py", "Employee Relations", ":material/handshake:"),
       ("pages/8_Data_Explorer.py", "Data Explorer", ":material/table_chart:"),
       ("pages/9_Downloads.py", "Downloads", ":material/download:")]

# ------------------------------------------------------------------ icons (Material Design, Apache-2.0)
_P = {
    "download": "M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z",
    "slides": "M10 8v8l5-4-5-4zm9-5H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 16H5V5h14v14z",
    "pdf": "M20 2H8c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-8.5 7.5c0 .83-.67 1.5-1.5 1.5H9v2H7.5V7H10c.83 0 1.5.67 1.5 1.5v1zm5 2c0 .83-.67 1.5-1.5 1.5h-2.5V7H15c.83 0 1.5.67 1.5 1.5v3zm4-3H19v1h1.5V11H19v2h-1.5V7h3v1.5zM9 9.5h1v-1H9v1zM4 6H2v14c0 1.1.9 2 2 2h14v-2H4V6zm10 5.5h1v-3h-1v3z",
    "groups": "M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z",
    "doc": "M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z",
    "clock": "M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z",
    "target": "M12 8c-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4-1.79-4-4-4zm8.94 3c-.46-4.17-3.77-7.48-7.94-7.94V1h-2v2.06C6.83 3.52 3.52 6.83 3.06 11H1v2h2.06c.46 4.17 3.77 7.48 7.94 7.94V23h2v-2.06c4.17-.46 7.48-3.77 7.94-7.94H23v-2h-2.06zM12 19c-3.87 0-7-3.13-7-7s3.13-7 7-7 7 3.13 7 7-3.13 7-7 7z",
    "person_add": "M15 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm-9-2V7H4v3H1v2h3v3h2v-3h3v-2H6zm9 4c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z",
    "rupee": "M13.66 7c-.56-1.18-1.76-2-3.16-2H6V3h12v2h-3.26c.48.58.84 1.26 1.05 2H18v2h-2.02c-.25 2.8-2.61 5-5.48 5h-.73l6.73 7h-2.77L7 14v-2h3.5c1.76 0 3.22-1.3 3.46-3H6V7h7.66z",
    "check": "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z",
    "up": "M16 6l2.29 2.29-4.88 4.88-4-4L2 16.59 3.41 18l6-6 4 4 6.3-6.29L22 12V6z",
    "down": "M16 18l2.29-2.29-4.88-4.88-4 4L2 7.41 3.41 6l6 6 4-4 6.3 6.29L22 12v6z",
    "school": "M5 13.18v4L12 21l7-3.82v-4L12 17l-7-3.82zM12 3L1 9l11 6 9-4.91V17h2V9L12 3z",
    "work": "M20 6h-4V4c0-1.11-.89-2-2-2h-4c-1.11 0-2 .89-2 2v2H4c-1.11 0-1.99.89-1.99 2L2 19c0 1.11.89 2 2 2h16c1.11 0 2-.89 2-2V8c0-1.11-.89-2-2-2zm-6 0h-4V4h4v2z",
    "hourglass": "M6 2v6h.01L6 8.01 10 12l-4 4 .01.01H6V22h12v-5.99h-.01L18 16l-4-4 4-3.99-.01-.01H18V2H6z",
    "star": "M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z",
    "forum": "M21 6h-2v9H6v2c0 .55.45 1 1 1h11l4 4V7c0-.55-.45-1-1-1zm-4 6V3c0-.55-.45-1-1-1H3c-.55 0-1 .45-1 1v14l4-4h10c.55 0 1-.45 1-1z",
    "chart": "M5 9.2h3V19H5zM10.6 5h2.8v14h-2.8zm5.6 8H19v6h-2.8z",
    "exit": "M10.09 15.59L11.5 17l5-5-5-5-1.41 1.41L12.67 11H3v2h9.67l-2.58 2.59zM19 3H5c-1.11 0-2 .9-2 2v4h2V5h14v14H5v-4H3v4c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2z",
    "calendar": "M17 12h-5v5h5v-5zM16 1v2H8V1H6v2H5c-1.11 0-1.99.9-1.99 2L3 19c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2h-1V1h-2zm3 18H5V8h14v11z",
    "heart": "M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z",
    "warn": "M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z",
    "arrow_up": "M4 12l1.41 1.41L11 7.83V20h2V7.83l5.58 5.59L20 12l-8-8-8 8z",
    "arrow_down": "M20 12l-1.41-1.41L13 16.17V4h-2v12.17l-5.58-5.59L4 12l8 8 8-8z",
    "table": "M10 10.02h5V21h-5zM17 21h3c1.1 0 2-.9 2-2v-9h-5v11zm3-18H5c-1.1 0-2 .9-2 2v3h19V5c0-1.1-.9-2-2-2zM3 19c0 1.1.9 2 2 2h3V10H3v9z",
}


def svg(name: str, size: int = 22, cls: str = "") -> str:
    return (f'<svg class="ico {cls}" viewBox="0 0 24 24" width="{size}" height="{size}" aria-hidden="true">'
            f'<path d="{_P.get(name, _P["chart"])}"/></svg>')


ICON_FOR = {
    "rec_requisitions": "groups", "rec_filled": "doc", "rec_time_to_hire": "clock", "rec_offer_acceptance": "target",
    "rec_new_hires": "person_add", "rec_cost_per_hire": "rupee", "rec_open_count": "work", "rec_open_ageing": "hourglass",
    "emp_headcount": "groups", "emp_new_hires": "person_add", "emp_exits": "exit", "emp_attrition": "down",
    "emp_tenure": "calendar", "trn_hours": "clock", "trn_employees": "school", "trn_participation": "groups",
    "trn_avg_hours": "hourglass", "trn_cert_rate": "check", "trn_effectiveness": "up", "trn_cost": "rupee",
    "trn_cost_per_employee": "rupee", "trn_budget_util": "chart", "pms_eligible": "groups", "pms_completed": "doc",
    "pms_completion": "check", "pms_high_performers": "star", "pms_high_pct": "star", "pms_avg_rating": "chart",
    "pms_goal_rate": "target", "pms_idp": "up", "rel_cases": "forum", "rel_open": "forum", "rel_closed": "check",
    "rel_pending": "hourglass", "rel_resolution_rate": "check", "rel_resolution_days": "clock",
    "rel_engagement": "heart", "rel_response_rate": "forum", "op": "groups", "cl": "groups", "vol": "exit",
}


# ------------------------------------------------------------------ assets
@lru_cache(maxsize=1)
def _logo_b64() -> str:
    return base64.b64encode(LOGO_PATH.read_bytes()).decode() if LOGO_PATH.exists() else ""


def logo_html(cls: str = "logo") -> str:
    b = _logo_b64()
    if b:
        return f'<img class="{cls}" src="data:image/png;base64,{b}" alt="SWITCH"/>'
    return f'<span class="{cls} wordmark">SW<span class="g">//</span>TCH</span>'


def _css() -> None:
    if CSS_PATH.exists():
        st.markdown(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


# ------------------------------------------------------------------ sidebar
# ------------------------------------------------------------------ sidebar
def _handle_upload(store: Store, up) -> None:
    if up is None:
        return
    data = up.getvalue()
    uid = f"{up.name}:{hashlib.sha256(data).hexdigest()}"   # content-based: a re-saved file with the same name is re-read
    if uid != store.last_upload_id:
        store.last_upload_id = uid
        with st.spinner("Reading all worksheets…"):
            store.ingest_bytes(data, up.name)


def _watcher(store: Store) -> None:
    if not (store.monitor_on and store.monitor_path):
        return

    @st.fragment(run_every=max(store.refresh_seconds, MIN_REFRESH_SECONDS))
    def _poll():
        verdict = store.poll()
        if verdict in ("reloaded", "rejected"):
            st.rerun()                                   # redraw every page with the new state
        txt = {"unchanged": "Watching — no change", "pending": "Change detected — waiting for save to finish",
               "missing": "File not found — keeping last valid data",
               "locked": "File is open or locked — will retry automatically, keeping last valid data"}.get(verdict, verdict)
        st.caption(f"👁 {txt}. Checked {pd.Timestamp.now():%H:%M:%S}")
    _poll()


def _sidebar(store: Store) -> None:
    with st.sidebar:
        st.markdown(f'<div class="sb-brand">{logo_html("sb-logo")}<div class="sb-sub">HR Analytics</div></div>',
                    unsafe_allow_html=True)
        st.markdown('<div class="sb-h">Dashboards</div>', unsafe_allow_html=True)
        for path, label, icon in NAV:
            try:
                st.page_link(path, label=label, icon=icon)
            except Exception:                            # page missing / older Streamlit: keep the app usable
                pass
        st.divider()
        st.markdown('<div class="sb-h">Data source</div>', unsafe_allow_html=True)
        up = st.file_uploader("Upload HR Excel workbook (.xlsx / .xlsm)", type=["xlsx", "xlsm"], key="sb_upload",
                              help="All worksheets are inspected automatically. Data stays on this computer.")
        _handle_upload(store, up)
        with st.expander("Monitor a local file (auto-refresh)"):
            path = st.text_input("Workbook path", value=store.monitor_path, key="mon_path",
                                 placeholder="C:\\HR\\workbook.xlsx")
            secs = st.number_input("Check every (seconds)", MIN_REFRESH_SECONDS, 3600, store.refresh_seconds, 5)
            on = st.toggle("Monitor this file", value=store.monitor_on, key="mon_on")
            load_now = st.button("Load / refresh now", use_container_width=True)
            store.refresh_seconds = int(secs)
            if (on and path and (path != store.monitor_path or not store.monitor_on)) or load_now:
                store.monitor_path = clean_path(path)
                if store.monitor_path:
                    with st.spinner("Loading…"):
                        store.ingest_path(store.monitor_path)
            store.monitor_on, store.monitor_path = on, clean_path(path)
            st.caption("Save the workbook in Excel (Ctrl+S) — a change is picked up once the file has been idle for "
                       "a few seconds. Monitoring only works while this app is running.")
        _watcher(store)
        _status_block(store)


def _status_block(store: Store) -> None:
    m = store.model
    if m is None:
        st.caption("No workbook loaded.")
        return
    warn = sum(i.count for i in m.issues if i.severity == "warning")
    st.caption(f"**Workbook:** {html.escape(m.source_name)}  \n**Status:** {store.state.value.replace('_', ' ').title()}"
               + (f"  \n**Refreshed:** {store.last_refresh_ok:%d %b %Y %H:%M}" if store.last_refresh_ok else "")
               + f"  \n**Data quality:** {'%d warnings' % warn if warn else 'no warnings'}")



# ------------------------------------------------------------------ header
def _pill(icon: str, label_: str, value: str) -> str:
    return (f'<div class="pill-static">{svg(icon, 20, "pill-ico")}<div class="pill-txt"><div class="pill-l">{html.escape(label_)}</div>'
            f'<div class="pill-v">{html.escape(value)}</div></div></div>')


def page_setup(title: str, subtitle: str = "", icon: str = "📊") -> Store:
    """Draw the page frame. ``title`` e.g. 'Recruitment' → header 'Recruitment Dashboard'."""
    st.set_page_config(page_title=f"{title} · SWITCH HR", page_icon=icon, layout="wide")
    _css()
    store = get_store()
    _sidebar(store)
    hdr = st.container(key="hdr")
    cols = hdr.columns([4.4, 1.3, 0.95, 1.1, 1.25, 0.42], vertical_alignment="center", gap="small")
    cols[0].markdown(f'<div class="hdr-brand">{logo_html("hdr-logo")}<span class="hdr-div"></span>'
                     f'<div class="hdr-text"><div class="hdr-title">{html.escape(title)} Dashboard</div>'
                     f'<div class="hdr-sub">{html.escape(TAGLINE)}</div></div></div>', unsafe_allow_html=True)
    slots = {k: cols[i].empty() for i, k in enumerate(("updated", "year", "period", "location"), start=1)}
    upd = f"{store.last_refresh_ok:%d %b %Y}" if store.last_refresh_ok else "—"
    slots["updated"].markdown(_pill("calendar", "Last Updated", upd), unsafe_allow_html=True)
    slots["year"].markdown(_pill("calendar", "Year", "—"), unsafe_allow_html=True)
    slots["period"].markdown(_pill("calendar", "Period", "—"), unsafe_allow_html=True)
    slots["location"].markdown(_pill("target", "Location", "All"), unsafe_allow_html=True)
    with cols[5]:
        slots["filters"] = st.popover(":material/filter_alt:", help="More filters", use_container_width=True)
    store._slots = slots                                   # per-session, per-run handles for context()/filters()
    _banner(store)
    return store


def header_slot(store: Store, name: str):
    """Container in the header pill ``name`` (year / period / location / updated), replacing its placeholder."""
    return store._slots[name].container()


def _banner(store: Store) -> None:
    s = store.state
    if store.failure and store.model is not None:
        st.warning(f"**{store.failed_name}** was rejected: {store.failure} Showing the last valid workbook "
                   f"(**{store.model.source_name}**, refreshed {store.last_refresh_ok:%d %b %H:%M}). "
                   "Values below come from that earlier workbook, not the rejected file.")
    elif s == DataState.INVALID_FILE:
        st.error(f"**{store.failed_name}** could not be used: {store.failure} No figures are shown. "
                 "Upload a valid .xlsx or .xlsm workbook.")
    elif s == DataState.NO_SUPPORTED_DATA:
        st.warning("The workbook was read, but no worksheet matched supported HR data. Open **Data Explorer** to "
                   "inspect the sheets and map columns manually.")
    elif s == DataState.PARTIAL_DATA:
        have = ", ".join(sorted(store.model.datasets))
        st.info(f"Partial data: detected {have}. Metrics that need other data show **Not available** with the reason.")


def gate(store: Store, labels: list[str] = (), needs: tuple[str, ...] = ()) -> None:
    """Stop the page with an 'awaiting' view when no data exists, or when none of ``needs`` is present."""
    if store.has_data and (not needs or any(n in store.model.datasets for n in needs)):
        return
    if store.state == DataState.NO_FILE:
        st.info("**Please upload your HR Excel workbook to view analytics.** All worksheets will be inspected "
                "automatically; nothing leaves this computer.")
        _handle_upload(store, st.file_uploader("Upload HR Excel workbook", type=["xlsx", "xlsm"], key="main_upload"))
        if store.has_data:
            st.rerun()
    elif store.has_data:
        st.warning(f"This page needs {' / '.join(needs)} data, which was not found in **{store.model.source_name}**. "
                   "Check the mapping in Data Explorer.")
    if labels:
        cards = "".join(f'<div class="kpi na"><div class="kpi-ico">{svg("chart", 34)}</div><div class="kpi-body">'
                        f'<div class="kpi-label">{html.escape(l)}</div><div class="kpi-value">{AWAITING}</div></div></div>'
                        for l in labels)
        st.markdown(f'<div class="kpi-grid">{cards}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="awaiting">{AWAITING} — charts, tables and insights appear after a valid workbook is loaded.</div>',
                unsafe_allow_html=True)
    st.stop()


# ------------------------------------------------------------------ period / context
class Ctx(P.PeriodCtx):
    """Page context: the shared PeriodCtx plus the Store it came from."""

    def __init__(self, store: Store, base: P.PeriodCtx, year=None, choice=None):
        super().__init__(**{k: getattr(base, k) for k in base.__dataclass_fields__})
        self.store, self.year, self.choice = store, year, choice


def context(store: Store, with_period: bool = True) -> Ctx:
    m = store.model
    ds_all = dict(m.datasets)
    b = data_bounds(ds_all)
    fp = m.fingerprint[:10]
    locs = P.locations(ds_all)
    with header_slot(store, "location"):
        loc = st.selectbox("Location", ["All"] + locs, key=f"loc_{fp}", disabled=not locs,
                           help="Applies to every dataset with a location column.")
    ds = P.apply_location(ds_all, loc)
    if not (b and with_period):
        if with_period is False:
            with header_slot(store, "year"):
                st.markdown(_pill("calendar", "Year", "All"), unsafe_allow_html=True)
            with header_slot(store, "period"):
                st.markdown(_pill("calendar", "Period", "All"), unsafe_allow_html=True)
        return Ctx(store, P.PeriodCtx(ds, store.settings, b, None, None, "", None, "All data", loc))
    years = P.year_options(b)
    dy, dc = P.default_selection(b)
    with header_slot(store, "year"):
        year = st.selectbox("Year", years, index=years.index(dy) if dy in years else 0, key=f"yr_{fp}")
    opts = P.period_options(year, b)
    default = dc if (year == dy and dc in opts) else ("Full year" if "Full year" in opts else opts[0])
    with header_slot(store, "period"):
        choice = st.selectbox("Period", opts, index=opts.index(default), key=f"pd_{fp}_{year}")
    period, prev, vs, win = P.resolve(year, choice, b)
    name = P.period_name(year, choice, period)
    with store._slots["filters"]:
        st.markdown("**Reporting period**")
        if st.toggle("Use a custom date range", key=f"cust_{fp}"):
            val = st.date_input("From – To", value=(period.start.date(), period.end.date()), min_value=b[0].date(),
                                max_value=b[1].date(), key=f"rng_{fp}")
            if isinstance(val, (tuple, list)) and len(val) == 2:
                period = M.Period(pd.Timestamp(val[0]), pd.Timestamp(val[1]))
                prev, vs, win, name, choice = period.previous(), "previous period", period, period.label(), "Custom"
        st.caption(f"Showing **{period.label()}**; changes compare with {vs} ({prev.label()}) when that period lies "
                   f"inside the data. Data covers {b[0]:%d %b %Y} – {b[1]:%d %b %Y}.")
    return Ctx(store, P.PeriodCtx(ds, store.settings, b, period, prev, vs, win, name, loc), year, choice)


def filters(df: pd.DataFrame, fields: dict[str, str], key: str) -> pd.DataFrame:
    """Multi-select filters inside the header filter button, shown only for columns that exist in the data."""
    avail = {c: l for c, l in fields.items() if c in df.columns and df[c].notna().any()}
    if not avail:
        return df
    store = get_store()
    with store._slots["filters"]:
        st.markdown("**Filters**")
        for c, l in avail.items():
            opts = sorted(df[c].dropna().astype(str).unique())
            sel = st.multiselect(l, opts, key=f"f_{key}_{c}")
            if sel:
                df = df[df[c].astype(str).isin(sel)]
    return df


# ------------------------------------------------------------------ KPI cards
def _delta_html(d) -> str:
    if not d:
        return ""
    if isinstance(d, str):
        return f'<div class="kpi-vs">{html.escape(d)}</div>'
    if d.value == 0:
        return f'<div class="kpi-delta neutral"><b>No change</b></div><div class="kpi-vs">vs. {html.escape(d.vs)}</div>'
    return (f'<div class="kpi-delta {d.tone}">{svg("arrow_up" if d.up else "arrow_down", 16)}<b>{d.text}</b></div>'
            f'<div class="kpi-vs">vs. {html.escape(d.vs)}</div>')


def kpi_cards(items, secondary=None) -> None:
    """Six icon cards in a row (the reference format); any further KPIs go into a compact strip below."""
    items = list(items)
    if secondary is None:
        items, secondary = items[:6], items[6:]
    out = []
    for i, (m, d) in enumerate(items):
        ico = svg(ICON_FOR.get(m.key, "chart"), 34)
        tone = "alt" if i % 2 else ""
        if m.available:
            tip = html.escape(m.detail or m.label)
            out.append(f'<div class="kpi" title="{tip}"><div class="kpi-ico {tone}">{ico}</div><div class="kpi-body">'
                       f'<div class="kpi-label">{html.escape(label(m))}</div><div class="kpi-value">{html.escape(fmt(m))}</div>'
                       f'{_delta_html(d)}</div></div>')
        else:
            out.append(f'<div class="kpi na" title="{html.escape(m.reason)}"><div class="kpi-ico">{ico}</div>'
                       f'<div class="kpi-body"><div class="kpi-label">{html.escape(label(m))}</div>'
                       f'<div class="kpi-value">Not available</div><div class="kpi-vs clamp">{html.escape(m.reason)}</div></div></div>')
    st.markdown(f'<div class="kpi-grid">{"".join(out)}</div>', unsafe_allow_html=True)
    if secondary:
        mini = []
        for m, d in secondary:
            val = fmt(m) if m.available else "Not available"
            sub = _delta_html(d) if m.available else f'<div class="kpi-vs clamp">{html.escape(m.reason)}</div>'
            mini.append(f'<div class="mini {"na" if not m.available else ""}" title="{html.escape(m.detail or m.reason)}">'
                        f'{svg(ICON_FOR.get(m.key, "chart"), 22)}<div class="mini-body"><div class="mini-l">{html.escape(label(m))}</div>'
                        f'<div class="mini-v">{html.escape(val)}</div>{sub}</div></div>')
        st.markdown(f'<div class="mini-grid">{"".join(mini)}</div>', unsafe_allow_html=True)


def tiles(items: list[tuple[str, str, str]]) -> None:
    """Simple icon tiles (label, value, icon) for non-metric facts (Home, Data Explorer)."""
    out = "".join(f'<div class="kpi"><div class="kpi-ico {"alt" if i % 2 else ""}">{svg(ic, 34)}</div><div class="kpi-body">'
                  f'<div class="kpi-label">{html.escape(l)}</div><div class="kpi-value sm">{html.escape(str(v))}</div></div></div>'
                  for i, (l, v, ic) in enumerate(items))
    st.markdown(f'<div class="kpi-grid">{out}</div>', unsafe_allow_html=True)


# ------------------------------------------------------------------ panels
def row(weights=(1.35, 1, 1, 1.25)):
    """Columns for a panel row. The default matches the reference: trend · donut · funnel · focus."""
    return st.columns(list(weights), gap="small")


def section(title: str, caption: str = "", parent=None, icon: str | None = None, height: int | None = None):
    kw = {"border": True}
    if height:
        kw["height"] = height
    box = (parent or st).container(**kw)
    ico = svg(icon, 20, "ph-ico") if icon else ""
    box.markdown(f'<div class="ph">{ico}<span>{html.escape(title)}</span></div>'
                 f'<div class="ph-sub">{html.escape(caption) if caption else "&nbsp;"}</div>', unsafe_allow_html=True)
    return box


def panel(parent, title: str, caption: str = "", icon: str | None = None):
    """A four-panel-row card (fixed height so the row lines up)."""
    return section(title, caption, parent, icon, PANEL_H)


def card(title: str, caption: str = "", parent=None, icon: str | None = None):
    """A detail-row card (fixed height so every card in the row lines up)."""
    return section(title, caption, parent, icon, DETAIL_H)


def unavailable(box, reason: str) -> None:
    box.markdown(f'<div class="na-box">Not available — {html.escape(reason)}</div>', unsafe_allow_html=True)


# ------------------------------------------------------------------ charts
def _short(s, n: int = 22) -> str:
    s = str(s)
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _d3(values, fmt_: str | None) -> str:
    if fmt_:
        return fmt_
    v = pd.to_numeric(pd.Series(values), errors="coerce").dropna()
    return ",.0f" if len(v) == 0 or (v.round(0) == v).all() else ",.1f"


def _style(fig: go.Figure, height: int, legend: str = "top", r: int = 10) -> go.Figure:
    if legend == "top":
        leg = dict(orientation="h", y=1.0, x=0, xanchor="left", yanchor="bottom", font=dict(size=11),
                   bgcolor="rgba(0,0,0,0)")
        mt = 34
    elif legend == "right":
        leg = dict(orientation="v", x=1.0, y=0.5, xanchor="left", yanchor="middle", font=dict(size=11),
                   bgcolor="rgba(0,0,0,0)", itemclick=False)
        mt = 6
    else:
        leg = dict(orientation="h", x=0.5, y=-0.04, xanchor="center", yanchor="top", font=dict(size=11))
        mt = 6
    fig.update_layout(height=height, margin=dict(l=6, r=r, t=mt, b=6), autosize=True,
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family=FONT, size=12, color=INK), colorway=PALETTE, legend=leg, legend_title_text="",
                      hoverlabel=dict(font_size=12, bgcolor="#fff"), bargap=0.3, bargroupgap=0.08,
                      uniformtext=dict(minsize=9, mode="hide"))
    fig.update_xaxes(gridcolor=GRID, zeroline=False, title_text="", tickfont=dict(color=MUTED, size=11),
                     showline=False, automargin=True)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, title_text="", tickfont=dict(color=MUTED, size=11), automargin=True)
    return fig


def plot(box, fig: go.Figure, height: int = CHART_H, legend: str = "top", r: int = 10) -> None:
    cfg = {"displayModeBar": False, "responsive": True}
    fig = _style(fig, height, legend, r)
    try:
        box.plotly_chart(fig, theme=None, width="stretch", config=cfg)
    except TypeError:
        box.plotly_chart(fig, theme=None, use_container_width=True, config=cfg)


def table(box, df: pd.DataFrame | None, height: int = 320, key: str = "", searchable: bool = False) -> None:
    if df is None or df.empty:
        unavailable(box, "no rows for the current scope.")
        return
    if searchable:
        q = box.text_input("Search", key=f"q_{key}", label_visibility="collapsed", placeholder="Search…")
        if q:
            m = df.astype(str).apply(lambda c: c.str.contains(q, case=False, na=False)).any(axis=1)
            df = df[m]
    try:
        box.dataframe(df, hide_index=True, height=height, width="stretch")
    except TypeError:
        box.dataframe(df, hide_index=True, height=height, use_container_width=True)


def _empty(box, df) -> bool:
    if df is None or len(df) == 0:
        unavailable(box, "no data for this chart in the current scope.")
        return True
    return False


def _month_ticks(fig, x) -> None:
    try:
        xs = pd.to_datetime(pd.Series(x))
        fig.update_xaxes(tickformat="%b" if xs.dt.year.nunique() == 1 else "%b %y",
                         dtick="M1" if len(xs) <= 12 else "M2")
    except Exception:
        pass


def _top(values) -> float:
    v = pd.to_numeric(pd.Series(values), errors="coerce").dropna()
    return float(v.max()) if len(v) and v.max() > 0 else 1.0


def combo(box, df, x: str, bars: list[str], line: str | None = None, line_secondary: bool = False,
          height: int = CHART_H, bar_names: dict | None = None, line_name: str | None = None) -> None:
    """Grouped bars plus a labelled line (the 'Hiring Trend' chart). Axes are scaled so the line labels sit above
    the bars and never collide with them."""
    if _empty(box, df):
        return
    fig = go.Figure()
    cols = [BRAND_BLUE, BRAND_TEAL, "#5B8BD9", "#7FCFCB"]
    bars = [b for b in bars if b in df.columns]
    is_dt = pd.api.types.is_datetime64_any_dtype(df[x])
    hov = "%{x|%b %Y}" if is_dt else "%{x}"
    for i, c in enumerate(bars):
        fig.add_bar(x=df[x], y=df[c], name=(bar_names or {}).get(c, c), marker_color=cols[i % len(cols)],
                    marker_cornerradius=3, hovertemplate=hov + ": %{y:,.0f}<extra>" + (bar_names or {}).get(c, c) + "</extra>")
    bar_top = max([_top(df[c]) for c in bars] or [1.0])
    if line and line in df.columns:
        vals = pd.to_numeric(df[line], errors="coerce")
        step = 1 if len(df) <= 12 else 2
        txt = ["" if pd.isna(v) or i % step else P.num(float(v), 0 if abs(float(v)) >= 100 else 1)
               for i, v in enumerate(vals)]
        fig.add_scatter(x=df[x], y=vals, name=line_name or line, mode="lines+markers+text", text=txt,
                        textposition="top center", textfont=dict(size=11, color=INK),
                        line=dict(color=BRAND_GREEN, width=2.5), marker=dict(size=7, color=BRAND_GREEN),
                        yaxis="y2" if line_secondary else "y", cliponaxis=False,
                        hovertemplate=hov + ": %{y:,.1f}<extra>" + (line_name or line) + "</extra>")
        if line_secondary:
            lt = _top(vals)
            lo = float(vals.min()) if vals.notna().any() else 0
            base = max(0.0, lo - (lt - lo) * 1.8) if lt > lo else 0
            # line in the upper band, bars in the lower band
            fig.update_layout(yaxis=dict(range=[0, bar_top * 2.1]),
                              yaxis2=dict(overlaying="y", side="right", showgrid=False, tickfont=dict(color=MUTED, size=11),
                                          range=[base, lt + (lt - base) * 0.18]))
        else:
            fig.update_yaxes(range=[0, max(bar_top, _top(vals)) * 1.25])
    else:
        fig.update_yaxes(range=[0, bar_top * 1.2])
        for tr in fig.data:
            tr.update(text=tr.y, texttemplate="%{y:,.0f}", textposition="outside", textfont=dict(size=10, color=INK),
                      cliponaxis=False)
    fig.update_layout(barmode="group")
    if is_dt:
        _month_ticks(fig, df[x])
    else:
        fig.update_xaxes(type="category")
    plot(box, fig, height)


def bar(box, df, x, y, orient="v", color=None, barmode="group", fmt=None, height=CHART_H, top: int = 10):
    """Single-series bar chart with value labels that always have room (no clipping or overlap)."""
    if _empty(box, df):
        return
    d = df.copy()
    val, cat = (x, y) if orient == "h" else (y, x)
    note = ""
    if orient == "h":
        d = d.sort_values(val, ascending=False)
        if len(d) > top:
            d = d.head(top)
            note = f"Top {top} of {len(df)} shown."
    vals = pd.to_numeric(d[val], errors="coerce")
    tf = _d3(vals, (fmt or "").lstrip(":") or None)
    mx = _top(vals)
    cats = d[cat].astype(str) if not pd.api.types.is_datetime64_any_dtype(d[cat]) else d[cat]
    show_text = len(d) <= 16
    if orient == "h":
        fig = go.Figure(go.Bar(x=vals, y=[_short(c) for c in cats], orientation="h", marker_color=BRAND_BLUE,
                               marker_cornerradius=3, text=vals if show_text else None, texttemplate=f"%{{x:{tf}}}",
                               textposition="outside", cliponaxis=False, textfont=dict(size=11, color=INK),
                               customdata=list(cats), hovertemplate=f"%{{customdata}}: %{{x:{tf}}}<extra></extra>"))
        fig.update_yaxes(autorange="reversed", showgrid=False, type="category")
        fig.update_xaxes(showgrid=False, showticklabels=False, range=[0, mx * 1.28])
        fig.update_layout(bargap=0.35 if len(d) > 3 else 0.55)
    else:
        fig = go.Figure(go.Bar(x=cats if pd.api.types.is_datetime64_any_dtype(d[cat]) else [_short(c, 14) for c in cats],
                               y=vals, marker_color=BRAND_TEAL, marker_cornerradius=3,
                               text=vals if show_text else None, texttemplate=f"%{{y:{tf}}}", textposition="outside",
                               cliponaxis=False, textfont=dict(size=11, color=INK),
                               hovertemplate=f"%{{x}}: %{{y:{tf}}}<extra></extra>"))
        fig.update_yaxes(range=[0, mx * 1.2])
        if pd.api.types.is_datetime64_any_dtype(d[cat]):
            _month_ticks(fig, d[cat])
        else:
            fig.update_xaxes(type="category", tickangle=0 if len(d) <= 6 else -30)
    fig.update_layout(showlegend=False)
    plot(box, fig, height)
    if note:
        box.caption(note)


def line(box, df, x, ys: list[str], height=CHART_H):
    if _empty(box, df):
        return
    fig = go.Figure()
    mx = 0.0
    for i, c in enumerate(ys):
        v = pd.to_numeric(df[c], errors="coerce")
        mx = max(mx, _top(v))
        lbl = len(df) <= 12 and len(ys) == 1
        fig.add_scatter(x=df[x], y=v, name=c, mode="lines+markers+text" if lbl else "lines+markers",
                        text=[("" if pd.isna(t) else P.num(float(t), 0 if abs(float(t)) >= 100 else 1)) for t in v] if lbl else None,
                        textposition="top center", textfont=dict(size=11, color=INK), cliponaxis=False,
                        line=dict(width=2.5, color=PALETTE[i]), marker=dict(size=7),
                        fill="tozeroy" if len(ys) == 1 else None, fillcolor="rgba(31,165,166,0.08)")
    fig.update_yaxes(range=[0, mx * 1.25])
    if pd.api.types.is_datetime64_any_dtype(df[x]):
        _month_ticks(fig, df[x])
    else:
        fig.update_xaxes(type="category")
    fig.update_layout(showlegend=len(ys) > 1)
    plot(box, fig, height)


def donut(box, df, names, values, height=CHART_H, center: str | None = None, top: int = 6):
    """Donut with the total in the centre and a 'Name  28% (28)' legend (the 'Hiring by Function' chart).
    Slice labels under 6% are hidden so they never overlap; the legend still lists every slice."""
    if _empty(box, df):
        return
    d = df[[names, values]].copy()
    d[values] = pd.to_numeric(d[values], errors="coerce").fillna(0)
    d = d[d[values] > 0].sort_values(values, ascending=False)
    if d.empty:
        unavailable(box, "no data for this chart in the current scope.")
        return
    if len(d) > top:
        rest = d.iloc[top - 1:][values].sum()
        d = pd.concat([d.iloc[:top - 1], pd.DataFrame({names: ["Others"], values: [rest]})])
    tot = d[values].sum()
    share = d[values] / tot * 100
    labels = [f"{_short(n, 16)}  {s:.0f}% ({v:,.0f})" for n, v, s in zip(d[names].astype(str), d[values], share)]
    text = [f"{s:.0f}%" if s >= 6 else "" for s in share]
    fig = go.Figure(go.Pie(labels=labels, values=d[values], hole=0.62, sort=False, direction="clockwise",
                           marker=dict(colors=PALETTE[: len(d)], line=dict(color="#fff", width=2)),
                           text=text, textinfo="text", textposition="inside", insidetextorientation="horizontal",
                           textfont=dict(size=11, color="#fff"), hovertemplate="%{label}<extra></extra>"))
    if center:
        fig.add_annotation(text=f"<b style='font-size:20px'>{tot:,.0f}</b><br><span style='font-size:10px;color:{MUTED}'>"
                                f"{html.escape(center)}</span>", showarrow=False, x=0.5, y=0.5, xref="paper", yref="paper")
    plot(box, fig, height, legend="bottom" if len(d) > 4 else "right")


def _blend(c1: str, c2: str, t: float) -> str:
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def funnel(box, stages, counts, height=CHART_H) -> None:
    """Teal-to-blue funnel; value and % of first stage are printed beside each bar so narrow stages stay legible."""
    n = len(list(stages))
    colors = [_blend("#3CC1C0", BRAND_BLUE, i / max(n - 1, 1)) for i in range(n)]
    fig = go.Figure(go.Funnel(y=[_short(s, 16) for s in stages], x=list(counts), marker=dict(color=colors),
                              texttemplate="%{value:,} · %{percentInitial:.0%}", textposition="outside",
                              textfont=dict(color=INK, size=11), cliponaxis=False,
                              connector=dict(fillcolor="#EAF1FA", line=dict(width=0))))
    fig.update_yaxes(tickfont=dict(color=INK, size=11))
    fig.update_layout(showlegend=False)
    plot(box, fig, height, r=84)


def suppressed_note(box, n: int) -> None:
    if n:
        box.caption(f"🔒 {n} group(s) below the minimum group size hidden for confidentiality.")


# ------------------------------------------------------------------ initiatives & focus
def focus(box, items: list[Insight], page_key: str) -> None:
    """Checklist panel ('Recruitment Initiatives & Focus'): your own focus items plus rule-based insights."""
    store = get_store()
    own = store.settings.setdefault("focus_items", {}).get(page_key, [])
    rows = [(t, "", "own") for t in own]
    for i in items:
        rows.append((i.text, i.rule, "att" if i.kind == "attention" else "ok"))
        if i.action:
            rows.append((i.action, i.rule, "act"))
    if not rows:
        box.markdown('<div class="na-box">No rule-based items from the current data. Add your own focus items below.</div>',
                     unsafe_allow_html=True)
    lis = "".join(f'<li class="{k}" title="{html.escape("Rule: " + r) if r else "Your focus item"}">'
                  f'{svg("warn" if k == "att" else "check", 18)}<span>{html.escape(t)}</span></li>' for t, r, k in rows)
    box.markdown(f'<ul class="focus">{lis}</ul>', unsafe_allow_html=True)
    with box.popover(":material/edit: Edit focus items"):
        txt = st.text_area("One item per line", value="\n".join(own), key=f"focus_{page_key}", height=160,
                           help="Your team's initiatives for this page. Kept for this session (not written to the workbook).")
        if st.button("Save", key=f"focus_save_{page_key}"):
            store.settings["focus_items"][page_key] = [x.strip() for x in txt.splitlines() if x.strip()]
            st.rerun()
    if any(k != "own" for _, _, k in rows):
        box.caption("Hover an item to see the rule that produced it.")


def insights_panel(items: list[Insight]) -> None:
    """Three-column detail view (kept for pages that want the full list with rules)."""
    c1, c2, c3 = st.columns(3)
    ins = [i for i in items if i.kind == "insight"]
    att = [i for i in items if i.kind == "attention"]
    acts = [(i.action, i.rule) for i in items if i.action]
    for col, title, rows, cls in ((c1, "Key insights", [(i.text, i.rule) for i in ins], ""),
                                  (c2, "Areas requiring attention", [(i.text, i.rule) for i in att], "attention"),
                                  (c3, "Recommended next actions", acts, "")):
        box = section(title, parent=col)
        if not rows:
            box.caption("No rule-based items from the current data.")
        for text, rule in rows:
            box.markdown(f'<div class="insight {cls}">{html.escape(text)}<div class="rule">Rule: {html.escape(rule)}</div></div>',
                         unsafe_allow_html=True)


def mask_preview(df: pd.DataFrame) -> pd.DataFrame:
    """Read-only preview with identifier / personal-data columns masked."""
    out = df.head(PREVIEW_ROWS).copy()
    for c in out.columns:
        n = str(c).lower()
        if any(t in n for t in SENSITIVE_NAME_TOKENS) or n.endswith(("id", "code", "no")) or " id" in n:
            out[c] = "••••"
    return out
