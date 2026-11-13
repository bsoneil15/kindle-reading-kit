"""Build the Editorial Soft review EPUB, contact sheet and six chart assets locally."""
from pathlib import Path
import argparse, html, os, sys
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import kindle_epub as ep
import kindle_charts as kit
from epub_nav import build_nav
from render_charts import build, DATA, SOURCE

def main(out):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    charts=build(out/'charts')
    title='E-ink Chart Default: Editorial Soft'
    meta=dict(title=title,date='2026-11-06',
              desc='Six chart forms with bold black emphasis and soft gray context; all data fictional.')
    ep.CSS+='\n.chart-page .fig {margin:0;} .chart-page .next {margin-top:0.3em;font-size:0.75em;} .chart-page .small {font-size:0.75em;} .compact h1 {margin-bottom:0.4em;} .compact .short {margin-bottom:0.65em;}\n'
    escape=html.escape
    # Library cover image at Amazon's recommended 1600 x 2560. The reading spine opens with native cover text.
    ep.make_cover(str(out/'cover.jpg'),'PAPERWHITE DESIGN REVIEW',['Editorial','Soft'],
                  '6 chart forms. 1 bold black focal series. Thin gray context.','FICTIONAL DATA')
    src_note='<p class="small">'+escape(SOURCE)+'</p>'
    by_file={Path(c['path']).stem:c for c in charts}
    # One chapter per topic. Each chart is a section file (h2) under its chapter (h1).
    chapters=[
        ('trend','Change over time','North pulls away over 12 months.',
         ['4 views show the same 12 months.','North is the black series in each.','South gains only 4.'],
         [('line','Line'),('slope','Slope'),('sparkline-table','Sparkline table'),('small-multiples','Small multiples')]),
        ('size','Size and spread','North leads December and spans the widest range.',
         ['North ends the year at 96.','South ends at 40.','Ranges are observed minima and maxima.'],
         [('ranked-bar','Ranked bar'),('range','Observed range')]),
    ]
    order=['cover','start','contents']
    for cid,_l,_t,_s,secs in chapters: order+=[cid]+[f for f,_ in secs]
    order+=['data','feedback']
    titles={}
    for cid,label,_t,_s,secs in chapters:
        titles[cid]=label
        for f,lab in secs: titles[f]=lab
    titles.update(cover='Cover',start='How this edition works',contents='Contents',data='Data in text',feedback='Feedback')
    def nxt(name):
        i=order.index(name); n=order[i+1] if i+1<len(order) else 'contents'
        return ep.next_link(n+'.xhtml',titles[n])
    bodies={}
    bodies['cover']=('<p class="label">Paperwhite design review</p><h1>Editorial Soft</h1>'
        '<p class="lede">6 chart forms. One unmistakable focal series.</p>'
        '<p>Tufte-soft gray context, editorial guides and a black top rule. '
        '<b>Bold black emphasis stays across every style.</b></p>'
        '<p>All shipment data are fictional. This is a design test, not a business report.</p>'
        +nxt('cover')+src_note,'cover')
    start=ep.chapter_head('How this edition works','1 black series carries the story.',[
        '6 chart forms use the same fictional data.',
        '3 regions share one highlighted series: North.',
        '4 alternative styles remain in the draft skill.'])
    start+='<p class="lede">Read without zooming. Compare the hierarchy, not just the chart form.</p>'
    start+='<p><b>Fast path:</b> <a href="line.xhtml">line</a>, <a href="ranked-bar.xhtml">ranked bar</a>, then <a href="feedback.xhtml">3 questions</a>.</p>'
    start+='<p class="small">Target: 6.8-inch Paperwhite, 300 ppi, portrait. Preview is simulated, not verified on hardware. Page count varies with settings.</p>'
    bodies['start']=('<div class="compact">'+start+nxt('start')+src_note+'</div>','chapter')
    images=[]
    for cid,label,claim,short,secs in chapters:
        h=ep.chapter_head(label,claim,short,[(f+'.xhtml',lab) for f,lab in secs])
        bodies[cid]=('<div class="compact">'+h+nxt(cid)+src_note+'</div>','chapter')
        for f,lab in secs:
            c=by_file[f]; src='img/'+Path(c['path']).name
            images.append((c['path'],src))
            fig=kit.figure_html(c,alt=kit.text_fallback(c))
            body=ep.section_head(lab)+ep.to_xhtml(ep.generic(fig,ep.Notes(f),{src:fig}))
            body+=nxt(f)+'<p class="small">'+escape(SOURCE)+' <a href="data.xhtml">Values in text</a>.</p>'
            bodies[f]=('<div class="chart-page">'+body+'</div>','section')
    import kindle_tables as kt
    data=ep.chapter_head('Data in text','3 regions repeat the same 12 months.',[
        'North rises from 52 to 96 thousand shipments.',
        'Central rises from 48 to 64 thousand shipments.',
        'South rises from 36 to 40 thousand shipments.'],
        [('jan-dec','January and December'),('all-months','All 12 months')])
    data+='<p class="lede">The full fictional input is retained for checking every form.</p>'
    data+='<p class="small">Months: '+', '.join(DATA['months'])+'. Units: thousand shipments, 2025.</p>'
    rows=[{'Region':k,'Jan':v[0],'Dec':v[-1]} for k,v in DATA['series'].items()]
    data+='<h2 id="jan-dec">January and December</h2><p class="small kt-lead">Thousand shipments.</p>'
    data+=kt.text_table_html(['Region','Jan','Dec'],rows,focal='North',sort_by='Dec')
    data+='<h2 id="all-months">All 12 months</h2>'
    for region,values in DATA['series'].items():
        data+='<div class="rec"><p class="rec-h">'+escape(region)+'</p><p>'+', '.join(map(str,values))+'.</p></div>'
    data+=nxt('data')+'<p class="small">'+escape(SOURCE)+' Ranges show observed monthly minima and maxima, not uncertainty intervals.</p>'
    bodies['data']=('<div class="compact">'+data+'</div>','chapter')
    feedback=ep.chapter_head('Feedback','3 answers will refine the default.',[
        '1 bold black series stays in every option.',
        '4 alternative styles remain available.',
        '0 files have been published by this build.'])
    feedback+='<ol><li><b>Emphasis:</b> Does the black North series stand out enough without feeling heavy?</li>'
    feedback+='<li><b>Softness:</b> Are gray context and light guides visible at normal size, or too faint?</li>'
    feedback+='<li><b>Forms:</b> Which of the 6 chart types feels most useful, and which needs work?</li></ol>'
    feedback+='<p class="small">The draft also keeps Tufte Minimal, Bold Highlight, Pattern &amp; Texture, and Economist-style Editorial.</p>'
    feedback+=ep.next_link('contents.xhtml','Contents')+src_note
    bodies['feedback']=('<div class="compact">'+feedback+'</div>','chapter')
    def doc(name,body,kind): return (name+'.xhtml',titles[name],ep.page(titles[name],body,kind))
    bodies['contents']=('','toc')
    docs=[doc(n,*bodies[n]) for n in order]
    nav=build_nav(docs)
    docs[order.index('contents')]=doc('contents','<div class="compact">'+ep.contents_html(nav)+nxt('contents')+src_note+'</div>','toc')
    ep.write_epub(str(out/'E-ink-Chart-Default-Sample.epub'),meta,docs,images,str(out/'cover.jpg'))
    names=['Line','Ranked bar','Slope','Sparkline table','Small multiples','Observed range']
    tilew,tileh,header=680,775,55
    sheet=Image.new('RGB',(2*tilew,3*tileh),'white');dr=ImageDraw.Draw(sheet)
    for i,(c,label) in enumerate(zip(charts,names)):
        x=(i%2)*tilew;y=(i//2)*tileh
        dr.text((x+14,y+12),f'{i+1} · {label}',font=ImageFont.truetype('DejaVuSans-Bold.ttf',25),fill=0)
        chart=Image.open(c['path']).convert('RGB');chart.thumbnail((tilew-28,tileh-header-15))
        sheet.paste(chart,(x+14,y+header))
    sheet.save(out/'contact-default.png')
    print(f'Built {len(docs)} spine documents in {len(nav)} chapters; 6 chart PNGs passed check_png; contact-default.png')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=ROOT/'output/sample')
    main(parser.parse_args().out)
