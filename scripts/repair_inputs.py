"""Retry explicitly failed reads, retaining the original responses."""
import concurrent.futures as cf
import gzip,hashlib,json,datetime as dt
from pathlib import Path
from fetch_inputs import ROOT,BASE,get,store

def repair_candle(file):
    with gzip.open(file,'rt') as f:env=json.load(f)
    if not env['payload'].get('http_status'):return None
    ticker=file.name[:-8];dest=ROOT/'data/raw/candles_retry'/file.name
    params=env['params']
    store(dest,get(BASE+'/series/'+ticker.split('-')[0]+'/markets/'+ticker+'/candlesticks',params),params)
    return ticker

def repair_market(ticker):
    responses=[]
    for prefix in ['/markets/','/historical/markets/']:
        p=get(BASE+prefix+ticker);responses.append(p)
        if 'market' in p:break
    name='recovery_'+hashlib.sha256(ticker.encode()).hexdigest()[:24]+'.json.gz'
    dest=ROOT/'data/raw/metadata'/name
    if dest.exists():return
    with gzip.open(dest,'wt') as f:json.dump({'requested':[ticker],'retrieved_at':dt.datetime.now(dt.timezone.utc).isoformat(),'payload':{'markets':[p['market']] if 'market' in p else []},'recovery_responses':responses},f,separators=(',',':'))
    return 'market' in p

if __name__=='__main__':
    catalog=json.loads((ROOT/'data/derived/catalog_summary.json').read_text())
    with cf.ThreadPoolExecutor(max_workers=4) as pool:
        mr=list(pool.map(repair_market,catalog['missing_tickers']))
        cr=list(pool.map(repair_candle,(ROOT/'data/raw/candles').glob('*.json.gz')))
    print('retried missing markets',len(mr),'recovered',sum(bool(x) for x in mr),'failed candles retried',sum(x is not None for x in cr))
