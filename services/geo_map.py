import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import ASSETS_DIR, BRAND_BLUE, BRAND_TEAL
from services import ui

GEO_FILE = ASSETS_DIR / "india_states.geojson"
# Workbook spellings -> spelling used in the boundary file (lower case, '&' written as 'and').
STATE_ALIASES = {
    "orissa": "odisha", "uttaranchal": "uttarakhand", "pondicherry": "puducherry",
    "andaman and nicobar islands": "andaman and nicobar", "delhi": "nct of delhi", "new delhi": "nct of delhi",
    "daman and diu": "dadra and nagar haveli and daman and diu",
    "dadra and nagar haveli": "dadra and nagar haveli and daman and diu",
}

# City -> state lookup, used only when an employee has no State value in the workbook.
# Keys are lower case. Cities not listed here are reported on the page and never guessed.
# Edit or extend this list to match your own locations.
CITY_STATE = {
    # Maharashtra
    "mumbai": "Maharashtra", "pune": "Maharashtra", "nagpur": "Maharashtra", "nashik": "Maharashtra",
    "thane": "Maharashtra", "navi mumbai": "Maharashtra", "kolhapur": "Maharashtra", "solapur": "Maharashtra",
    "aurangabad": "Maharashtra", "chhatrapati sambhajinagar": "Maharashtra",
    # Karnataka
    "bengaluru": "Karnataka", "bangalore": "Karnataka", "mysuru": "Karnataka", "mysore": "Karnataka",
    "mangaluru": "Karnataka", "mangalore": "Karnataka", "hubballi": "Karnataka", "hubli": "Karnataka",
    "belagavi": "Karnataka", "belgaum": "Karnataka",
    # Tamil Nadu
    "chennai": "Tamil Nadu", "coimbatore": "Tamil Nadu", "madurai": "Tamil Nadu", "trichy": "Tamil Nadu",
    "tiruchirappalli": "Tamil Nadu", "salem": "Tamil Nadu", "hosur": "Tamil Nadu", "tiruppur": "Tamil Nadu",
    # Telangana
    "hyderabad": "Telangana", "secunderabad": "Telangana", "warangal": "Telangana",
    # Andhra Pradesh
    "visakhapatnam": "Andhra Pradesh", "vizag": "Andhra Pradesh", "vijayawada": "Andhra Pradesh",
    "tirupati": "Andhra Pradesh", "guntur": "Andhra Pradesh",
    # Delhi (NCT)
    "delhi": "Delhi", "new delhi": "Delhi",
    # Haryana
    "gurugram": "Haryana", "gurgaon": "Haryana", "faridabad": "Haryana", "manesar": "Haryana",
    # Uttar Pradesh
    "noida": "Uttar Pradesh", "ghaziabad": "Uttar Pradesh", "lucknow": "Uttar Pradesh",
    "kanpur": "Uttar Pradesh", "agra": "Uttar Pradesh", "varanasi": "Uttar Pradesh",
    # Gujarat
    "ahmedabad": "Gujarat", "surat": "Gujarat", "vadodara": "Gujarat", "rajkot": "Gujarat",
    "gandhinagar": "Gujarat",
    # West Bengal
    "kolkata": "West Bengal", "howrah": "West Bengal", "siliguri": "West Bengal",
    # Rajasthan
    "jaipur": "Rajasthan", "jodhpur": "Rajasthan", "udaipur": "Rajasthan",
    # Kerala
    "kochi": "Kerala", "cochin": "Kerala", "thiruvananthapuram": "Kerala", "trivandrum": "Kerala",
    "kozhikode": "Kerala", "calicut": "Kerala", "thrissur": "Kerala",
    # Madhya Pradesh
    "bhopal": "Madhya Pradesh", "indore": "Madhya Pradesh", "gwalior": "Madhya Pradesh",
    "jabalpur": "Madhya Pradesh",
    # Punjab / Chandigarh
    "ludhiana": "Punjab", "amritsar": "Punjab", "mohali": "Punjab", "chandigarh": "Chandigarh",
    # Odisha, Bihar, Jharkhand, Assam, Goa, Chhattisgarh, Uttarakhand, Himachal, J&K
    "bhubaneswar": "Odisha", "cuttack": "Odisha", "rourkela": "Odisha",
    "patna": "Bihar", "ranchi": "Jharkhand", "jamshedpur": "Jharkhand", "guwahati": "Assam",
    "panaji": "Goa", "margao": "Goa", "raipur": "Chhattisgarh", "dehradun": "Uttarakhand",
    "shimla": "Himachal Pradesh", "srinagar": "Jammu and Kashmir", "jammu": "Jammu and Kashmir",
}


def _norm(s) -> str:
    s = " ".join(str(s).lower().replace("&", "and").split())
    return STATE_ALIASES.get(s, s)


STATES = [
    "Andaman and Nicobar", "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chandigarh", "Chhattisgarh",
    "Dadra and Nagar Haveli and Daman and Diu", "Delhi", "Goa", "Gujarat", "Haryana", "Himachal Pradesh",
    "Jammu and Kashmir", "Jharkhand", "Karnataka", "Kerala", "Ladakh", "Lakshadweep", "Madhya Pradesh",
    "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Puducherry", "Punjab", "Rajasthan",
    "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
]
STATE_BY_NAME = {_norm(s): s for s in STATES}


def _lookup(value):
    """A city (from CITY_STATE) or a state name typed directly, e.g. 'Kerala'. Anything else is None."""
    if pd.isna(value):
        return None
    v = " ".join(str(value).lower().split())
    return CITY_STATE.get(v) or STATE_BY_NAME.get(_norm(v))


def add_state(df: pd.DataFrame) -> pd.DataFrame:
    """Adds a 'state' column: the workbook's State value when filled, otherwise the state of the city or
    state named in Location."""
    from_loc = (df["location"].map(_lookup) if "location" in df.columns
                else pd.Series(None, index=df.index, dtype=object))
    if "state" in df.columns:
        return df.assign(state=df["state"].where(df["state"].notna(), from_loc))
    return df.assign(state=from_loc)


@st.cache_data(show_spinner=False)
def _geo():
    """Boundary file for India's states. Returns (geojson, property name holding the state name) or (None, None)."""
    if not GEO_FILE.exists():
        return None, None
    geo = json.loads(GEO_FILE.read_text(encoding="utf-8"))
    props = [f.get("properties", {}) for f in geo.get("features", [])]
    key = next((k for k in ("st_nm", "ST_NM", "NAME_1", "state", "STATE", "name", "NAME")
                if any(k in p for p in props)), None)
    return geo, key


def _state_table(df: pd.DataFrame, on, depts, locs):
    """Active employees at ``on`` by state, with the department and location detail shown on hover."""
    if "hire_date" not in df.columns or "state" not in df.columns:
        return None, 0
    d = df[df["hire_date"] <= on]
    if "exit_date" in d.columns:
        d = d[d["exit_date"].isna() | (d["exit_date"] > on)]
    if "employee_id" in d.columns:
        d = d.drop_duplicates("employee_id")
    if depts and "department" in d.columns:
        d = d[d["department"].astype(str).isin(depts)]
    if locs and "location" in d.columns:
        d = d[d["location"].astype(str).isin(locs)]
    missing = int(d["state"].isna().sum())
    d = d[d["state"].notna()].assign(state=lambda t: t["state"].astype(str).str.strip())
    if d.empty:
        return pd.DataFrame(), missing
    total = len(d)
    rows = []
    for name, g in d.groupby("state"):
        top = g["department"].astype(str).value_counts().head(3) if "department" in g.columns else pd.Series(dtype=int)
        cities = sorted(g["location"].dropna().astype(str).unique()) if "location" in g.columns else []
        rows.append({"State": name, "Employees": len(g), "Share": len(g) / total,
                     "Departments": " · ".join(f"{k} {v}" for k, v in top.items()),
                     "Locations": ", ".join(cities)})
    return pd.DataFrame(rows).sort_values("Employees", ascending=False), missing


def _draw_map(box, table: pd.DataFrame, geo: dict, key: str) -> None:
    """One map trace for all states: states with no employees stay soft grey, the rest are coloured by headcount.
    The boundary data is sent to the browser once per draw, so keep assets/india_states.geojson small."""
    names = [f["properties"].get(key, "") for f in geo["features"]]
    canon = {_norm(n): n for n in names}
    table = table.assign(Map=table["State"].map(lambda s: canon.get(_norm(s))))
    m = table[table["Map"].notna()]
    unmatched = table[table["Map"].isna()]
    values = {n: 0 for n in names}
    hover = {}
    for name, n, sh, dp, lc in zip(m["Map"], m["Employees"], m["Share"], m["Departments"], m["Locations"]):
        values[name] = int(n)
        hover[name] = (f"<b>{int(n):,}</b> employees · {sh:.1%} of total<br>"
                       f"Departments: {dp or '—'}<br>Locations: {lc or '—'}")
    locs = list(values)
    z = [values[n] for n in locs]
    text = [hover.get(n, "No employees in this view") for n in locs]
    top = max(z) if z and max(z) > 0 else 1
    cut = 0.5 / top                                    # colour positions below this mean 0 employees (grey)
    fig = go.Figure(go.Choropleth(
        geojson=geo, locations=locs, z=z, featureidkey=f"properties.{key}", zmin=0, zmax=top,
        colorscale=[[0, "#E4EAF3"], [cut, "#E4EAF3"], [cut, "#9FDDD8"], [0.5, "#1FA5A6"], [1, BRAND_BLUE]],
        marker_line_color="#FFFFFF", marker_line_width=1, text=text,
        hovertemplate="<b>%{location}</b><br>%{text}<extra></extra>",
        colorbar=dict(title=dict(text="Employees", side="right"), thickness=12, len=0.55, x=1.0,
                      outlinewidth=0, tickfont=dict(size=11, color="#5E6B85"))))
    fig.update_geos(fitbounds=False, visible=False, projection_type="natural earth", bgcolor="rgba(0,0,0,0)",
                    lonaxis_range=[67, 98], lataxis_range=[6, 37.5])
    fig.update_layout(height=470, margin=dict(l=0, r=0, t=8, b=0), paper_bgcolor="rgba(0,0,0,0)",
                      font=dict(family=ui.FONT, color=ui.INK),
                      hoverlabel=dict(bgcolor="#FFFFFF", bordercolor=BRAND_TEAL, font=dict(size=12)))
    cfg = {"displayModeBar": False, "scrollZoom": False}
    try:
        box.plotly_chart(fig, theme=None, width="stretch", config=cfg)
    except TypeError:
        box.plotly_chart(fig, theme=None, use_container_width=True, config=cfg)
    if len(unmatched):
        box.caption("Not on the map (name not recognised): " + ", ".join(unmatched["State"].astype(str)))