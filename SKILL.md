---
name: kindle-reading-kit
description: >
  Design or redraw charts for Kindle and other grayscale e-readers. Trigger
  phrases include "make this chart readable on Kindle", "e-ink friendly chart",
  and "grayscale chart for e-reader". Use for chart form, the focal series,
  gray values, and short chart samples. For a full book or report conversion,
  use kindle-edition. Also known as eink-chart-design.
---

# kindle-reading-kit

Grayscale charts that stay legible on e-ink. The default style is **Editorial Soft**.
This file is the portable recipe. Repository commands are in `RUNBOOK.md`.

## Capability tiers

Pick a tier from the tools you have on this turn, not from a product name. The
same assistant can land in any tier. Report the tier and every check you skip.
A skip is not a pass. Never claim a file was rendered or checked unless you did it.

| Tier | Capability | What you do |
| --- | --- | --- |
| A | Shell, and installs are allowed | Render, package, check, and preview. Follow `RUNBOOK.md`. |
| B | Python, no pip, no network | Render with Matplotlib and Pillow. Run `check_png` when the kit imports. Package or check an EPUB only if `bs4` and `lxml` already import. Skip preview. Do not run pip. |
| C | No code execution | Return a chart spec and self-contained Matplotlib code. Do not claim a render or a check. |

Chart spec: form, focal series, title, subtitle, source line, gray values, label
positions. Tier C code imports Matplotlib and Pillow only and follows the table below.

## Outcome

Make the finding obvious at reading size. **Editorial Soft** is Tufte-style restraint,
thin gray comparison series, a black top rule, quiet horizontal guides, and **one
black thick focal series or bar with bold direct labels**. Softness is for context.
This recipe is independent. It is not an official template.

## Story and source

Prefer a table, CSV, or JSON. Record metric, unit, period, provenance, and caveats.
Mark synthetic data **fictional** on every source line. Do not invent an observation.
If the only input is an image, estimate, label the chart `Values approximated from image`,
show the estimates in a text table, and ask for the real series. One message per chart.
Choose the focal series before drawing and keep it black, heavy, and bold-labeled in
every style. Do not move the highlight, the values, or the axis limits so another style
looks better. Titles are full sentences, usually with a number. Bad: "Regional
performance." Good: "North gains 44 in 12 months." Highlight the series that proves
the claim. If the claim is that South is flat, highlight South even when North is
larger. Every chart has a metric/unit/period subtitle, a dated source line, and a
text fallback when the picture is dense. Do not publish, deliver, email, create a
repository, or change someone else's system unless that exact action was authorized.
Stop and ask. The kit works best when the user adds the agent's email address to
their Amazon Approved Personal Document E-mail List, so the agent can email the
EPUB to the user's Send to Kindle address; otherwise the user moves the file over
by hand, and the agent sends only when the user asks.

## Numeric spec

Asset target: 11th-generation 6.8-inch 300 ppi Paperwhite, portrait, 1236 x 1648,
nominal 16 gray levels. Later hardware differs. The 2024 12th-generation Paperwhite
is a 7-inch 300 ppi grayscale panel (reviewers report 1264 x 1680). Kindle Colorsoft
is a 7-inch color panel; Amazon lists 300 ppi in black and white, 150 ppi in color,
and 16 gray levels. Confirm the device. Keep the 1236 px grayscale asset unless
asked otherwise. Do not encode meaning in color. Device processing can still change
separation, so spaced grays are a target, not a guarantee.

| Item | Spec |
| --- | --- |
| Canvas | Mode `L`, 1236 px wide, height 1236-1606 (aspect 1.00-1.30), drawn at 4.12 in and 300 dpi. EPUB margins mean this is the file size, not a 1:1 display promise. |
| Strokes | Context and guides at least 1.5 pt (about 6.25 px at 1236, about 3.8 px at 758). Focal stroke 3.4 pt (about 14 px). Softness comes from light gray, not from a hairline. |
| Grays | 0 / 85 / 153 / 221 / 255 (`#000` / `#555` / `#999` / `#DDD` / white), steps 0 / 5 / 9 / 13 / 15. Guides 221. Context 85 or 153. Focus and primary text 0. Do not encode categories with adjacent steps. |
| Type | Headlines 13-14 pt (about 54-58 px), labels 11 pt (about 46 px), subtitles 10.5 pt (about 44 px), sources and ticks at least 9.5 pt (about 40 px). At 758 px the minimum em is about 24 px. |
| EPUB text | Relative `em` only. No font-family lock and no absolute font size. Raster chart fonts stay fixed. |

## Forms and styles

Caps are limits, not targets. Direct-label the focal mark. Comparisons use a dash
or a marker as well as a gray. With more than 3 series, patterns are required and
small multiples are preferred. Split series that cross or land on the same label.

- **Line:** change over time, at most 4 series, sparse ticks, endpoint labels, honest scales.
- **Ranked horizontal bar:** size, at most 8 bars, zero baseline, values at the ends. Descend unless order is meaningful (time, rank the user asked for).
- **Small multiples:** shared units, period, and y limits. One black panel. Prefer 3-4.
- **Sparkline table:** aligned trends plus end values, at most 4 rows, shared scales. An image, not an HTML table.
- **Slope:** start versus end, ideally at most 4 entities, both ends labeled. Do not move a label without keeping its pairing obvious.
- **Dot/range:** less ink, or an observed min-max. Say which. A range is not a confidence interval. The `dot_range` helper draws ranges, not a statistical estimate.
- **Otherwise:** histogram or ECDF with bins and sample size, sparse labeled scatter, or a short waterfall. Dense matrices and maps belong in native text. Do not invent a helper the kit does not have.

No 3-D, dual axes, fine gradients, transparency-as-meaning, or decorative grids.
Guides must help estimation. Push back on pies. If one is unavoidable, use at most
3 directly labeled slices and say a ranked bar is usually clearer.

One default plus four alternatives. Keep all five available.

1. **Editorial Soft** (`editorial-soft`, default): 3.4 pt black focus, 1.5 pt gray context, 1.5 pt light guides, black top rule, compact sans titles.
2. **Tufte Minimal** (`tufte-minimal`): serif raster type, fewer rules, no guides, same strong black focal mark.
3. **Bold Highlight** (`bold-highlight`): 3.8 pt focal stroke, 14 pt titles, no top rule or guides.
4. **Pattern & Texture** (`pattern-texture`): hatches on comparison bars and open markers on comparison trends. Focus stays solid black. Avoid moiré.
5. **Economist-style Editorial** (`economist-editorial`): top rule, guides, 2 pt context strokes. Grammar only: no logo, trade dress, or claim of affiliation.

## Handoff

Tier A and tier B follow `RUNBOOK.md`, then list checks that ran and checks that
were skipped. A preview is a simulation, not a device test, and it does not certify
store conversion. Tier C stops after the spec and the code.
