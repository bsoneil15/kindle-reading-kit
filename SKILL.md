---
name: eink-chart-design
description: Design or redraw charts, graphs and compact data displays for Kindle Paperwhite or other grayscale e-ink readers; use before plotting or packaging a chart-rich EPUB.
---
# E-ink chart design

## Outcome
Make the finding obvious at normal reading size. Default to **Editorial Soft**:
Tufte-inspired restraint and thin gray comparison series, an editorial black top
rule and quiet horizontal reference guides, and **one black, thick focal series
or bar with bold direct labels**. Softness is for context, never for the finding.
This is an independent design recipe, not an official publication template.

## 1. Establish the story and source
- Start with structured source data, never infer values from an image or memory.
  Record metric, unit, period, provenance and any caveats. Mark synthetic data
  **fictional** in every source line. Do not manufacture a source or observation.
- Answer first: conclusion, then up to three supporting claims. The sequence of
  action titles alone must tell the story. Each title is a full-sentence takeaway,
  usually with a number: “North gains 44 in 12 months,” not “Regional performance.”
- One message per chart. Identify the series/bar that proves it **before** drawing.
  Every option keeps that element black, heavy and bold-labeled. Never change the
  highlight, values or axis limits merely to make another style look better.
- Use a metric/unit/period subtitle and a dated source line on every chart. Keep
  a meaningful caption or text fallback with underlying values for dense content.

## 2. Design for the reference screen
Default: **6.8-inch, 300 ppi Paperwhite, portrait, 1236 × 1648 pixels, nominal
16-level grayscale** (the 11th-generation reference, not every Paperwhite model).
Newer/larger and older/smaller readers may differ; confirm the actual target.
- Chart PNGs: mode `L`, **1236 px wide**, 1236–1606 px tall (square to 1.30:1).
  EPUB margins reduce the displayed size; these dimensions are an asset target,
  not a promise of one-to-one display pixels. Avoid tight-crop resizing.
- Plot at 4.12 inches wide and 300 dpi. Context and reference strokes **≥1.5 pt
  (~6.25 px)**; focal strokes **3.4 pt (~14 px)**. At 758 px the minimum is about
  3.8 px. Do not copy screen hairlines. Light gray, not subpixel width, creates softness.
- Five nominal gray values: **0 / 85 / 153 / 221 / 255** (`#000`, `#555`, `#999`,
  `#DDD`, white), corresponding to 16-level steps **0 / 5 / 9 / 13 / 15**. Reserve
  221 for guides, 85/153 for context, and 0 for the focus and primary text. Do not
  use adjacent gray levels to encode categories. Device processing can change
  appearance; separated values alone never guarantee perceptual distinction.
- Raster text: **13–14 pt headlines (~54–58 px em), 11 pt data labels (~46 px),
  10.5 pt subtitles (~44 px), 9.5 pt minimum sources/ticks (~40 px)**. Small text
  is allowed when legible; don't enlarge everything by reflex. At 758 px the
  minimum em is ~24 px. If it fails without zoom, shorten, split or use native text.
- Native EPUB text uses relative `em` sizes, no fixed font family or absolute font
  size; reader settings remain in control. Raster chart fonts are deliberately fixed.
- Never rely on color. Direct-label lines at their ends and bars at their values.
  Add dashes or marker shapes for comparisons even with 2–3 series. With **>3
  series**, redundant patterns/markers are mandatory; prefer small multiples.
- No fine gradients, transparency-dependent meaning, 3-D, dual axes or decorative
  gridlines. Guides must support estimation. Avoid pies; if necessary, at most
  3 directly labeled slices. A bar or dot chart is usually clearer.

## 3. Choose a form and a style
Chart forms (limits are design caps, not targets):
- **Line:** evolution, ≤4 series, sparse time ticks, direct endpoint labels; show
  honest scales. Split crossing/near-identical series rather than colliding labels.
- **Ranked horizontal bar:** category size, ≤8 bars, descending order unless time
  or another meaningful order applies. Zero baseline; label values at ends.
- **Small multiples:** compare shapes without spaghetti. Shared units, periods
  and y-axis bounds; one black focal panel, gray context panels. Prefer 3–4 per image.
- **Sparkline table:** aligned trend rows + directly labeled end values, ≤4 rows
  per image and shared scales. This is a chart image, not an HTML `<table>`.
- **Slope:** paired start/end changes, ideally ≤4 entities; label both endpoints.
  Never silently move labels without making their association clear.
- **Dot/range:** ranking with less ink, or observed min–max/real uncertainty.
  Specify which; an observed range is **not** a confidence interval. The included
  `dot_range` helper handles ranges, not a fabricated statistical estimate.
- **Other forms:** distribution → histogram/ECDF with explicit bins/sample size;
  relationship → sparse scatter with direct labels; components of change → a
  short waterfall. Prefer stacked native-text records for dense heatmaps/matrices
  and maps. Do not invent an unimplemented helper; extend and test the kit first.

Named options (retain all four alternatives):
1. **Editorial Soft** (`editorial-soft`, default): 3.4 pt black focus, 1.5 pt gray
   context, 1.5 pt light horizontal guides, black top rule, compact sans titles.
2. **Tufte Minimal** (`tufte-minimal`): serif raster type, fewer rules, no guides;
   keep the same strong black focal mark. Use for calm, low-density comparisons.
3. **Bold Highlight** (`bold-highlight`): 3.8 pt focal stroke, 14 pt titles; no
   top rule or guides. Use when rapid scanning matters most.
4. **Pattern & Texture** (`pattern-texture`): hatches for comparison bars and
   open marker shapes for comparison trends; focus stays solid black. Use when
   tonal differences are unreliable; avoid textures so dense they create moiré.
5. **Economist-style Editorial** (`economist-editorial`): top rule and guides,
   2 pt context strokes; more structured than Editorial Soft. Publication-inspired
   grammar only: no logos, trade dress claims or implication of affiliation.

## 4. Render with the portable helpers
Use `scripts/kindle_charts.py` for chart frames, core forms, direct labels,
quantization and `check_png`; `scripts/eink_style.py` adds style contexts,
small multiples and sparkline tables. No account, connector or network is needed.
See `examples/render_charts.py` for six runnable forms on one fictional dataset.

```python
import sys
sys.path.insert(0, 'scripts')
import kindle_charts as kc
from eink_style import style
kc.OUT = 'output'
with style('editorial-soft') as design:
    chart = kc.line_chart(
        ['Jan', 'Dec'], {'Focus': [52, 96], 'Context': [48, 64]},
        title='Focus gains 44 in 12 months.',
        sub='Shipments, thousands · 2025', name='growth.png',
        source='Source: Fictional example data, 2025.',
        highlight='Focus', ylim=(0, 100), grid=design['grid'])
assert not kc.check_png(chart['path'])
```
Always pass `grid=design['grid']` to `line_chart`; core calls outside a style
context do not add an editorial top rule. Contexts set module globals temporarily:
use sequentially, not across concurrent threads. Source-required APIs have legacy
low-level escape hatches; the author remains responsible for the rules above.

## 5. Package and validate
For EPUB, use the included `kindle_epub.py`: EPUB3 + NCX, native reflowable text,
visible contents, tap navigation, source notes, no HTML tables, no private URLs.
Use one XHTML per section. Chapter openers: kicker, action title, exactly 3 concise
summary claims, lede, and jump links if there are ≥2 h2 sections. Chart-only
sections can remain one figure with next link and local source notes. Give every
image meaningful alt text; keep source data or a text alternative in the book.
Register `figure_html(chart)` in `FIGMAP` if using `generic()`, which otherwise
drops unregistered figures. Close each section with Next, then its source notes.

Before handoff:
1. Run `python scripts/test_kit.py` and `python tests/test_styles.py`.
2. Run `check_png()` for every chart (dimensions, mode, palette).
3. Run `python scripts/check_epub.py path/to/book.epub`; require **OK**.
4. Run `python scripts/preview_kindle.py path/to/book.epub preview/` and inspect
   **every** sheet at reading size: no clipped labels, orphaned headings, split
   charts, tiny sources, bad links or oversize summary boxes. Inspect 758 px chart
   downscales as a stress test. Fix, rebuild, rerun checks.
5. State that previews are simulated, not physical-device verification. Automated
   checks do not certify legibility or Amazon conversion. Never publish, deliver,
   email, create a repository or change a customer system without authorization.
