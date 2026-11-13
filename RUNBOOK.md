# RUNBOOK

Repository commands for kindle-reading-kit. Design rules and capability tiers
live in `SKILL.md`. Read that first. This file assumes you have the repo files.

Report the tier from `SKILL.md` and every skipped check. A skip is not a pass.

## Install

Core charts need Python 3.10+ plus:

```sh
python -m pip install -r requirements.txt
```

That installs Matplotlib and Pillow only. EPUB build, `check_epub.py`, and
`preview_kindle.py` need optional packages, and preview also needs Poppler
(`pdftoppm` on `PATH`, for example Debian `poppler-utils`):

```sh
python -m pip install -r requirements-optional.txt
```

Tier B does not run pip and does not use the network. If `import bs4`, `lxml`,
`weasyprint`, or `pdftoppm` fails, skip that step, name the missing piece, and
continue with the checks you can run.

## Paths

Resolve the repo from a file location. A bare `scripts` entry on `sys.path`
works only when the current directory is the repo root.

```python
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]  # this file lives in examples/
sys.path.insert(0, str(ROOT / "scripts"))
import kindle_charts as kc
from eink_style import style
kc.OUT = str(Path("/absolute/output/charts"))
with style("editorial-soft") as design:
    chart = kc.line_chart(
        ["Jan", "Dec"], {"Focus": [52, 96], "Context": [48, 64]},
        title="Focus gains 44 in 12 months.",
        sub="Shipments, thousands · 2025", name="growth.png",
        source="Source: Fictional example data, 2025.",
        highlight="Focus", ylim=(0, 100), grid=design["grid"])
assert not kc.check_png(chart["path"])
```

You can pass `style="editorial-soft"` into `line_chart`, `hbar`, `slope_chart`,
`dot_range`, `callout_card`, `stacked_label_bars`, `sparkline_table`, and
`small_multiples` instead of the `with` block. If you omit `grid` on
`line_chart`, the active style's grid flag is used, including inside
`with style(...)`. An explicit `grid=` still wins.

`style()` assigns `kindle_charts` module globals and swaps `finish` for the
duration, then restores them. Nesting on the same thread restores inside out.
A second thread raises `RuntimeError`. Do not share these modules across threads.
Passing `style=` uses the same context for one call.

`examples/render_charts.py` draws the six forms on one fictional dataset.
`examples/matplotlib_only.py` is a self-contained Matplotlib script for tier C.
Tier C returns that kind of code and does not claim it ran.

## Package a short chart sample

`scripts/kindle_epub.py` builds an EPUB3 file with NCX, reflowable text, a visible
contents list, tap navigation, and source notes. It is for a chart sample in this
repo. A full book or report conversion belongs to the kindle-edition skill.

Use one XHTML file per chapter or section. Open a chapter with `chapter_head()`:
the kicker (the chapter's menu name) and the action title share the `h1`, then
exactly three short claims, a lede, and jump links when there are two or more
sections. A chart section starts with `section_head("Line")` (a short `h2`), then
one figure, a next link, and the local source note. Wrap bodies with
`page(title, body, kind)`, where kind is `chapter`, `section`, `cover`, or `toc`. Give every image meaningful alt text and keep the values in the book
as text. No private URLs. Native text stays in `em`. The only HTML tables are
`kindle_tables` output (class `kt`, at most 3 columns). `generic()` keeps those
and turns every other table into stacked records.

`generic()` drops a `div.fig` whose image `src` is not a `FIGMAP` key. Register
`FIGMAP[src] = figure_html(chart)` or append the figure after `generic()`.
`figure_html` and `text_fallback` live in `kindle_charts.py`. Close each section
with Next, then its source notes.

Contents come from the headings. `write_epub(path, meta, docs, images, cover)`
calls `epub_nav.build_nav(docs)` when you omit `nav`: each file with an `h1` is a
chapter, every `h2` inside it (with an `id`; `add_h2_ids` sets them) is a section,
and a file that starts with an `h2` is a section of the chapter before it. Notes
blocks are skipped. The cover (first document) and `contents.xhtml` stay out of
the menu. Build the visible contents page with `contents_html(build_nav(docs))`.
A hand-written `nav` deeper than 2 levels raises `ValueError`. The NCX declares
the real depth.

Metadata: `meta` needs `title`, `date`, and `desc`. `author` defaults to
`kindle-reading-kit`. The book id comes from title, author, and date, so a new
date or author makes a new id; pass `identifier` to pin one. Make the library
cover with `make_cover()` (1600 x 2560 JPEG, Lato if installed, else DejaVu).

`check_epub.py` reads the package path from `META-INF/container.xml`. It does not
assume `OEBPS/content.opf`. It checks the mimetype entry, XML parsing, manifest
paths, internal links, tables, and navigation: at most 2 levels, no duplicates,
contents in reading order, an entry for every spine document except the cover and
contents page, labels that match their headings, and an NCX that mirrors the nav. It is a structural check for when epubcheck is absent.
It does not certify Kindle conversion.

## Tables and dense data

Design rules are in `SKILL.md`. `scripts/kindle_tables.py` has no third-party
imports, so tier B can use it.

```python
import kindle_tables as kt
rows = [{"Region": "East", "Q3, k": 1702, "YoY": "+9.1%", "Util": "71%"}, ...]
html_out, plan = kt.render(["Region", "Q3, k", "YoY", "Util"], rows,
                           show=["Region", "Q3, k", "YoY"], title="Q3 by region",
                           focal="East", sort_by="Q3, k",
                           notes=["k = thousand units. YoY = change from Q3 last year."])
print(plan["form"], plan["reasons"])  # text-table, then cards for Util
```

`plan()` picks prose, ranked list, text table, or record cards and says why.
`text_table_html()` raises `ValueError` when a table breaks a cap, so a wide
table cannot slip through. `table_fit()` estimates the font scale where a row
stops fitting one line (`LINE_EM` 26 em at the default size, an assumption from
the preview page). `notes` land under the table, where the short headers appear.
A whole `kt` table avoids a page break inside it. Give any line between its
heading and the table `class="kt-lead"` so the heading moves with the table.
`detail_notes` land under the record cards. Put the source line after both.

`check_epub.py` flags any table with more than 3 columns, a nested table, or a
fixed width. `examples/table_ladder.py` builds an after EPUB that passes and a
before EPUB (7 columns floated beside the chart) that fails on purpose.

Check reflow at two sizes. `--font-scale` multiplies the 9.5 pt base text; chart
images keep their size, as on a Kindle. At 1.5 and above the preview sets text
ragged right, imitating Kindle's documented fallback to left-aligned text at
large sizes (the exact device threshold is not published):

```sh
python examples/table_ladder.py --out output/tables
python scripts/preview_kindle.py output/tables/Table-Ladder-After.epub output/tables/after-1x
python scripts/preview_kindle.py output/tables/Table-Ladder-After.epub output/tables/after-2x --font-scale 2
```

## Preview safety

```sh
python scripts/preview_kindle.py path/to/book.epub output/preview
python scripts/preview_kindle.py path/to/book.epub output/preview --force
```

The script writes a `.kindle-preview` marker when it creates the destination.
`--force` replaces only a non-empty folder that has that marker. A non-empty
folder without the marker is refused and left untouched. `--force` does not
override a dangerous path. Refused paths include the filesystem root,
the home directory, the current directory, this repo, `/tmp` itself, and other
broad system directories, including ancestors of the repo, home, or current
directory. A symlink destination is refused. The destination must not contain
the EPUB, because replacing it would delete the input.

Missing Pillow, WeasyPrint, pypdf, or `pdftoppm` prints `preview skipped: ...`,
exits non-zero, and does not claim success. Nothing is deleted in that case.

Each spine item is still rendered on its own. The footer counter starts at the
running page total, so numbers continue across items instead of showing 1 on
every page. That behavior was checked with WeasyPrint 69. Sheets are
`sheet_NN.png` (12 pages each). Inspect every sheet at reading size, and inspect
a 758 px downscale (`kindle_charts.downscale`). Look for clipped labels, orphaned
headings, split charts, tiny sources, and broken links.

Previews are simulated. They are not a physical-device test.

## Send to Kindle

The kit works best when the user adds the agent's email address to their Amazon
Approved Personal Document E-mail List. Then you can email the EPUB to the user's
Send to Kindle address. Without that, the user moves the file over by hand.
Stop before sending. Send only when the user asks.

## Devices

The asset grid is the 11th-generation 6.8-inch 300 ppi Paperwhite, 1236 x 1648,
nominal 16 gray levels. 1236 / 300 = 4.12 inches wide.

The 2024 12th-generation Paperwhite is described as a 7-inch 300 ppi grayscale
panel. Reviewers report 1264 x 1680 (Good e-Reader, 24 Oct 2024; Gadgets 360).
Amazon's Colorsoft comparison table lists that Paperwhite as 7-inch, 300 ppi,
without a pixel grid. Treat 1264 x 1680 as a reported figure and confirm it
before using it as an asset size.

Kindle Colorsoft, on the Amazon product technical details consulted for this
note, is a 7-inch color panel at 300 ppi in black and white, 150 ppi in color,
with 16 gray levels. Those details do not publish a pixel grid, so this repo
does not invent one. A retailer figure was left out for that reason. Charts stay
mode `L`. Color is not a data channel.

## Commands

From any working directory, pass paths or rely on the scripts' `__file__` roots:

```sh
python examples/render_charts.py --out output/charts
python examples/render_charts.py --style pattern-texture --out output/pattern
python scripts/test_kit.py
python tests/test_styles.py
python tests/test_portability.py
python tests/test_tables.py
python tests/test_nav.py
python examples/build_sample.py --out output/sample
python scripts/check_epub.py output/sample/E-ink-Chart-Default-Sample.epub
python scripts/preview_kindle.py output/sample/E-ink-Chart-Default-Sample.epub output/preview
```

`check_png` checks mode, width, aspect, and the five gray values. It does not
check font size, collisions, wording, or a real panel.
