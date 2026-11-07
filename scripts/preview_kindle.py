"""Render an EPUB at Kindle Paperwhite page size (1236x1648 px equivalent) and build contact sheets.
Usage: python3 preview_kindle.py book.epub outdir   ->  outdir/all.pdf, outdir/sheet_NN.png (12 pages each)
Read every sheet before shipping. Kindle reflows differently; this catches overflow, bad breaks, unreadable charts."""
import zipfile, sys, re, os, shutil, glob, subprocess
from weasyprint import HTML, CSS
from pypdf import PdfWriter
from PIL import Image
epub, outdir = sys.argv[1], sys.argv[2]
shutil.rmtree(outdir, ignore_errors=True); os.makedirs(outdir)
tmp = outdir + "/x"; zipfile.ZipFile(epub).extractall(tmp)
opf = open(tmp + "/OEBPS/content.opf").read()
ids = dict(re.findall(r'<item id="([^"]+)" href="([^"]+)"', opf))
spine = [ids[i] for i in re.findall(r'<itemref idref="([^"]+)"', opf)]
kcss = CSS(string="@page { size: 4.12in 5.49in; margin: 0.22in 0.25in 0.3in 0.25in; @bottom-center { content: counter(page); font-size: 7pt; } } "
                  "html { font-family: 'Bitstream Charter', 'DejaVu Serif', serif; font-size: 9.5pt; text-align: justify; } img { max-height: 4.8in; }")
w = PdfWriter()
for f in spine:
    p = "%s/OEBPS/%s" % (tmp, f); out = "%s/%s.pdf" % (outdir, os.path.basename(f).replace(".xhtml", ""))
    HTML(filename=p, base_url=os.path.dirname(p) + "/").write_pdf(out, stylesheets=[kcss]); w.append(out)
w.write(outdir + "/all.pdf")
subprocess.run(["pdftoppm", "-r", "110", "-png", outdir + "/all.pdf", outdir + "/p"], check=True)
fs = sorted(glob.glob(outdir + "/p-*.png"))
for k in range(0, len(fs), 12):
    ims = [Image.open(f) for f in fs[k:k + 12]]; wd, ht = ims[0].size
    s = Image.new("RGB", (wd * 6, ht * 2), "white")
    for i, im in enumerate(ims): s.paste(im, ((i % 6) * wd, (i // 6) * ht))
    s.save("%s/sheet_%02d.png" % (outdir, k // 12))
print("pages", len(fs), "sheets", (len(fs) + 11) // 12)
