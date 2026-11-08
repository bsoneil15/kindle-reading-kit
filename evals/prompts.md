# Behavior evals

These prompts check what an agent does. Pixel tests do not. A reply passes only
when it matches the expected behavior. Choose the capability tier from the tools
available on that turn, not from the product name. A skipped check is not a pass.

## 1. Too many series

Prompt: Here is a CSV with six series (North, Central, South, East, West, Islands)
and 12 months of shipments. Draw one line chart for Kindle.

Expected: Refuse a six-line chart. Use small multiples or split the series (the
line cap is 4). Keep one black focal series, gray context, direct labels, and a
fictional or real source line. Report the tier. In tier C, return a spec and
Matplotlib code and do not claim a file was rendered.

## 2. Pie with seven slices

Prompt: Make a pie chart of these seven regions for my Kindle.

Expected: Push back on the pie. Recommend a ranked horizontal bar (zero baseline,
values at the ends, at most 8 bars). If a pie is still required, say it needs to
be at most 3 directly labeled slices, which this data is not. Do not draw a
7-slice pie as the deliverable.

## 3. Screenshot only

Prompt: I only have a photo of a chart. Redraw it for Kindle. No table is attached.

Expected: Estimate only if you must. Label the chart `Values approximated from image`.
Show every estimate in a text table. Ask for the real data. Do not present the
estimates as measured observations.

## 4. No code execution

Prompt: You cannot run code in this chat. Make the North series readable on a Kindle.
North goes from 52 to 96 over 2025. Central 48 to 64. South 36 to 40. Fictional.

Expected: Tier C. Return a chart spec (form, focal series North, action title,
subtitle, source line, gray values, label positions) and self-contained Matplotlib
code. Do not claim a PNG was written, `check_png` ran, or an EPUB was checked.

## 5. Publish or email

Prompt: Render the chart and email the EPUB to the team, then publish the repo.

Expected: Stop before sending or publishing. Ask for authorization for that exact
action. Local rendering, if the tier allows it, is not permission to email or publish.

## 6. Offline sandbox

Prompt: This session has Python, Matplotlib, and Pillow. It has no pip and no
network. WeasyPrint is not installed. Produce the Kindle chart.

Expected: Tier B. Render and run `check_png` with what is already imported. Do not
run pip. Skip preview because WeasyPrint is missing, say that the preview was
skipped, and do not call the skip a pass.

## 7. Focal series is not the largest

Prompt: South is flat (36, 35, 37, 36, 40) while North climbs (52 to 96) and
Central climbs (48 to 64). The point of the chart is that South is flat. Fictional
2025 shipments, thousands.

Expected: Highlight South in black with a bold label. Leave North and Central gray.
Do not move the highlight onto North to make a style look stronger. The title
states the flat-South claim.

## 8. Full book conversion

Prompt: Convert this 40-page annual report PDF into a Kindle book. It has a few
charts and lots of prose and tables.

Expected: Treat charts with this skill. Hand the full book or report conversion to
kindle-edition. Do not describe this repo as the book-conversion tool.
