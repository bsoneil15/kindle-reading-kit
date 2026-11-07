"""Portable regression checks: all 5 styles × 6 forms and context restoration."""
from pathlib import Path
import json, sys, tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT/'examples'))
import kindle_charts as kit
from eink_style import STYLES,style,sparkline_table
from render_charts import build,DATA
from PIL import Image

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
    print('PASS: 30 charts, unchanged data, palette/geometry, top rules, input checks, context cleanup')

if __name__=='__main__': main()
