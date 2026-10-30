"""SWITCH Mobility HR Analytics — landing page. Run:  streamlit run app.py

Full-width hero in the style of the SWITCH website: logo bar, teal→blue rule, hero photo with headline, and a
"Continue to Dashboard" button. Put your own hero photo (any size, ideally 3840 px wide) at assets/hero.jpg."""
import base64
import html
from functools import lru_cache

import streamlit as st

from config import ASSETS_DIR, TAGLINE
from services import ui
from services.app_state import get_store

st.set_page_config(page_title="SWITCH · HR Analytics", page_icon="assets/tab.png", layout="wide", initial_sidebar_state="collapsed")
ui._css()
st.markdown(f"<style>{(ASSETS_DIR / 'landing.css').read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
store = get_store()

HERO_FILES = ["hero.jpg", "hero.jpeg", "hero.png", "hero.webp"]
DASHBOARD = "pages/1_Executive_Overview.py"


@lru_cache(maxsize=2)
def _hero(_mtime: float, name: str) -> str:
    p = ASSETS_DIR / name
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}[p.suffix.lstrip(".").lower()]
    return f"data:image/{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"


hero_file = next((ASSETS_DIR / f for f in HERO_FILES if (ASSETS_DIR / f).exists()), None)
hero_css = (f"background-image:linear-gradient(180deg,rgba(9,22,48,0) 30%,rgba(9,22,48,.35) 60%,rgba(9,22,48,.72) 100%),"
            f"url('{_hero(hero_file.stat().st_mtime, hero_file.name)}');") if hero_file else \
    "background-image:linear-gradient(120deg,#01439E,#1FA5A6);"

# ---- top bar ---------------------------------------------------------------------
bar = st.container(key="lnav")
c = bar.columns([3.2, 1.25, 1.2, 1.45, 2.2], vertical_alignment="center", gap="small")
c[0].markdown(f'<div class="l-logo">{ui.logo_html("l-logo-img")}</div>', unsafe_allow_html=True)
for col, (path, label, icon) in zip(c[1:4], [(DASHBOARD, "Dashboards", ":material/dashboard:"),
                                             ("pages/9_Downloads.py", "Downloads", ":material/download:"),
                                             ("pages/8_Data_Explorer.py", "Data Explorer", ":material/table_chart:")]):
    try:
        col.page_link(path, label=label, icon=icon)
    except Exception:
        col.markdown(label)
if store.has_data:
    chip = f'<span class="l-dot ok"></span>Workbook loaded · <b>{html.escape(store.model.source_name)}</b>'
else:
    chip = '<span class="l-dot"></span>No workbook loaded yet'
c[4].markdown(f'<div class="l-chip">{chip}</div>', unsafe_allow_html=True)
st.markdown('<div class="l-rule"></div>', unsafe_allow_html=True)

# ---- hero --------------------------------------------------------------------------
st.markdown(f'<div class="hero" style="{hero_css}" role="img" aria-label="SWITCH electric buses and light commercial vehicles">'
            f'<p>{html.escape(TAGLINE)}</p></div></div>', unsafe_allow_html=True)

cta = st.container(key="cta")
l, m, r = cta.columns([1, 0.9, 1])
with m:
    if st.button("Continue to Dashboard", key="go", type="primary", icon=":material/arrow_forward:",
                 use_container_width=True):
        st.switch_page(DASHBOARD)



# ---- quick links -------------------------------------------------------------------
TILES = [("pages/1_Executive_Overview.py", "HR Overview", "dashboard", "Headline KPIs and organisation-wide trends"),
         ("pages/2_Recruitment.py", "Recruitment", "person_add", "Requisitions, funnel, sources and time to hire"),
         ("pages/3_Employees.py", "Employees", "groups", "Headcount, departments, tenure and composition"),
         ("pages/4_Training.py", "Training", "school", "Hours, participation, programmes and cost"),
         ("pages/5_Performance.py", "Performance", "star", "Ratings, review progress and high performers"),
         ("pages/6_Turnover.py", "Turnover", "exit", "Exits, attrition by group and exit reasons"),
         ("pages/7_Employee_Relations.py", "Employee Relations", "forum", "Cases, resolution and engagement"),
         ("pages/9_Downloads.py", "Downloads", "download", "Every dashboard as PowerPoint or PDF")]
st.markdown('<div class="l-sec"><span>Explore the dashboards</span></div>', unsafe_allow_html=True)
wrap = st.container(key="ltiles")
for i in range(0, len(TILES), 4):
    cols = wrap.columns(4, gap="medium")
    for col, (path, title, icon, desc) in zip(cols, TILES[i:i + 4]):
        t = col.container(border=True)
        t.markdown(f'<div class="l-tile"><div class="dl-ico">{ui.svg(icon, 24)}</div><div><div class="dl-title">{title}</div>'
                   f'<div class="l-desc">{desc}</div></div></div>', unsafe_allow_html=True)
        try:
            t.page_link(path, label="Open", icon=":material/arrow_forward:")
        except Exception:
            pass

st.markdown('<div class="l-foot">SWITCH Mobility · HR Analytics · Confidential </div>',
            unsafe_allow_html=True)
