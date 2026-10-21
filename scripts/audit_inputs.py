"""Inventory immutable raw inputs and reconcile coverage after collection."""
from collections import Counter
import datetime as dt
import gzip,hashlib,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def read(path):
    with gzip.open(path,'rt') as f:return json.load(f)

def main():
    catalog=json.loads((ROOT/'data/derived/catalog_summary.json').read_text())
    markets=read(ROOT/'data/derived/cfb_two_leg_markets.json.gz')
    required={l['market_ticker'] for m in markets for l in m['mve_selected_legs']}
    coverage={'catalog':catalog,'required_individual_legs':len(required),'sources':{}}
    for directory,key in [('legs','market'),('candles','candlesticks'),('candles_retry','candlesticks'),('rfqs','rfqs'),('polymarket_history','history')]:
        counts=Counter();failures=[]
        for path in (ROOT/'data/raw'/directory).glob('*.json.gz'):
            env=read(path);p=env['payload'];counts['files']+=1
            if 'retrieved_at' not in env:counts['missing_retrieval_timestamp']+=1
            if p.get('http_status'):failures.append({'file':str(path.relative_to(ROOT)),'status':p['http_status']})
            elif not p.get(key):counts['empty_success']+=1
            else:counts['nonempty_success']+=1
        coverage['sources'][directory]={'counts':dict(counts),'failures':failures}
    coverage['missing_leg_files']=sorted(t for t in required if not (ROOT/'data/raw/legs'/f'{t}.json.gz').exists())
    coverage['missing_candle_files']=sorted(t for t in required if not (ROOT/'data/raw/candles'/f'{t}.json.gz').exists())
    mapping=json.loads((ROOT/'data/derived/polymarket_mapping.json').read_text())
    coverage['polymarket_matching']=dict(Counter(mapping.get(t,{}).get('status','missing') for t in required))
    coverage['cfb_shards']=dict(Counter('-'.join(m['event_ticker'].split('-')[:2]) for m in markets))
    (ROOT/'output/input_coverage.json').write_text(json.dumps(coverage,indent=2))
    count=0;size=0
    with (ROOT/'output/raw_input_sha256.jsonl').open('w') as out:
        for path in sorted((ROOT/'data/raw').rglob('*')):
            if not path.is_file() or path.suffix=='.tmp':continue
            count+=1;size+=path.stat().st_size
            with path.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
            out.write(json.dumps({'path':str(path.relative_to(ROOT)),'bytes':path.stat().st_size,'sha256':digest})+'\n')
    print(json.dumps({'raw_files':count,'raw_bytes':size,'missing_markets':len(catalog['missing_tickers']),'coverage':coverage['sources']}))

if __name__=='__main__':main()
