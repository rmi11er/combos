#!/usr/bin/env python3
"""One-fixture retrospective mapping overlay; bounded public PM requests only."""
import argparse,copy,gzip,hashlib,json,math,subprocess,sys,time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from mlb_exchange_acquire import pm_match,stamp
from mlb_entry_sweep import paired_day
from combos.backtest import BacktestConfig,run_backtest

TOKEN='26JUL161910NYMPHI';SLUG='mlb-nym-phi-2026-07-16';EVENT_ID='687903';GAME_ID=10078738
ORIGINAL=stamp('2026-07-16T23:10:00Z');REVISED=stamp('2026-07-16T22:10:00Z')
ALLOWED={'KXMLBGAME-'+TOKEN+'-PHI','KXMLBGAME-'+TOKEN+'-NYM','KXMLBSPREAD-'+TOKEN+'-PHI2','KXMLBSPREAD-'+TOKEN+'-NYM2','KXMLBTOTAL-'+TOKEN+'-10','KXMLBTOTAL-'+TOKEN+'-11','KXMLBTOTAL-'+TOKEN+'-6'}
SOURCE='https://www.mlb.com/news/mets-phillies-july-16-game-time-change'
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def readgz(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def dump(p,d):
 p.parent.mkdir(parents=True,exist_ok=True)
 if p.suffix=='.gz':
  with gzip.open(p,'wt') as f:json.dump(d,f,separators=(',',':'),allow_nan=False)
 else:p.write_text(json.dumps(d,indent=2,allow_nan=False)+'\n')

def reviewed_candidates(events,native,baseline):
 candidates=[e for e in events if str(e.get('id'))==EVENT_ID and e.get('slug')==SLUG]
 if len(candidates)!=1:raise ValueError('exact unique fullgame event required')
 event=candidates[0]
 if event.get('gameId')!=GAME_ID or stamp(event['startTime'])!=REVISED or 'July 16 at 7:10PM ET' not in event['description']:raise ValueError('event schedule evidence changed')
 money=[m for m in event['markets'] if m.get('sportsMarketType')=='moneyline']
 if len(money)!=1 or str(money[0]['id'])!='2870228':raise ValueError('unique fullgame moneyline identity required')
 if any(stamp(m['gameStartTime'])!=REVISED for m in event['markets']):raise ValueError('unexpected market-specific clock')
 result=copy.deepcopy(baseline);review=copy.deepcopy(event);review['startTime']='2026-07-16T23:10:00Z'
 for ticker in sorted(ALLOWED):
  n=native[ticker]
  if 'Jul 16, 2026 at 7:10 PM EDT' not in n['rules_primary'] or TOKEN not in ticker:raise ValueError('original native schedule evidence changed')
  if baseline[ticker]['status']!='unmatched':raise ValueError('overlay may replace only reviewed baseline exclusions')
  m=pm_match(n,[review])
  if m['status']!='matched':raise ValueError('exact ordinary payoff mapping absent')
  m.update(original_scheduled_start_at=ORIGINAL,revised_scheduled_start_at=REVISED,conservative_pregame_cutoff_at=REVISED-60,
   mapping_reference=SOURCE,identity_review='Retrospective one-fixture schedule-revision review; not known prospectively on July15',
   schedule_change_available_at=None,source_metadata_is_later_snapshot=True,
   doubleheader_identity_basis='Exact allowlisted fixture/event/gameId and original contract prose; not a global schedule tolerance')
  result[ticker]=m
 if len({result[t]['token'] for t in ALLOWED})!=7:raise ValueError('seven distinct required token histories')
 return result

def enforce_cutoff(at,legs):
 if any(TOKEN in l['market_ticker'] for l in legs) and at>=REVISED-60:raise ValueError('revised pregame cutoff')

def acquire(out,token,params,attempt_file):
 path=out/(token+'.json.gz')
 if path.exists():
  env=readgz(path)
  if env['params']==params and env['status']==200:return
 attempts=[json.loads(l) for l in attempt_file.read_text().splitlines()] if attempt_file.exists() else []
 for _ in range(4):
  if len(attempts)>=28 or sum(r['token']==token for r in attempts)>=4:raise ValueError('persistent public request budget exhausted')
  record={'token':token,'started_at':time.time(),'url':'https://clob.polymarket.com/prices-history','params':params}
  with attempt_file.open('a') as f:f.write(json.dumps(record)+'\n')
  attempts.append(record)
  session=requests.Session();session.trust_env=False
  try:
   response=session.get(record['url'],params=params,timeout=30,allow_redirects=False)
   payload=response.json();status=response.status_code
  except (requests.RequestException,ValueError) as exc:payload={'error_type':type(exc).__name__};status=0
  finally:session.close()
  dump(path,{'url':record['url'],'params':params,'status':status,'retrieved_at':time.time(),'payload':payload})
  if status==200:
   history=payload.get('history')
   if not isinstance(history,list):raise ValueError('missing historical PM rows')
   for r in history:
    if not math.isfinite(float(r['p'])) or not 0<=float(r['p'])<=1 or not params['startTs']<=float(r['t'])<=params['endTs']:raise ValueError('invalid public PM historical row')
   return
  if status not in (0,429) and status<500:raise ValueError('nonretryable public PM error')
  time.sleep(1)
 raise ValueError('public PM attempts failed')

def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--execute',action='store_true');a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 base=ROOT/'runs/mlb_historical_20260907/dated_fee_primary/2026-07-15';evidence=ROOT/'runs/july15_mapping_audit_20260907/coverage.json';audit=json.loads(evidence.read_text())
 for path,h in audit['evidence_hashes'].items():
  if digest(path)!=h:raise ValueError('audit evidence hash changed')
 events=json.loads((base/'exchange/pm_events_complete.json').read_text());native=readgz(base/'cohort/underlying_markets.json.gz');baseline=json.loads((base/'exchange/polymarket_mapping_reviewed.json').read_text());mapping=reviewed_candidates(events,native,baseline)
 data=json.loads((base/'replay/opportunities.json').read_text());markets=readgz(base/'cohort/combo_markets.json.gz')
 if datetime.fromtimestamp(data['start_at']).strftime('%Y-%m-%d')!='2026-07-15':raise ValueError('only July15 audited overlay allowed')
 for r in data['opportunities']:enforce_cutoff(r['at'],markets[r['source']['combo_ticker']]['mve_selected_legs'])
 hashes={str(f):digest(f) for f in [Path(__file__),ROOT/'scripts/mlb_exchange_acquire.py',ROOT/'scripts/mlb_model_replay.py',ROOT/'scripts/mlb_entry_sweep.py',ROOT/'src/combos/backtest.py',evidence,*[Path(x) for x in audit['evidence_hashes']]]}
 plan={'source_hashes':hashes,'allowlist':sorted(ALLOWED),'original_start_at':ORIGINAL,'revised_start_at':REVISED,'schedule_change_available_at':None,'retrospective_only':True,'max_public_attempts':28,'max_per_token_attempts':4,'orders_enabled':False,'paid_calls':False}
 planpath=a.out/'plan.json'
 if planpath.exists() and json.loads(planpath.read_text())!=plan:raise ValueError('immutable overlay plan changed')
 dump(planpath,plan)
 if not a.execute:print(json.dumps(plan));return
 exchange=a.out/'exchange';exchange.mkdir(exist_ok=True);pm=exchange/'polymarket';pm.mkdir(exist_ok=True)
 kalshi=exchange/'kalshi_parts'
 if not kalshi.exists():kalshi.symlink_to((base/'exchange/kalshi_parts').resolve(),target_is_directory=True)
 for f in (base/'exchange/polymarket').glob('*.json.gz'):
  target=pm/f.name
  if not target.exists():target.symlink_to(f.resolve())
 dump(exchange/'polymarket_mapping_reviewed.json',mapping)
 for ticker in sorted(ALLOWED):
  token=mapping[ticker]['token'];params={'market':token,'startTs':int(data['start_at']-86400),'endTs':int(data['end_at']+360),'fidelity':1}
  acquire(pm,token,params,a.out/'attempts.jsonl')
 command=[sys.executable,str(ROOT/'scripts/mlb_model_replay.py'),'--cohort',str(base/'cohort'),'--exchange',str(exchange),'--fee-scenario',str(ROOT/'runs/mlb_historical_20260907/fee_scenarios/2026-07-15.json'),'--out',str(a.out/'replay')]
 with (a.out/'replay.log').open('w') as log:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
 expanded=json.loads((a.out/'replay/opportunities.json').read_text());old,start,end,_=paired_day(data,'2026-07-15');new,_,_,_=paired_day(expanded,'2026-07-15');oldkeys={(r['model'],r['evaluation_id']) for r in old};newby={(r['model'],r['evaluation_id']):r for r in new}
 for r in old:
  other=newby[(r['model'],r['evaluation_id'])]
  for key in ('fair_point','stressed_upper','maker_fee','quantity','yes_price','buckets','quote_allowed','risk_multiplier'):
   if r[key]!=other[key]:raise ValueError('baseline intersection altered: '+key)
 cohorts={'baseline_common':old,'newly_priced': [r for r in new if (r['model'],r['evaluation_id']) not in oldkeys],'expanded_common':new};results={}
 for label,rows in cohorts.items():
  for constrained in (True,False):
   for policy in ('selection','sell_all'):
    key=label+'_'+('funded' if constrained else 'unlimited')+'_'+policy
    result=run_backtest(rows,start,end,BacktestConfig(entry_basis='point',entry_filter='minimum_edge' if policy=='selection' else 'all_priced'),constrained)
    dump(a.out/(key+'.json.gz'),result);results[key]=result['summaries']
 for path,h in hashes.items():
  if digest(path)!=h:raise ValueError('source evidence changed during overlay')
 summary={'cohort_prints':{k:len(v)//4 for k,v in cohorts.items()},'baseline_common_prices_unchanged':True,'results':results,'public_requests':len((a.out/'attempts.jsonl').read_text().splitlines()),'plan':plan,'new_history_sha256':{mapping[t]['token']:digest(pm/(mapping[t]['token']+'.json.gz')) for t in ALLOWED},'limitations':['Retrospective identity review and conservative earlier cutoff; announcement intraday availability unknown.','Baseline dated fee and exceptional-payoff assumptions unchanged. No Pinnacle.','New-only funded experiment starts a separate10k account; expanded funded run reallocates all eligible dates chronologically.','Public observed-print hypothetical execution; no RFQ acceptance evidence.']}
 dump(a.out/'summary.json',summary)
 lines=['# July15 reviewed NYM–PHI overlay','','Common priced prints: '+str(summary['cohort_prints'])+'. Baseline common prices, fee amounts, guards and risk identities are unchanged.','','| Cohort | Funding | Policy | Model | Fills | Net known P&L | Model edge | Peak cash |','|---|---|---|---|---:|---:|---:|---:|']
 for key,rr in results.items():
  for r in rr:lines.append(f"| {key} | {'funded' if '_funded_' in key else 'unlimited'} | {'sell all' if key.endswith('sell_all') else 'selection'} | {r['model']} | {r['fills']} | ${r['trade_attributed_pnl']:,.2f} | ${r['accepted_point_edge']:,.2f} | ${r['peak_committed_cash']:,.2f} |")
 lines+=['',*summary['limitations'],'',f"Public requests: {summary['public_requests']}; maximum28 persistent attempts,4 per token. Existing cached exchange inputs read through symlinks; frozen baseline files unchanged."]
 (a.out/'REPORT.md').write_text('\n'.join(lines)+'\n');print(json.dumps({'coverage':summary['cohort_prints'],'public_requests':summary['public_requests']}))
if __name__=='__main__':main()
