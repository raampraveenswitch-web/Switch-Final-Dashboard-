"""PPT/PDF exports: every dashboard renders to a valid file from a workbook, and an empty model gives no figures."""
import io
import zipfile

import pytest
from pptx import Presentation

from services import presentation as P
from services import report_data as R
from services import report_pdf, report_pptx


@pytest.fixture
def ctx(full_store):
    return P.build_ctx(full_store.model.datasets, full_store.settings)


@pytest.mark.parametrize("key", list(R.BUILDERS))
def test_each_dashboard_exports_pptx_and_pdf(key, ctx, full_store):
    rep = R.build(key, ctx, full_store.model)
    pptx = report_pptx.render(rep)
    assert zipfile.is_zipfile(io.BytesIO(pptx))
    deck = Presentation(io.BytesIO(pptx))
    assert len(deck.slides) >= (3 if rep.available else 2)
    pdf = report_pdf.render(rep)
    assert pdf[:5] == b"%PDF-" and len(pdf) > 5000


def test_pack_contains_every_available_dashboard(ctx, full_store):
    reps = [R.build(k, ctx, full_store.model) for k in R.BUILDERS if R.availability(ctx.ds, k)[0]]
    deck = Presentation(io.BytesIO(report_pptx.render_pack(reps)))
    text = " ".join(sh.text_frame.text for s in deck.slides for sh in s.shapes if sh.has_text_frame)
    for r in reps:
        assert r.title in text
    assert report_pdf.render_pack(reps)[:5] == b"%PDF-"


def test_export_kpis_match_dashboard_metrics(ctx, full_store):
    from services import metrics as M
    rep = R.build("recruitment", ctx, full_store.model)
    r = ctx.ds["recruitment"]
    assert rep.kpis[0][0].value == M.rec_requisitions(r, ctx.period).value
    assert rep.kpis[1][0].value == M.rec_filled(r, ctx.period).value


def test_missing_dataset_is_reported_not_invented(full_store):
    ds = {k: v for k, v in full_store.model.datasets.items() if k != "training"}
    rep = R.build("training", P.build_ctx(ds, full_store.settings))
    assert not rep.available and "training" in rep.reason and not rep.kpis
