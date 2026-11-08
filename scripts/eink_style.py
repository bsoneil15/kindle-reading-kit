"""E-ink styles and compact chart forms. No network or account dependencies.

Use `with style("editorial-soft"):` around kindle_charts calls, or pass
style="editorial-soft" into a chart function. The context assigns module globals
for the duration and restores them afterward. Same-thread nesting restores
inside out. A second thread raises RuntimeError.
"""
from contextlib import contextmanager
import threading
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
import kindle_charts as kit

STYLES = {
    'editorial-soft': dict(name='Editorial Soft', font='DejaVu Sans', title=13,
                           hi=3.4, context=1.5, rule=True, grid=True),
    'tufte-minimal': dict(name='Tufte Minimal', font='DejaVu Serif', title=13,
                          hi=3.4, context=1.5, rule=False, grid=False),
    'bold-highlight': dict(name='Bold Highlight', font='DejaVu Sans', title=14,
                           hi=3.8, context=1.7, rule=False, grid=False),
    'pattern-texture': dict(name='Pattern & Texture', font='DejaVu Sans', title=13,
                            hi=3.4, context=1.5, rule=False, grid=False),
    'economist-editorial': dict(name='Economist-style Editorial', font='DejaVu Sans',
                                title=13, hi=3.4, context=2.0, rule=True, grid=True),
}
_ACTIVE = STYLES['editorial-soft']
_STYLE_LOCK = threading.RLock()

@contextmanager
def style(key='editorial-soft'):
    """Every option preserves black + heavy + bold emphasis on the key data."""
    global _ACTIVE
    if key not in STYLES:
        raise ValueError("unknown style %r; choose from %s" % (key, ", ".join(STYLES)))
    if not _STYLE_LOCK.acquire(blocking=False):
        raise RuntimeError("style() changes kindle_charts globals and is not thread-safe; "
                           "run style contexts sequentially on one thread")
    config = STYLES[key]
    previous = _ACTIVE
    keys = ['FONT','TITLE_PT','LW_HI','LW_MUTED','LW_GRID','LIGHT']
    saved = {k: getattr(kit, k) for k in keys}
    original_finish = kit.finish
    try:
        _ACTIVE = config
        kit.FONT = config['font']; kit.TITLE_PT = config['title']
        kit.LW_HI = config['hi']; kit.LW_MUTED = config['context']
        kit.LW_GRID = 1.5; kit.LIGHT = '#DDDDDD'
        def finish(fig, chart_name, tight=False):
            # End dots and stroke caps must not be clipped by plot boundaries.
            for ax in fig.axes:
                for line in ax.lines:
                    line.set_clip_on(False)
            if key == 'tufte-minimal':
                fig.lines.clear()  # remove footer rule, retain the actual source text
            if config['rule']:
                fig.lines.append(Line2D([.015,.985],[.995,.995],
                                 transform=fig.transFigure, color='black', lw=1.5))
            if key == 'pattern-texture':
                for ax in fig.axes:
                    for i, patch in enumerate(ax.patches):
                        if isinstance(patch, Rectangle):
                            is_key = sum(patch.get_facecolor()[:3]) < .1
                            patch.set_facecolor('black' if is_key else 'white')
                            patch.set_edgecolor('black'); patch.set_linewidth(1.5)
                            if not is_key: patch.set_hatch(['//','..','xx'][i % 3])
                    j = 0
                    for line in ax.lines:
                        # Data lines, not horizontal guides, with redundant identity.
                        x, y = list(line.get_xdata()), list(line.get_ydata())
                        if len(x) >= 2 and len(set(x)) > 1 and len(set(y)) > 1:
                            is_key = line.get_linewidth() >= config['hi']
                            line.set_color('black')
                            line.set_marker('o' if is_key else ['s','^','D'][j % 3])
                            line.set_markersize(5); line.set_markeredgewidth(1.5)
                            line.set_markerfacecolor('black' if is_key else 'white')
                            if not is_key: j += 1
            return original_finish(fig, chart_name, tight)
        kit.finish = finish
        with plt.rc_context({'font.family': config['font'], 'hatch.linewidth': 1.5}):
            yield config
    finally:
        kit.finish = original_finish
        for attr, value in saved.items():
            setattr(kit, attr, value)
        _ACTIVE = previous
        _STYLE_LOCK.release()

_style_context = style


def _validate_series(x, series, highlight):
    if not 1 <= len(series) <= 4:
        raise ValueError('Use 1–4 rows; split denser data into multiple images.')
    if not x or any(len(v) != len(x) for v in series.values()):
        raise ValueError('Each series must have one value per x label.')
    if highlight not in series:
        raise ValueError('Name a highlighted series present in the data.')


def compact_trends(x, series, title, sub, name, source, highlight,
                   ylim=(0,100), small_multiples=False, style=None):
    """Aligned sparkline table or stacked small multiples, shared scales.

    Rows preserve input order. One series is black/heavy; others gray/dashed.
    This is a chart image, never an HTML table. A result dict retains all data.
    """
    if style is not None:
        with _style_context(style):
            return compact_trends(x, series, title, sub, name, source, highlight,
                                  ylim=ylim, small_multiples=small_multiples, style=None)
    kit._need_source(source); _validate_series(x, series, highlight)
    if ylim[1] <= ylim[0] or any(not ylim[0] <= v <= ylim[1]
                                  for values in series.values() for v in values):
        raise ValueError('ylim must contain every observation and have positive span.')
    fr = kit._Frame(2.8, title, sub, source)
    fr.ax.axis('off'); fig = fr.fig
    n = len(series); row = fr.body_h / n
    for i, (label, values) in enumerate(series.items()):
        h = label == highlight
        y = fr.bot + fr.body_h - (i+1)*row
        fig.text(.06, y+row-.05, label, transform=fig.dpi_scale_trans,
                 fontsize=11, va='top', fontweight='bold' if h else 'normal')
        left = .40 if small_multiples else 1.1
        width = 2.9 if small_multiples else 2.15
        bottom = y+.23 if small_multiples else y+.15
        height = row-.51 if small_multiples else min(.5, row-.35)
        ax = fig.add_axes([left/kit.W, bottom/fr.H, width/kit.W, height/fr.H])
        kit._clean(ax); ax.set_ylim(*ylim); ax.set_xlim(0,len(x)-1)
        ax.set_xticks([]); ax.set_yticks([])
        if small_multiples:
            guides = [ylim[0], (ylim[0]+ylim[1])/2, ylim[1]]
            if _ACTIVE['grid']:
                for v in guides: ax.axhline(v,color=kit.LIGHT,lw=1.5,zorder=0)
            ax.set_yticks([ylim[0],ylim[1]])
            ax.set_yticklabels([kit._fmt(ylim[0]),kit._fmt(ylim[1])],fontsize=9.5)
        ax.plot(values,color='black' if h else kit.DARK,
                lw=kit.LW_HI if h else kit.LW_MUTED,
                ls='-' if h else [(0,(5,2.2)),(0,(1,1.6))][i%2])
        ax.plot([len(x)-1],[values[-1]],'o',ms=6 if h else 5,
                color='black' if h else kit.DARK,clip_on=False)
        fig.text(3.99, y+row/2, kit._fmt(values[-1]),
                 transform=fig.dpi_scale_trans,ha='right',va='center',
                 fontsize=11,fontweight='bold' if h else 'normal')
        if small_multiples:
            ax.text(0,-.12,str(x[0]),transform=ax.transAxes,fontsize=9.5,va='top')
            ax.text(1,-.12,str(x[-1]),transform=ax.transAxes,fontsize=9.5,va='top',ha='right')
    path=kit.finish(fig,name)
    return kit._result('lines',path,title,sub,source,
                      dict(x=list(x),series={k:list(v) for k,v in series.items()},
                           highlight=[highlight]),None)


def sparkline_table(x, series, **kwargs):
    return compact_trends(x, series, small_multiples=False, **kwargs)


def small_multiples(x, series, **kwargs):
    return compact_trends(x, series, small_multiples=True, **kwargs)
