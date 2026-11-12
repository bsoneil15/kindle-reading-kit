"""Path safety, container.xml, optional-dependency honesty, and cwd independence."""
from pathlib import Path
import os
import posixpath
import subprocess
import sys
import tempfile
import textwrap
import threading
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT / "examples"))

import kindle_charts as kit
from eink_style import style
import check_epub
import preview_kindle
from PIL import Image

PY = sys.executable


def run(args, cwd, env=None):
    return subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True)


def write_epub(path, opf_rel="OEBPS/content.opf", quote='"', pages=("Alpha section",), broken=False):
    path = Path(path)
    opf_dir = posixpath.dirname(opf_rel)
    names = []
    bodies = []
    for index, label in enumerate(pages, start=1):
        name = "c%d.xhtml" % index
        names.append(name)
        link = '<p><a href="missing.xhtml">bad</a></p>' if broken and index == 1 else ""
        bodies.append((name, '''<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"><head><title>%s</title></head>
<body><p id="p%d">%s</p>%s</body></html>''' % (label, index, label, link)))
    manifest = "".join(
        '<item id="c%d" href="%s" media-type="application/xhtml+xml"/>' % (i, name)
        for i, name in enumerate(names, start=1))
    spine = "".join('<itemref idref="c%d"/>' % i for i in range(1, len(names) + 1))
    opf = '''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="uid">urn:uuid:test</dc:identifier>
<dc:title>T</dc:title></metadata>
<manifest>%s</manifest><spine>%s</spine></package>''' % (manifest, spine)
    full = "%s%s%s" % (quote, opf_rel, quote)
    container = '''<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles><rootfile full-path=%s media-type="application/oebps-package+xml"/></rootfiles>
</container>''' % full
    with zipfile.ZipFile(path, "w") as zf:
        info = zipfile.ZipInfo("mimetype")
        zf.writestr(info, "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr("META-INF/container.xml", container)
        zf.writestr(opf_rel, opf)
        for name, body in bodies:
            target = posixpath.join(opf_dir, name) if opf_dir else name
            zf.writestr(target, body)
    return path


def _replace_zip_entry(path, name, content):
    """Rewrite one zip entry in place so the archive does not keep two copies."""
    path = Path(path)
    original = path.read_bytes()
    buffer = Path(str(path) + ".tmp")
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(buffer, "w") as dest:
        for info in source.infolist():
            data = content.encode("utf-8") if info.filename == name else source.read(info.filename)
            dest.writestr(info.filename, data, compress_type=info.compress_type)
    buffer.replace(path)
    if not original:
        raise AssertionError("empty zip")


def assert_true(cond, message):
    if not cond:
        raise AssertionError(message)


def test_dangerous_paths(tmp):
    safe = tmp / "out"
    assert_true(preview_kindle.dangerous_output_reason(safe) is None, "temp outdir should be allowed")
    for path in (Path("/"), Path("/tmp"), Path.home(), ROOT, Path("."), Path(".."), Path("~")):
        reason = preview_kindle.dangerous_output_reason(path)
        assert_true(reason and "force does not override" in reason, "expected refusal for %s, got %r" % (path, reason))
    link = tmp / "linked"
    link.symlink_to(tmp, target_is_directory=True)
    assert_true("symlink" in preview_kindle.dangerous_output_reason(link), "symlink must be refused")
    epub = write_epub(tmp / "book.epub")
    for target in ("/", str(ROOT), str(Path.home()), str(tmp)):
        # tmp itself is the cwd of this test only when we set it. Refuse repo and root with --force.
        proc = run([PY, str(SCRIPTS / "preview_kindle.py"), str(epub), target, "--force"], cwd=tmp)
        assert_true(proc.returncode == 2, "dangerous --force exit %s for %s\n%s" % (proc.returncode, target, proc.stderr))
        assert_true("dangerous" in proc.stderr or "contains" in proc.stderr or "too-broad" in proc.stderr,
                    proc.stderr)
        assert_true("OK" not in proc.stdout and "pages" not in proc.stdout, proc.stdout)
    assert_true((ROOT / "SKILL.md").is_file(), "repo skill file missing after refusal")


def _snapshot(directory):
    return sorted((path.name, path.read_bytes()) for path in directory.iterdir())


def test_force_respects_marker(tmp):
    """--force replaces only a folder that already has this script's marker."""
    marked = tmp / "marked"
    marked.mkdir()
    (marked / preview_kindle.PREVIEW_MARKER).write_text("kindle-reading-kit preview output\n")
    (marked / "old.txt").write_text("old")
    preview_kindle._prepare_outdir(marked, force=True)
    assert_true(not (marked / "old.txt").exists(), "--force should replace a marked preview folder")
    assert_true((marked / preview_kindle.PREVIEW_MARKER).is_file(), "replaced folder should keep the marker")
    assert_true(list(marked.iterdir()) == [marked / preview_kindle.PREVIEW_MARKER], list(marked.iterdir()))

    foreign = tmp / "documents"
    foreign.mkdir()
    keep = foreign / "taxes.txt"
    keep.write_text("keep")
    before = _snapshot(foreign)
    try:
        preview_kindle._prepare_outdir(foreign, force=True)
        raise AssertionError("unmarked folder was replaced")
    except ValueError as exc:
        assert_true("Nothing was deleted" in str(exc), exc)
        assert_true(".kindle-preview" in str(exc), exc)
    assert_true(_snapshot(foreign) == before, "unmarked folder was changed")
    assert_true(keep.read_text() == "keep", keep.read_text())

    linked = tmp / "linked-marker"
    linked.mkdir()
    outside = tmp / "outside-marker-target"
    outside.write_text("not a preview")
    (linked / preview_kindle.PREVIEW_MARKER).symlink_to(outside)
    (linked / "notes.txt").write_text("notes")
    linked_before = _snapshot(linked)
    try:
        preview_kindle._prepare_outdir(linked, force=True)
        raise AssertionError("symlink marker authorized a delete")
    except ValueError as exc:
        assert_true("Nothing was deleted" in str(exc), exc)
    assert_true(_snapshot(linked) == linked_before, "symlink-marker folder was changed")
    assert_true(outside.read_text() == "not a preview", "marker symlink target was changed")


def test_nonempty_and_pages(tmp):
    epub = write_epub(tmp / "two.epub", opf_rel="OPS/package.opf", pages=("Alpha section", "Beta section"))
    foreign = tmp / "not-ours"
    foreign.mkdir()
    sentinel = foreign / "keep.txt"
    sentinel.write_text("keep")
    before = _snapshot(foreign)
    for extra in ([], ["--force"]):
        blocked = run([PY, str(SCRIPTS / "preview_kindle.py"), str(epub), str(foreign), *extra], cwd=tmp)
        assert_true(blocked.returncode == 2, blocked.stderr)
        assert_true("non-empty" in blocked.stderr, blocked.stderr)
        assert_true("Nothing was deleted" in blocked.stderr, blocked.stderr)
        assert_true("OK" not in blocked.stdout and "pages" not in blocked.stdout, blocked.stdout)
        assert_true(_snapshot(foreign) == before, "preview changed an unmarked folder: %s" % extra)
        assert_true(sentinel.read_text() == "keep", "preview deleted a non-empty directory")
    assert_true(".kindle-preview" in blocked.stderr, blocked.stderr)

    outdir = tmp / "preview"
    first = run([PY, str(SCRIPTS / "preview_kindle.py"), str(epub), str(outdir)], cwd=tmp)
    assert_true(first.returncode == 0, first.stderr)
    assert_true("pages 2" in first.stdout, first.stdout)
    marker = outdir / preview_kindle.PREVIEW_MARKER
    assert_true(marker.is_file() and not marker.is_symlink(), "preview did not mark its own folder")
    assert_true((outdir / "sheet_00.png").is_file(), "contact sheet missing")
    from pypdf import PdfReader

    def page_texts():
        reader = PdfReader(str(outdir / "all.pdf"))
        return [page.extract_text() or "" for page in reader.pages]

    texts = page_texts()
    assert_true(len(texts) == 2, texts)
    assert_true("Alpha section" in texts[0] and texts[0].strip().splitlines()[-1] == "1", texts[0])
    assert_true("Beta section" in texts[1] and texts[1].strip().splitlines()[-1] == "2", texts[1])
    stale = outdir / "keep.txt"
    stale.write_text("keep")
    blocked = run([PY, str(SCRIPTS / "preview_kindle.py"), str(epub), str(outdir)], cwd=tmp)
    assert_true(blocked.returncode == 2, blocked.stderr)
    assert_true(stale.read_text() == "keep", "preview deleted a marked folder without --force")
    forced = run([PY, str(SCRIPTS / "preview_kindle.py"), str(epub), str(outdir), "--force"], cwd=tmp)
    assert_true(forced.returncode == 0, forced.stderr)
    assert_true("pages 2" in forced.stdout, forced.stdout)
    assert_true(not stale.exists(), "--force should replace a marked preview folder")
    assert_true(marker.is_file(), "replacement should write the marker again")
    texts = page_texts()
    assert_true(len(texts) == 2, texts)
    assert_true("Alpha section" in texts[0] and texts[0].strip().splitlines()[-1] == "1", texts[0])
    assert_true("Beta section" in texts[1] and texts[1].strip().splitlines()[-1] == "2", texts[1])


def test_container(tmp):
    standard = write_epub(tmp / "standard.epub", opf_rel="OEBPS/content.opf")
    ops = write_epub(tmp / "ops.epub", opf_rel="OPS/package.opf", quote="'")
    for path in (standard, ops):
        proc = run([PY, str(SCRIPTS / "check_epub.py"), str(path)], cwd=tmp)
        assert_true(proc.returncode == 0, proc.stdout + proc.stderr)
        assert_true(proc.stdout.strip().endswith("OK"), proc.stdout)
    missing = tmp / "missing-opf.epub"
    write_epub(missing, opf_rel="OPS/package.opf")
    _replace_zip_entry(missing, "META-INF/container.xml", '''<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles><rootfile full-path="OPS/missing.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>''')
    proc = run([PY, str(SCRIPTS / "check_epub.py"), str(missing)], cwd=tmp)
    assert_true(proc.returncode == 1, proc.stdout)
    assert_true("missing package document" in proc.stdout, proc.stdout)
    assert_true(not proc.stdout.strip().endswith("OK"), proc.stdout)
    escaped = tmp / "escape.epub"
    write_epub(escaped)
    _replace_zip_entry(escaped, "META-INF/container.xml", '''<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles><rootfile full-path="../outside.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>''')
    proc = run([PY, str(SCRIPTS / "check_epub.py"), str(escaped)], cwd=tmp)
    assert_true(proc.returncode == 1, proc.stdout + proc.stderr)
    assert_true("escapes" in proc.stdout, proc.stdout)
    broken = write_epub(tmp / "broken.epub", broken=True)
    proc = run([PY, str(SCRIPTS / "check_epub.py"), str(broken)], cwd=tmp)
    assert_true(proc.returncode == 1 and "broken link" in proc.stdout, proc.stdout)


def _blocked_source(blocked, argv):
    return textwrap.dedent('''
        import sys
        BLOCKED = %r
        class Block:
            def find_spec(self, name, path, target=None):
                if name.split(".")[0] in BLOCKED:
                    raise ModuleNotFoundError(name)
                return None
        sys.meta_path.insert(0, Block())
        for key in list(sys.modules):
            if key.split(".")[0] in BLOCKED:
                del sys.modules[key]
        sys.argv = %r
        import runpy
        try:
            runpy.run_path(sys.argv[0], run_name="__main__")
        except SystemExit as exc:
            code = exc.code
            if code is None:
                code = 0
            elif not isinstance(code, int):
                code = 1
            raise SystemExit(code)
    ''') % (blocked, argv)


def test_missing_optional(tmp):
    epub = write_epub(tmp / "plain.epub")
    outdir = tmp / "skipped-preview"
    runner = tmp / "block_preview.py"
    runner.write_text(_blocked_source(("weasyprint",), [str(SCRIPTS / "preview_kindle.py"), str(epub), str(outdir)]))
    proc = run([PY, str(runner)], cwd=tmp)
    combined = proc.stdout + proc.stderr
    assert_true(proc.returncode == 2, combined)
    assert_true("preview skipped:" in combined, combined)
    assert_true("OK" not in proc.stdout and "pages" not in proc.stdout, proc.stdout)
    assert_true(not outdir.exists(), "skip must not create or delete the destination")
    checker = tmp / "block_check.py"
    checker.write_text(_blocked_source(("lxml",), [str(SCRIPTS / "check_epub.py"), str(epub)]))
    proc = run([PY, str(checker)], cwd=tmp)
    combined = proc.stdout + proc.stderr
    assert_true(proc.returncode == 2, combined)
    assert_true("check_epub skipped:" in combined, combined)
    assert_true("OK" not in combined, combined)
    empty_bin = tmp / "empty-bin"
    empty_bin.mkdir()
    env = os.environ.copy()
    env["PATH"] = str(empty_bin)
    proc = run([PY, str(SCRIPTS / "preview_kindle.py"), str(epub), str(tmp / "no-poppler")], cwd=tmp, env=env)
    combined = proc.stdout + proc.stderr
    assert_true(proc.returncode == 2, combined)
    assert_true("preview skipped:" in combined and "pdftoppm" in combined, combined)
    assert_true("pages" not in proc.stdout, proc.stdout)
    core = tmp / "core_only.py"
    core.write_text(textwrap.dedent('''
        import sys
        BLOCKED = {"weasyprint", "pypdf", "lxml", "bs4"}
        class Block:
            def find_spec(self, name, path, target=None):
                if name.split(".")[0] in BLOCKED:
                    raise ModuleNotFoundError(name)
                return None
        sys.meta_path.insert(0, Block())
        for key in list(sys.modules):
            if key.split(".")[0] in BLOCKED:
                del sys.modules[key]
        sys.path.insert(0, %r)
        import kindle_charts as kc
        kc.OUT = %r
        chart = kc.hbar([("North", 96), ("South", 40)], "North leads at 96.", "Thousands",
                        "bar.png", source="Source: Fictional example data, 2025.", highlight="North",
                        style="editorial-soft")
        assert kc.check_png(chart["path"]) == []
        print("CORE_OK")
    ''') % (str(SCRIPTS), str(tmp / "core-out")))
    proc = run([PY, str(core)], cwd=tmp)
    assert_true(proc.returncode == 0 and "CORE_OK" in proc.stdout, proc.stdout + proc.stderr)


def test_style_argument_and_threads(tmp):
    original_width = kit.LW_HI
    original_finish = kit.finish
    kit.OUT = str(tmp / "styled")
    chart = kit.line_chart(
        ["Jan", "Dec"], {"Focus": [52, 96], "Context": [48, 64]},
        title="Focus gains 44 in 12 months.",
        sub="Shipments, thousands · 2025", name="growth.png",
        source="Source: Fictional example data, 2025.",
        highlight="Focus", ylim=(0, 100), style="editorial-soft")
    assert_true(kit.check_png(chart["path"]) == [], kit.check_png(chart["path"]))
    assert_true(kit.LW_HI == original_width and kit.finish is original_finish, "style= did not restore globals")
    image = Image.open(chart["path"])
    assert_true(image.getpixel((image.width // 2, round(image.height * 0.005))) == 0, "top rule missing")
    try:
        kit.hbar([("A", 1)], "Title.", "sub", "nope.png", source="Source: x", style="not-a-style")
        raise AssertionError("unknown style accepted")
    except ValueError:
        pass
    with style("editorial-soft"):
        pass
    started = threading.Event()
    release = threading.Event()
    errors = []

    def hold():
        try:
            with style("editorial-soft"):
                started.set()
                release.wait(5)
        except Exception as exc:
            errors.append(exc)
            started.set()

    thread = threading.Thread(target=hold)
    thread.start()
    assert_true(started.wait(5), "style holder did not start")
    refused = False
    try:
        with style("bold-highlight"):
            pass
    except RuntimeError:
        refused = True
    finally:
        release.set()
        thread.join(5)
    assert_true(refused, "second thread entered style()")
    assert_true(not errors, errors)
    assert_true(not thread.is_alive(), "style holder is still running")
    assert_true(kit.finish is original_finish and kit.LW_HI == original_width, "thread test leaked globals")


def test_outside_repo(tmp):
    outside = Path(tempfile.mkdtemp(prefix="kindle-outside-"))
    proc = run([PY, str(SCRIPTS / "test_kit.py")], cwd=outside)
    assert_true(proc.returncode == 0 and "all tests passed" in proc.stdout, proc.stdout + proc.stderr)
    proc = run([PY, str(ROOT / "tests" / "test_styles.py")], cwd=outside)
    assert_true(proc.returncode == 0 and "PASS:" in proc.stdout, proc.stdout + proc.stderr)
    charts = outside / "charts"
    proc = run([PY, str(ROOT / "examples" / "render_charts.py"), "--out", str(charts), "--style", "tufte-minimal"],
               cwd=outside)
    assert_true(proc.returncode == 0, proc.stderr)
    assert_true(len(list(charts.glob("*.png"))) == 6, list(charts.glob("*")))
    solo = outside / "solo.png"
    proc = run([PY, str(ROOT / "examples" / "matplotlib_only.py"), "--out", str(solo)], cwd=outside)
    assert_true(proc.returncode == 0, proc.stderr)
    image = Image.open(solo)
    levels = {value for value, count in enumerate(image.histogram()) if count}
    assert_true(image.mode == "L" and image.width == 1236, image.size)
    assert_true(levels <= {0, 85, 153, 221, 255}, levels)
    assert_true("Fictional example data" in proc.stdout, proc.stdout)
    epub = write_epub(outside / "from-outside.epub", opf_rel="OPS/book.opf", quote="'")
    proc = run([PY, str(SCRIPTS / "check_epub.py"), str(epub)], cwd=outside)
    assert_true(proc.returncode == 0 and proc.stdout.strip().endswith("OK"), proc.stdout + proc.stderr)


def main():
    with tempfile.TemporaryDirectory(prefix="kindle-port-") as directory:
        tmp = Path(directory)
        test_dangerous_paths(tmp)
        test_container(tmp)
        test_missing_optional(tmp)
        test_style_argument_and_threads(tmp)
        test_force_respects_marker(tmp)
        test_nonempty_and_pages(tmp)
        test_outside_repo(tmp)
    print("PASS: dangerous paths, marker-only --force, continuous page numbers,")
    print("container.xml OPF resolution, core render without optional packages,")
    print("style= restoration, second-thread refusal, and kit runs from outside the repo.")
    print("Skip checks exited non-zero and did not print OK. A skip is not a pass.")


if __name__ == "__main__":
    main()
