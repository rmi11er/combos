#!/usr/bin/env python3
"""Bounded historical acquisition for a predeclared CFB fixture cohort."""
import argparse,gzip,hashlib,json,sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from combos.matching import norm
from combos.oddspapi import OddsPapi,iter_history
from combos.request_budget import RequestBudget


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--key-file',type=Path,required=True)
 p.add_argument('--out',type=Path,default=Path('runs/cfb_fair_pilot_20260907'));p.add_argument('--count',type=int,default=20)
 a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 c=json.load(open('config/oddspapi_polling.json'));budget=RequestBudget(c['budget_path'],c['billing_cycle_start'],c['billing_cycle_end'],c['subscription_request_limit'],known_used=c['known_used']+1)
 client=OddsPapi(a.out/'raw',api_key=a.key_file.read_text().strip(),request_budget=budget)
 report={'errors':[],'history':[]}
 try:
  before=client.get('account',refresh=True);active=[s for s in before['payload']['subscriptions'] if s['is_active']]
  report['account_before']=[{k:s[k] for k in ('request_count','bookmakers','request_limit')} for s in active]
  fixtures=json.load(open(a.out/'fixtures.json'))['payload'];mp=json.load(open('data/derived/polymarket_mapping.json'));by=defaultdict(list)
  for ticker,m in mp.items():
   if m['status']=='matched':by[(tuple(m['teams']),m['start_time'])].append(ticker)
  candidates=[]
  for f in fixtures:
   teams=tuple(sorted(norm(f.get('participant'+str(i)+'ShortName','')) for i in (1,2)))
   matched=[keys for (ts,start),keys in by.items() if ts==teams and datetime.fromisoformat(start.replace('Z','+00:00'))==datetime.fromisoformat(f['startTime'].replace('Z','+00:00'))]
   if len(matched)==1 and len(matched[0])>=10:candidates.append({'fixture':f,'kalshi_tickers':sorted(matched[0])})
  candidates.sort(key=lambda x:hashlib.sha256(('cfb-pilot-20260907:'+x['fixture']['fixtureId']).encode()).hexdigest())
  selected=candidates[:a.count]
  plan={'selection':'first 20 by SHA256(cfb-pilot-20260907:fixture_id), among exact existing exchange-mapped fixtures with >=10 mapped lines; independent of odds/outcomes',
        'candidate_fixtures':len(candidates),'selected':selected,'cohort_limitation':'existing exchange mappings cover September 5 fixtures; pricing window is August 31–September 6'}
  (a.out/'selection.json').write_text(json.dumps(plan,indent=2))
  (a.out/'history').mkdir(exist_ok=True)
  for item in selected:
   f=item['fixture'];fid=f['fixtureId']
   try:
    r=client.get('historical-odds',{'fixtureId':fid,'bookmakers':'pinnacle+30'})
    with gzip.open(a.out/'history'/f'{fid}.json.gz','wt') as stream:json.dump(r,stream,separators=(',',':'))
    rows=list(iter_history(r['payload']));result={'fixture_id':fid,'rows':len(rows),'earliest':min((x['snapshot']['createdAt'] for x in rows),default=None)}
    report['history'].append(result);print(json.dumps(result),flush=True)
   except Exception as exc:report['errors'].append({'fixture_id':fid,'error':str(exc)})
  after=client.get('account',refresh=True);active=[s for s in after['payload']['subscriptions'] if s['is_active']]
  report['account_after']=[{k:s[k] for k in ('request_count','bookmakers','request_limit')} for s in active]
  used=max(s['request_count'] for s in active);c.update(known_used=used,usage_verified_at=after['retrieved_at'],usage_reference=str(a.out/'acquisition.json'))
  Path('config/oddspapi_polling.json').write_text(json.dumps(c,indent=2)+'\n')
 finally:
  a.key_file.unlink(missing_ok=True);report['temporary_key_file_deleted']=not a.key_file.exists();budget.close()
  (a.out/'acquisition.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
