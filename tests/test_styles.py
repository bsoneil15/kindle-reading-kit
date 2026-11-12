"""Portable regression checks: all 5 styles × 6 forms and context restoration."""
from pathlib import Path
import json, sys, tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT/'examples'))
import kindle_charts as kit
from eink_style import STYLES,style,sparkline_table
from render_charts import build,DATA
from PIL import Image

def guide_bands(path):
    """Thick horizontal bands of guide tone 221. A 1.5 pt guide is several rows.

    Single antialiased rows are ignored, so a chart with guides off stays at zero.
    """
    image = Image.open(path).convert('L')
    width, height = image.size
    raw = image.tobytes()
    heavy = []
    for y in range(height):
        row = raw[y * width:(y + 1) * width]
        if row.count(221) >= width * 0.45:
            heavy.append(y)
    bands = 0
    start = prev = None
    for y in heavy:
        if prev is None or y != prev + 1:
            if start is not None and prev - start + 1 >= 3:
                bands += 1
            start = y
        prev = y
    if start is not None and prev - start + 1 >= 3:
        bands += 1
    return bands

def main():
    original=kit.finish; width=kit.LW_HI
    with tempfile.TemporaryDirectory() as temp:
        for key in STYLES:
            charts=build(Path(temp)/key,key)
            assert len(charts)==6
            assert kit.finish is original and kit.LW_HI==width
            for chart in charts:
                assert not kit.check_png(chart['path'])
                assert 'Fictional' in chart['source']
                assert 'North' in kit.text_fallback(chart)
                im=Image.open(chart['path'])
                assert im.getextrema()==(0,255)
                if STYLES[key]['rule']:
                    y=round(im.height*.005)
                    assert im.getpixel((im.width//2,y))==0,'Editorial top rule missing'
            assert charts[0]['data']['series']==DATA['series']
            assert [r[1] for r in charts[1]['data']]==[96,64,40]
            assert charts[5]['data']['rows']==[('North',52,96,None),('Central',48,64,None),('South',35,41,None)]
        try:
            with style('bold-highlight'):
                raise RuntimeError('test context cleanup')
        except RuntimeError:
            pass
        assert kit.finish is original and kit.LW_HI==width
        for bad in ({'North':[1]}, {str(i):[1,2] for i in range(5)}):
            try:
                sparkline_table(['Jan','Dec'],bad,title='Test',sub='Test',
                                name='bad.png',source='Source: Fictional test',highlight='North')
                raise AssertionError('Invalid series accepted')
            except ValueError:
                pass
        kit.OUT = str(Path(temp)/'grid')
        series = {'Focus': [52, 70, 96], 'Context': [48, 55, 64]}
        common = dict(
            x=['Jan', 'Jun', 'Dec'], series=series,
            title='Focus gains 44 in 12 months.',
            sub='Shipments, thousands · 2025',
            source='Source: Fictional example data, 2025.',
            highlight='Focus', ylim=(0, 100))
        with style('tufte-minimal'):
            quiet = kit.line_chart(name='quiet.png', **common)
            forced_on = kit.line_chart(name='forced-on.png', grid=True, **common)
        with style('editorial-soft'):
            guided = kit.line_chart(name='guided.png', **common)
            forced_off = kit.line_chart(name='forced-off.png', grid=False, **common)
        via_kw = kit.line_chart(name='via-style-kw.png', style='tufte-minimal', **common)
        via_on = kit.line_chart(name='via-style-kw-on.png', style='tufte-minimal', grid=True, **common)
        quiet_rows, on_rows = guide_bands(quiet['path']), guide_bands(forced_on['path'])
        guided_rows, off_rows = guide_bands(guided['path']), guide_bands(forced_off['path'])
        assert quiet_rows == 0, quiet_rows
        assert off_rows == 0, off_rows
        assert on_rows >= 3, on_rows
        assert guided_rows >= 3, guided_rows
        assert guide_bands(via_kw['path']) == 0
        assert guide_bands(via_on['path']) >= 3
        assert kit.finish is original and kit.LW_HI == width
    print('PASS: 30 charts, unchanged data, palette/geometry, top rules, input checks, context cleanup')
    print('PASS: line_chart grid follows the active style unless grid= is passed')

if __name__=='__main__': main()
