"""E-ink chart kit for Kindle editions (McKinsey-style, grayscale, direct labels, no legends).

Drop-in superset of the original kindle_charts.py: finish(fig, name) and
stacked_label_bars(rows, title, sub, name, fmt, xmax) keep their signatures.

Every chart function:
  * takes title (an ACTION title: the takeaway, ideally with a number), sub (metric, unit, period),
    name (file name inside OUT), source ("Source: ..." footer, required on new functions);
  * writes OUT/name as a mode-'L' PNG exactly 1236 px wide, portrait or square, snapped to the
    5 tones in TONES (nominal 16-level grid; device rendering may still resample);
  * returns a dict (kind, path, title, sub, source, data, fmt) you can pass to text_fallback() or figure_html().

E-ink constants (why):
  WIDTH_PX 1236     6.8-inch Paperwhite (11th generation) reference width at 300 ppi (W = 4.12 in at 300 dpi).
  TONES             0 / 85 / 153 / 221 / 255 = 0, 5, 9, 13, 15 of 16 Kindle gray steps: exact panel levels,
                    widely spaced design targets; verify separation on the actual device.
  MIN_PT 9.5        9.5 pt at 300 dpi = 40 px em, ~29 px cap height (DejaVu cap = 0.73 em): about the
                    cap height of default Kindle body text, so nothing needs zoom; still ~18 px cap at 758 px.
  LW_MIN 1.5 pt     6 px at 1236 px (>= 2.5 px rule even after downscaling to 758 px: ~3.8 px).
  LW_HI 3.4 pt      highlighted series: ~14 px, unmistakably black and heavy.
  MIN_ASPECT 1.0    height >= width (portrait or square); MAX_ASPECT 1.30 keeps the image inside one
                    Paperwhite page (1648/1236 = 1.33) so the reader never shrinks it to fit.
  MAX_BARS 8, MAX_LINES 4   more than that is a table -> use text_fallback().
Fonts: DejaVu Sans, which ships inside matplotlib (no system font dependency).

Optional keyword style= on the chart functions applies one eink_style preset for
that call and restores module globals afterward. Omit it to keep the current
globals, including an enclosing style() block. Pass grid= explicitly to override
the preset's guides on line_chart.
"""
import os, re, html, textwrap, warnings
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.backends.backend_agg import RendererAgg
from matplotlib.ticker import MaxNLocator
from PIL import Image

# ---------------------------------------------------------------- constants
OUT = "kchart/"
DPI = 300
WIDTH_PX = 1236
W = WIDTH_PX / DPI                    # 4.12 in
MIN_ASPECT, MAX_ASPECT = 1.0, 1.30
TONES = (0, 85, 153, 221, 255)        # black, dark, mid, light, white
BLACK, DARK, MID, LIGHT = "#000000", "#555555", "#999999", "#DDDDDD"
TITLE_PT, SUB_PT, LABEL_PT, MIN_PT, BIG_PT = 13, 10.5, 11, 9.5, 64
LW_MIN, LW_MUTED, LW_HI, LW_GRID = 1.5, 1.5, 3.4, 1.5
MAX_BARS, MAX_LINES = 8, 4
MARGIN = 0.06                          # in, left/right page margin inside the image
FONT = "DejaVu Sans"
MUTED_STYLES = [(DARK, (0, (5, 2.2))), (MID, (0, (1, 1.6))), (DARK, (0, (6, 1.6, 1, 1.6)))]  # dash, dot, dash-dot
plt.rcParams.update({"font.family": FONT, "font.size": LABEL_PT, "text.color": BLACK,
    "axes.edgecolor": BLACK, "xtick.color": DARK, "ytick.color": DARK, "savefig.dpi": DPI,
    "figure.dpi": DPI, "lines.solid_capstyle": "round", "lines.dash_capstyle": "round",
    "axes.linewidth": LW_MIN, "xtick.major.width": LW_MIN, "ytick.major.width": LW_MIN,
    "xtick.labelsize": MIN_PT, "ytick.labelsize": MIN_PT, "text.parse_math": False})  # "$150K" stays literal
DARK_TXT = "#333333"  # snaps to DARK (85) after quantization; used only for secondary text
_OMIT = object()

def _styled(style_key, call):
    """Run call(design) inside one style preset, then restore module globals."""
    from eink_style import style as style_ctx
    with style_ctx(style_key) as design:
        return call(design)

_R = RendererAgg(10, 10, DPI)
def text_w(s, size, bold=False):
    """Rendered width of s in inches."""
    fp = FontProperties(family=FONT, size=size, weight="bold" if bold else "normal")
    return _R.get_text_width_height_descent(s, fp, ismath=False)[0] / DPI

def wrap(s, size, width_in, bold=False):
    """Greedy word wrap to width_in inches using real glyph metrics."""
    out = []
    for para in str(s).split("\n"):
        line = ""
        for word in para.split():
            t = (line + " " + word).strip()
            if line and text_w(t, size, bold) > width_in: out.append(line); line = word
            else: line = t
        out.append(line)
    return out

def one_line(s, size, width_in, bold=False):
    """First wrapped line; adds an ellipsis and warns if text was cut (shorten the label instead)."""
    ls = wrap(s, size, width_in, bold)
    if len(ls) == 1: return ls[0]
    warnings.warn("label cut to fit: %r" % s); t = ls[0]
    while t and text_w(t + "…", size, bold) > width_in: t = t[:-1]
    return t.rstrip() + "…"

def lh(size, k=1.28): return size * k / 72.0  # line pitch in inches

# ---------------------------------------------------------------- frame + save
class _Frame:
    """Vertical stack: title, subtitle, body axes, source footer. Units: inches."""
    def __init__(self, body_h, title, sub, source, min_body=0.0, left=MARGIN, right=MARGIN, body_gap=0.14, below=0.0):
        tw = W - 2 * MARGIN
        self.tl = wrap(title, TITLE_PT, tw, True) if title else []
        self.sl = wrap(sub, SUB_PT, tw) if sub else []
        src = source if (not source or source.lower().startswith("source")) else "Source: " + source
        self.fl = wrap(src, MIN_PT, tw) if src else []
        top = 0.06 + len(self.tl) * lh(TITLE_PT) + (0.03 + len(self.sl) * lh(SUB_PT) if self.sl else 0) + body_gap
        bot = (0.12 + len(self.fl) * lh(MIN_PT) + 0.05) if self.fl else 0.08
        bot += below
        body_h = max(body_h, min_body, W * MIN_ASPECT - top - bot)
        H = top + body_h + bot
        if H > W * MAX_ASPECT + 1e-6:
            warnings.warn("chart is %.2f:1 tall; Kindle will shrink it to fit a page - split it or trim rows" % (H / W))
        self.H, self.top, self.bot, self.body_h = H, top, bot, body_h
        self.fig = plt.figure(figsize=(W, H))
        self.ax = self.fig.add_axes([left / W, bot / H, (W - left - right) / W, body_h / H])
        self.ax_w = W - left - right
        T = self.fig.dpi_scale_trans
        y = H - 0.06
        for l in self.tl:
            self.fig.text(MARGIN, y, l, transform=T, fontsize=TITLE_PT, fontweight="bold", va="top"); y -= lh(TITLE_PT)
        if self.sl: y -= 0.03
        for l in self.sl:
            self.fig.text(MARGIN, y, l, transform=T, fontsize=SUB_PT, color=DARK_TXT, va="top"); y -= lh(SUB_PT)
        if self.fl:
            y = 0.05 + len(self.fl) * lh(MIN_PT)  # footer sits under any `below` space
            self.fig.lines.append(plt.Line2D([MARGIN / W, (W - MARGIN) / W], [(y + 0.05) / H] * 2,
                                             transform=self.fig.transFigure, color=MID, lw=LW_MIN))
            for l in self.fl:
                self.fig.text(MARGIN, y, l, transform=T, fontsize=MIN_PT, color=DARK_TXT, va="top"); y -= lh(MIN_PT)

def _quantize(im):
    lut = [min(TONES, key=lambda t: abs(t - v)) for v in range(256)]
    return im.convert("L").point(lut)

def finish(fig, name, tight=False):
    """Save fig to OUT/name as an e-ink-safe PNG: mode L, exactly WIDTH_PX wide, portrait/square,
    snapped to TONES, optimized. Works for any figure (old callers included)."""
    os.makedirs(OUT or ".", exist_ok=True); path = os.path.join(OUT, name)
    kw = dict(bbox_inches="tight", pad_inches=0.08) if tight else {}
    fig.savefig(path, facecolor="white", dpi=DPI, **kw); plt.close(fig)
    im = Image.open(path).convert("L")
    if im.width != WIDTH_PX:
        im = im.resize((WIDTH_PX, round(im.height * WIDTH_PX / im.width)), Image.LANCZOS)
    if im.height < im.width * MIN_ASPECT:  # never ship landscape: pad white below
        pad = Image.new("L", (im.width, round(im.width * MIN_ASPECT)), 255); pad.paste(im, (0, (pad.height - im.height) // 2)); im = pad
    _quantize(im).save(path, optimize=True)
    return path

def check_png(path):
    """Return a list of e-ink rule violations for a PNG (empty list = OK)."""
    im = Image.open(path); p = []
    if im.mode != "L": p.append("mode %s, want L" % im.mode)
    if im.width != WIDTH_PX: p.append("width %d, want %d" % (im.width, WIDTH_PX))
    if im.height < im.width * MIN_ASPECT - 1: p.append("landscape %dx%d" % im.size)
    if im.height > im.width * MAX_ASPECT + 1: p.append("taller than a page %dx%d" % im.size)
    lv = sorted(v for v, c in enumerate(im.convert("L").histogram()) if c)
    if not set(lv) <= set(TONES): p.append("gray levels %s" % lv)
    return p

def downscale(path, width=758, out=None):
    """Simulate an older 758 px Kindle: resize, re-snap tones, save next to original (*_758.png)."""
    im = Image.open(path).convert("L"); im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    out = out or re.sub(r"\.png$", "_%d.png" % width, path); _quantize(im).save(out, optimize=True); return out

def _result(kind, path, title, sub, source, data, fmt):
    return dict(kind=kind, path=path, title=title, sub=sub, source=source, data=data, fmt=fmt or _fmt)

def _fmt(v): return ("%.1f" % v).rstrip("0").rstrip(".") if isinstance(v, float) else str(v)
def _need_source(source):
    if not source: raise ValueError("source= is required: every chart ends with a source line (e.g. 'Source: X, 2026')")
def _hiset(labels, highlight):
    if highlight is None: return set()
    if isinstance(highlight, (str, int)): highlight = [highlight]
    return {labels[h] if isinstance(h, int) else h for h in highlight}
def _clean(ax):
    ax.set_facecolor("none")
    for s in ax.spines.values(): s.set_visible(False)
    ax.tick_params(length=0)

def _spread(ys, gap, lo=None, hi=None):
    """Push label y-positions apart so neighbours are >= gap apart (keeps order). ys: list of (y, key)."""
    ys = sorted(ys); pos = [y for y, _ in ys]
    for _ in range(60):
        moved = False
        for i in range(1, len(pos)):
            d = pos[i] - pos[i - 1]
            if d < gap: s = (gap - d) / 2; pos[i - 1] -= s; pos[i] += s; moved = True
        if lo is not None and pos and pos[0] < lo: sh = lo - pos[0]; pos = [p + sh for p in pos]
        if hi is not None and pos and pos[-1] > hi: sh = pos[-1] - hi; pos = [p - sh for p in pos]
        if not moved: break
    return {k: p for (_, k), p in zip(ys, pos)}

# ---------------------------------------------------------------- 1. original stacked bars (compatible)
def stacked_label_bars(rows, title, sub, name, fmt, xmax, source=None, style=None):
    """rows: (label, sublabel_or_"", value, highlight_bool). Left column labels, bar + value on the right.
    Kept for old build scripts; prefer hbar() for new charts."""
    if style is not None:
        return _styled(style, lambda _design: stacked_label_bars(
            rows, title, sub, name, fmt, xmax, source=source, style=None))
    if len(rows) > MAX_BARS: raise ValueError("max %d bars; use text_fallback() for the rest" % MAX_BARS)
    if not source: warnings.warn("stacked_label_bars without source=: add a 'Source: ...' line")
    n = len(rows); rh = 0.56
    labw = 0.47 * W
    fr = _Frame(rh * n, title, sub, source, left=labw)
    ax, fig = fr.ax, fr.fig; T = fig.dpi_scale_trans
    rh = fr.body_h / n; bh = min(0.6, 0.30 / rh)
    vw = max(text_w(fmt(v), LABEL_PT, True) for _, _, v, _ in rows) + 0.1
    ax.set_xlim(0, xmax / max(0.3, 1 - vw / fr.ax_w)); ax.set_ylim(-0.5, n - 0.5); ax.axis("off")
    for i, (lab, sl, v, hi) in enumerate(rows):
        y = n - 1 - i
        ax.barh(y, v, height=bh, color=BLACK if hi else MID)
        ax.annotate(fmt(v), (v, y), xytext=(4, 0), textcoords="offset points", va="center",
                    fontsize=LABEL_PT, fontweight="bold" if hi else "normal", color=BLACK if hi else DARK_TXT)
        yc = fr.bot + rh * (y + 0.5)
        lines = wrap(lab, LABEL_PT, labw - MARGIN - 0.08, hi)[:2]
        sls = wrap(sl, MIN_PT, labw - MARGIN - 0.08)[:1] if sl else []
        tot = len(lines) * lh(LABEL_PT, 1.15) + len(sls) * lh(MIN_PT, 1.15)
        yy = yc + tot / 2
        for l in lines:
            fig.text(MARGIN, yy, l, transform=T, fontsize=LABEL_PT, fontweight="bold" if hi else "normal", va="top"); yy -= lh(LABEL_PT, 1.15)
        for l in sls:
            fig.text(MARGIN, yy, l, transform=T, fontsize=MIN_PT, color=DARK_TXT, va="top")
    path = finish(fig, name)
    return _result("bars", path, title, sub, source, [(r[0] + (" (%s)" % r[1] if r[1] else ""), r[2], r[3]) for r in rows], fmt)

# ---------------------------------------------------------------- 2. horizontal bars
def hbar(data, title, sub, name, source=None, fmt=None, highlight=None, sort=True, xmax=None, style=None):
    """data: [(label, value), ...] or {label: value}. highlight: label, index or list of them (black + bold).
    Label sits above each bar (full width, long labels OK); value at the bar end. Sorted desc unless sort=False."""
    if style is not None:
        return _styled(style, lambda _design: hbar(
            data, title, sub, name, source=source, fmt=fmt, highlight=highlight,
            sort=sort, xmax=xmax, style=None))
    _need_source(source); fmt = fmt or _fmt
    data = list(data.items()) if isinstance(data, dict) else [tuple(d[:2]) for d in data]
    if len(data) > MAX_BARS: raise ValueError("max %d bars; chart the top %d and text_fallback() the rest" % (MAX_BARS, MAX_BARS))
    if any(v < 0 for _, v in data): raise ValueError("hbar draws non-negative values only")
    hi = _hiset([l for l, _ in data], highlight)
    if sort: data = sorted(data, key=lambda d: -d[1])
    n = len(data); row = lh(LABEL_PT, 1.2) + 0.26 + 0.10
    fr = _Frame(row * n, title, sub, source); ax = fr.ax; _clean(ax); ax.axis("off")
    rin = fr.body_h / n                                   # inches per row
    bh_in = min(0.30, rin * 0.40); lab_in = lh(LABEL_PT, 1.2)
    vmax = xmax or max(v for _, v in data) or 1
    vw = max(text_w(fmt(v), LABEL_PT, True) for _, v in data) + 0.08
    ax.set_xlim(0, vmax / max(0.3, 1 - vw / fr.ax_w)); ax.set_ylim(0, fr.body_h)
    for i, (lab, v) in enumerate(data):
        h = lab in hi; top = fr.body_h - i * rin - (rin - bh_in - lab_in - 0.04) / 2
        ax.text(0, top, one_line(lab, LABEL_PT, fr.ax_w, h), va="top", fontsize=LABEL_PT,
                fontweight="bold" if h else "normal", color=BLACK)
        yb = top - lab_in - 0.04 - bh_in / 2
        ax.barh(yb, v, height=bh_in, color=BLACK if h else MID)
        ax.annotate(fmt(v), (v, yb), xytext=(5, 0), textcoords="offset points", va="center", fontsize=LABEL_PT,
                    fontweight="bold" if h else "normal", color=BLACK if h else DARK_TXT)
    path = finish(fr.fig, name)
    return _result("bars", path, title, sub, source, [(l, v, l in hi) for l, v in data], fmt)

# ---------------------------------------------------------------- 3. line chart
def line_chart(x, series, title, sub, name, source=None, fmt=None, highlight=None, xticks=None, ylim=None, grid=_OMIT, style=None):
    """x: list of x labels/values; series: {name: [values]} (<= 4). highlight: series name (black, thick, solid).
    Others: thinner gray AND a distinct dash pattern (dash / dot / dash-dot). Direct end labels, no legend."""
    if style is not None:
        def _again(design):
            use_grid = design["grid"] if grid is _OMIT else grid
            return line_chart(x, series, title, sub, name, source=source, fmt=fmt, highlight=highlight,
                              xticks=xticks, ylim=ylim, grid=use_grid, style=None)
        return _styled(style, _again)
    if grid is _OMIT:
        grid = True
    _need_source(source); fmt = fmt or _fmt
    if len(series) > MAX_LINES: raise ValueError("max %d lines per chart; split into small multiples" % MAX_LINES)
    names = list(series); hi = _hiset(names, highlight if highlight is not None else names[0])
    endlab = {k: "%s %s" % (fmt(series[k][-1]), k) for k in names}
    lw_max = min(max(text_w(endlab[k], LABEL_PT, k in hi) for k in names) + 0.12, 0.48 * W)
    for k in names:
        if text_w(endlab[k], LABEL_PT, k in hi) > lw_max - 0.1: endlab[k] = "\n".join(wrap(endlab[k], LABEL_PT, lw_max - 0.12, k in hi)[:2])
    left = MARGIN + max(text_w(fmt(v), MIN_PT) for v in [min(min(s) for s in series.values()), max(max(s) for s in series.values())]) + 0.12
    fr = _Frame(2.6, title, sub, source, left=left, right=lw_max + MARGIN, below=lh(MIN_PT) + 0.12)
    ax = fr.ax; _clean(ax); xs = list(range(len(x)))
    allv = [v for s in series.values() for v in s]
    lo, hi_v = ylim or (min(allv), max(allv)); pad = (hi_v - lo) * 0.06 or 1
    if not ylim and 0 <= lo <= 0.5 * hi_v: lo, lpad = 0, 0          # start at zero when it is close
    else: lpad = 0 if ylim else pad
    ax.set_ylim(lo - lpad, hi_v + (0 if ylim else pad)); ax.set_xlim(0, len(x) - 1)
    ax.yaxis.set_major_locator(MaxNLocator(4))
    yt = [t for t in ax.get_yticks() if ax.get_ylim()[0] <= t <= ax.get_ylim()[1]]
    ax.set_yticks(yt); ax.set_yticklabels([fmt(type(allv[0])(t)) if isinstance(allv[0], int) and float(t).is_integer() else fmt(float(t)) for t in yt], fontsize=MIN_PT, color=DARK_TXT)
    if grid:
        for t in yt: ax.axhline(t, color=LIGHT, lw=LW_GRID, zorder=0)
    idx = xticks if xticks is not None else sorted({0, len(x) - 1} | ({(len(x) - 1) // 2} if len(x) > 4 else set(xs)))
    ax.set_xticks(idx); ax.set_xticklabels([str(x[i]) for i in idx], fontsize=MIN_PT, color=DARK_TXT)
    ax.tick_params(axis="x", pad=6); ax.spines["bottom"].set_visible(True); ax.spines["bottom"].set_color(BLACK)
    labels = ax.get_xticklabels()
    if labels: labels[0].set_ha("left"); labels[-1].set_ha("right")
    styles = iter(MUTED_STYLES)
    yspan = ax.get_ylim()[1] - ax.get_ylim()[0]; per_in = yspan / fr.body_h
    for k in names:
        if k in hi: ax.plot(xs, series[k], color=BLACK, lw=LW_HI, zorder=5)
        else:
            c, ls = next(styles); ax.plot(xs, series[k], color=c, lw=LW_MUTED, ls=ls, zorder=3)
    gap = lambda k: lh(LABEL_PT, 1.15) * (endlab[k].count("\n") + 1) * per_in
    pos = _spread([(series[k][-1], k) for k in names], max(gap(k) for k in names) * 0.9 + 0.03 * per_in, *ax.get_ylim())
    for k in names:
        h = k in hi
        ax.annotate(endlab[k], (xs[-1], pos[k]), xytext=(8, 0), textcoords="offset points", va="center", ha="left",
                    fontsize=LABEL_PT, fontweight="bold" if h else "normal", color=BLACK if h else DARK_TXT,
                    annotation_clip=False, linespacing=1.1)
        ax.plot([xs[-1]], [series[k][-1]], "o", ms=7 if h else 5, color=BLACK if h else DARK, zorder=6, clip_on=False)
    path = finish(fr.fig, name)
    return _result("lines", path, title, sub, source, dict(x=list(x), series={k: list(v) for k, v in series.items()}, highlight=sorted(hi)), fmt)

# ---------------------------------------------------------------- 4. slope chart
def slope_chart(rows, title, sub, name, source=None, fmt=None, highlight=None, left_label="Before", right_label="After", style=None):
    """rows: [(label, before, after), ...] (<= 8). Highlighted rows: black thick line + bold label; others gray dashed."""
    if style is not None:
        return _styled(style, lambda _design: slope_chart(
            rows, title, sub, name, source=source, fmt=fmt, highlight=highlight,
            left_label=left_label, right_label=right_label, style=None))
    _need_source(source); fmt = fmt or _fmt
    if len(rows) > MAX_BARS: raise ValueError("max %d rows per slope chart" % MAX_BARS)
    hi = _hiset([r[0] for r in rows], highlight)
    lw_l = max(text_w(fmt(r[1]), LABEL_PT, True) for r in rows) + 0.12
    rlab = {r[0]: "%s  %s" % (fmt(r[2]), r[0]) for r in rows}
    lw_r = min(max(text_w(v, LABEL_PT, True) for v in rlab.values()) + 0.12, 0.5 * W)
    for r in rows:
        if text_w(rlab[r[0]], LABEL_PT, True) > lw_r - 0.1: rlab[r[0]] = "\n".join(wrap(rlab[r[0]], LABEL_PT, lw_r - 0.12, True)[:2])
    nl = sum(v.count("\n") + 1 for v in rlab.values())
    fr = _Frame(max(2.6, nl * lh(LABEL_PT, 1.25) + 0.6), title, sub, source, left=MARGIN + lw_l, right=MARGIN + lw_r)
    ax = fr.ax; _clean(ax); ax.set_xticks([]); ax.set_yticks([])
    allv = [v for r in rows for v in r[1:3]]; lo, hv = min(allv), max(allv); pad = (hv - lo) * 0.04 or 1
    head = 0.42  # inches reserved for column headers
    ax.set_xlim(0, 1); ax.set_ylim(lo - pad, hv + pad + (hv - lo + 2 * pad) * head / (fr.body_h - head))
    per_in = (ax.get_ylim()[1] - ax.get_ylim()[0]) / fr.body_h
    for xx in (0, 1): ax.axvline(xx, ymax=1 - head / fr.body_h, color=LIGHT, lw=LW_MIN, zorder=0)
    ytop = ax.get_ylim()[1]
    ax.text(0, ytop, left_label, ha="center", va="top", fontsize=MIN_PT, fontweight="bold", color=DARK_TXT)
    ax.text(1, ytop, right_label, ha="center", va="top", fontsize=MIN_PT, fontweight="bold", color=DARK_TXT)
    g = lh(LABEL_PT, 1.15) * per_in
    pl = _spread([(r[1], r[0]) for r in rows], g * 1.05, lo - pad, hv + pad)
    pr = _spread([(r[2], r[0]) for r in rows], 0, lo - pad, hv + pad)
    # right labels may be 2 lines: spread with per-label height
    ordered = sorted(rows, key=lambda r: r[2]); pos = []; 
    for r in ordered:
        hgt = (rlab[r[0]].count("\n") + 1) * g
        y = r[2] if not pos else max(r[2], pos[-1][1] + pos[-1][2] / 2 + hgt / 2 + 0.02 * per_in)
        pos.append((r[0], y, hgt))
    over = pos[-1][1] + pos[-1][2] / 2 - (hv + pad) if pos else 0
    if over > 0: pos = [(k, y - over, h_) for k, y, h_ in pos]
    pr = {k: y for k, y, _ in pos}
    for lab, a, b in sorted(rows, key=lambda r: r[0] in hi):
        h = lab in hi
        ax.plot([0, 1], [a, b], color=BLACK if h else MID, lw=LW_HI if h else LW_MUTED, ls="-" if h else (0, (5, 2.2)), clip_on=False,
                zorder=5 if h else 3, marker="o", ms=7 if h else 5)
        kw = dict(fontsize=LABEL_PT, fontweight="bold" if h else "normal", color=BLACK if h else DARK_TXT, va="center", annotation_clip=False)
        ax.annotate(fmt(a), (0, pl[lab]), xytext=(-8, 0), textcoords="offset points", ha="right", **kw)
        ax.annotate(rlab[lab], (1, pr[lab]), xytext=(8, 0), textcoords="offset points", ha="left", linespacing=1.1, **kw)
    path = finish(fr.fig, name)
    return _result("slope", path, title, sub, source, dict(rows=[tuple(r) for r in rows], highlight=sorted(hi),
                   left=left_label, right=right_label), fmt)

# ---------------------------------------------------------------- 5. dot / range plot
def dot_range(rows, title, sub, name, source=None, fmt=None, highlight=None, sort=True, point_label=None, style=None):
    """rows: [(label, low, high), ...] or (label, low, high, point). Thick range bar with end dots, values at ends,
    optional point marker (e.g. median) as a white-filled ring. Sorted by high desc unless sort=False."""
    if style is not None:
        return _styled(style, lambda _design: dot_range(
            rows, title, sub, name, source=source, fmt=fmt, highlight=highlight,
            sort=sort, point_label=point_label, style=None))
    _need_source(source); fmt = fmt or _fmt
    if len(rows) > MAX_BARS: raise ValueError("max %d rows per range plot" % MAX_BARS)
    rows = [tuple(r) + (None,) * (4 - len(r)) for r in rows]
    hi = _hiset([r[0] for r in rows], highlight)
    if sort: rows = sorted(rows, key=lambda r: -r[2])
    n = len(rows); row = lh(LABEL_PT, 1.2) + 0.46
    fr = _Frame(row * n + (0.2 if point_label else 0), title, sub, source); ax = fr.ax; ax.axis("off")
    allv = [v for r in rows for v in r[1:3]]; lo, hv = min(allv), max(allv)
    lw_ = max(text_w(fmt(r[1]), LABEL_PT, True) for r in rows) + 0.16
    rw_ = max(text_w(fmt(r[2]), LABEL_PT, True) for r in rows) + 0.16
    span = (hv - lo) or 1; inner = fr.ax_w - lw_ - rw_
    ax.set_xlim(lo - span * lw_ / inner, hv + span * rw_ / inner); ax.set_ylim(0, fr.body_h)
    rin = (fr.body_h - (0.2 if point_label else 0)) / n; lab_in = lh(LABEL_PT, 1.2)
    x0 = ax.get_xlim()[0]
    for i, (lab, a, b, p) in enumerate(rows):
        h = lab in hi; top = fr.body_h - i * rin - (rin - lab_in - 0.30) / 2
        ax.text(x0, top, one_line(lab, LABEL_PT, fr.ax_w, h), va="top", fontsize=LABEL_PT, fontweight="bold" if h else "normal")
        y = top - lab_in - 0.17; c = BLACK if h else MID
        ax.plot([a, b], [y, y], color=c, lw=7 if h else 5, solid_capstyle="butt", zorder=3)
        ax.plot([a, b], [y, y], "o", color=BLACK if h else DARK, ms=9 if h else 7, zorder=4)
        if p is not None:
            ax.plot([p], [y], "o", mfc="white", mec=BLACK, mew=2.4, ms=10, zorder=5)
        kw = dict(fontsize=LABEL_PT, fontweight="bold" if h else "normal", color=BLACK if h else DARK_TXT, va="center")
        ax.annotate(fmt(a), (a, y), xytext=(-9, 0), textcoords="offset points", ha="right", **kw)
        ax.annotate(fmt(b), (b, y), xytext=(9, 0), textcoords="offset points", ha="left", **kw)
    if point_label:
        ax.plot([x0 + span * 0.06], [0.1], "o", mfc="white", mec=BLACK, mew=2.4, ms=10)
        ax.annotate(point_label, (x0 + span * 0.06, 0.1), xytext=(10, 0), textcoords="offset points", va="center", fontsize=MIN_PT, color=DARK_TXT)
    path = finish(fr.fig, name)
    return _result("range", path, title, sub, source, dict(rows=rows, highlight=sorted(hi), point_label=point_label), fmt)

# ---------------------------------------------------------------- 6. big-number callout
def callout_card(number, context, name, source=None, title=None, sub=None, style=None):
    """One key stat as an image: optional action title, the number huge and black, one line of context."""
    if style is not None:
        return _styled(style, lambda _design: callout_card(
            number, context, name, source=source, title=title, sub=sub, style=None))
    _need_source(source)
    fr = _Frame(2.0, title, sub, source); ax = fr.ax; ax.axis("off"); ax.set_xlim(0, fr.ax_w); ax.set_ylim(0, fr.body_h)
    size = BIG_PT
    while text_w(str(number), size, True) > fr.ax_w - 0.3 and size > 28: size -= 2
    cl = wrap(context, 13, fr.ax_w - 0.3)
    blk = size / 72 * 0.95 + 0.18 + len(cl) * lh(13)
    y = fr.body_h / 2 + blk / 2
    ax.plot([0.04, 0.04], [y, y - blk], color=BLACK, lw=6, solid_capstyle="butt")
    ax.text(0.22, y, str(number), fontsize=size, fontweight="bold", va="top")
    y -= size / 72 * 0.95 + 0.18
    for l in cl: ax.text(0.22, y, l, fontsize=13, va="top"); y -= lh(13)
    path = finish(fr.fig, name)
    return _result("callout", path, title or "", sub, source, dict(number=str(number), context=context), None)

# ---------------------------------------------------------------- text fallback + figure html
def text_fallback(chart, html_out=False, max_items=8):
    """Short plain-text (or Kindle-safe HTML: <p>/<ul>, no tables) summary of a chart result dict.
    Use under dense charts, or instead of a chart that would break MAX_BARS/MAX_LINES."""
    k, f, d = chart["kind"], chart["fmt"] or _fmt, chart["data"]
    head = chart["title"] + (" (%s)" % chart["sub"] if chart.get("sub") else "")
    items = []
    if k == "bars":
        for lab, v, h in d[:max_items]: items.append(("%s: %s" % (lab, f(v)), h))
    elif k == "lines":
        x = d["x"]
        for s, vals in d["series"].items():
            ch = vals[-1] - vals[0]
            items.append(("%s: %s in %s to %s in %s (%s%s)" % (s, f(vals[0]), x[0], f(vals[-1]), x[-1], "+" if ch >= 0 else "-", f(abs(ch))), s in d["highlight"]))
    elif k == "slope":
        for lab, a, b in d["rows"][:max_items]:
            items.append(("%s: %s %s to %s %s" % (lab, d["left"], f(a), d["right"], f(b)), lab in d["highlight"]))
    elif k == "range":
        for lab, a, b, p in d["rows"][:max_items]:
            items.append(("%s: %s to %s%s" % (lab, f(a), f(b), "" if p is None else ", %s %s" % ((d["point_label"] or "point").lower(), f(p))), lab in d["highlight"]))
    elif k == "callout":
        items.append(("%s: %s" % (d["number"], d["context"]), True))
    src = chart.get("source") or ""
    if not html_out:
        return "\n".join([head] + ["- " + t + (" (highlighted)" if h and k != "callout" else "") for t, h in items] + ([src] if src else []))
    e = html.escape
    li = "".join("<li>%s</li>" % ("<b>%s</b>" % e(t) if h else e(t)) for t, h in items)
    return '<div class="box"><p><b>%s</b></p><ul>%s</ul>%s</div>' % (e(head), li, '<p class="small">%s</p>' % e(src) if src else "")

def figure_html(chart, src=None, alt=None, fallback=False):
    """<div class="fig"> snippet. src defaults to img/<file name>. kindle_epub.generic() DROPS any div.fig whose
    img src is not a FIGMAP key, so either put this in chapter html AND set FIGMAP[src] = figure_html(chart),
    or append it to the soup after generic(). The fallback box is not a div.fig, so it survives either way."""
    src = src or "img/" + os.path.basename(chart["path"]); alt = alt or chart["title"]
    out = '<div class="fig"><img src="%s" alt="%s"/></div>' % (html.escape(src), html.escape(alt))
    return out + (text_fallback(chart, html_out=True) if fallback else "")

if __name__ == "__main__":  # smoke test (original behaviour)
    r = stacked_label_bars([("2024", "412 deals", 12.0, False), ("2025", "", 26.4, False), ("2026", "first half", 47.4, True)],
        "One half-year beat the prior two", "Example data, $B", "demo.png", lambda v: f"${v:.1f}B", 50, source="Source: Example data")
    print("wrote", r["path"], check_png(r["path"]) or "OK")
