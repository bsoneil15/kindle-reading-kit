"""Build the Editorial Soft review EPUB, contact sheet and six chart assets locally."""
from pathlib import Path
import argparse, html, os, sys
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import kindle_epub as ep
import kindle_charts as kit
from render_charts import build, DATA, SOURCE

def main(out):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    charts=build(out/'charts')
    title='E-ink Chart Default: Editorial Soft'
    meta=dict(title=title,date='2026-11-06',author='E-ink Chart Lab',
              desc='Six chart forms with bold black emphasis and soft gray context; all data fictional.')
    ep.CSS+='\n.chart-page .fig {margin:0;} .chart-page .next {margin-top:0.3em;font-size:0.75em;} .chart-page .small {font-size:0.75em;} .compact h1 {margin-bottom:0.4em;} .compact .short {margin-bottom:0.65em;}\n'
    escape=html.escape
    # Library cover; the reading spine opens with native, reflowable cover text.
    cover=Image.new('L',(1236,1648),255); d=ImageDraw.Draw(cover)
    font=ImageFont.truetype('DejaVuSans.ttf',48)
    bold=ImageFont.truetype('DejaVuSans-Bold.ttf',76)
    d.rectangle((65,80,1170,86),fill=0)
    for y,line in [(230,'Editorial'),(330,'Soft'),(580,'6 chart forms')]:
        d.text((65,y),line,font=bold if y<500 else font,fill=0)
    d.text((65,690),'1 bold black focal series',font=font,fill=0)
    d.text((65,780),'Thin gray context',font=font,fill=85)
    for i,y in enumerate([1090,1240,1390]):
        d.line((85,y,1120,y-130-i*20),fill=[0,85,153][i],width=[14,6,6][i])
    d.text((65,1520),'FICTIONAL DATA · PAPERWHITE',font=ImageFont.truetype('DejaVuSans.ttf',38),fill=85)
    cover.convert('RGB').save(out/'cover.jpg',quality=95)
    docs=[('cover.xhtml','Cover',ep.page(title,
        '<p class="label">Paperwhite design review</p><h1>Editorial Soft</h1>'
        '<p class="lede">6 chart forms. One unmistakable focal series.</p>'
        '<p>Tufte-soft gray context, editorial guides and a black top rule. '
        '<b>Bold black emphasis stays across every style.</b></p>'
        '<p>All shipment data are fictional. This is a design test, not a business report.</p>'
        +ep.next_link('start.xhtml','How this edition works')
        +'<p class="small">Source: Fictional example data, 2025.</p>'))]
    start=ep.chapter_head('How this edition works','1 black series carries the story.',[
        '6 chart forms use the same fictional data.',
        '3 regions share one highlighted series: North.',
        '4 alternative styles remain in the draft skill.'])
    start+='<p class="lede">Read without zooming. Compare the hierarchy, not just the chart form.</p>'
    start+='<p><b>Fast path:</b> <a href="line.xhtml">line</a>, <a href="ranked-bar.xhtml">ranked bar</a>, then <a href="feedback.xhtml">3 questions</a>.</p>'
    start+='<p class="small">Target: 6.8-inch Paperwhite, 300 ppi, portrait. Preview is simulated, not verified on hardware. Page count varies with settings.</p>'
    start+=ep.next_link('contents.xhtml','Contents')+'<p class="small">Source: Fictional example data, 2025.</p>'
    docs.append(('start.xhtml','How this edition works',ep.page('How this edition works','<div class="compact">'+start+'</div>')))
    names=['Line','Ranked bar','Slope','Sparkline table','Small multiples','Observed range']
    files=['line','ranked-bar','slope','sparkline-table','small-multiples','range']
    toc='<p class="label">Contents</p><h1>6 views of one fictional year.</h1>'
    for label,fn in zip(names,files):toc+=f'<p><a href="{fn}.xhtml">{escape(label)}</a></p>'
    toc+='<p><a href="data.xhtml">Data in text</a></p><p><a href="feedback.xhtml">3 feedback questions</a></p>'
    toc+=ep.next_link('line.xhtml',charts[0]['title'])+'<p class="small">Source: Fictional example data, 2025.</p>'
    docs.append(('contents.xhtml','Contents',ep.page('Contents',toc)))
    nav=[('How this edition works','start.xhtml',[]),('Contents','contents.xhtml',[])]
    images=[];figmap={}
    for i,(c,fn,label) in enumerate(zip(charts,files,names)):
        src='img/'+Path(c['path']).name
        images.append((c['path'],src))
        alt=kit.text_fallback(c)
        fig=kit.figure_html(c,alt=alt)
        figmap[src]=fig
        body=ep.to_xhtml(ep.generic(fig,ep.Notes(fn),figmap))
        nxt=files[i+1]+'.xhtml' if i<5 else 'data.xhtml'
        next_title=charts[i+1]['title'] if i<5 else 'Data in text'
        body+=ep.next_link(nxt,next_title)
        body+='<p class="small">'+escape(SOURCE)+' <a href="data.xhtml">Values in text</a>.</p>'
        docs.append((fn+'.xhtml',label,ep.page(c['title'],'<div class="chart-page">'+body+'</div>')))
        nav.append((label,fn+'.xhtml',[]))
    data=ep.chapter_head('Data in text','3 regions repeat the same 12 months.',[
        'North rises from 52 to 96 thousand shipments.',
        'Central rises from 48 to 64 thousand shipments.',
        'South rises from 36 to 40 thousand shipments.'])
    data+='<p class="lede">The full fictional input is retained for checking every form.</p>'
    data+='<p class="small">Months: '+', '.join(DATA['months'])+'. Units: thousand shipments, 2025.</p>'
    for region,values in DATA['series'].items():
        data+='<div class="rec"><p class="rec-h">'+escape(region)+'</p><p>'+', '.join(map(str,values))+'.</p></div>'
    data+=ep.next_link('feedback.xhtml','3 feedback questions')+'<p class="small">'+escape(SOURCE)+' Ranges show observed monthly minima and maxima, not uncertainty intervals.</p>'
    docs.append(('data.xhtml','Data in text',ep.page('Data in text','<div class="compact">'+data+'</div>')))
    nav.append(('Data in text','data.xhtml',[]))
    feedback=ep.chapter_head('Next design decision','3 answers will refine the default.',[
        '1 bold black series stays in every option.',
        '4 alternative styles remain available.',
        '0 files have been published by this build.'])
    feedback+='<ol><li><b>Emphasis:</b> Does the black North series stand out enough without feeling heavy?</li>'
    feedback+='<li><b>Softness:</b> Are gray context and light guides visible at normal size, or too faint?</li>'
    feedback+='<li><b>Forms:</b> Which of the 6 chart types feels most useful, and which needs work?</li></ol>'
    feedback+='<p class="small">The draft also keeps Tufte Minimal, Bold Highlight, Pattern &amp; Texture, and Economist-style Editorial.</p>'
    feedback+=ep.next_link('contents.xhtml','Revisit the charts')+'<p class="small">'+escape(SOURCE)+'</p>'
    docs.append(('feedback.xhtml','3 feedback questions',ep.page('Feedback','<div class="compact">'+feedback+'</div>')))
    nav.append(('3 feedback questions','feedback.xhtml',[]))
    ep.write_epub(str(out/'E-ink-Chart-Default-Sample.epub'),meta,docs,images,str(out/'cover.jpg'),nav)
    tilew,tileh,header=680,775,55
    sheet=Image.new('RGB',(2*tilew,3*tileh),'white');dr=ImageDraw.Draw(sheet)
    for i,(c,label) in enumerate(zip(charts,names)):
        x=(i%2)*tilew;y=(i//2)*tileh
        dr.text((x+14,y+12),f'{i+1} · {label}',font=ImageFont.truetype('DejaVuSans-Bold.ttf',25),fill=0)
        chart=Image.open(c['path']).convert('RGB');chart.thumbnail((tilew-28,tileh-header-15))
        sheet.paste(chart,(x+14,y+header))
    sheet.save(out/'contact-default.png')
    print(f'Built {len(docs)} spine documents; 6 chart PNGs passed check_png; contact-default.png')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=ROOT/'output/sample')
    main(parser.parse_args().out)
