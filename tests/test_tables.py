"""Table ladder: form choice, caps, focal rows, kt tables kept by generic(), check_epub lint, font scale."""
from pathlib import Path
import subprocess, sys, tempfile, zipfile
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "examples"))
import kindle_tables as kt

COLS = ["Region", "Q1, k", "Q2, k", "Q3, k", "YoY", "Util", "Note"]
ROWS = [dict(zip(COLS, r)) for r in [
    ("North", 1240, 1310, 1295, "+4.4%", "62%", "Q3 dip"), ("South", 980, 975, 990, "+1.0%", "48%", "flat"),
    ("East", 1560, 1610, 1702, "+9.1%", "71%", "new site"), ("West", 1105, 1080, 1121, "+1.4%", "55%", ""),
    ("Central", 870, 902, 944, "+8.5%", "44%", "pilot")]]


def raises(f):
    try: f(); return False
    except ValueError: return True


def test_plan():
    assert kt.plan(["Region", "Q3, k"], ROWS[:1])["form"] == "prose"
    assert kt.plan(["Region", "Q3, k"], ROWS, show=["Region", "Q3, k"])["form"] == "ranked-list"
    p = kt.plan(COLS, ROWS, show=["Region", "Q3, k", "YoY"])
    assert p["form"] == "text-table" and p["details"] == ["Q1, k", "Q2, k", "Util", "Note"], p
    assert p["fit"]["max_scale"] >= kt.MIN_SCALE, p
    p = kt.plan(COLS, ROWS)
    assert p["form"] == "record-cards" and any("columns" in r for r in p["reasons"]), p
    long = [dict(r, Region=r["Region"] + " Metropolitan Statistical Area") for r in ROWS]
    assert kt.plan(COLS, long, show=["Region", "Q3, k", "YoY"])["form"] == "record-cards"
    assert raises(lambda: kt.plan(COLS, ROWS, show=["Q3, k", "Region"]))


def test_fit_scales():
    wide = kt.table_fit(["Region", "Q3, k", "YoY"], ROWS)
    narrow = kt.table_fit(["Region", "Q3, k"], ROWS)
    assert narrow["max_scale"] > wide["max_scale"] > 1, (narrow, wide)
    assert kt.text_em("1,702", True) > kt.text_em("1,702")


def test_table_html():
    h = kt.text_table_html(["Region", "Q3, k", "YoY"], ROWS, title="Q3 by region", focal="East", sort_by="Q3, k",
                           notes=["k = thousand units."])
    assert h.index("East") < h.index("North") < h.index("West") < h.index("South") < h.index("Central")
    assert '<tr class="kt-f"><td class="kt-l">East</td>' in h and '<td class="kt-n">1,702</td>' in h
    assert '<th class="kt-n" scope="col">Q3, k</th>' in h and 'class="kt kt-c3"' in h
    assert h.endswith('<p class="kt-note">k = thousand units.</p>') and "style=" not in h
    assert raises(lambda: kt.text_table_html(["Region", "Q1, k", "Q2, k", "Q3, k"], ROWS))
    assert raises(lambda: kt.text_table_html(["Region", "Note"], [dict(Region="A", Note="a long note in a cell")]))
    assert raises(lambda: kt.text_table_html(["Region", "Q3, k"], ROWS, focal="Atlantis"))
    many = [dict(Region="R%02d" % i, V=i) for i in range(30)]
    h = kt.text_table_html(["Region", "V"], many, title="All", max_rows=12)
    assert h.count("<table") == 3 and h.count("<thead>") == 3 and "(continued, 3 of 3)" in h


def test_cards_and_list():
    h = kt.record_cards_html(COLS, ROWS, focal="East", sort_by="Q3, k", head_value="Q3, k")
    assert '<div class="rec kt-f"><p class="rec-h">East \u00b7 Q3:\u00a01,702\u00a0k</p>' in h, h
    assert "Note:\u00a0new\u00a0site" in h and "West" in h and h.count('<div class="rec') == 5
    assert "Note:" not in h.split("West")[1].split("</div>")[0]  # empty note left out
    l = kt.ranked_list_html(ROWS, "Region", "Q3, k", focal="East", extra="YoY")
    assert l.index("East") < l.index("Central") and '<li class="kt-f">East:\u00a01,702 (+9.1%)</li>' in l, l
    html, p = kt.render(COLS, ROWS, show=["Region", "Q3, k", "YoY"], focal="East", sort_by="Q3, k",
                        notes=["k = thousand units."])
    assert p["form"] == "text-table" and html.index("<table") < html.index("kt-note") < html.index("kt-cards")
    html, p = kt.render(COLS, ROWS, show=["Region", "Q3, k", "YoY"], focal="East", notes=["k = thousand units."],
                        detail_notes=["Util = share of capacity."])
    assert html.index("k = thousand") < html.index("kt-cards") < html.index("Util = share"), html


def test_epub_integration(tmp):
    import kindle_epub as ep
    assert "table.kt" in ep.CSS
    t = kt.text_table_html(["Region", "Q3, k"], ROWS)
    soup = ep.generic(t + "<table><tr><th>A</th><th>B</th><th>C</th></tr><tr><td>x</td><td>1</td><td>2</td></tr></table>",
                      ep.Notes("c"))
    out = str(soup)
    assert out.count("<table") == 1 and 'class="kt kt-c2"' in out and 'class="rec"' in out
    assert kt.lint_table_html(ep.page("t", t)) == []
    bad = ep.page("t", "<table style=\"width:600px\"><tr>%s</tr></table>" % ("<td>1</td>" * 5))
    probs = kt.lint_table_html(bad)
    assert any("5 columns" in p for p in probs) and any("fixed width" in p for p in probs), probs
    assert kt.lint_table_html(ep.page("t", '<table style="border-top:1px solid #000;width:100%"><tr><td>a</td></tr></table>')) == []
    proc = subprocess.run([sys.executable, str(ROOT / "examples" / "table_ladder.py"), "--out", str(tmp / "tl")],
                          capture_output=True, text=True)
    assert proc.returncode == 0 and "plan: text-table" in proc.stdout, proc.stdout + proc.stderr
    check = lambda name: subprocess.run([sys.executable, str(ROOT / "scripts" / "check_epub.py"), str(tmp / "tl" / name)],
                                        capture_output=True, text=True)
    good, bad = check("Table-Ladder-After.epub"), check("Table-Ladder-Before.epub")
    assert good.returncode == 0 and good.stdout.strip().endswith("OK"), good.stdout
    assert bad.returncode == 1 and "7 columns" in bad.stdout, bad.stdout
    return tmp / "tl" / "Table-Ladder-After.epub"


def test_font_scale(tmp, epub):
    import preview_kindle
    if preview_kindle.dependency_problem():
        print("font-scale preview skipped:", preview_kindle.dependency_problem()); return False
    small = preview_kindle.render_preview(epub, tmp / "p1")
    large = preview_kindle.render_preview(epub, tmp / "p2", font_scale=2.0)
    assert large > small, (small, large)
    assert raises(lambda: preview_kindle.render_preview(epub, tmp / "p9", font_scale=9))
    return True


def main():
    test_plan(); test_fit_scales(); test_table_html(); test_cards_and_list()
    with tempfile.TemporaryDirectory(prefix="kindle-tables-") as d:
        epub = test_epub_integration(Path(d))
        ran = test_font_scale(Path(d), epub)
    print("PASS: table ladder plan, caps, focal rows, split headers, cards, generic() keeps kt tables,")
    print("check_epub flags wide tables, " + ("larger font scale adds pages." if ran else "font-scale preview SKIPPED (not a pass)."))


if __name__ == "__main__":
    main()
