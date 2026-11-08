"""Resolve the EPUB package document from META-INF/container.xml.

Zip paths stay forward-slash relative to the archive root. Both check_epub.py
and preview_kindle.py use this so an OPF file does not have to live at
OEBPS/content.opf.
"""
import posixpath
import re
import zipfile


def norm_zip(path):
    """Return a normalized zip path, or None if it escapes the archive."""
    parts = []
    for part in str(path).replace("\\", "/").split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if not parts:
                return None
            parts.pop()
            continue
        parts.append(part)
    return "/".join(parts)


def package_opf_path(zf):
    """Return the package path declared by META-INF/container.xml."""
    if not isinstance(zf, zipfile.ZipFile):
        raise TypeError("package_opf_path expects a ZipFile")
    try:
        raw = zf.read("META-INF/container.xml")
    except KeyError as exc:
        raise ValueError("EPUB has no META-INF/container.xml") from exc
    text = raw.decode("utf-8", errors="replace")
    match = re.search(r"""full-path\s*=\s*['"]([^'"]+)['"]""", text, re.I)
    if not match or not match.group(1).strip():
        raise ValueError("container.xml has no rootfile full-path")
    opf = norm_zip(match.group(1).strip())
    if opf is None:
        raise ValueError("container.xml full-path escapes the EPUB")
    if opf not in zf.namelist():
        raise ValueError("container.xml points to missing package document: %s" % opf)
    return opf


def join_zip(base_dir, href):
    """Join href to the OPF or document directory. None means the path escapes."""
    target = href.split("#", 1)[0]
    if target.startswith(("http://", "https://", "mailto:")):
        return target
    combined = posixpath.join(base_dir, target) if base_dir else target
    return norm_zip(combined)
