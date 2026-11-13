"""Navigation: two-level contents from headings, NCX depth, landmarks, nav lint, cover, book id."""
from pathlib import Path
import subprocess, sys, tempfile, warnings, zipfile
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "examples"))
import kindle_epub as ep
import epub_nav
import check_epub
from epub_paths import join_zip, package_opf_path


def raises(f, kind=ValueError):
    try: f(); return False
    except kind: return True


def book(tmp, name="multi.epub", nav=None, meta=None, extra_section=True):
    """Cover, start chapter with 2 h2, contents page, chapter 2 with two section files."""
    start = ep.chapter_head("Start here", "Two sections follow.", None, [("a", "Alpha"), ("b", "Beta")])
    start += '<h2 id="a">Alpha</h2><p>a</p><h2 id="b">Beta</h2><p>b</p>'
    start += '<section class="notes" epub:type="endnotes"><h2>Sources for this section</h2></section>'
    docs = [("cover.xhtml", "Cover", ep.page("Cover", "<h1>Cover</h1>", "cover")),
            ("start.xhtml", "Start", ep.page("Start", start, "chapter")),
            ("contents.xhtml", "Contents", ep.page("Contents", "", "toc")),
            ("ch2.xhtml", "Charts", ep.page("Charts", ep.chapter_head("Charts", "Charts in two files."), "chapter")),
            ("s1.xhtml", "Line", ep.page("Line", ep.section_head("Line") + "<p>x</p>", "section"))]
    if extra_section:
        docs.append(("s2.xhtml", "Bar", ep.page("Bar", ep.section_head("Bar") + "<p>y</p>", "section")))
    tree = epub_nav.build_nav(docs)
    docs[2] = ("contents.xhtml", "Contents", ep.page("Contents", ep.contents_html(tree), "toc"))
    cover = tmp / "cover.jpg"
    if not cover.exists(): ep.make_cover(str(cover), "KICKER", ["Test", "Book"], "Sub line.", "FOOT")
    path = tmp / name
    ep.write_epub(str(path), meta or dict(title="Nav test", date="2026-11-12", desc="d"), docs, [], str(cover), nav)
    return path, tree


def lint(path):
    with zipfile.ZipFile(path) as z:
        return epub_nav.lint_nav(z, package_opf_path(z), join_zip)


def rewrite(path, name, fn):
    data = {}
    with zipfile.ZipFile(path) as z:
        infos = z.infolist()
        for i in infos: data[i.filename] = z.read(i.filename)
    data[name] = fn(data[name].decode("utf-8")).encode("utf-8")
    with zipfile.ZipFile(path, "w") as z:
        for i in infos: z.writestr(i, data[i.filename])


def test_tree(tmp):
    path, tree = book(tmp)
    assert tree == [("Start here", "start.xhtml", [("Alpha", "start.xhtml#a", []), ("Beta", "start.xhtml#b", [])]),
                    ("Charts", "ch2.xhtml", [("Line", "s1.xhtml", []), ("Bar", "s2.xhtml", [])])], tree
    with zipfile.ZipFile(path) as z:
        nav = z.read("OEBPS/nav.xhtml").decode(); ncx = z.read("OEBPS/toc.ncx").decode()
        opf = z.read("OEBPS/content.opf").decode(); contents = z.read("OEBPS/contents.xhtml").decode()
        start = z.read("OEBPS/start.xhtml").decode()
    toc = nav.split('epub:type="landmarks"')[0]
    assert "contents.xhtml" not in toc and "Sources for this section" not in toc and "cover.xhtml" not in toc
    assert 'epub:type="toc" href="contents.xhtml"' in nav and 'epub:type="bodymatter" href="start.xhtml"' in nav
    assert '<meta name="dtb:depth" content="2"/>' in ncx and ncx.count("<navPoint") == 6
    assert 'class="toc2"><a href="s1.xhtml">Line</a>' in contents and 'class="toc1"><a href="ch2.xhtml">Charts</a>' in contents
    assert '<section epub:type="chapter" role="doc-chapter"><h1><span class="label">Start here</span>' in start
    assert "<dc:creator>%s</dc:creator>" % ep.DEFAULT_AUTHOR in opf
    assert lint(path) == [], lint(path)
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_epub.py"), str(path)], capture_output=True, text=True)
    assert proc.returncode == 0 and proc.stdout.strip().endswith("OK"), proc.stdout
    flat, _ = book(tmp, "flat.epub", nav=[("Start here", "start.xhtml", []), ("Charts", "ch2.xhtml", [])])
    with zipfile.ZipFile(flat) as z:
        assert '<meta name="dtb:depth" content="1"/>' in z.read("OEBPS/toc.ncx").decode()
    assert any("no contents entry" in p for p in lint(flat)), lint(flat)


def test_builder_errors(tmp):
    deep = [("A", "start.xhtml", [("B", "start.xhtml#a", [("C", "start.xhtml#b", [])])])]
    assert raises(lambda: book(tmp, "deep.epub", nav=deep))
    cover = ("cover.xhtml", "c", ep.page("c", "<p>c</p>"))
    assert raises(lambda: epub_nav.build_nav([cover, ("x.xhtml", "x", ep.page("x", "<p>no heading</p>"))]))
    assert raises(lambda: epub_nav.build_nav([cover, ("x.xhtml", "x", ep.page("x", "<h2>orphan</h2>"))]))
    assert raises(lambda: epub_nav.build_nav([cover, ("x.xhtml", "x", ep.page("x", "<h1>A</h1><h2>no id</h2>"))]))
    assert raises(lambda: epub_nav.build_nav([cover, ("x.xhtml", "x", ep.page("x", "<h1>A</h1><h1>B</h1>"))]))


def test_lint_catches(tmp):
    path, _ = book(tmp, "bad-label.epub")
    rewrite(path, "OEBPS/nav.xhtml", lambda s: s.replace(">Line</a>", ">Line chart</a>", 1))
    assert any("does not match the heading" in p for p in lint(path)), lint(path)
    assert any("differ from the toc nav" in p for p in lint(path)), lint(path)
    path, _ = book(tmp, "dup.epub")
    rewrite(path, "OEBPS/nav.xhtml", lambda s: s.replace('<a href="s2.xhtml">Bar</a>', '<a href="s1.xhtml">Line</a>', 1))
    probs = lint(path)
    assert any("duplicate" in p for p in probs) and any("s2.xhtml has no contents entry" in p for p in probs), probs
    path, _ = book(tmp, "order.epub")
    rewrite(path, "OEBPS/nav.xhtml", lambda s: s.replace('<a href="s1.xhtml">Line</a>', "@@").replace(
        '<a href="s2.xhtml">Bar</a>', '<a href="s1.xhtml">Line</a>').replace("@@", '<a href="s2.xhtml">Bar</a>'))
    assert any("out of reading order" in p for p in lint(path)), lint(path)
    path, _ = book(tmp, "depth.epub")
    rewrite(path, "OEBPS/toc.ncx", lambda s: s.replace('content="2"', 'content="3"'))
    assert any("dtb:depth says 3" in p for p in lint(path)), lint(path)
    path, _ = book(tmp, "self.epub")
    rewrite(path, "OEBPS/nav.xhtml", lambda s: s.replace('<ol><li><a href="start.xhtml">',
                                                           '<ol><li><a href="contents.xhtml">Contents</a></li><li><a href="start.xhtml">', 1))
    assert any("cover or contents page" in p for p in lint(path)), lint(path)


def test_meta_and_cover(tmp):
    a = ep.book_id(dict(title="Same", date="2026-11-12"))
    b = ep.book_id(dict(title="Same", date="2026-11-12", author="Brendan"))
    c = ep.book_id(dict(title="Same", date="2026-11-13"))
    assert len({a, b, c}) == 3 and a == ep.book_id(dict(title="Same", date="2026-11-12"))
    assert ep.book_id(dict(title="Same", identifier="urn:isbn:1")) == "urn:isbn:1"
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        book(tmp, "warn.epub")
    from PIL import Image
    assert Image.open(tmp / "cover.jpg").size == (1600, 2560)


def main():
    with tempfile.TemporaryDirectory(prefix="kindle-nav-") as d:
        tmp = Path(d)
        test_tree(tmp); test_builder_errors(tmp); test_lint_catches(tmp); test_meta_and_cover(tmp)
    print("PASS: two-level contents from headings, notes headings skipped, NCX depth, landmarks,")
    print("contents page indent, nav lint (labels, duplicates, order, missing, depth, self entry), book id, cover size.")


if __name__ == "__main__":
    main()
