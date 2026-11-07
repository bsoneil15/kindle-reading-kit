"""Kindle EPUB toolkit: e-ink CSS, per-section tap-to-open source notes, print-HTML -> Kindle-HTML
transform (tables -> stacked records, figures swapped or dropped), EPUB3 + NCX packaging, cover art.

Import from a build script:  sys.path.insert(0, "<skill>/scripts"); from kindle_epub import *
Call set_sources({key: (label, url)}) once if content uses [[key]] citation markers.
"""
import re, html, uuid, zipfile, datetime, sys, os
from bs4 import BeautifulSoup, NavigableString

CSS = """
body { margin: 0; padding: 0; }
a { color: #000; text-decoration: underline; }
p { margin: 0 0 0.55em 0; text-indent: 0; line-height: 1.4; }
.label { font-size: 0.78em; font-weight: bold; letter-spacing: 0.1em; text-transform: uppercase; margin: 0 0 0.15em 0; }
h1 { font-size: 1.45em; line-height: 1.2; margin: 0 0 0.7em 0; page-break-after: avoid; }
h2 { font-size: 1.2em; line-height: 1.25; margin: 1.5em 0 0.45em 0; page-break-after: avoid; }
h3 { font-size: 1.05em; line-height: 1.25; margin: 1.3em 0 0.25em 0; page-break-after: avoid; }
.lede { font-size: 1.05em; margin-bottom: 1em; }
.short { border: 2px solid #000; padding: 0.5em 0.7em 0.2em 0.7em; margin: 0 0 1.1em 0; }
.short-t { font-weight: bold; font-size: 0.85em; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 0.3em; }
.short ul { margin: 0 0 0.3em 1.1em; }
.inthis { font-size: 0.9em; margin: 0 0 1.2em 0; }
.inthis p { margin: 0 0 0.25em 0; }
.rec { margin: 0 0 0.9em 0; padding: 0 0 0 0.55em; border-left: 3px solid #555; page-break-inside: avoid; }
.rec-h { font-weight: bold; margin-bottom: 0.15em; }
.rec p { margin-bottom: 0.2em; }
.k { font-weight: bold; }
.box { border: 1px solid #000; padding: 0.5em 0.7em 0.2em 0.7em; margin: 0.9em 0 1em 0; }
.box h3 { margin-top: 0.1em; }
.ask, .say { border-left: 4px solid #000; padding: 0.1em 0 0.1em 0.6em; margin: 0.4em 0 0.6em 0; }
.say p { margin-bottom: 0.25em; }
.say { font-size: 1.15em; line-height: 1.45; }
.role { font-size: 0.9em; font-weight: bold; margin: 0 0 0.35em 0; }
.note, .cap { font-size: 0.85em; }
.fig { margin: 0.8em 0 0.4em 0; text-align: center; }
.fig img { width: 100%; max-width: 100%; }
ul, ol { margin: 0.2em 0 0.8em 1.2em; padding: 0; }
li { margin: 0 0 0.4em 0; line-height: 1.38; }
sup { font-size: 0.7em; line-height: 0; }
a.nref { text-decoration: none; }
.notes h2 { font-size: 1em; }
.notes p { font-size: 0.8em; margin-bottom: 0.45em; }
.next { margin-top: 1.6em; font-weight: bold; }
.pick { border: 2px solid #000; padding: 0.45em 0.6em 0.1em 0.6em; margin: 0.3em 0 0.7em 0; }
.sess { margin: 0 0 0.6em 0; padding-left: 0.55em; border-left: 3px solid #999; }
.sess p, .pick p { margin-bottom: 0.15em; }
.where { font-size: 0.85em; font-weight: bold; letter-spacing: 0.04em; text-transform: uppercase; }
.small { font-size: 0.85em; }
.tier { font-size: 0.8em; font-weight: bold; letter-spacing: 0.06em; text-transform: uppercase; }
.cover { text-align: center; margin: 0; padding: 0; }
.cover img { width: 100%; }
"""

SRC = {}
def set_sources(d):
    SRC.clear(); SRC.update(d)

class Notes:
    """Per-chapter source notes: each source gets one number per chapter; repeats reuse it."""
    def __init__(self, cid): self.cid = cid; self.order = []; self.idx = {}; self.refs = {}
    def ref(self, key):
        if key not in SRC: raise SystemExit("missing source " + key)
        if key not in self.idx:
            self.order.append(key); self.idx[key] = len(self.order)
        n = self.idx[key]; occ = self.refs.get(key, 0) + 1; self.refs[key] = occ
        rid = "r_%s_%d_%d" % (self.cid, n, occ)
        return '<sup><a class="nref" epub:type="noteref" id="%s" href="#n_%s_%d">%d</a></sup>' % (rid, self.cid, n, n)
    def sub(self, s):
        s = re.sub(r"(\[\[[a-z0-9_]+\]\])(\s*\1)+", r"\1", s)  # collapse adjacent duplicates
        def f(m):
            keys = re.findall(r"\[\[([a-z0-9_]+)\]\]", m.group(0)); seen = []; out = []
            for k in keys:
                if k in seen: continue
                seen.append(k); out.append(self.ref(k))
            return '<sup>,</sup>'.join(out)
        return re.sub(r"(?:\[\[[a-z0-9_]+\]\])+", f, s)
    def html(self):
        if not self.order: return ""
        h = '<section class="notes" epub:type="endnotes"><h2>Sources for this section</h2>'
        for k in self.order:
            n = self.idx[k]; lab, url = SRC[k]
            h += ('<aside epub:type="footnote" id="n_%s_%d"><p><a href="#r_%s_%d_1">%d.</a> %s. <a href="%s">%s</a></p></aside>'
                  % (self.cid, n, self.cid, n, n, html.escape(lab), html.escape(url), html.escape(url)))
        return h + "</section>"

def slug(t): return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:40]

def tables_to_records(soup):
    for t in soup.find_all("table"):
        rows = t.find_all("tr")
        if not rows: t.decompose(); continue
        head = [c.get_text(" ", strip=True) for c in rows[0].find_all("th")]
        body = rows[1:] if head else rows
        out = soup.new_tag("div")
        for r in body:
            cells = r.find_all(["td", "th"])
            if len(cells) == 1:  # section break row
                p = soup.new_tag("h3"); p.append(BeautifulSoup(cells[0].decode_contents(), "html.parser")); out.append(p); continue
            rec = soup.new_tag("div", attrs={"class": "rec"})
            h = soup.new_tag("p", attrs={"class": "rec-h"}); h.append(BeautifulSoup(cells[0].decode_contents(), "html.parser")); rec.append(h)
            for i, c in enumerate(cells[1:], start=1):
                inner = c.decode_contents().strip()
                if not inner: continue
                p = soup.new_tag("p")
                if head and len(cells) > 2 and i < len(head):
                    lab = soup.new_tag("span", attrs={"class": "k"}); lab.string = head[i] + ": "; p.append(lab)
                p.append(BeautifulSoup(inner, "html.parser")); rec.append(p)
            out.append(rec)
        t.replace_with(out)

CAPTION_FIXES = []  # (old, new) pairs: rewrite print captions that mention color, e.g. ("Teal bars are X.", "X names are in bold with black bars.")

def generic(html_in, notes, figmap=None):
    """Transform print HTML into Kindle HTML. figmap: img src -> replacement HTML (or None to drop)."""
    s = notes.sub(html_in)
    soup = BeautifulSoup(s, "html.parser")
    for el in soup.find_all(style=True): del el["style"]
    for f in soup.find_all("div", class_="fig"):
        img = f.find("img"); src = img["src"] if img else ""
        cap = f.find("p", class_="cap")
        rep = (figmap or {}).get(src, "DROP")
        if rep == "DROP": f.decompose(); continue
        new = BeautifulSoup(rep, "html.parser")
        if cap:
            cap["class"] = "cap"
            capt = cap.decode_contents()
            for a, b in CAPTION_FIXES: capt = capt.replace(a, b)
            new.append(BeautifulSoup('<p class="cap">%s</p>' % capt, "html.parser"))
        f.replace_with(new)
    for kn in soup.find_all("div", class_="keynums"):
        ul = soup.new_tag("ul")
        for k in kn.find_all("div", class_="kn"):
            n = k.find(class_="kn-n").get_text(strip=True); l = k.find(class_="kn-l").decode_contents()
            ul.append(BeautifulSoup("<li><b>%s</b>: %s</li>" % (n, l), "html.parser"))
        kn.replace_with(ul)
    for c in soup.find_all("div", class_="callout"): c["class"] = "box"
    for c in soup.find_all("div", class_="card"):
        hdr = c.find("div", class_="card-h")
        if hdr:
            n = hdr.find(class_="card-n"); t = hdr.find(class_="card-t")
            h3 = BeautifulSoup('<h3 id="%s">%s</h3>%s' % ("c-" + slug(n.get_text()), n.decode_contents(),
                 ('<p class="role">%s</p>' % t.decode_contents()) if t else ""), "html.parser")
            hdr.replace_with(h3)
        c.name = "section"; c["class"] = "card"
    for p in soup.find_all("p", class_="ask"):
        if p.get_text(strip=True).startswith("Ask"): p["class"] = "ask"
    tables_to_records(soup)
    for ol in soup.find_all(["ol", "ul"]):
        if ol.get("class"): del ol["class"]
    return soup

def add_h2_ids(soup):
    items = []
    for h in soup.find_all("h2"):
        i = h.get("id") or "h-" + slug(h.get_text()); h["id"] = i; items.append((i, h.get_text(" ", strip=True)))
    return items

def page(title, body):
    return ('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n<html xmlns="http://www.w3.org/1999/xhtml" '
            'xmlns:epub="http://www.idpf.org/2007/ops" lang="en" xml:lang="en"><head><meta charset="utf-8"/>'
            '<title>%s</title><link rel="stylesheet" type="text/css" href="style.css"/></head><body>%s</body></html>'
            % (html.escape(title), body))

def to_xhtml(soup_or_str):
    s = soup_or_str.decode(formatter="minimal") if hasattr(soup_or_str, "decode") else soup_or_str
    for t in ["br", "img", "hr", "meta", "link"]:
        s = re.sub(r"<%s(\s[^>]*?)?\s*/?>" % t, lambda m: "<%s%s/>" % (t, (m.group(1) or "").rstrip()), s)
    s = s.replace("&nbsp;", "&#160;")
    return s

def write_epub(path, meta, docs, images, cover_img, nav):
    """meta: title, date (YYYY-MM-DD), desc, optional author/lang. docs: ordered (fname, title, xhtml);
    docs[0] must be cover.xhtml, docs[1] is the start page. Add contents.xhtml for a visible TOC.
    images: (local_path, "img/name.png"). nav: (title, href, [children]) recursive."""
    from lxml import etree
    for fn, t, x in docs:
        try: etree.fromstring(x.encode("utf-8"))
        except Exception as e: raise SystemExit("XHTML error in %s: %s" % (fn, e))
    uid = "urn:uuid:" + str(uuid.uuid5(uuid.NAMESPACE_URL, meta["title"]))
    mod = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    def navol(items):
        h = "<ol>"
        for t, href, ch in items:
            h += '<li><a href="%s">%s</a>%s</li>' % (href, html.escape(t), navol(ch) if ch else "")
        return h + "</ol>"
    first_body = docs[1][0]
    tocref = "contents.xhtml" if any(d[0] == "contents.xhtml" for d in docs) else first_body
    navx = page("Contents", '<nav epub:type="toc" id="toc"><h1>Contents</h1>%s</nav>'
                '<nav epub:type="landmarks" hidden="hidden"><ol><li><a epub:type="cover" href="cover.xhtml">Cover</a></li>'
                '<li><a epub:type="toc" href="TOCREF">Contents</a></li>'
                '<li><a epub:type="bodymatter" href="%s">Start</a></li></ol></nav>' % (navol(nav), first_body)).replace("TOCREF", tocref)
    cnt = [0]
    def ncxp(items):
        h = ""
        for t, href, ch in items:
            cnt[0] += 1
            h += '<navPoint id="np%d" playOrder="%d"><navLabel><text>%s</text></navLabel><content src="%s"/>%s</navPoint>' % (cnt[0], cnt[0], html.escape(t), href, ncxp(ch) if ch else "")
        return h
    ncx = ('<?xml version="1.0" encoding="utf-8"?><ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">'
           '<head><meta name="dtb:uid" content="%s"/><meta name="dtb:depth" content="2"/></head><docTitle><text>%s</text></docTitle>'
           '<navMap>%s</navMap></ncx>' % (uid, html.escape(meta["title"]), ncxp(nav)))
    man = ['<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
           '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
           '<item id="css" href="style.css" media-type="text/css"/>',
           '<item id="cover-img" href="img/cover.jpg" media-type="image/jpeg" properties="cover-image"/>']
    spine = []
    for i, (fn, t, x) in enumerate(docs):
        man.append('<item id="d%d" href="%s" media-type="application/xhtml+xml"/>' % (i, fn))
        spine.append('<itemref idref="d%d"%s/>' % (i, ' linear="yes"'))
    for i, (src, arc) in enumerate(images):
        man.append('<item id="im%d" href="%s" media-type="image/png"/>' % (i, arc))
    opf = ('<?xml version="1.0" encoding="utf-8"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid" xml:lang="en">'
           '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="uid">%s</dc:identifier><dc:title>%s</dc:title>'
           '<dc:creator>%s</dc:creator><dc:language>%s</dc:language><dc:date>%s</dc:date><dc:description>%s</dc:description>'
           '<meta property="dcterms:modified">%s</meta><meta name="cover" content="cover-img"/></metadata>'
           '<manifest>%s</manifest><spine toc="ncx">%s</spine>'
           '<guide><reference type="cover" title="Cover" href="cover.xhtml"/><reference type="toc" title="Contents" href="TOCREF"/>'
           '<reference type="text" title="Start" href="%s"/></guide></package>'
           % (uid, html.escape(meta["title"]), html.escape(meta.get("author", "E-ink Chart Lab")), meta.get("lang", "en"), meta["date"], html.escape(meta["desc"]), mod, "".join(man), "".join(spine), first_body)).replace("TOCREF", tocref)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>', compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/content.opf", opf, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/nav.xhtml", navx, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/toc.ncx", ncx, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/style.css", CSS, compress_type=zipfile.ZIP_DEFLATED)
        z.write(cover_img, "OEBPS/img/cover.jpg", compress_type=zipfile.ZIP_STORED)
        for src, arc in images: z.write(src, "OEBPS/" + arc, compress_type=zipfile.ZIP_DEFLATED)
        for fn, t, x in docs: z.writestr("OEBPS/" + fn, x, compress_type=zipfile.ZIP_DEFLATED)

def cover_doc(title):
    return page(title, '<div class="cover"><img src="img/cover.jpg" alt="%s"/></div>' % html.escape(title))

def make_cover(path, kicker, title_lines, sub, foot, band="#000000", rule="#555555"):
    """1600x2560 JPEG. title_lines: 2-3 short lines (about 14 chars each at this size)."""
    from PIL import Image, ImageDraw, ImageFont
    W, H = 1600, 2560
    im = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(im)
    L = "/usr/share/fonts/truetype/sand-box/google/Lato/"  # swap for any TTF family if Lato is absent
    fb = ImageFont.truetype(L + "Lato-Black.ttf", 150); fk = ImageFont.truetype(L + "Lato-Bold.ttf", 52)
    fs = ImageFont.truetype(L + "Lato-Regular.ttf", 64); ff = ImageFont.truetype(L + "Lato-Bold.ttf", 54)
    d.rectangle([0, 0, W, 900], fill=band)
    d.text((120, 260), kicker, font=fk, fill="white")
    y = 1020
    for ln in title_lines:
        d.text((120, y), ln, font=fb, fill="#111111"); y += 180
    y += 50; d.rectangle([120, y, 300, y + 14], fill=rule); y += 70
    import textwrap
    for ln in textwrap.wrap(sub, 38):
        d.text((120, y), ln, font=fs, fill="#222222"); y += 88
    d.text((120, H - 240), foot, font=ff, fill=band)
    im.save(path, "JPEG", quality=90)


def chapter_head(label, title, short=None, sections=None, short_title="The short version"):
    """Standard chapter opener: kicker label, h1, 3-bullet summary box, in-chapter jump links."""
    h = '<p class="label">%s</p>' % html.escape(label) if label else ""
    h += "<h1>%s</h1>" % html.escape(title)
    if short:
        h += '<div class="short"><p class="short-t">%s</p><ul>%s</ul></div>' % (html.escape(short_title), "".join("<li>%s</li>" % html.escape(x) for x in short))
    if sections and len(sections) >= 2:
        h += '<div class="inthis"><p><b>In this chapter</b></p>%s</div>' % "".join('<p><a href="#%s">%s</a></p>' % (a, html.escape(t)) for a, t in sections)
    return h

def next_link(href, title): return '<p class="next"><a href="%s">Next: %s</a></p>' % (href, html.escape(title))
