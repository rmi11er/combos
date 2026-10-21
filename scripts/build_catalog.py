"""Build exact combo tape and recover composition for every traded combo."""
import concurrent.futures as cf
from collections import Counter
import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path
import threading
import time
import requests
from rate_limit import pace

ROOT=Path(__file__).resolve().parents[1]
BASE="https://external-api.kalshi.com/trade-api/v2"
START=1788584400
END=START+86400
local=threading.local()

def fetch_batch(tickers):
    name=hashlib.sha256(','.join(tickers).encode()).hexdigest()[:24]
    dest=ROOT/'data/raw/metadata'/f'{name}.json.gz'
    if not dest.exists():
        if not hasattr(local,'session'): local.session=requests.Session()
        for attempt in range(9):
            pace()
            try:
                r=local.session.get(BASE+'/markets',params={'tickers':','.join(tickers),'limit':1000},timeout=40)
            except requests.RequestException:
                if attempt==8: raise
                time.sleep(min(15,2**attempt)); continue
            if r.status_code==429 or r.status_code>=500:
                time.sleep(min(15,2**attempt)); continue
            r.raise_for_status(); break
        else: raise RuntimeError('metadata retries exhausted')
        payload=r.json()
        if payload.get('cursor'): raise RuntimeError('unexpected truncated market batch')
        env={'requested':tickers,'retrieved_at':dt.datetime.now(dt.timezone.utc).isoformat(),'payload':payload}
        with gzip.open(dest.with_suffix('.tmp'),'wt') as f: json.dump(env,f,separators=(',',':'))
        dest.with_suffix('.tmp').replace(dest)
    with gzip.open(dest,'rt') as f: env=json.load(f)
    return env

def ingest(hour):
    out=ROOT/'data/derived/tape'/f'hour_{hour:02d}.json.gz'
    if out.exists():
        with gzip.open(out,'rt') as f: return json.load(f)
    records={}; nraw=0; outside=0; conflicts=0; duplicates=0; byseries=Counter()
    lo=START+hour*3600; hi=lo+3600
    for file in sorted((ROOT/'data/raw/trades'/f'hour_{hour:02d}').glob('page_*.json.gz')):
        with gzip.open(file,'rt') as f: payload=json.load(f)['payload']
        for r in payload['trades']:
            nraw+=1
            t=dt.datetime.fromisoformat(r['created_time'].replace('Z','+00:00')).timestamp()
            if not lo <= t < hi:
                outside+=1; continue
            if not r['ticker'].startswith('KXMVE'): continue
            key=r['trade_id']
            if key in records:
                duplicates+=1
                if records[key]!=r: conflicts+=1
            records[key]=r
    if conflicts: raise RuntimeError('conflicting trade IDs')
    data={'hour':hour,'raw_rows':nraw,'outside_partition':outside,'combo_duplicates':duplicates,'combos':list(records.values())}
    with gzip.open(out,'wt') as f: json.dump(data,f,separators=(',',':'))
    return data

if __name__=='__main__':
    (ROOT/'data/derived/tape').mkdir(parents=True,exist_ok=True)
    (ROOT/'data/raw/metadata').mkdir(parents=True,exist_ok=True)
    complete=set(); covered=set(); markets=set(); traded=set(); cfb_by_ticker={}; total=0
    def accept(m):
        markets.add(m['ticker'])
        ls=m.get('mve_selected_legs',[])
        if len(ls)==2 and all(l['event_ticker'].startswith('KXNCAAF') and '-26SEP05' in l['event_ticker'] for l in ls): cfb_by_ticker[m['ticker']]=m
    for f in (ROOT/'data/raw/metadata').glob('*.json.gz'):
        with gzip.open(f,'rt') as stream: env=json.load(stream)
        covered.update(env['requested'])
        for m in env['payload']['markets']: accept(m)
    with cf.ThreadPoolExecutor(max_workers=8) as pool:
        while len(complete)<24:
            hours=[h for h in range(24) if h not in complete and (ROOT/'data/raw/trades'/f'hour_{h:02d}'/'manifest.json').exists()]
            if not hours: time.sleep(5); continue
            for h in hours:
                tape=ingest(h); total+=len(tape['combos']); complete.add(h)
                traded.update(r['ticker'] for r in tape['combos'])
                tickers=sorted({r['ticker'] for r in tape['combos']}-covered)
                batches=[tickers[i:i+100] for i in range(0,len(tickers),100)]
                for j,env in enumerate(pool.map(fetch_batch,batches)):
                    covered.update(env['requested'])
                    for m in env['payload']['markets']: accept(m)
                    if j%100==0: print(json.dumps({'hour':h,'batch':j,'batches':len(batches),'markets':len(markets)}),flush=True)
                cfb=list(cfb_by_ticker.values())
                with gzip.open(ROOT/'data/derived/cfb_two_leg_markets.json.gz','wt') as f: json.dump(cfb,f,separators=(',',':'))
                print(json.dumps({'hour_done':h,'combo_trades':total,'metadata_markets':len(markets),'cfb_two_leg':len(cfb)}),flush=True)
    missing=sorted(traded-markets)
    summary={'hours':len(complete),'combo_trades':total,'unique_requested_markets':len(traded),'metadata_markets':len(markets & traded),'missing_tickers':missing,'cfb_two_leg_markets':len(cfb)}
    (ROOT/'data/derived/catalog_summary.json').write_text(json.dumps(summary,indent=2))
