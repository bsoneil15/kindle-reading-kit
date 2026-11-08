"""Render an EPUB near Kindle Paperwhite page size and build contact sheets.

Usage:
  python3 preview_kindle.py book.epub outdir
  python3 preview_kindle.py book.epub outdir --force

Refuses a non-empty outdir unless --force is set. Refuses dangerous paths
(filesystem root, home, cwd, this repo, /tmp, other broad directories, symlinks)
even when --force is set. Missing WeasyPrint, Pillow, pypdf, or pdftoppm prints
"preview skipped" and exits 2. A skip is not a pass.

The package path comes from META-INF/container.xml. Each spine item is rendered
separately. The footer counter continues across items (WeasyPrint 69:
@page:first { counter-reset: page N } displays N on the first page).
"""
import argparse
import glob
import os
import posixpath
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from epub_paths import join_zip, package_opf_path

PAGE_CSS = """
@page {
  size: 4.12in 5.49in;
  margin: 0.22in 0.25in 0.3in 0.25in;
  @bottom-center { content: counter(page); font-size: 7pt; }
}
html { font-family: 'Bitstream Charter', 'DejaVu Serif', serif; font-size: 9.5pt; text-align: justify; }
img { max-height: 4.8in; }
"""

_BROAD = (
    "/tmp", "/var", "/var/tmp", "/home", "/usr", "/etc", "/opt", "/bin", "/sbin",
    "/lib", "/lib64", "/boot", "/proc", "/sys", "/dev", "/root", "/workspace",
    "/private", "/private/tmp", "/Users",
)


def _contains(parent, child):
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def dangerous_output_reason(path):
    """Return a refusal string, or None when path is a safe preview destination."""
    path = Path(path)
    text = str(path).strip()
    if text in {"", ".", "..", "/", "~"}:
        return ("refusing dangerous preview path: %s. --force does not override this. "
                "Nothing was deleted." % path)
    if path.is_symlink():
        return ("refusing symlink preview path: %s. --force does not override this. "
                "Nothing was deleted." % path)
    try:
        resolved = path.expanduser().resolve()
    except OSError as exc:
        return "refusing preview path %s (%s). Nothing was deleted." % (path, exc)
    home = Path.home().resolve()
    repo = Path(__file__).resolve().parents[1]
    cwd = Path.cwd().resolve()
    protected = {home, repo, cwd, Path(resolved.anchor)}
    for name in _BROAD:
        candidate = Path(name)
        if candidate.is_absolute():
            protected.add(candidate)
    if resolved in protected:
        return ("refusing dangerous preview path: %s. --force does not override this. "
                "Nothing was deleted." % resolved)
    for sensitive in (repo, home, cwd):
        if sensitive != resolved and _contains(resolved, sensitive):
            return ("refusing preview path that contains %s: %s. --force does not override "
                    "this. Nothing was deleted." % (sensitive, resolved))
    if len(resolved.parts) < 3:
        return ("refusing too-broad preview path: %s. --force does not override this. "
                "Nothing was deleted." % resolved)
    return None


def dependency_problem():
    """Return a skip message when preview cannot run, else None."""
    missing = []
    for module, label in (("PIL", "Pillow"), ("weasyprint", "WeasyPrint"), ("pypdf", "pypdf")):
        try:
            __import__(module)
        except Exception as exc:
            missing.append("%s (%s)" % (label, exc))
    if missing:
        return ("preview skipped: missing Python packages: %s. "
                "Install requirements.txt and requirements-optional.txt. "
                "Nothing was rendered or checked."
                % ", ".join(missing))
    if shutil.which("pdftoppm") is None:
        return ("preview skipped: pdftoppm (Poppler) is not on PATH. "
                "Install poppler-utils. Nothing was rendered or checked.")
    return None


def _spine(zf, opf_path):
    opf = zf.read(opf_path).decode("utf-8")
    ids = dict(re.findall(r'<item id="([^"]+)" href="([^"]+)"', opf))
    opf_dir = posixpath.dirname(opf_path)
    items = []
    for idref in re.findall(r'<itemref idref="([^"]+)"', opf):
        if idref not in ids:
            raise ValueError("spine idref %s is not in the manifest" % idref)
        target = join_zip(opf_dir, ids[idref])
        if target is None:
            raise ValueError("spine href escapes the EPUB: %s" % ids[idref])
        items.append(target)
    if not items:
        raise ValueError("spine is empty")
    return items


def _safe_extract(zf, dest):
    dest = Path(dest).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    for info in zf.infolist():
        name = info.filename.replace("\\", "/")
        if name.startswith("/") or name.split("/")[0] == "..":
            raise ValueError("refusing EPUB entry that escapes the archive: %s" % name)
        target = (dest / name).resolve()
        if target != dest and not _contains(dest, target):
            raise ValueError("refusing EPUB entry that escapes the archive: %s" % name)
        zf.extract(info, dest)


def _prepare_outdir(outdir, force):
    if outdir.exists() and not outdir.is_dir():
        raise ValueError("refusing preview path because it is a file: %s. Nothing was deleted." % outdir)
    if outdir.exists():
        entries = list(outdir.iterdir())
        if entries and not force:
            raise ValueError("refusing to replace non-empty directory %s. "
                             "Pass --force to replace it. Nothing was deleted." % outdir)
        if entries:
            shutil.rmtree(outdir)
    outdir.mkdir(parents=True, exist_ok=True)


def _section_css(start_page):
    from weasyprint import CSS
    return CSS(string=PAGE_CSS + "\n@page:first { counter-reset: page %d; }\n" % start_page)


def render_preview(epub, outdir, force=False):
    """Render epub into outdir. Raises ValueError on refusal. Returns page count."""
    epub = Path(epub)
    outdir = Path(outdir)
    skipped = dependency_problem()
    if skipped:
        raise ValueError(skipped)
    reason = dangerous_output_reason(outdir)
    if reason:
        raise ValueError(reason)
    if not epub.is_file():
        raise ValueError("EPUB not found: %s. Nothing was deleted." % epub)
    epub_resolved = epub.resolve()
    out_resolved = outdir.expanduser().resolve()
    if epub_resolved == out_resolved or _contains(out_resolved, epub_resolved):
        raise ValueError("refusing to use a preview path that contains the EPUB (%s). "
                         "Nothing was deleted." % outdir)
    try:
        zf = zipfile.ZipFile(epub)
    except zipfile.BadZipFile as exc:
        raise ValueError("not a zip/EPUB: %s. Nothing was deleted." % exc) from exc
    opf_path = package_opf_path(zf)
    spine = _spine(zf, opf_path)
    _prepare_outdir(out_resolved, force)
    extract_root = out_resolved / "x"
    _safe_extract(zf, extract_root)
    from weasyprint import HTML
    from pypdf import PdfWriter
    writer = PdfWriter()
    start = 1
    for item in spine:
        source = extract_root / item
        pdf_path = out_resolved / (source.stem + ".pdf")
        document = HTML(filename=str(source), base_url=str(source.parent) + os.sep).render(
            stylesheets=[_section_css(start)])
        document.write_pdf(str(pdf_path))
        start += len(document.pages)
        writer.append(str(pdf_path))
    merged = out_resolved / "all.pdf"
    writer.write(str(merged))
    subprocess.run(["pdftoppm", "-r", "110", "-png", str(merged), str(out_resolved / "p")], check=True)
    frames = sorted(glob.glob(str(out_resolved / "p-*.png")))
    from PIL import Image
    for offset in range(0, len(frames), 12):
        images = [Image.open(frame) for frame in frames[offset:offset + 12]]
        width, height = images[0].size
        sheet = Image.new("RGB", (width * 6, height * 2), "white")
        for index, image in enumerate(images):
            sheet.paste(image, ((index % 6) * width, (index // 6) * height))
        sheet.save(str(out_resolved / ("sheet_%02d.png" % (offset // 12))))
    return len(frames)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("epub", type=Path)
    parser.add_argument("outdir", type=Path)
    parser.add_argument("--force", action="store_true",
                        help="replace a non-empty outdir; does not override a dangerous path")
    args = parser.parse_args(argv)
    reason = dangerous_output_reason(args.outdir)
    if reason:
        print(reason, file=sys.stderr)
        return 2
    skipped = dependency_problem()
    if skipped:
        print(skipped, file=sys.stderr)
        return 2
    try:
        pages = render_preview(args.epub, args.outdir, force=args.force)
    except (ValueError, subprocess.CalledProcessError, OSError) as exc:
        message = str(exc)
        if "preview skipped" not in message and "Nothing was deleted" not in message:
            message = "preview failed: %s" % message
        print(message, file=sys.stderr)
        refused = "Nothing was deleted" in message or "refusing" in message or "preview skipped" in message
        return 2 if refused else 1
    sheets = (pages + 11) // 12
    print("pages", pages, "sheets", sheets)
    return 0


if __name__ == "__main__":
    sys.exit(main())
