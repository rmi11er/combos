"""Paginated whole-session public tape, parallel nonoverlapping time buckets."""
import gzip,hashlib,json,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import requests
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'runs/shadow_exchange_fallback_20260909/public_session';OUT.mkdir(parents=True,exist_ok=True)
LO=1788988292;HI=1788999600

def bucket(lo,hi):
    cursor='';seen=set();count=0;pages=0
    with requests.Session() as session:
        for page in range(500):
            path=OUT/f'{lo}_{page:04d}.json.gz'
            if path.exists():
                with gzip.open(path,'rt') as f:record=json.load(f)
                data=record['payload']
            else:
                params={'min_ts':lo,'max_ts':hi,'limit':1000}
                if cursor:params['cursor']=cursor
                for attempt in range(6):
                    response=session.get('https://external-api.kalshi.com/trade-api/v2/markets/trades',params=params,timeout=30)
                    if response.status_code in (429,500,502,503,504):time.sleep(min(5,attempt+1));continue
                    response.raise_for_status();break
                else:raise RuntimeError('retries_exhausted')
                data=response.json();record={'url':response.url,'retrieved_at':time.time(),'payload':data}
                with gzip.open(path,'wt') as f:json.dump(record,f)
            count+=len(data['trades']);pages+=1;cursor=data.get('cursor')
            if cursor=='':return dict(lo=lo,hi=hi,complete=True,pages=pages,trades=count)
            if not isinstance(cursor,str) or cursor in seen:raise RuntimeError('invalid_cursor')
            seen.add(cursor)
    return dict(lo=lo,hi=hi,complete=False,pages=pages,trades=count)

jobs=[(t,min(t+300,HI)) for t in range(LO,HI,300)];results=[]
with ThreadPoolExecutor(max_workers=4) as pool:
    futures={pool.submit(bucket,*job):job for job in jobs}
    for future in as_completed(futures):
        try:result=future.result()
        except Exception as e:result=dict(lo=futures[future][0],hi=futures[future][1],complete=False,error=str(e))
        results.append(result);print(len(results),'/',len(jobs),result,flush=True)
        (OUT/'manifest.json').write_text(json.dumps(sorted(results,key=lambda r:r['lo']),indent=2)+'\n')
if not all(r['complete'] for r in results):raise SystemExit('incomplete_public_tape')
