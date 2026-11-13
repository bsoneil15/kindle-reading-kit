"""Build two short EPUBs from the same fictional table to compare at two font sizes.

  after:  chart first, then a 3-column text table, then record cards (kindle_tables)
  before: a 7-column print table floated beside the chart (what not to ship)

python examples/table_ladder.py --out output/tables
python scripts/check_epub.py output/tables/Table-Ladder-After.epub
python scripts/preview_kindle.py output/tables/Table-Ladder-After.epub output/tables/after-1x
python scripts/preview_kindle.py output/tables/Table-Ladder-After.epub output/tables/after-2x --font-scale 2
The before EPUB fails check_epub on purpose: its table has 7 columns.
"""
from pathlib import Path
import argparse, html, sys
from PIL import Image
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import kindle_epub as ep
import kindle_charts as kit
import kindle_tables as kt

SOURCE = "Source: Fictional example data, 2025."
COLUMNS = ["Region", "Q1, k", "Q2, k", "Q3, k", "YoY", "Util", "Note"]
ROWS = [dict(zip(COLUMNS, r)) for r in [
    ("North", 1240, 1310, 1295, "+4.4%", "62%", "Q3 dip"),
    ("South", 980, 975, 990, "+1.0%", "48%", "flat"),
    ("East", 1560, 1610, 1702, "+9.1%", "71%", "new site"),
    ("West", 1105, 1080, 1121, "+1.4%", "55%", ""),
    ("Central", 870, 902, 944, "+8.5%", "44%", "pilot"),
]]
TITLE = "East leads Q3 at 1,702 and grows fastest."
HEADING = "Q3 volume across five regions"
NOTES = ["k = thousand units. YoY = Q3 change from Q3 last year."]
DETAIL_NOTES = ["Util = share of site capacity used in Q3."]


def _cover(out, label):
    im = Image.new("L", (1236, 1648), 255)
    im.convert("RGB").save(out / ("cover-%s.jpg" % label), quality=90)
    return str(out / ("cover-%s.jpg" % label))


def build_after(out, chart):
    body = ep.chapter_head("Tables and dense data", HEADING)
    body += '<p class="lede">Chart first for the pattern. The values follow as text, so they reflow at any font size.</p>'
    fig = kit.figure_html(chart, alt=kit.text_fallback(chart))
    body += ep.to_xhtml(ep.generic(fig, ep.Notes("t"), {"img/" + Path(chart["path"]).name: fig}))
    table, plan = kt.render(COLUMNS, ROWS, show=["Region", "Q3, k", "YoY"], title="Q3 by region",
                            focal="East", sort_by="Q3, k", notes=NOTES, detail_notes=DETAIL_NOTES,
                            detail_title="Other fields by region")
    body += table + '<p class="small">%s</p>' % html.escape(SOURCE)
    docs = [("cover.xhtml", "Cover", ep.page("Table ladder", '<h1>Table ladder: after</h1><p>Fictional data.</p>' + ep.next_link("data.xhtml", "Data"))),
            ("data.xhtml", "Q3 by region", ep.page(TITLE, ep.to_xhtml(body), "chapter"))]
    path = out / "Table-Ladder-After.epub"
    ep.write_epub(str(path), dict(title="Table ladder after", date="2026-11-12", desc="Fictional table ladder sample."),
                  docs, [(chart["path"], "img/" + Path(chart["path"]).name)], _cover(out, "after"))
    return path, plan


def build_before(out, chart):
    head = "".join("<th>%s</th>" % html.escape(c) for c in COLUMNS)
    rows = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % html.escape(kt._fmt(r[c])) for c in COLUMNS) for r in ROWS)
    body = ('<h1>%s</h1><div style="float:left;width:50%%"><img src="img/%s" alt="%s" style="width:100%%"/></div>'
            '<table style="width:50%%;font-size:0.7em;border-top:1px solid #DDD"><tr>%s</tr>%s</table>'
            '<p style="clear:both">%s</p>' % (html.escape(TITLE), Path(chart["path"]).name, html.escape(chart["title"]),
                                             head, rows, html.escape(SOURCE)))
    docs = [("cover.xhtml", "Cover", ep.page("Table ladder", "<h1>Table ladder: before</h1><p>Fictional data.</p>")),
            ("data.xhtml", "Q3 by region", ep.page(TITLE, body))]
    path = out / "Table-Ladder-Before.epub"
    ep.write_epub(str(path), dict(title="Table ladder before", date="2026-11-12", desc="Fictional print-style table."),
                  docs, [(chart["path"], "img/" + Path(chart["path"]).name)], _cover(out, "before"))
    return path


def main(out):
    out = Path(out).resolve(); out.mkdir(parents=True, exist_ok=True)
    kit.OUT = str(out / "charts")
    chart = kit.hbar({r["Region"]: r["Q3, k"] for r in ROWS}, title=TITLE, sub="Q3 units, thousands · 2025",
                     name="q3.png", source=SOURCE, highlight="East", fmt=lambda v: "{:,}".format(v), style="editorial-soft")
    assert not kit.check_png(chart["path"])
    after, plan = build_after(out, chart)
    before = build_before(out, chart)
    print("plan:", plan["form"], "|", "; ".join(plan["reasons"]))
    print("wrote", after); print("wrote", before)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=ROOT / "output/tables")
    main(parser.parse_args().out)
