#!/usr/bin/env python3
"""Resumable complete public-tape days, with explicit historical routing.

Default is a zero-network plan. --execute --max-new-requests N acquires at most N
public GET attempts this invocation. An exhausted budget leaves partitions
incomplete; it never promotes first pages to a census. No paid odds calls.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta
import gzip
import hashlib
import json
from pathlib import Path
import threading
import time
from zoneinfo import ZoneInfo
import requests
from rate_limit import pace
ROOT=Path(__file__).resolve().parents[1]
BASE='https://external-api.kalshi.com/trade-api/v2'
DEFAULT_DATES=['2026-07-01','2026-07-15','2026-07-29','2026-08-12','2026-08-26','2026-09-05']

def ts(value):return datetime.fromisoformat(value.replace('Z','+00:00')).timestamp() if isinstance(value,str) else float(value)
def routes(start,end,cutoff):
 if not start<end:raise ValueError('Empty or reversed interval')
 return [(lo,hi,path) for lo,hi,path in ((start,min(end,cutoff),'/historical/trades'),(max(start,cutoff),end,'/markets/trades')) if lo<hi]
def save(path,value):
 tmp=path.with_suffix(path.suffix+'.tmp')
 if path.suffix=='.gz':
  with gzip.open(tmp,'wt') as f:json.dump(value,f,separators=(',',':'))
 else:tmp.write_text(json.dumps(value,indent=2)+'\n')
 tmp.replace(path)
def read(path):
 if path.suffix=='.gz':
  with gzip.open(path,'rt') as f:return json.load(f)
 return json.loads(path.read_text())
class BudgetExhausted(Exception):pass
class Client:
 def __init__(self,root,budget):self.root=root;self.budget=budget;self.count=0;self.lock=threading.Lock()
 def get(self,path,params):
  for retry in range(5):
   with self.lock:
    if self.count>=self.budget:raise BudgetExhausted()
    self.count+=1
    with (self.root/'attempts.jsonl').open('a') as f:f.write(json.dumps({'at':time.time(),'endpoint':path,'params':params})+'\n')
   pace();session=requests.Session();session.trust_env=False
   try:
    response=session.get(BASE+path,params=params,timeout=40,allow_redirects=False)
    env={'request':{'endpoint':path,'params':params},'retrieved_at':time.time(),'http_status':response.status_code,'response_sha256':hashlib.sha256(response.content).hexdigest(),'payload':response.json()}
   except requests.RequestException:env={'request':{'endpoint':path,'params':params},'retrieved_at':time.time(),'http_status':None,'transport_error':'public_transport_failure'}
   finally:session.close()
   if env['http_status']==200:return env
   failure=self.root/'failures';failure.mkdir(exist_ok=True);save(failure/(str(time.time_ns())+'.json.gz'),env)
   if env['http_status'] is not None and env['http_status']<500 and env['http_status']!=429:raise RuntimeError('Public API HTTP '+str(env['http_status']))
   time.sleep(min(8,2**retry))
  raise RuntimeError('Public request retries exhausted')

def collect_partition(client,folder,lo,hi,path):
 folder.mkdir(parents=True,exist_ok=True); manifest=folder/'manifest.json'
 if manifest.exists():
  existing=read(manifest)
  if [existing['start_at'],existing['end_at'],existing['endpoint']] != [lo,hi,path]:raise ValueError('Cached partition route mismatch')
  if existing['complete']:return existing
 cursor='';seen=set();pages=[];total=0;combos=0
 while True:
  params={'min_ts':int(lo)-1,'max_ts':int(hi)+1,'limit':1000}
  if cursor:params['cursor']=cursor
  file=folder/(f'page_{len(pages):05d}.json.gz')
  try:
   if file.exists():env=read(file)
   else:env=client.get(path,params);save(file,env)
  except BudgetExhausted:
   result={'start_at':lo,'end_at':hi,'endpoint':path,'complete':False,'stopped_reason':'invocation_request_budget','pages':pages,'raw_rows':total,'raw_combo_rows':combos,'next_cursor':cursor};save(manifest,result);return result
  if env['request']!={'endpoint':path,'params':params}:raise ValueError('Cached query mismatch')
  payload=env['payload'];rows=payload.get('trades')
  if not isinstance(rows,list):raise ValueError('Invalid trade response')
  total+=len(rows);combos+=sum(r['ticker'].startswith('KXMVE') for r in rows)
  pages.append({'path':file.name,'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'rows':len(rows)})
  cursor=payload.get('cursor') or ''
  if not cursor:break
  if cursor in seen:raise ValueError('Repeated pagination cursor')
  seen.add(cursor)
 result={'start_at':lo,'end_at':hi,'endpoint':path,'complete':True,'pages':pages,'raw_rows':total,'raw_combo_rows':combos,'retention_rule':'Downstream deduplicate trade_id and keep start_at <= created_time < end_at; boundary buffers intentionally overlap'};save(manifest,result);return result

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--dates',nargs='+',default=DEFAULT_DATES);p.add_argument('--out',type=Path,default=ROOT/'runs/mlb_historical_20260907/daily_acquisition');p.add_argument('--execute',action='store_true');p.add_argument('--max-new-requests',type=int,default=0);p.add_argument('--workers',type=int,default=4)
 p.add_argument('--plan-file',default='plan.json',help='Distinct immutable plan filename when expanding cached dates')
 p.add_argument('--date-selection',default='Fixed fortnightly Wednesdays from July 1 plus existing September 5 census; chosen before MLB outcome inspection')
 a=p.parse_args()
 if Path(a.plan_file).name!=a.plan_file or not a.plan_file.endswith('.json'):raise ValueError('Invalid plan filename')
 if not 1<=a.workers<=6 or a.max_new_requests<0:raise ValueError('Invalid workers or budget')
 dates=sorted(set(a.dates));[datetime.strptime(d,'%Y-%m-%d') for d in dates];a.out.mkdir(parents=True,exist_ok=True)
 plan={'dates':dates,'timezone':'America/Chicago','date_selection':'Fixed fortnightly Wednesdays from July 1 plus existing September 5 census; chosen before MLB outcome inspection','target_window':['2026-07-01','2026-09-06'],'not_full_target_window':True,'observed_reference_day_pages':11875,'rough_new_day_cost':'~12k public GET pages/day at Sep5 activity; actual dates can differ','paid_API_requests':0,'combos_scope':'All KXMVE-prefix public prints; metadata classification follows full tape collection','other_days':'Unobserved, never scaled into portfolio fills','existing_census_reference':str(ROOT/'data/raw/trades/manifest.json') if '2026-09-05' in dates else None}
 plan['date_selection']=a.date_selection
 dest=a.out/a.plan_file
 if dest.exists() and read(dest)!=plan:raise ValueError('Frozen plan differs; use a new output directory')
 save(dest,plan)
 if not a.execute:print(json.dumps(plan,indent=2));return
 if a.max_new_requests<1:raise ValueError('Execution requires positive public request bound')
 client=Client(a.out,a.max_new_requests);cut=client.get('/historical/cutoff',{});save(a.out/('cutoff_'+str(time.time_ns())+'.json'),cut);boundary=ts(cut['payload']['trades_created_ts']);tasks=[]
 for date in dates:
  if date=='2026-09-05':continue
  start=datetime.fromisoformat(date).replace(tzinfo=ZoneInfo('America/Chicago'));end=start+timedelta(days=1);at=int(start.timestamp());until=int(end.timestamp())
  while at<until:
   stop=min(at+3600,until)
   for lo,hi,path in routes(at,stop,boundary):tasks.append((client,a.out/date/f'{int(lo)}_{int(hi)}',lo,hi,path))
   at=stop
 with ThreadPoolExecutor(max_workers=a.workers) as pool:results=list(pool.map(lambda x:collect_partition(*x),tasks))
 save(a.out/'progress.json',{'new_GETs':client.count,'all_new_partitions_complete':all(r['complete'] for r in results),'partitions':results,'cached_sep5_census_not_downloaded':True})
 print(json.dumps({'new_GETs':client.count,'complete_partitions':sum(r['complete'] for r in results),'total_partitions':len(results)}))
if __name__=='__main__':main()
