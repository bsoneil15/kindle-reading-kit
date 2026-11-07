"""Render the same fictional dataset in six forms; no network calls."""
from pathlib import Path
import argparse, json, sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import kindle_charts as kit
from eink_style import style, STYLES, sparkline_table, small_multiples

DATA = json.loads((ROOT/'examples/data.json').read_text())
SOURCE = 'Source: Fictional example data, 2025.'

def build(out, option='editorial-soft'):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    kit.OUT = str(out)
    series, months = DATA['series'], DATA['months']
    common = dict(source=SOURCE, highlight='North')
    charts = []
    with style(option) as config:
        charts.append(kit.line_chart(months,series,
            title='North rises from 52 to 96.', sub='Monthly shipments, thousands · 2025',
            name='line.png',xticks=[0,5,11],ylim=(0,100),grid=config['grid'],**common))
        charts.append(kit.hbar({k:v[-1] for k,v in series.items()},
            title='North leads December at 96.',sub='December shipments, thousands · 2025',
            name='ranked-bar.png',xmax=100,**common))
        charts.append(kit.slope_chart([(k,v[0],v[-1]) for k,v in series.items()],
            title='North gains 44 in 12 months.',sub='Shipments, thousands · January → December 2025',
            name='slope.png',left_label='January',right_label='December',**common))
        charts.append(sparkline_table(months,series,
            title='North grows in all 11 intervals.',sub='Jan–Dec 2025 · shared 0–100 scale · end values',
            name='sparkline-table.png',**common))
        charts.append(small_multiples(months,series,
            title='North gains 44; South gains 4.',sub='Monthly shipments, thousands · 2025 · same axes',
            name='small-multiples.png',**common))
        charts.append(kit.dot_range([(k,min(v),max(v)) for k,v in series.items()],
            title='North spans 52–96 over the year.',
            sub='Observed monthly min–max, thousands · 2025',name='range.png',**common))
    for c in charts:
        issues=kit.check_png(c['path'])
        if issues: raise ValueError(issues)
    (out/'charts.json').write_text(json.dumps([{**c,'fmt':None} for c in charts],indent=2))
    return charts

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=ROOT/'examples/output')
    parser.add_argument('--style',choices=STYLES,default='editorial-soft')
    args=parser.parse_args()
    print(f'{len(build(args.out,args.style))} chart PNGs passed check_png')
