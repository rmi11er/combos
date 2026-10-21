"""Recover public leg candles and historical RFQs for identified CFB combos."""
import concurrent.futures as cf
import datetime as dt
import argparse,gzip,hashlib,json,os,sys,threading,time
from pathlib import Path
import requests
from rate_limit import pace
ROOT=Path(__file__).resolve().parents[1]
BASE='https://external-api.kalshi.com/trade-api/v2'
START=1788584400; END=START+86400
sys.path.insert(0,'../kalshi_mm')
from src.kalshi_v2 import KalshiRequestSigner
SIGNER=KalshiRequestSigner(os.environ['KALSHI_API_KEY_ID'],Path(os.environ['KALSHI_PRIVATE_KEY_PATH']).expanduser().read_text())
LOCAL=threading.local()

def get(url,params=None,auth=False):
    if not hasattr(LOCAL,'session'): LOCAL.session=requests.Session()
    for attempt in range(8):
        pace()
        headers=SIGNER.headers('GET','/trade-api/v2/communications/rfqs') if auth else {}
        try:
            r=LOCAL.session.get(url,params=params,headers=headers,timeout=40)
        except requests.RequestException:
            if attempt==7: raise
            time.sleep(min(15,2**attempt)); continue
        if r.status_code==429 or r.status_code>=500:
            time.sleep(min(15,2**attempt)); continue
        if r.status_code in [400,404]: return {'http_status':r.status_code,'error':r.text[:500]}
        r.raise_for_status(); return r.json()
    return {'http_status':r.status_code,'error':r.text[:500],'retry_exhausted':True,'request_url':r.url}

def store(path,payload,params):
    path.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(path.with_suffix('.tmp'),'wt') as f: json.dump({'retrieved_at':dt.datetime.now(dt.timezone.utc).isoformat(),'params':params,'payload':payload},f,separators=(',',':'))
    path.with_suffix('.tmp').replace(path)

def fetch_leg(ticker):
    meta=ROOT/'data/raw/legs'/f'{ticker}.json.gz'
    if not meta.exists(): store(meta,get(BASE+'/markets/'+ticker),{})
    candles=ROOT/'data/raw/candles'/f'{ticker}.json.gz'
    if not candles.exists():
        params={'start_ts':START-3600,'end_ts':END,'period_interval':1,'include_latest_before_start':'true'}
        store(candles,get(BASE+'/series/'+ticker.split('-')[0]+'/markets/'+ticker+'/candlesticks',params),params)
    return ticker

def fetch_rfq(ticker):
    dest=ROOT/'data/raw/rfqs'/f'{ticker}.json.gz'
    if dest.exists(): return ticker
    params={'market_ticker':ticker,'limit':100}; rows=[]; cursors=set()
    while True:
        payload=get(BASE+'/communications/rfqs',params,True)
        if 'rfqs' not in payload: store(dest,payload,params);return ticker
        rows.extend(payload['rfqs']); cursor=payload.get('cursor')
        if not cursor: break
        if cursor in cursors: raise RuntimeError('RFQ repeated cursor')
        cursors.add(cursor);params['cursor']=cursor
    store(dest,{'rfqs':rows,'complete_for_market':True}, {'market_ticker':ticker,'limit':100})
    return ticker

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--retained-rfqs-only',action='store_true',help='Freeze existing RFQ enrichment; complete all leg inputs.')
    args=parser.parse_args()
    seen_files=set(); markets={};done=set();legs_done=set()
    with cf.ThreadPoolExecutor(max_workers=8) as pool:
        while True:
            for file in (ROOT/'data/raw/metadata').glob('*.json.gz'):
                if file in seen_files: continue
                seen_files.add(file)
                with gzip.open(file,'rt') as f: env=json.load(f)
                for m in env['payload']['markets']:
                    ls=m.get('mve_selected_legs',[])
                    if len(ls)==2 and all(l['event_ticker'].startswith('KXNCAAF') and '-26SEP05' in l['event_ticker'] for l in ls): markets[m['ticker']]=m
            legs=sorted({l['market_ticker'] for m in markets.values() for l in m['mve_selected_legs']}-legs_done)
            for tick in pool.map(fetch_leg,legs): legs_done.add(tick)
            # Bounded creator/RFQ enrichment. The exhaustive public-trade frame
            # is separate; these RFQs cannot measure the full opportunity tape.
            sampled=set(sorted(markets,key=lambda t:hashlib.sha256(t.encode()).digest())[:500])
            if args.retained_rfqs_only:
                done={p.name[:-8] for p in (ROOT/'data/raw/rfqs').glob('*.json.gz')} & set(markets)
            pending=[] if args.retained_rfqs_only else sorted(sampled-done)
            for tick in pool.map(fetch_rfq,pending): done.add(tick)
            (ROOT/'data/derived/input_progress.json').write_text(json.dumps({'markets':len(markets),'legs':len(legs_done),'rfq_markets':len(done)}))
            print('inputs',len(markets),'legs',len(legs_done),'rfq_markets',len(done),flush=True)
            if (ROOT/'data/derived/catalog_summary.json').exists():
                # Rescan once after the completed catalog becomes visible so a
                # final batch arriving during this pass cannot be skipped.
                if len(seen_files)==len(list((ROOT/'data/raw/metadata').glob('*.json.gz'))):
                    (ROOT/'data/derived/input_complete.json').write_text(json.dumps({'markets':len(markets),'legs':len(legs_done),'rfq_markets':len(done)}))
                    (ROOT/'data/derived/rfq_sample_manifest.json').write_text(json.dumps({'sample':'Retained adaptive traded-market enrichment; no inclusion-probability weighting or full RFQ census' if args.retained_rfqs_only else '500 smallest SHA-256 among traded two-leg CFB markets; prior adaptive retrievals preserved separately','tickers':sorted(done),'intended_hash_sample':sorted(sampled),'intended_sample_recovered':len(sampled & done),'universe_markets':len(markets),'enrichment_frozen':args.retained_rfqs_only}))
                    break
            time.sleep(10)
