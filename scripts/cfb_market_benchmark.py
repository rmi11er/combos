#!/usr/bin/env python3
"""All available pure-CFB YES-taker prints: unlimited opposite-side benchmark.

No forecasting, selection, capital constraints, or expansion of sampled prints.
Existing native metadata is preserved. Optional public outcome refresh is cached.
"""
import argparse,csv,gzip,hashlib,json,sqlite3,sys,time
from collections import Counter,defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from combos.pricing import total_fee
from combos.cfb_market_scope import classify_combo
ZONE=ZoneInfo('America/Chicago')
def stamp(s):return datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()
def gz(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def writecsv(p,rows):
 if not rows:return
 op=gzip.open if str(p).endswith('.gz') else open
 with op(p,'wt',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
 pa=argparse.ArgumentParser(description=__doc__);pa.add_argument('--out',type=Path,default=ROOT/'runs/cfb_performance_audit_20260907/market_benchmark');pa.add_argument('--refresh-outcomes',action='store_true');pa.add_argument('--max-requests',type=int,default=0);a=pa.parse_args();out=a.out;out.mkdir(parents=True,exist_ok=True)
 lo=stamp('2026-08-31T05:00:00Z');hi=stamp('2026-09-07T05:00:00Z');source={};trades={};all_seen=set();counts=Counter();meta={}
 index=ROOT/'data/raw/cfb_week_20260831/metadata.sqlite';db=sqlite3.connect(f'file:{index}?mode=ro',uri=True)
 cfb={t:json.loads(c) for t,c in db.execute('select ticker,classification from markets') if json.loads(c)['pure_cfb']};db.close()
 sources=[];manifest=ROOT/'data/raw/trades/manifest.json';m=json.loads(manifest.read_text())
 if len(m['partitions'])!=24 or not all(p['complete'] for p in m['partitions']):raise ValueError('incomplete Saturday census')
 for p in m['partitions']:sources.append((ROOT/'data/derived/tape'/f'hour_{p["hour"]:02d}.json.gz',True,p['start'],p['end']))
 plan=ROOT/'runs/cfb_week_20260831/sampling_plan.json'
 for start,end in json.loads(plan.read_text())['windows']:sources.append((ROOT/'data/raw/cfb_week_20260831'/str(start)/'complete.json',False,start,end))
 for path,census,start,end in sources:
  env=gz(path) if path.suffix=='.gz' else json.loads(path.read_text());source[str(path.relative_to(ROOT))]=sha(path)
  for t in env['combos']:
   at=stamp(t['created_time'])
   if not lo<=at<hi:continue
   if not start<=at<end:raise ValueError('print outside source interval')
   tid=t['trade_id']
   if tid in all_seen:
    if tid in trades and trades[tid]['trade']!=t:raise ValueError('conflicting duplicate')
    counts['duplicate_print']+=1;continue
   all_seen.add(tid);counts['all_retained_combo_prints']+=1
   if t['ticker'] not in cfb:continue
   trades[tid]={'trade':t,'at':at,'census':census,'source':str(path.relative_to(ROOT)),'interval':[start,end]};counts['pure_cfb_all_sides']+=1
 print(json.dumps({'stage':'tape','counts':counts,'cfb_combos':len({x['trade']['ticker'] for x in trades.values()})}),flush=True)
 wanted={x['trade']['ticker'] for x in trades.values()};cache=out/'native_metadata.sqlite';db=sqlite3.connect(cache);db.execute('create table if not exists metadata(ticker text primary key,data text not null,source text not null)');db.execute('create table if not exists files(path text primary key,sha256 text not null)')
 for i,path in enumerate(sorted((ROOT/'data/raw/metadata').glob('*.json.gz'))):
  if db.execute('select 1 from files where path=?',(str(path),)).fetchone():continue
  env=gz(path)
  with db:
   for market in env['payload']['markets']:
    if market['ticker'] in wanted:db.execute('insert or replace into metadata values(?,?,?)',(market['ticker'],json.dumps(market,separators=(',',':')),str(path.relative_to(ROOT))))
   db.execute('insert into files values(?,?)',(str(path),sha(path)))
  if i%1000==0:print(json.dumps({'stage':'native_metadata','files':i+1}),flush=True)
 for t,raw,p in db.execute('select ticker,data,source from metadata'):
  if t in wanted:
   meta[t]=json.loads(raw)
   if p not in source:source[p]=sha(ROOT/p)
 original_missing=sorted(wanted-meta.keys());unknown_before=sum(not x.get('settlement_ts') for x in meta.values())
 # Reuse outcome refresh already collected without touching original sources.
 prior=ROOT/'runs/cfb_full_week_20260907/replay_settlement_refreshed/settlement_snapshot.json'
 if prior.exists():
  source[str(prior.relative_to(ROOT))]=sha(prior)
  for t,m in json.loads(prior.read_text()).items():
   if t in wanted and (t not in meta or not meta[t].get('settlement_ts')):meta[t]=m
 rawdir=out/'outcome_refresh';rawdir.mkdir(exist_ok=True)
 for path in sorted(rawdir.glob('*.json.gz')):
  env=gz(path)
  if env.get('status')==200 and not env['payload'].get('cursor'):
   for m in env['payload'].get('markets',[]):
    if m['ticker'] in wanted:meta[m['ticker']]=m
  source[str(path.relative_to(ROOT))]=sha(path)
 yes_tickers={x['trade']['ticker'] for x in trades.values() if x['trade'].get('taker_outcome_side',x['trade'].get('taker_side'))=='yes'}
 unknown=sorted(t for t in yes_tickers if t not in meta or not meta[t].get('settlement_ts'))
 (out/'unresolved_combo_tickers.json').write_text(json.dumps(unknown)+'\n')
 print(json.dumps({'stage':'outcomes','metadata':len(meta),'missing_metadata':len(original_missing),'original_unknown':unknown_before,'remaining_unknown':len(unknown),'refresh_batch_GETs':(len(unknown)+99)//100}),flush=True)
 newrequests=0;failures=[]
 if a.refresh_outcomes:
  import requests
  from rate_limit import pace
  session=requests.Session();session.trust_env=False
  for offset in range(0,len(unknown),100):
   batch=unknown[offset:offset+100]
   if newrequests>=a.max_requests:break
   dest=rawdir/(hashlib.sha256(','.join(batch).encode()).hexdigest()+'.json.gz')
   for attempt in range(4):
    if newrequests>=a.max_requests:break
    if attempt:time.sleep(min(8,2**attempt))
    pace();newrequests+=1;params={'tickers':','.join(batch),'limit':1000};env={'requested':batch,'params':params,'request_started_at':time.time()}
    try:
     r=session.get('https://external-api.kalshi.com/trade-api/v2/markets',params=params,timeout=30,allow_redirects=False);env.update(status=r.status_code,url=r.url,retrieved_at=time.time(),payload=r.json())
    except (requests.RequestException,ValueError) as e:env.update(status=None,error=type(e).__name__,retrieved_at=time.time())
    if dest.exists():dest.rename(dest.with_name(dest.stem+'.attempt'+str(time.time_ns())+'.json.gz'))
    with gzip.open(dest,'wt') as f:json.dump(env,f,separators=(',',':'))
    if env.get('status')==200 and not env['payload'].get('cursor'):break
   source[str(dest.relative_to(ROOT))]=sha(dest)
   if env.get('status')!=200 or env['payload'].get('cursor'):failures+=batch;continue
   for m in env['payload'].get('markets',[]):
    if m['ticker'] not in batch:raise ValueError('unexpected requested ticker')
    meta[m['ticker']]=m
   print(json.dumps({'stage':'outcome_refresh','requested':min(offset+100,len(unknown)),'total':len(unknown),'new_GETs':newrequests}),flush=True)
  session.close()
 mappings=ROOT/'runs/cfb_full_week_20260907/polymarket_mapping.json';source[str(mappings.relative_to(ROOT))]=sha(mappings);starts={}
 for t,r in json.loads(mappings.read_text()).items():
  if r.get('start_time'):starts[t.split('-')[1]]=stamp(r['start_time'])
 summaries=defaultdict(lambda:defaultdict(float));rows=[];timeline=defaultdict(lambda:defaultdict(float));series=Counter();unpriced=[];fee_rates=Counter()
 def add(group,row):
  d=summaries[group];d['prints']+=1;d['yes_premium']+=row['yes_premium'];d['payout_notional']+=row['quantity'];d['maker_fees_all']+=row['maker_fee']
  if row['settled_at'] is not None:d['resolved_prints']+=1;d['known_gross_pnl']+=row['gross_pnl'];d['known_fees']+=row['maker_fee'];d['known_net_pnl']+=row['net_pnl']
  else:d['unresolved_prints']+=1;d['unresolved_premium']+=row['yes_premium'];d['unresolved_payout_notional']+=row['quantity'];d['unresolved_fees']+=row['maker_fee']
 for x in sorted(trades.values(),key=lambda x:(x['at'],x['trade']['trade_id'])):
  t=x['trade'];side=t.get('taker_outcome_side',t.get('taker_side'));counts['pure_cfb_taker_'+str(side)]+=1
  if side!='yes':continue
  market=meta.get(t['ticker'])
  if market is None:unpriced.append({'trade_id':t['trade_id'],'reason':'missing_native_metadata'});continue
  event=market['event_ticker']
  if event.startswith('KXMVECROSSCATEGORY-SHARD1-'):rate=.035
  elif event.startswith('KXMVECROSSCATEGORY0-SHARD1-'):rate=0.
  else:unpriced.append({'trade_id':t['trade_id'],'reason':'unreviewed_fee_series'});continue
  q=float(t['count_fp']);p=float(t['yes_price_dollars'])
  if not q>0 or not 0<=p<=1:raise ValueError('invalid trade economics')
  fee=total_fee(q,round(1-p,10),rate);legs=market.get('mve_selected_legs') or [];fixtures=[l['market_ticker'].split('-')[1] for l in legs];knownstarts=[starts.get(f) for f in fixtures]
  try:c=classify_combo(market);scope=c['scope'];props='no_player_props'
  except ValueError:scope='unreviewed_family';props='unknown'
  series.update(l['market_ticker'].split('-')[0] for l in legs)
  phase='inplay_or_started' if any(s is not None and x['at']>=s for s in knownstarts) else 'pregame' if all(s is not None for s in knownstarts) else 'unknown_start'
  settled=stamp(market['settlement_ts']) if market.get('settlement_ts') else None;y=float(market['settlement_value_dollars']) if settled is not None else None
  if settled is not None and (settled<=x['at'] or not 0<=y<=1):raise ValueError('invalid actual settlement')
  gross=q*(p-y) if y is not None else None;net=gross-fee if gross is not None else None
  day=datetime.fromtimestamp(x['at'],ZONE).date().isoformat();nlegs=len(legs);lg=str(nlegs) if nlegs<5 else '5+'
  row={'trade_id':t['trade_id'],'ticker':t['ticker'],'at':x['at'],'created_time':t['created_time'],'day':day,'taker_side':side,'quantity':q,'yes_price':p,'yes_premium':q*p,'maker_fee':fee,'maker_fee_rate':rate,'no_principal':q*(1-p),'settled_at':settled,'yes_settlement':y,'gross_pnl':gross,'net_pnl':net,'nlegs':nlegs,'leg_group':lg,'scope':scope,'props':props,'phase':phase,'distinct_fixtures':len(set(fixtures))==len(fixtures),'fixture_keys':json.dumps(fixtures,separators=(',',':')),'legs':json.dumps(legs,separators=(',',':')),'complete_trade_day':x['census'],'sampling_weight':1,'source_file':x['source']}
  rows.append(row);fee_rates[str(rate)]+=1
  for key in ('all','day:'+day,'legs:'+lg,'scope:'+scope,'props:'+props,'phase:'+phase,'day_legs:'+day+':'+lg):add(key,row)
  b=int((x['at']-lo)//1800);d=timeline[b];d['prints']+=1;d['yes_premium']+=q*p;d['payout_notional']+=q;d['maker_fees_all']+=fee
  if net is not None:d['known_gross_pnl']+=gross;d['known_net_pnl']+=net;d['resolved_prints']+=1
  else:d['unresolved_prints']+=1
 writecsv(out/'per_trade.csv.gz',rows)
 agg=[{'group':k,**{name:v.get(name,0) for name in ['prints','resolved_prints','unresolved_prints','yes_premium','payout_notional','maker_fees_all','known_gross_pnl','known_fees','known_net_pnl','unresolved_premium','unresolved_payout_notional','unresolved_fees']}} for k,v in sorted(summaries.items())];writecsv(out/'breakdowns.csv',agg)
 totals=defaultdict(float);curves=[]
 for b in range(int((hi-lo)/1800)):
  for k,v in timeline[b].items():totals[k]+=v
  curves.append({'at':lo+(b+1)*1800,'time':datetime.fromtimestamp(lo+(b+1)*1800,ZONE).isoformat(),'trade_attributed_equity_reporting_10k':10000+totals['known_net_pnl'],**{'cumulative_'+k:totals[k] for k in ['prints','yes_premium','payout_notional','maker_fees_all','known_gross_pnl','known_net_pnl','resolved_prints','unresolved_prints']}})
 writecsv(out/'curves.csv',curves)
 (out/'missing_or_unreviewed.json').write_text(json.dumps(unpriced)+'\n')
 report={'title':'Unlimited seller benchmark for every available pure-CFB YES-taker print','start_at':lo,'end_at':hi,'timezone':str(ZONE),'counts':dict(counts),'benchmark_prints':len(rows),'unique_combos':len(wanted),'missing_metadata_original':len(original_missing),'original_unresolved_combos':unknown_before,'remaining_unresolved_combos':sum(not meta.get(t,{}).get('settlement_ts') for t in wanted),'new_public_GETs':newrequests,'refresh_failures':failures,'excluded_missing_or_unreviewed_prints':len(unpriced),'fee_rate_counts':dict(fee_rates),'leg_series':dict(series),'aggregate':dict(summaries['all']),'limitations':['Opposite side of every observed YES-taker print; not actual industry P&L or realizable execution.','Unlimited funding, no fair model, no edge filter, no leg, phase, prop, capital or risk restrictions.','Equity is 10000 plus known eventual P&L attributed to trade time; not spendable capital or mark-to-market.','Unknown outcomes remain unresolved, not zero-return completed trades.','Saturday is a full census; other days contain only saved sampled intervals at weight one, with no 60x expansion.','Phase uses current cached verified game schedules; unknown start remains unknown.','Unknown leg families are labeled unknown, not assumed player props.'],'finished_at':datetime.now().astimezone().isoformat()}
 (out/'summary.json').write_text(json.dumps(report,indent=2)+'\n');(out/'manifest.json').write_text(json.dumps({'script_sha256':sha(Path(__file__)),'sources':source,'classification_index_sha256':sha(index),'sampling_plan_sha256':sha(plan),'census_manifest_sha256':sha(manifest)},indent=2)+'\n');db.close();print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':main()
