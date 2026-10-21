import concurrent.futures as cf
import datetime as dt
import gzip,json,sys,threading,time
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.combos.matching import event_index,match_market
events=json.load(open(ROOT/'data/raw/probes/polymarket_cfb_slate.json'))
events+=json.load(open(ROOT/'data/raw/probes/polymarket_cfb_slate_100.json'))['payload']
INDEX=event_index(events)
LOCAL=threading.local()

def fetch(match):
    token=match['token'];path=ROOT/'data/raw/polymarket_history'/f'{token}.json.gz'
    if path.exists():return
    if not hasattr(LOCAL,'session'):LOCAL.session=requests.Session()
    params={'market':token,'startTs':1788580800,'endTs':1788670800,'fidelity':1}
    for attempt in range(8):
        r=LOCAL.session.get('https://clob.polymarket.com/prices-history',params=params,timeout=30)
        if r.status_code==429 or r.status_code>=500:time.sleep(min(10,2**attempt));continue
        r.raise_for_status();break
    else:raise RuntimeError('PM retries exhausted')
    path.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(path.with_suffix('.tmp'),'wt') as f:json.dump({'retrieved_at':dt.datetime.now(dt.timezone.utc).isoformat(),'params':params,'payload':r.json()},f,separators=(',',':'))
    path.with_suffix('.tmp').replace(path)

if __name__=='__main__':
    seen=set();mapping={}
    with cf.ThreadPoolExecutor(max_workers=6) as pool:
        while True:
            matches=[]
            for file in (ROOT/'data/raw/legs').glob('*.json.gz'):
                if file in seen:continue
                with gzip.open(file,'rt') as f:m=json.load(f)['payload'].get('market')
                seen.add(file)
                if not m:continue
                match=match_market(m,INDEX);mapping[m['ticker']]=match
                if match['status']=='matched':matches.append(match)
            list(pool.map(fetch,matches))
            (ROOT/'data/derived/polymarket_mapping.json').write_text(json.dumps(mapping,indent=2))
            print('PM mapping',len(mapping),'matched',sum(v['status']=='matched' for v in mapping.values()),flush=True)
            if (ROOT/'data/derived/input_complete.json').exists():break
            time.sleep(15)
