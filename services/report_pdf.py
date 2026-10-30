"""PDF export (16:9 landscape pages) mirroring the PowerPoint layout. Drawn with matplotlib, so it needs no
browser, Office or system fonts (matplotlib ships DejaVu Sans, which includes ₹, ▲, ▼ and ✔)."""
from __future__ import annotations

import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.image as mpimg  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Polygon, Rectangle  # noqa: E402
from matplotlib.ticker import FuncFormatter, MaxNLocator  # noqa: E402

from config import APP_NAME, LOGO_PATH, PALETTE, TAGLINE  # noqa: E402
from services import presentation as P  # noqa: E402
from services.report_data import MIN_GROUP_NOTE, Chart, Report  # noqa: E402
from services.report_pptx import (BAD, BG, CARD, GOOD, GREEN, H, INK, LINE, MUTED, NAVY, TEAL, W,  # noqa: E402
                                  blend)

FONT = "DejaVu Sans"
plt.rcParams.update({"font.family": FONT, "font.size": 9, "axes.edgecolor": LINE, "pdf.fonttype": 42})
PT = 1.0  # font sizes below are in points; page is 13.333 x 7.5 in like the deck


class Page:
    """One 16:9 page with an inch-based, top-left-origin drawing layer."""

    def __init__(self, bg=BG):
        self.fig = plt.figure(figsize=(W, H), dpi=100)
        self.fig.patch.set_facecolor(bg)
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set_xlim(0, W)
        self.ax.set_ylim(H, 0)
        self.ax.axis("off")

    def box(self, x, y, w, h, fill=CARD, line=LINE, r=0.08, lw=0.8, z=1):
        p = FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}", fc=fill or "none",
                           ec=line or "none", lw=lw if line else 0, zorder=z)
        self.ax.add_patch(p)

    def rect(self, x, y, w, h, fill, z=1):
        self.ax.add_patch(Rectangle((x, y), w, h, fc=fill, ec="none", zorder=z))

    def text(self, x, y, s, size=11, color=INK, bold=False, ha="left", va="top", italic=False, wrap_w=None, z=5):
        if wrap_w:
            s = _wrap(s, wrap_w, size)
        return self.ax.text(x, y, s, fontsize=size, color=color, fontweight="bold" if bold else "normal", ha=ha, va=va,
                            style="italic" if italic else "normal", zorder=z, linespacing=1.3)

    def chart_ax(self, x, y, w, h):
        return self.fig.add_axes([x / W, 1 - (y + h) / H, w / W, h / H])

    def logo(self, x, y, h):
        if LOGO_PATH.exists():
            img = mpimg.imread(str(LOGO_PATH))
            ratio = img.shape[1] / img.shape[0]
            a = self.chart_ax(x, y, h * ratio, h)
            a.imshow(img)
            a.axis("off")
            return h * ratio
        self.text(x, y + h / 2, "SW//TCH", h * 50, NAVY, True, va="center")
        return h * 5


def _wrap(s: str, width_in: float, size: float) -> str:
    per_line = max(10, int(width_in * 72 / (size * 0.55)))
    out, line = [], ""
    for word in str(s).split():
        if len(line) + len(word) + 1 > per_line and line:
            out.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    out.append(line)
    return "\n".join(out)


def _numfmt(fmt: str):
    return {"int": lambda v: f"{v:,.0f}", "dec1": lambda v: P.num(v), "dec2": lambda v: f"{v:.2f}",
            "pct": lambda v: f"{v:.1f}%"}.get(fmt, lambda v: f"{v:,.0f}")


def _clean_ax(a, grid=True, left=True):
    for s in ("top", "right"):
        a.spines[s].set_visible(False)
    a.spines["left"].set_visible(False)
    a.spines["bottom"].set_color(LINE)
    a.tick_params(colors=MUTED, labelsize=8.5, length=0)
    if grid:
        a.grid(axis="y", color="#E6EBF3", lw=0.8)
        a.set_axisbelow(True)
    if not left:
        a.set_yticks([])
    a.set_facecolor("none")


# ------------------------------------------------------------------ chart drawing
def _combo(pg: Page, c: Chart, x, y, w, h):
    a = pg.chart_ax(x + 0.35, y + 0.35, w - 0.75, h - 0.65)
    n, k = len(c.cats), max(len(c.series), 1)
    bw = 0.8 / k
    cols = [NAVY, TEAL, "#5B8BD9", "#7FCFCB"]
    xs = list(range(n))
    bar_top = max([max([v for v in vals if v is not None] or [0]) for _, vals in c.series] or [1]) or 1
    handles = []
    for i, (name, vals) in enumerate(c.series):
        off = (i - (k - 1) / 2) * bw
        b = a.bar([p + off for p in xs], [v or 0 for v in vals], bw * 0.92, color=cols[i % 4], label=name, zorder=2)
        handles.append(b)
        if not c.line:
            for p, v in zip(xs, vals):
                if v is not None:
                    a.text(p + off, v + bar_top * 0.02, _numfmt(c.fmt)(v), ha="center", va="bottom", fontsize=8, color=INK)
    _clean_ax(a)
    a.set_xticks(xs)
    a.set_xticklabels(c.cats, fontsize=8.5)
    a.set_xlim(-0.6, n - 0.4)
    a.yaxis.set_major_locator(MaxNLocator(5, integer=all(float(v or 0).is_integer() for _, vs in c.series for v in vs)))
    a.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}" if float(v).is_integer() else f"{v:,.1f}"))
    if c.line:
        lv = c.line[1]
        pts = [(p, v) for p, v in zip(xs, lv) if v is not None]
        tgt = a.twinx() if c.secondary else a
        if c.secondary:
            _clean_ax(tgt, grid=False)
            lo, hi = min(v for _, v in pts), max(v for _, v in pts)
            base = max(0.0, lo - (hi - lo) * 1.8) if hi > lo else 0
            tgt.set_ylim(base, hi + (hi - base) * 0.2 if hi > base else hi * 1.2 + 1)
            a.set_ylim(0, bar_top * 2.1)
            tgt.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
        else:
            a.set_ylim(0, max(bar_top, max(v for _, v in pts)) * 1.28)
        ln, = tgt.plot([p for p, _ in pts], [v for _, v in pts], color=GREEN, lw=2.2, marker="o", ms=5,
                       mec="white", mew=1, zorder=4, label=c.line[0])
        handles.append(ln)
        integer = all(float(v).is_integer() for _, v in pts)
        for p, v in pts:
            tgt.annotate(f"{v:,.0f}" if integer or v >= 100 else P.num(v), (p, v), textcoords="offset points",
                         xytext=(0, 6), ha="center", fontsize=8, color=INK, fontweight="bold", zorder=5)
    else:
        a.set_ylim(0, bar_top * 1.2)
    if len(handles) > 1 or c.line:
        a.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=len(handles), frameon=False,
                 fontsize=8.5, handlelength=1.2)


def _bars(pg: Page, c: Chart, x, y, w, h, horizontal: bool):
    vals = [v or 0 for v in c.series[0][1]]
    cats = [s if len(s) <= 24 else s[:23] + "…" for s in map(str, c.cats)]
    f = _numfmt(c.fmt)
    top = max(vals) if vals and max(vals) > 0 else 1
    if horizontal:
        lab_w = min(2.0, max(0.6, max(len(s) for s in cats) * 0.075))
        a = pg.chart_ax(x + 0.2 + lab_w, y + 0.2, w - 0.5 - lab_w, h - 0.35)
        n = len(vals)
        hgt = 0.45 if n <= 3 else 0.6 if n <= 5 else 0.72
        a.barh(range(n), vals, hgt, color=NAVY, zorder=2)
        a.set_yticks(range(n))
        a.set_yticklabels(cats, fontsize=9, color=INK)
        a.invert_yaxis()
        a.set_xlim(0, top * 1.22)
        for i, v in enumerate(vals):
            a.text(v + top * 0.015, i, f(v), va="center", fontsize=8.5, color=INK)
        _clean_ax(a, grid=False)
        a.set_xticks([])
        a.spines["bottom"].set_visible(False)
    else:
        a = pg.chart_ax(x + 0.4, y + 0.25, w - 0.65, h - 0.55)
        n = len(vals)
        a.bar(range(n), vals, 0.6 if n > 3 else 0.45, color=TEAL, zorder=2)
        a.set_xticks(range(n))
        a.set_xticklabels([s if len(s) <= 14 else s[:13] + "…" for s in cats], fontsize=8.5,
                          rotation=0 if n <= 6 else 30, ha="center" if n <= 6 else "right")
        a.set_ylim(0, top * 1.18)
        for i, v in enumerate(vals):
            a.text(i, v + top * 0.02, f(v), ha="center", va="bottom", fontsize=8.5, color=INK)
        _clean_ax(a)
        a.yaxis.set_major_locator(MaxNLocator(5, integer=all(float(v).is_integer() for v in vals)))


def _line(pg: Page, c: Chart, x, y, w, h):
    a = pg.chart_ax(x + 0.4, y + 0.25, w - 0.65, h - 0.55)
    vals = c.series[0][1]
    xs = list(range(len(vals)))
    pts = [(p, v) for p, v in zip(xs, vals) if v is not None]
    a.plot([p for p, _ in pts], [v for _, v in pts], color=TEAL, lw=2.2, marker="o", ms=5, zorder=3)
    a.fill_between([p for p, _ in pts], [v for _, v in pts], color=TEAL, alpha=0.08)
    f = _numfmt(c.fmt)
    for p, v in pts:
        a.annotate(f(v), (p, v), textcoords="offset points", xytext=(0, 6), ha="center", fontsize=8, color=INK)
    a.set_xticks(xs)
    a.set_xticklabels(c.cats, fontsize=8.5)
    a.set_ylim(0, max(v for _, v in pts) * 1.25 if pts else 1)
    _clean_ax(a)


def _donut(pg: Page, c: Chart, x, y, w, h):
    vals = [v or 0 for v in c.series[0][1]]
    tot = sum(vals) or 1
    share = [v / tot * 100 for v in vals]
    d = min(w * 0.5, h * 0.92)
    a = pg.chart_ax(x + 0.02 * w + (0.5 * w - d) / 2, y + (h - d) / 2, d, d)
    cols = [PALETTE[i % len(PALETTE)] for i in range(len(vals))]
    wedges, _ = a.pie(vals, colors=cols, startangle=90, counterclock=False,
                      wedgeprops=dict(width=0.38, edgecolor="white", linewidth=1.5))
    import math
    for wd, s in zip(wedges, share):
        if s >= 6:
            ang = math.radians((wd.theta1 + wd.theta2) / 2)
            a.text(0.81 * math.cos(ang), 0.81 * math.sin(ang), f"{s:.0f}%", ha="center", va="center", fontsize=8,
                   color="white", fontweight="bold")
    a.text(0, 0.06, f"{tot:,.0f}", ha="center", va="center", fontsize=17, fontweight="bold", color=INK)
    if c.center:
        a.text(0, -0.2, c.center, ha="center", va="center", fontsize=8, color=MUTED)
    a.set_aspect("equal")
    lx, lw = x + 0.56 * w, 0.43 * w
    rowh = min(0.42, 0.84 * h / max(len(vals), 1))
    ly = y + (h - rowh * len(vals)) / 2
    for i, (nme, v, s) in enumerate(zip(c.cats, vals, share)):
        yy = ly + i * rowh + rowh / 2
        pg.box(lx, yy - 0.07, 0.14, 0.14, fill=cols[i], line=None, r=0.03, z=3)
        nm = nme if len(nme) <= 20 else nme[:19] + "…"
        pg.text(lx + 0.24, yy, f"{nm}", 9.5, INK, va="center")
        pg.text(lx + lw - 0.05, yy, f"{s:.0f}%  ({v:,.0f})", 9.5, INK, True, ha="right", va="center")


def _funnel(pg: Page, c: Chart, x, y, w, h):
    stages, vals = c.cats, [v or 0 for v in c.series[0][1]]
    n = len(stages)
    first, mx = (vals[0] or 1), (max(vals) or 1)
    rh = min(0.62, h / n)
    gap = rh * 0.16
    name_w, val_w = w * 0.26, w * 0.2
    bx0, bwid = x + name_w, w - name_w - val_w
    top = y + (h - rh * n) / 2
    for i, (s, v) in enumerate(zip(stages, vals)):
        bw = max(0.35, bwid * v / mx)
        by = top + i * rh
        pg.box(bx0 + (bwid - bw) / 2, by + gap / 2, bw, rh - gap, fill=blend("#3CC1C0", NAVY, i / max(n - 1, 1)), line=None,
               r=0.06, z=3)
        pg.text(x + name_w - 0.1, by + rh / 2, str(s), 10, INK, True, ha="right", va="center")
        pg.text(x + w - val_w + 0.08, by + rh / 2, f"{v:,.0f}", 10.5, INK, True, va="center")
        pg.text(x + w - val_w + 0.08 + 0.12 * len(f"{v:,.0f}") + 0.12, by + rh / 2, f"{v / first * 100:.0f}%", 9.5, MUTED, va="center")


def _card(pg: Page, x, y, w, h, title, sub=""):
    pg.box(x, y, w, h)
    pg.text(x + 0.22, y + 0.18, title, 13, INK, True)
    if sub:
        pg.text(x + 0.22, y + 0.5, sub, 9.5, MUTED)


def draw_chart(pg: Page, c: Chart, x, y, w, h):
    _card(pg, x, y, w, h, c.title, c.subtitle)
    cx, cy, cw, ch = x + 0.15, y + 0.85, w - 0.3, h - 1.05 - (0.25 if c.note else 0)
    if not c.ok:
        pg.box(x + 0.3, y + 1.0, w - 0.6, 1.0, fill="#F7F9FC", line="#C8D1E0", z=2)
        pg.text(x + 0.45, y + 1.5, f"Not available — {c.reason}", 10.5, MUTED, va="center", wrap_w=w - 0.9)
        return
    if c.kind == "combo":
        _combo(pg, c, cx, cy, cw, ch)
    elif c.kind in ("bar", "hbar"):
        _bars(pg, c, cx, cy, cw, ch, c.kind == "hbar")
    elif c.kind == "line":
        _line(pg, c, cx, cy, cw, ch)
    elif c.kind == "donut":
        _donut(pg, c, cx, cy, cw, ch)
    elif c.kind == "funnel":
        _funnel(pg, c, cx + 0.1, cy + 0.05, cw - 0.2, ch - 0.1)
    if c.note:
        pg.text(x + 0.22, y + h - 0.32, c.note, 8.5, MUTED, italic=True)


# ------------------------------------------------------------------ page furniture
def header(pg: Page, rep: Report):
    pg.rect(0, 0, W, 1.08, CARD)
    lw = pg.logo(0.45, 0.3, 0.46)
    x = 0.45 + lw + 0.28
    pg.rect(x, 0.26, 0.04, 0.56, NAVY, z=2)
    pg.rect(x, 0.54, 0.04, 0.28, GREEN, z=3)
    pg.text(x + 0.22, 0.24, rep.title, 21, NAVY, True)
    pg.text(x + 0.22, 0.66, TAGLINE, 11.5, GREEN, True)
    pg.box(W - 3.75, 0.33, 3.3, 0.46, fill="#F3F6FA", line=LINE, r=0.23, z=2)
    loc = rep.location if rep.location and rep.location != "All" else "All locations"
    pg.text(W - 2.1, 0.56, f"{rep.period}  ·  {loc}", 11, INK, True, ha="center", va="center")
    pg.rect(0, 1.08, W, 0.035, NAVY, z=2)
    pg.rect(0, 1.08, 2.2, 0.035, GREEN, z=3)


def footer(pg: Page, rep: Report, n: int, color=MUTED):
    pg.text(0.45, H - 0.3, f"{APP_NAME}  ·  Confidential", 8.5, color)
    pg.text(W / 2, H - 0.3, f"{rep.period_range}  ·  Source: {rep.source or 'workbook'}", 8.5, color, ha="center")
    pg.text(W - 0.45, H - 0.3, str(n), 8.5, color, ha="right")


def _stripes(pg: Page, x, y, h, color, n=2):
    for i in range(n):
        x0 = x + i * 0.62
        pg.ax.add_patch(Polygon([(x0 + 0.4, y), (x0 + 0.9, y), (x0 + 0.5, y + h), (x0, y + h)], fc=color, ec="none", zorder=2))


def cover(rep: Report, title: str, area: str, lines=None) -> Page:
    pg = Page("#FFFFFF")
    pg.rect(8.75, 0, W - 8.75, H, NAVY)
    _stripes(pg, 10.0, 1.6, 4.3, GREEN)
    pg.text(9.15, H - 1.2, "HR Analytics", 16, "#FFFFFF", True)
    pg.text(9.15, H - 0.82, "Automated from your HR workbook", 10.5, "#C9D6EE")
    pg.logo(0.8, 0.85, 0.85)
    pg.rect(0.8, 2.15, 1.2, 0.06, GREEN)
    pg.text(0.8, 2.4, title, 36, NAVY, True)
    pg.text(0.8, 3.3, area, 17, MUTED)
    pg.text(0.8, 3.8, TAGLINE, 19, GREEN, True)
    loc = rep.location if rep.location and rep.location != "All" else "All locations"
    meta = lines or [f"Reporting period:  {rep.period}  ({rep.period_range})", f"Location:  {loc}",
                     f"Source workbook:  {rep.source or '—'}", f"Generated:  {rep.generated:%d %b %Y, %H:%M}"]
    for i, m in enumerate(meta):
        pg.text(0.8, 4.75 + i * 0.32, m, 11.5, INK)
    pg.text(0.8, H - 0.5, f"{APP_NAME}  ·  Confidential", 8.5, MUTED)
    return pg


def divider(rep: Report, n: int) -> Page:
    pg = Page(NAVY)
    _stripes(pg, 10.4, 0, H, "#1F5BB8")
    _stripes(pg, 11.1, 2.2, 3.1, GREEN)
    pg.text(0.9, 2.6, rep.title, 34, "#FFFFFF", True)
    pg.text(0.9, 3.5, rep.area, 17, "#C9D6EE")
    pg.text(0.9, 4.1, f"{rep.period}  ·  {rep.period_range}", 11.5, "#C9D6EE")
    pg.text(W - 0.45, H - 0.3, str(n), 8.5, "#C9D6EE", ha="right")
    return pg


def kpi_page(rep: Report, n: int) -> Page:
    pg = Page()
    header(pg, rep)
    pg.text(0.45, 1.32, "Key Metrics", 14, INK, True)
    vs = next((d.vs for _, d in rep.kpis if d), "")
    if vs:
        pg.text(W - 0.45, 1.36, f"Arrows compare with {vs}. Green = better, red = worse, blue = neutral.", 9, MUTED, ha="right")
    head, extra = rep.kpis[:6], rep.kpis[6:10]
    cw, chh, gx, gy = (W - 0.9 - 0.5) / 3, 1.62, 0.25, 0.22
    for i, (m, d) in enumerate(head):
        x, y = 0.45 + (i % 3) * (cw + gx), 1.78 + (i // 3) * (chh + gy)
        pg.box(x, y, cw, chh)
        pg.rect(x, y + 0.18, 0.07, chh - 0.36, TEAL if i % 2 else NAVY, z=2)
        pg.text(x + 0.3, y + 0.18, P.label(m), 11.5, MUTED, True)
        if m.available:
            pg.text(x + 0.3, y + 0.5, P.fmt(m), 27, INK, True)
            if d:
                tone = {"good": GOOD, "bad": BAD}.get(d.tone, NAVY)
                arrow = "" if d.value == 0 else ("▲ " if d.up else "▼ ")
                t = pg.text(x + 0.3, y + 1.2, arrow + d.text, 11.5, tone, True)
                pg.text(x + 0.3 + 0.11 * len(arrow + d.text) + 0.2, y + 1.22, f"vs {d.vs}", 9.5, MUTED)
            elif m.detail:
                pg.text(x + 0.3, y + 1.22, m.detail, 9, MUTED)
        else:
            pg.text(x + 0.3, y + 0.55, "Not available", 16, "#7A8499", True)
            pg.text(x + 0.3, y + 0.98, m.reason.replace("Not available — ", ""), 8.5, MUTED, wrap_w=cw - 0.5)
    if extra:
        y = 1.78 + 2 * (chh + gy) + 0.05
        mw = (W - 0.9 - 0.25 * (len(extra) - 1)) / len(extra) if len(extra) > 1 else 4.0
        for i, (m, d) in enumerate(extra):
            x = 0.45 + i * (mw + 0.25)
            pg.box(x, y, mw, 1.05)
            pg.text(x + 0.22, y + 0.15, P.label(m), 10, MUTED, True)
            val = P.fmt(m) if m.available else "Not available"
            pg.text(x + 0.22, y + 0.68, val, 17 if m.available else 12, INK if m.available else "#7A8499", True, va="center")
            if d and m.available:
                tone = {"good": GOOD, "bad": BAD}.get(d.tone, NAVY)
                pg.text(x + 0.22 + 0.15 * len(val) + 0.25, y + 0.69, ("" if d.value == 0 else ("▲ " if d.up else "▼ ")) + d.text,
                        10, tone, True, va="center")
    footer(pg, rep, n)
    return pg


def chart_page(rep: Report, charts: list[Chart], n: int) -> Page:
    pg = Page()
    header(pg, rep)
    cw = (W - 0.9 - 0.25) / 2
    for i, c in enumerate(charts[:2]):
        draw_chart(pg, c, 0.45 + i * (cw + 0.25), 1.35, cw if len(charts) > 1 else W - 0.9, 5.55)
    footer(pg, rep, n)
    return pg


def table_page(rep: Report, n: int) -> Page:
    title, df = rep.table
    pg = Page()
    header(pg, rep)
    t, sub = (title.split(" — ") + [""])[:2]
    _card(pg, 0.45, 1.35, W - 0.9, 5.55, t, sub)
    cols = list(df.columns)
    x0, y0, tw = 0.7, 2.2, W - 1.4
    cw = tw / len(cols)
    rh = 0.34
    pg.rect(x0, y0, tw, rh, NAVY, z=2)
    for j, c in enumerate(cols):
        pg.text(x0 + j * cw + 0.1, y0 + rh / 2, str(c), 9.5, "#FFFFFF", True, va="center")
    for i, (_, r) in enumerate(df.iterrows(), start=1):
        yy = y0 + i * rh
        if i % 2 == 0:
            pg.rect(x0, yy, tw, rh, "#F3F6FA", z=2)
        for j, c in enumerate(cols):
            v = r[c]
            txt = "" if v is None or (isinstance(v, float) and v != v) else (P.num(float(v)) if isinstance(v, float) else str(v))
            pg.text(x0 + j * cw + 0.1, yy + rh / 2, txt[:28], 9.5, INK, va="center")
    footer(pg, rep, n)
    return pg


def _focus_rows(rep: Report):
    rows = []
    for i in rep.focus:
        rows.append(("⚠" if i.kind == "attention" else "✔", "#D08A14" if i.kind == "attention" else GREEN, i.text))
        if i.action:
            rows.append(("➜", TEAL, i.action))
    return rows or [("•", MUTED, "No rule-based items from the current data.")]


def _focus_card(pg: Page, rep: Report, x, y, w, h, max_rows=9):
    _card(pg, x, y, w, h, "Initiatives & Focus", "Rule-based items from the current data")
    yy = y + 0.9
    for sym, col, txt in _focus_rows(rep)[:max_rows]:
        wrapped = _wrap(txt, w - 1.0, 11)
        pg.text(x + 0.3, yy, sym, 13, col, True)
        pg.text(x + 0.7, yy + 0.02, wrapped, 11, INK)
        yy += 0.25 + 0.24 * (wrapped.count("\n") + 1)
        if yy > y + h - 0.5:
            break


def _notes(rep: Report):
    out = [(t, r) for t, r in rep.notes[:7]] + [("Confidentiality", MIN_GROUP_NOTE)]
    vs = next((d.vs for _, d in rep.kpis if d), "")
    if vs:
        out.append(("Comparison", f"changes are vs {vs}."))
    return out


def _notes_block(pg: Page, items, x, y, w, size=9.5):
    for t, r in items:
        s = _wrap(r, w, size)
        pg.text(x, y, t, size, INK, True)
        pg.text(x, y + 0.2, s, size, MUTED)
        y += 0.2 * (s.count("\n") + 2) + 0.1
    return y


def focus_page(rep: Report, n: int, chart: Chart | None = None) -> Page:
    pg = Page()
    header(pg, rep)
    if chart is not None:
        cw = (W - 0.9 - 0.25) / 2
        draw_chart(pg, chart, 0.45, 1.35, cw, 5.55)
        rx = 0.45 + cw + 0.25
        _focus_card(pg, rep, rx, 1.35, cw, 3.6, max_rows=6)
        _card(pg, rx, 5.15, cw, 1.75, "Data Notes")
        _notes_block(pg, _notes(rep)[-2:], rx + 0.22, 5.55, cw - 0.44, 8.5)
    else:
        lw = (W - 0.9) * 0.6
        _focus_card(pg, rep, 0.45, 1.35, lw, 5.55)
        rx, rw = 0.45 + lw + 0.25, W - 0.9 - lw - 0.25
        _card(pg, rx, 1.35, rw, 5.55, "Data Notes", "What could not be shown, and why")
        _notes_block(pg, _notes(rep), rx + 0.25, 2.15, rw - 0.5)
    footer(pg, rep, n)
    return pg


def _pages(rep: Report, n: int, with_cover: bool):
    yield (cover(rep, rep.title, rep.area) if with_cover else divider(rep, n))
    n += 1
    if not rep.available:
        pg = Page()
        header(pg, rep)
        pg.text(0.8, 2.5, f"Not available — {rep.reason}", 15, MUTED)
        footer(pg, rep, n)
        yield pg
        return
    yield kpi_page(rep, n)
    n += 1
    ok = [c for c in rep.charts if c.ok]
    last = ok.pop() if len(ok) % 2 else None
    for i in range(0, len(ok), 2):
        yield chart_page(rep, ok[i:i + 2], n)
        n += 1
    if rep.table is not None:
        yield table_page(rep, n)
        n += 1
    yield focus_page(rep, n, last)


def _save(pages, title: str) -> bytes:
    buf = io.BytesIO()
    with PdfPages(buf, metadata={"Title": title, "Author": "SWITCH HR Analytics"}) as pdf:
        for pg in pages:
            pdf.savefig(pg.fig, facecolor=pg.fig.get_facecolor())
            plt.close(pg.fig)
    return buf.getvalue()


def render(rep: Report) -> bytes:
    return _save(_pages(rep, 1, True), f"SWITCH {rep.title} — {rep.period}")


def render_pack(reports: list[Report]) -> bytes:
    def gen():
        first = reports[0]
        yield cover(first, "HR Analytics Pack", "All dashboards")
        pg = Page()
        header(pg, first)
        pg.text(0.45, 1.4, "Contents", 18, INK, True)
        for i, r in enumerate(reports):
            y = 2.0 + i * 0.62
            pg.box(0.45, y, 0.46, 0.46, fill=NAVY if i % 2 == 0 else TEAL, line=None, r=0.23, z=2)
            pg.text(0.68, y + 0.23, str(i + 1), 12, "#FFFFFF", True, ha="center", va="center")
            pg.text(1.1, y + 0.23, r.title, 13.5, INK, True, va="center")
            pg.text(1.1 + 0.13 * len(r.title) + 0.3, y + 0.24, r.area, 10.5, MUTED, va="center")
        footer(pg, first, 2)
        yield pg
        n = 3
        for r in reports:
            pages = list(_pages(r, n, False))
            n += len(pages)
            yield from pages
    return _save(gen(), f"SWITCH HR Analytics Pack — {reports[0].period}")
