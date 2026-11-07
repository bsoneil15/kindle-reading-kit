# E-ink Chart Design

A portable, MIT-licensed design skill for small grayscale readers. **Editorial
Soft** combines thin gray context, a quiet editorial top rule and estimation
guides, and an unmistakable black focal mark with bold direct labels. The four
original alternatives remain selectable. No personal details, network calls,
accounts, proprietary fonts, repository setup or email delivery are required.

![Editorial Soft preview: six chart forms (line, ranked bar, slope, sparkline table, small multiples, observed range) on fictional data, each with one bold black focal series and thin gray context](assets/preview-editorial-soft.svg)

*Editorial Soft, the default style, on fictional example data. Vector preview of the 1236 px grayscale chart PNGs the kit renders for a 6.8-inch Paperwhite.*

## Quick start
Python 3.10+ recommended. From this folder:

```sh
python -m pip install -r requirements.txt
python examples/render_charts.py --out output/charts
python examples/render_charts.py --style pattern-texture --out output/pattern
python scripts/test_kit.py
python tests/test_styles.py
python examples/build_sample.py --out output/sample
python scripts/check_epub.py output/sample/E-ink-Chart-Default-Sample.epub
python scripts/preview_kindle.py output/sample/E-ink-Chart-Default-Sample.epub output/preview
```

Previews need Poppler's `pdftoppm` (e.g. Debian/Ubuntu `poppler-utils`) and
WeasyPrint's platform libraries. Plotting needs only Matplotlib and Pillow.
Do not pass an existing important directory as the preview destination: the
preview helper replaces that directory. Inspect all generated `sheet_*.png`.

## Files
- `SKILL.md`: reusable assistant recipe; copy this folder into a skill loader or
  supply it with the prompt. It needs no product-specific tool integration.
- `scripts/kindle_charts.py`: core bars, lines, slopes, ranges, callouts, palette
  validator, downscaling, text fallback and figure HTML.
- `scripts/eink_style.py`: five named style contexts, small multiples, sparklines.
- `scripts/kindle_epub.py`: EPUB3/NCX packaging and native-text components.
- `scripts/check_epub.py`, `preview_kindle.py`: structural checks and simulation.
- `examples/data.json`: **fictional** 2025 regional shipments in thousands;
  identical data across all forms and options. `render_charts.py` is the plotting
  example; `build_sample.py` builds a short EPUB and a six-chart contact sheet.
- `assets/preview-editorial-soft.svg`: README preview rendered from the fictional example data.
- `tests/test_styles.py`: all five styles × six forms, input checks, restoration.

## Design contract
Reference screen: **6.8-inch Paperwhite, 300 ppi, 1236 × 1648**, nominal 16 gray
levels. Not all Paperwhite generations have this geometry. Assets use five
widely separated nominal gray values and strokes ≥1.5 pt at 4.12 inches wide.
Small raster text is intentional (9.5 pt minimum); native text stays reflowable.
All styles preserve the bold black focal element. `style()` temporarily changes
module globals: sequential contexts only, not thread-safe. Return dictionaries
retain source values and support native-text alternatives. `check_png` validates
pixels, not font sizes, collisions, meaning, or actual hardware performance.

Data are fictional, not an estimate or business claim. Sample observed ranges
are min–max, not confidence intervals. Titles are illustrative action headlines.
See `SKILL.md` for chart selection, numeric guardrails and a review checklist.

## Provenance and scope
This recipe draws on Tufte's restraint/data-ink principles, consulting-style
answer-first storytelling and action headlines, and an editorial top-rule
visual grammar. These are design inspirations, not endorsements or copied book
content. The portable chart/EPUB helpers extend the local Kindle-edition toolkit;
style and compact-chart extensions are included here. Dependencies retain their
own licenses; no external typeface is bundled (Matplotlib resolves DejaVu).

A simulated preview cannot guarantee physical e-ink legibility or Amazon's
conversion. Recheck on target hardware after conversion. This project only
creates local files; sending and publishing are separate, explicitly authorized
steps.

License: MIT; see `LICENSE`.
