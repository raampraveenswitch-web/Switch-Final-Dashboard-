"""Downloads — every dashboard as an editable PowerPoint (native charts) or a print-ready PDF."""
import io
import re
import zipfile

import streamlit as st

from services import report_data as R
from services import report_pdf, report_pptx
from services import ui
from services.insights import Insight

store = ui.page_setup("Downloads", icon="⬇️")
ui.gate(store)
ctx = ui.context(store)
m = store.model

loc_txt = ctx.location if ctx.location and ctx.location != "All" else "All locations"
ui.tiles([("Reporting period", ctx.label or "All data", "calendar"),
          ("Date range", ctx.period.label() if ctx.period else "All data", "clock"),
          ("Location", loc_txt, "target"),
          ("Source workbook", m.source_name, "doc"),
          ("PowerPoint", "Editable native charts", "slides"),
          ("PDF", "Print-ready, 16:9 pages", "pdf")])
st.caption("Files use the **Year, Period and Location** selected in the header above (change them there first). "
           "Page-level filters such as department are not applied to exports. Performance exports use the latest review cycle.")


def _sig() -> str:
    s = {k: v for k, v in store.settings.items() if k != "focus_items"}
    return repr(sorted(s.items(), key=lambda kv: kv[0]))


@st.cache_data(show_spinner=False, max_entries=48)
def _render(key: str, fmt: str, fp: str, period: str, rng: str, loc: str, sig: str, focus: tuple, _ctx, _model) -> bytes:
    """Cached per workbook + selection, so a second click (or a rerun) is instant."""
    def rep_for(k):
        rep = R.build(k, _ctx, _model)
        own = dict(focus).get(k, ())
        rep.focus = [Insight(t, "Your focus item") for t in own] + rep.focus
        return rep
    if key == "pack":
        reps = [rep_for(k) for k, *_ in R.DASHBOARDS if R.availability(_ctx.ds, k)[0]]
        return report_pptx.render_pack(reps) if fmt == "pptx" else report_pdf.render_pack(reps)
    rep = rep_for(key)
    return report_pptx.render(rep) if fmt == "pptx" else report_pdf.render(rep)


def _file(key: str, fmt: str) -> bytes:
    focus = tuple((k, tuple(v)) for k, v in sorted(store.settings.get("focus_items", {}).items()))
    return _render(key, fmt, m.fingerprint, ctx.label, ctx.period.label() if ctx.period else "", ctx.location,
                   _sig(), focus, ctx, m)


def _name(title: str, ext: str) -> str:
    base = f"SWITCH_{title}_{ctx.label}_{loc_txt}".replace("&", "and")
    return re.sub(r"[^A-Za-z0-9_\-]+", "_", base).strip("_") + f".{ext}"


MIME = {"pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation", "pdf": "application/pdf",
        "zip": "application/zip"}


def _buttons(holder, key: str, title: str, enabled: bool):
    ready_key = f"dl_ready_{key}_{m.fingerprint[:8]}_{ctx.label}_{ctx.location}"
    if not st.session_state.get(ready_key):
        if holder.button("Prepare files", key=f"prep_{key}", icon=":material/bolt:", disabled=not enabled,
                         use_container_width=True, type="primary"):
            with st.spinner(f"Building {title}…"):
                _file(key, "pptx"), _file(key, "pdf")
            st.session_state[ready_key] = True
            st.rerun()
        return
    c1, c2 = holder.columns(2)
    c1.download_button("PowerPoint", _file(key, "pptx"), _name(title, "pptx"), MIME["pptx"], key=f"dlp_{key}",
                       icon=":material/slideshow:", use_container_width=True, type="primary")
    c2.download_button("PDF", _file(key, "pdf"), _name(title, "pdf"), MIME["pdf"], key=f"dlf_{key}",
                       icon=":material/picture_as_pdf:", use_container_width=True)


# ---- complete pack -------------------------------------------------------------
avail = {k: R.availability(ctx.ds, k) for k, *_ in R.DASHBOARDS}
n_ok = sum(1 for ok, _ in avail.values() if ok)
box = ui.section("Complete HR Analytics Pack", f"All {n_ok} available dashboards in one file — cover, contents and a section "
                 "per dashboard", icon="download")
a, b = box.columns([2, 1.2], vertical_alignment="center")
a.markdown('<div class="dl-meta">' + "".join(
    f'<span class="tag {"ok" if ok else "na"}">{html_title}</span>'
    for (k, html_title, *_), (ok, _) in zip(R.DASHBOARDS, avail.values())) + "</div>", unsafe_allow_html=True)
_buttons(b, "pack", "HR_Analytics_Pack", n_ok > 0)
zip_key = f"dl_ready_zip_{m.fingerprint[:8]}_{ctx.label}_{ctx.location}"
if not st.session_state.get(zip_key):
    if b.button("Prepare ZIP of separate files", key="prep_zip", icon=":material/folder_zip:", disabled=n_ok == 0,
                use_container_width=True):
        st.session_state[zip_key] = True
        st.rerun()
else:
    zbuf = io.BytesIO()
    with st.spinner("Building and zipping every dashboard (PowerPoint + PDF)…"):
        with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as z:
            for k, title, *_ in R.DASHBOARDS:
                if avail[k][0]:
                    z.writestr(_name(f"{title}_Dashboard", "pptx"), _file(k, "pptx"))
                    z.writestr(_name(f"{title}_Dashboard", "pdf"), _file(k, "pdf"))
    b.download_button("All dashboards as separate files (ZIP)", zbuf.getvalue(), _name("HR_Dashboards", "zip"), MIME["zip"],
                      key="dl_zip", icon=":material/folder_zip:", use_container_width=True)

# ---- one card per dashboard ------------------------------------------------------
st.markdown('<div class="sb-h" style="margin:.6rem 0 .3rem 0">Individual dashboards</div>', unsafe_allow_html=True)
cards = R.DASHBOARDS
for i in range(0, len(cards), 4):
    cols = st.columns(4, gap="small")
    for col, (key, title, area, needs, icon, desc) in zip(cols, cards[i:i + 4]):
        ok, status = avail[key]
        c = col.container(border=True, height=250)
        c.markdown(f'<div class="dl-head"><div class="dl-ico">{ui.svg(icon, 24)}</div><div><div class="dl-title">{title}</div>'
                   f'<div class="ph-sub">{area}</div></div></div><div class="dl-desc">{desc}</div>'
                   f'<div class="dl-meta"><span class="tag {"ok" if ok else "na"}">{status}</span>'
                   f'<span class="tag">PPTX</span><span class="tag">PDF</span></div>', unsafe_allow_html=True)
        _buttons(c, key, f"{title}_Dashboard", ok)
