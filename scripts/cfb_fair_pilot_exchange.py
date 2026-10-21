#!/usr/bin/env python3
"""Capture historical exchange candles/prices for the frozen pilot cohort."""
import gzip,json,time,sys
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor,as_completed
import requests
from rate_limit import pace
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'runs/cfb_fair_pilot_20260907'
START=1788152400;END=1788757200


def fetch(job):
 venue,key,url,params=job;path=OUT/venue/(key+'.json.gz')
 if path.exists():return {'venue':venue,'key':key,'cached':True}
 for attempt in range(4):
  if venue.startswith('kalshi'):pace()
  try:r=requests.get(url,params=params,timeout=30)
  except requests.RequestException:
   if attempt==3:return {'venue':venue,'key':key,'error':'transport'}
   continue
  if r.status_code==429 or r.status_code>=500:time.sleep(2**attempt);continue
  record={'url':r.url,'status':r.status_code,'retrieved_at':time.time(),'params':params,'payload':r.json()}
  path.parent.mkdir(parents=True,exist_ok=True)
  with gzip.open(path,'wt') as f:json.dump(record,f,separators=(',',':'))
  return {'venue':venue,'key':key,'status':r.status_code}
 return {'venue':venue,'key':key,'error':'retries_exhausted'}


def main():
 selection=json.load(open(OUT/'selection.json'));mappings=json.load(open(ROOT/'data/derived/polymarket_mapping.json'));jobs=[];tokens=set()
 for item in selection['selected']:
  end=int(datetime.fromisoformat(item['fixture']['startTime'].replace('Z','+00:00')).timestamp())
  for ticker in item['kalshi_tickers']:
   for part,lo in enumerate(range(START,end,3*86400)):
    jobs.append(('kalshi_parts',ticker+'.part'+str(part),'https://external-api.kalshi.com/trade-api/v2/series/'+ticker.split('-')[0]+'/markets/'+ticker+'/candlesticks',{'start_ts':lo,'end_ts':min(lo+3*86400,end),'period_interval':1,'include_latest_before_start':'true'}))
   tokens.add(mappings[ticker]['token'])
 for token in tokens:jobs.append(('polymarket',token,'https://clob.polymarket.com/prices-history',{'market':token,'startTs':START,'endTs':END,'fidelity':1}))
 results=[]
 with ThreadPoolExecutor(max_workers=6) as pool:
  for future in as_completed([pool.submit(fetch,j) for j in jobs]):
   results.append(future.result())
   if len(results)%50==0:print('completed',len(results),'/',len(jobs),flush=True)
 (OUT/'exchange_acquisition.json').write_text(json.dumps(results,indent=2)+'\n')
 print('complete',len(results),'errors',sum(r.get('status',200)!=200 or 'error' in r for r in results))
if __name__=='__main__':main()
