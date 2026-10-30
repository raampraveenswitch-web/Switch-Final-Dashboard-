import pandas as pd
import streamlit as st

from config import DATASET_LABELS, FIELDS, STATUS_RULES
from services import ui
from services.kpi_registry import KPIS
from services.overview import all_metrics, data_bounds

store = ui.page_setup("Data Explorer", "Workbook, Mapping & Data Quality", "🔎")
ui.gate(store)
m = store.model
ctx = ui.context(store)

ui.tiles([("Workbook", m.source_name, "doc"), ("Worksheets", len(m.sheets), "table"),
          ("Recognised datasets", len(m.datasets), "check"),
          ("Data-quality warnings", sum(i.count for i in m.issues if i.severity == "warning"), "warn"),
          ("Last successful refresh", f"{store.last_refresh_ok:%d %b %H:%M:%S}", "calendar"),
          ("Refresh status", store.watch_status or ("Manual" if not store.monitor_on else "Watching"), "clock")])

tabs = st.tabs(["Worksheets", "Mapping", "Data quality", "Relationships", "Metric availability",
                "Business definitions", "KPI definitions", "Safe preview"])

with tabs[0]:
    rows = [{"Worksheet": p.name, "Rows": p.rows, "Columns": p.columns, "Duplicate rows": p.duplicates,
             "Header row": (p.header_row + 1) if p.header_row is not None else None,
             "Detected as": DATASET_LABELS.get(m.classifications[p.name].dataset, "Not recognised"),
             "Notes": " ".join(p.warnings)} for p in m.profiles]
    ui.table(st, pd.DataFrame(rows), 260)
    for p in m.profiles:
        with st.expander(f"{p.name} — columns"):
            if p.empty:
                st.write("Empty sheet — no records are created from it.")
                continue
            ui.table(st, pd.DataFrame([{"Column": c.name, "Inferred type": c.inferred_type, "Non-null": c.non_null,
                                        "Missing": c.missing, "Unique": c.unique, "Min": c.min_value, "Max": c.max_value}
                                       for c in p.column_profiles]), 300)
    b = data_bounds(m.datasets)
    st.caption(f"Overall date range found in mapped date fields: {b[0]:%d %b %Y} – {b[1]:%d %b %Y}" if b else "No mapped date fields found.")

with tabs[1]:
    st.caption("Auto-detected by column names. Change a dataset type or column and press **Apply mapping** — "
               "nothing is changed in the original workbook.")
    with st.form("mapping_form"):
        new = {}
        types = ["(auto)", "(ignore sheet)"] + list(FIELDS)
        for name, sd in m.sheets.items():
            if sd.empty:
                continue
            cl = m.classifications[name]
            with st.expander(f"{name} → {DATASET_LABELS.get(cl.dataset, 'Not recognised')} ({cl.confidence})"):
                for w in cl.warnings:
                    st.warning(w)
                t = st.selectbox("Dataset type", types, key=f"t|{name}",
                                 index=0 if cl.source == "auto" else (1 if cl.dataset is None else types.index(cl.dataset)))
                target = cl.dataset if t == "(auto)" else None if t == "(ignore sheet)" else t
                if target:
                    cols = ["(not mapped)"] + list(sd.df.columns)
                    chosen = {}
                    gc = st.columns(3)
                    for i, (f, spec) in enumerate(FIELDS[target].items()):
                        cur = cl.mapping.get(f) if target == cl.dataset else None
                        chosen[f] = gc[i % 3].selectbox(spec["label"], cols, index=cols.index(cur) if cur in cols else 0,
                                                        key=f"m|{name}|{target}|{f}")
                    new[name] = {"dataset": target, "mapping": {k: v for k, v in chosen.items() if v != "(not mapped)"}}
                elif t == "(ignore sheet)":
                    new[name] = {"dataset": None, "mapping": {}}
        if st.form_submit_button("Apply mapping"):
            changed = {}
            for name, o in new.items():
                cl = m.classifications[name]
                if o["dataset"] != cl.dataset or o["mapping"] != cl.mapping or cl.source == "manual":
                    changed[name] = o
            store.overrides = {**store.overrides, **changed}
            store.rebuild()
            st.rerun()
    if store.overrides:
        st.info(f"Manual mapping active for: {', '.join(store.overrides)}")
        if st.button("Reset to auto-detected mapping"):
            store.overrides = {}
            store.rebuild()
            st.rerun()

with tabs[2]:
    if m.warnings:
        for w in m.warnings:
            st.warning(w)
    if m.issues:
        ui.table(st, pd.DataFrame([{"Sheet": i.sheet, "Field": i.field, "Count": i.count, "Severity": i.severity,
                                    "Message": i.message} for i in m.issues]), 320)
    elif not m.warnings:
        st.success("No data-quality issues were detected in mapped columns.")
    st.markdown("**Status normalisation audit** (raw wording → category used in metrics)")
    for (ds, fld), rules in STATUS_RULES.items():
        d = m.datasets.get(ds)
        if d is not None and fld + "_norm" in d.columns:
            a = d.groupby([fld, fld + "_norm"], dropna=False).size().reset_index(name="Records")
            a.columns = ["Raw value", "Treated as", "Records"]
            with st.expander(f"{DATASET_LABELS[ds]} · {FIELDS[ds][fld]['label']}"):
                ui.table(st, a, 240)

with tabs[3]:
    if m.relationships:
        st.caption("Datasets are never row-joined. Only distinct Employee IDs are compared, so nothing can be double-counted.")
        ui.table(st, pd.DataFrame(m.relationships), 200)
    else:
        st.info("No shared identifiers found between datasets.")
    if m.dataset_sheets:
        st.write({DATASET_LABELS[k]: v for k, v in m.dataset_sheets.items()})

with tabs[4]:
    res = all_metrics(ctx.ds, ctx.settings, ctx.period)
    rows = [{"Metric": x.label, "Status": "Available" if x.available else "Not available",
             "Reason / basis": x.reason if not x.available else x.detail} for x in res.values()]
    missing_ds = [DATASET_LABELS[d] for d in FIELDS if d not in m.datasets]
    if missing_ds:
        st.info("No data found for: " + ", ".join(missing_ds) + ". Their metrics are not listed as they cannot be calculated.")
    ui.table(st, pd.DataFrame(rows), 420, "avail", searchable=True)

with tabs[5]:
    st.caption("Business inputs the data cannot supply. Leave blank when not approved — dependent metrics then show "
               "'Not available'. No defaults are assumed.")
    S = store.settings
    stages = sorted({str(s) for d in [m.datasets.get("recruitment")] if d is not None and "stage" in d.columns
                     for s in d["stage"].dropna().unique()})
    with st.form("settings_form"):
        order = st.text_area("Recruitment funnel stages, in order (one per line)", "\n".join(S["funnel_order"]),
                             help=("Stage values found in the workbook: " + ", ".join(stages)) if stages else "No stage column mapped.")
        def _num(label, key, help_=""):
            raw = st.text_input(label, "" if S[key] is None else str(S[key]), help=help_)
            try:
                return float(raw) if raw.strip() else None
            except ValueError:
                st.error(f"{label}: enter a number or leave blank.")
                return S[key]
        hp = _num("High-performer threshold (rating ≥)", "high_perf_threshold", "Used only if the workbook has no formal high-performer flag.")
        rs = _num("Official rating scale maximum", "rating_scale_max", "Ratings above this (or below 0) are excluded and reported.")
        tg = _num("PMS completion target (%)", "pms_completion_target")
        bg = _num("Approved total training budget", "training_budget", "Used for budget utilisation if the workbook has no budget column.")
        dd = st.checkbox("Remove exact duplicate rows", S["dedupe_exact_rows"])
        if st.form_submit_button("Save definitions"):
            store.settings = {**S, "funnel_order": [x.strip() for x in order.splitlines() if x.strip()],
                              "high_perf_threshold": hp, "rating_scale_max": rs, "pms_completion_target": tg,
                              "training_budget": bg, "dedupe_exact_rows": dd}
            store.rebuild()
            st.rerun()

with tabs[6]:
    q = st.text_input("Search KPI definitions")
    for k in KPIS:
        if q and q.lower() not in (k["name"] + k["meaning"]).lower():
            continue
        with st.expander(k["name"]):
            st.markdown(f"**Meaning:** {k['meaning']}\n\n**Formula:** `{k['formula']}`\n\n**Numerator:** {k['numerator']} · "
                        f"**Denominator:** {k['denominator']}\n\n**Columns:** {k['columns']}\n\n**Grain:** {k['grain']} · "
                        f"**Period:** {k['period']}\n\n**Status:** {k['standard']}\n\n**Handling:** {k['treatment']}\n\n"
                        f"_{k['example']} (fictional)_")

with tabs[7]:
    st.warning("Previews can contain employee-level records. Identifier and personal-data columns are masked and only "
               f"the first rows are shown. Enable only when needed.")
    if st.toggle("Show read-only preview"):
        name = st.selectbox("Worksheet", [n for n, s in m.sheets.items() if not s.empty])
        if name:
            ui.table(st, ui.mask_preview(m.sheets[name].df.astype(object)), 300)
