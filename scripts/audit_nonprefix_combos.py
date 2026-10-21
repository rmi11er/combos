"""Check prepack/composite series omitted by the legacy KXMVE prefix screen."""
import concurrent.futures as cf
from collections import Counter
import gzip,json
from pathlib import Path
from build_catalog import ROOT,fetch_batch

if __name__=='__main__':
    series=json.load(open(ROOT/'data/raw/probes/kalshi_series.json'))['payload']['series']
    candidates={r['ticker'] for r in series if not r['ticker'].startswith('KXMVE') and any(s in r['title'].lower() for s in ['combo','mve','pre pack','parlay','prepack'])}
    rows={};counts=Counter()
    for folder in sorted((ROOT/'data/raw/trades').glob('hour_*')):
        for file in folder.glob('*.json.gz'):
            with gzip.open(file,'rt') as f:payload=json.load(f)['payload']
            for r in payload['trades']:
                if r['ticker'].split('-')[0] in candidates:rows[r['trade_id']]=r
    with gzip.open(ROOT/'data/derived/nonprefix_composite_trades.json.gz','wt') as f:json.dump(list(rows.values()),f,separators=(',',':'))
    ticks=sorted({r['ticker'] for r in rows.values()})
    with cf.ThreadPoolExecutor(max_workers=2) as pool:
        markets=[m for env in pool.map(fetch_batch,[ticks[i:i+100] for i in range(0,len(ticks),100)]) for m in env['payload']['markets']]
    fields=[{'ticker':m['ticker'],'title':m['title'],'mve_collection_ticker':m.get('mve_collection_ticker'),'legs':m.get('mve_selected_legs')} for m in markets]
    (ROOT/'data/derived/nonprefix_composite_audit.json').write_text(json.dumps({'candidate_series':sorted(candidates),'trades':len(rows),'markets':fields},indent=2))
    print('non-prefix composite trades',len(rows),'markets',len(markets),'with MVE legs',sum(bool(m.get('mve_selected_legs')) for m in markets),flush=True)
