"""Structural check for EPUBs (use when epubcheck/Java is unavailable).

Usage: python3 check_epub.py a.epub [b.epub ...]. Exits 1 on any problem.
Exits 2 when lxml is missing or no path was given. A skip is not a pass.

The package document path comes from META-INF/container.xml (full-path).
Kit EPUBs use OEBPS/content.opf. Other layouts work when the container names them.
Checks: mimetype first, package and content XML parse, manifest files exist,
every internal href/src and #anchor resolves.
"""
import os
import posixpath
import re
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from epub_paths import join_zip, package_opf_path


def _load_lxml():
    try:
        from lxml import etree
    except ImportError as exc:
        print("check_epub skipped: lxml is not installed (%s). The EPUB was not checked." % exc)
        return None
    return etree


def _check_one(etree, path):
    probs = []
    try:
        z = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        return ["not a zip/EPUB: %s" % exc]
    names = z.namelist()
    if not names or names[0] != "mimetype":
        probs.append("mimetype is not first entry")
    try:
        opf_path = package_opf_path(z)
    except ValueError as exc:
        probs.append(str(exc))
        return probs
    opf_dir = posixpath.dirname(opf_path)
    try:
        opf = z.read(opf_path).decode("utf-8")
        etree.fromstring(opf.encode("utf-8"))
    except Exception as exc:
        probs.append("package document: %s" % exc)
        return probs
    manifest = opf.split("<guide>")[0]
    for href in re.findall(r'href="([^"]+)"', manifest):
        if href.startswith(("http://", "https://", "mailto:")):
            continue
        target = join_zip(opf_dir, href)
        if target is None or target not in names:
            probs.append("manifest missing " + href)
    docs = [n for n in names if n.endswith((".xhtml", ".html", ".ncx"))]
    ids = {}
    for name in docs:
        text = z.read(name).decode("utf-8", errors="replace")
        try:
            etree.fromstring(text.encode("utf-8"))
        except Exception as exc:
            probs.append("parse %s: %s" % (name, exc))
        ids[name] = set(re.findall(r'id="([^"]+)"', text))
    for name in docs:
        text = z.read(name).decode("utf-8", errors="replace")
        base = posixpath.dirname(name)
        label = name.split("/")[-1]
        for href in re.findall(r'(?:href|src)="([^"]+)"', text):
            if href.startswith(("http://", "https://", "mailto:")) or href.endswith(".css"):
                continue
            target_href, _, anchor = href.partition("#")
            if not target_href:
                target = name
            else:
                target = join_zip(base, target_href)
            if target is None or target not in names:
                probs.append("%s: broken link %s" % (label, href))
                continue
            if anchor and target in ids and anchor not in ids[target]:
                probs.append("%s: broken link %s" % (label, href))
    return probs


def main(argv):
    etree = _load_lxml()
    if etree is None:
        return 2
    if len(argv) < 2:
        print("usage: python check_epub.py file.epub [more.epub ...]")
        return 2
    bad_any = False
    for path in argv[1:]:
        probs = _check_one(etree, path)
        print(path, "OK" if not probs else "%d problems" % len(probs))
        for problem in probs[:30]:
            print("  ", problem)
        bad_any = bad_any or bool(probs)
    return 1 if bad_any else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
