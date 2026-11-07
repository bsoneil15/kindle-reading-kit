"""Structural check for EPUBs built with kindle_epub.py (use when epubcheck/Java is unavailable).
Usage: python3 check_epub.py a.epub [b.epub ...]. Exits 1 on any problem.
Checks: mimetype first, all XHTML/OPF/NCX parse, manifest files exist, every internal href/src and #anchor resolves."""
import zipfile, re, sys
from lxml import etree
bad_any = False
for e in sys.argv[1:]:
    z = zipfile.ZipFile(e); names = z.namelist(); probs = []
    if names[0] != "mimetype": probs.append("mimetype is not first entry")
    opf = z.read("OEBPS/content.opf").decode(); etree.fromstring(opf.encode())
    probs += ["manifest missing " + h for h in re.findall(r'href="([^"]+)"', opf.split("<guide>")[0]) if "OEBPS/" + h not in names]
    xs = [n for n in names if n.endswith((".xhtml", ".ncx"))]; ids = {}
    for n in xs:
        t = z.read(n).decode()
        try: etree.fromstring(t.encode())
        except Exception as ex: probs.append("parse %s: %s" % (n, ex))
        ids[n.split("/")[-1]] = set(re.findall(r'id="([^"]+)"', t))
    for n in xs:
        t = z.read(n).decode(); base = n.split("/")[-1]
        for h in re.findall(r'(?:href|src)="([^"]+)"', t):
            if h.startswith(("http", "mailto")) or h.endswith(".css"): continue
            f, _, a = h.partition("#"); f = f or base
            if f.startswith("img/"):
                if "OEBPS/" + f not in names: probs.append("%s: missing image %s" % (base, h))
            elif f not in ids or (a and a not in ids[f]): probs.append("%s: broken link %s" % (base, h))
    print(e, "OK" if not probs else "%d problems" % len(probs)); [print("  ", p) for p in probs[:30]]
    bad_any |= bool(probs)
sys.exit(1 if bad_any else 0)
