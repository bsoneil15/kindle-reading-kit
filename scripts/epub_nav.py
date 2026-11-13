"""Navigation for kit EPUBs: build a two-level contents tree from headings, and lint it.

Kindle reads the EPUB 3 toc nav (or the NCX) for the Go To menu and for the
chapter part of its progress display, and supports two levels of nesting.

Heading rules the builder follows:
  * Each spine document after the cover is a chapter (it has an h1) or a section
    (its first heading is an h2). The cover (first document) and the visible
    contents page are left out of the menu.
  * A chapter is a top-level entry pointing at the file. Every h2 inside a chapter
    file is a child entry pointing at file#id, so those h2 need an id.
  * A section file is a child of the chapter before it, pointing at the file.
    Further h2 in a section file become siblings at the same level.
  * The label is the heading text. When the heading holds <span class="label">,
    the label is that span's text (the short chapter name shown above the title).
  * h3 and deeper never reach the menu (two levels at most).

Needs lxml.
"""
import posixpath
import re

XHTML = "http://www.w3.org/1999/xhtml"
OPS = "http://www.idpf.org/2007/ops"
MAX_DEPTH = 2
SKIP_FILES = ("contents.xhtml", "toc.xhtml")


def _etree():
    from lxml import etree
    return etree


def norm(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _local(el):
    return el.tag.split("}")[-1] if isinstance(el.tag, str) else ""


def heading_label(el):
    """Short name for a heading element: its span.label text if present, else its full text."""
    for sub in el.iter():
        if _local(sub) == "span" and "label" in (sub.get("class") or "").split():
            return norm("".join(sub.itertext()))
    return norm("".join(el.itertext()))


def heading_names(el):
    """Every label a menu entry may use for this heading: the short name and the full text."""
    return {heading_label(el), norm("".join(el.itertext()))}


def _in_notes(el):
    """True inside endnotes or a notes block; those headings stay out of the menu."""
    p = el.getparent()
    while p is not None:
        kind = (p.get("{%s}type" % OPS) or "").split()
        if "endnotes" in kind or "footnotes" in kind or "notes" in (p.get("class") or "").split():
            return True
        p = p.getparent()
    return False


def doc_headings(xhtml):
    """[(level, id, label, element)] for h1 and h2 in document order, outside notes blocks."""
    etree = _etree()
    root = etree.fromstring(xhtml.encode("utf-8") if isinstance(xhtml, str) else xhtml)
    out = []
    for el in root.iter():
        name = _local(el)
        if name in ("h1", "h2") and not _in_notes(el):
            out.append((int(name[1]), el.get("id"), heading_label(el), el))
    return out


def build_nav(docs, skip=SKIP_FILES):
    """docs: ordered (fname, title, xhtml). Returns [(label, href, children)] two levels deep."""
    tree = []
    for i, (fname, _title, xhtml) in enumerate(docs):
        if i == 0 or fname in skip:
            continue
        heads = doc_headings(xhtml)
        if not heads:
            raise ValueError("%s has no h1 or h2, so it cannot appear in the contents. "
                             "Give it a visible heading." % fname)
        first = heads[0]
        if first[0] == 1:
            chapter = (first[2], fname, [])
            tree.append(chapter)
            for level, hid, label, _el in heads[1:]:
                if level == 1:
                    raise ValueError("%s has more than one h1; split it into one file per chapter" % fname)
                if not hid:
                    raise ValueError("an h2 in %s has no id (%r); run add_h2_ids or set one" % (fname, label))
                chapter[2].append((label, "%s#%s" % (fname, hid), []))
        else:
            if not tree:
                raise ValueError("%s starts with an h2 but no chapter (h1) comes before it" % fname)
            parent = tree[-1][2]
            parent.append((first[2], fname, []))
            for level, hid, label, _el in heads[1:]:
                if level == 1:
                    raise ValueError("%s mixes a section h2 with a later h1; split the file" % fname)
                if not hid:
                    raise ValueError("an h2 in %s has no id (%r); run add_h2_ids or set one" % (fname, label))
                parent.append((label, "%s#%s" % (fname, hid), []))
    if not tree:
        raise ValueError("no chapters found for the contents")
    return tree


def nav_depth(items):
    return 0 if not items else 1 + max(nav_depth(ch) for _l, _h, ch in items)


def flatten(items, depth=1):
    for label, href, ch in items:
        yield depth, label, href
        yield from flatten(ch, depth + 1)


# ------------------------------------------------------------------ lint
def _parse_nav_ol(ol, depth=1):
    out = []
    for li in ol:
        if _local(li) != "li":
            continue
        a = next((c for c in li if _local(c) in ("a", "span")), None)
        label = norm("".join(a.itertext())) if a is not None else ""
        href = a.get("href") if a is not None else None
        out.append((depth, label, href))
        for c in li:
            if _local(c) == "ol":
                out.extend(_parse_nav_ol(c, depth + 1))
    return out


def _parse_ncx(points, depth=1):
    out = []
    for p in points:
        if _local(p) != "navPoint":
            continue
        label = norm("".join(next((c for c in p.iter() if _local(c) == "text"), p).itertext()))
        content = next((c for c in p if _local(c) == "content"), None)
        out.append((depth, label, content.get("src") if content is not None else None))
        out.extend(_parse_ncx(list(p), depth + 1))
    return out


def lint_nav(zf, opf_path, join_zip):
    """Problems with the toc nav and NCX in an open EPUB zip (empty list = OK)."""
    etree = _etree()
    probs = []
    opf_dir = posixpath.dirname(opf_path)
    opf = etree.fromstring(zf.read(opf_path))
    items = {}
    nav_href = ncx_href = None
    for it in opf.iter():
        if _local(it) == "item":
            items[it.get("id")] = it.get("href")
            if "nav" in (it.get("properties") or "").split():
                nav_href = it.get("href")
            if it.get("media-type") == "application/x-dtbncx+xml":
                ncx_href = it.get("href")
    spine = [items.get(r.get("idref")) for r in opf.iter() if _local(r) == "itemref"]
    if nav_href is None:
        return probs  # EPUB 2 style book; nothing to compare
    nav_path = join_zip(opf_dir, nav_href)
    nav_dir = posixpath.dirname(nav_path)
    nav = etree.fromstring(zf.read(nav_path))
    toc = landmarks = None
    for el in nav.iter():
        if _local(el) == "nav":
            kind = el.get("{%s}type" % OPS) or ""
            if "toc" in kind.split() and toc is None:
                toc = el
            if "landmarks" in kind.split():
                landmarks = el
    if toc is None:
        return ["nav: no toc nav element"]
    ol = next((c for c in toc if _local(c) == "ol"), None)
    entries = _parse_nav_ol(ol) if ol is not None else []
    if not entries:
        return ["nav: toc is empty"]
    depth = max(d for d, _l, _h in entries)
    if depth > MAX_DEPTH:
        probs.append("nav: %d levels deep; Kindle supports %d" % (depth, MAX_DEPTH))
    skip = set()
    if landmarks is not None:
        for a in landmarks.iter():
            if _local(a) == "a" and set((a.get("{%s}type" % OPS) or "").split()) & {"cover", "toc"}:
                skip.add(join_zip(nav_dir, a.get("href", "").partition("#")[0]))
    spine_paths = [join_zip(opf_dir, h) for h in spine if h]
    if spine_paths:
        skip.add(spine_paths[0])  # the cover page
    order = {p: i for i, p in enumerate(spine_paths)}
    seen = set()
    last = (-1, -1)
    docs_cache = {}
    in_nav = set()
    for d, label, href in entries:
        if not href:
            probs.append("nav: entry %r has no link" % label); continue
        file_part, _, anchor = href.partition("#")
        target = join_zip(nav_dir, file_part)
        key = (target, anchor)
        if key in seen:
            probs.append("nav: duplicate entry for %s" % href)
        seen.add(key)
        if target in skip:
            probs.append("nav: %s points at the cover or contents page; landmarks cover that" % href)
        if target not in order:
            probs.append("nav: %s is not in the spine" % href); continue
        in_nav.add(target)
        if target not in docs_cache:
            try:
                docs_cache[target] = etree.fromstring(zf.read(target))
            except Exception as exc:  # parse errors are reported elsewhere
                docs_cache[target] = None
        root = docs_cache[target]
        if root is None:
            continue
        els = list(root.iter())
        if anchor:
            hit = [i for i, e in enumerate(els) if e.get("id") == anchor]
            if not hit:
                probs.append("nav: %s anchor is missing" % href); continue
            pos, el = hit[0], els[hit[0]]
        else:
            heads = [(i, e) for i, e in enumerate(els) if _local(e) in ("h1", "h2")]
            if not heads:
                probs.append("nav: %s has no h1 or h2 to match %r" % (file_part, label)); continue
            pos, el = heads[0]
        if _local(el) not in ("h1", "h2", "h3", "h4", "h5", "h6"):
            probs.append("nav: %s points at a %s, not a heading" % (href, _local(el)))
        elif label not in heading_names(el):
            probs.append("nav: label %r does not match the heading %r in %s" % (label, heading_label(el), file_part))
        here = (order[target], pos)
        if here < last:
            probs.append("nav: %s is out of reading order" % href)
        last = max(last, here)
    for p in spine_paths:
        if p in skip or p in in_nav:
            continue
        probs.append("nav: spine document %s has no contents entry" % posixpath.basename(p))
    if ncx_href:
        ncx = etree.fromstring(zf.read(join_zip(opf_dir, ncx_href)))
        nav_map = next((e for e in ncx.iter() if _local(e) == "navMap"), None)
        ncx_entries = _parse_ncx(list(nav_map)) if nav_map is not None else []
        ncx_dir = posixpath.dirname(join_zip(opf_dir, ncx_href))
        a = [(d, l, join_zip(nav_dir, h or "")) for d, l, h in entries]
        b = [(d, l, join_zip(ncx_dir, h or "")) for d, l, h in ncx_entries]
        if a != b:
            probs.append("ncx: entries differ from the toc nav")
        declared = next((m.get("content") for m in ncx.iter()
                         if _local(m) == "meta" and m.get("name") == "dtb:depth"), None)
        real = max([d for d, _l, _h in ncx_entries] or [0])
        if declared is not None and str(real) != declared:
            probs.append("ncx: dtb:depth says %s but the entries are %d deep" % (declared, real))
    return probs
