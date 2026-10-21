#!/usr/bin/env python3
"""Build an MLB census/sampled-cell cohort before price-source selection.

Reads the retained public tape and all native combo metadata. Never scales a
sampled print into simulated fills. Optional public metadata GETs recover every
required MLB underlying in resumable batches; no provider or order calls.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys
import time
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from combos.fees import kalshi_fill_fee
CORE={'KXMLBGAME','KXMLBSPREAD','KXMLBTOTAL'}
NONPLAYER=CORE|{'KXMLB1H','KXMLB1HSPREAD','KXMLB1HTOTAL','KXMLBTEAMTOTAL','KXMLBF5','KXMLBF5SPREAD','KXMLBF5TOTAL','KXMLBNRFI','KXMLBYRFI'}
PROP={'KXMLBHR','KXMLBHRR','KXMLBKS','KXMLBHITS','KXMLBRBI','KXMLBRUNS','KXMLBSB','KXMLBTB','KXMLB1HIT','KXMLB2HITS'}

def stamp(s):return datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()
def load(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def write(p,d):p.write_text(json.dumps(d,indent=2)+'\n')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def classify(m):
 legs=m.get('mve_selected_legs') or []; tickers=[l.get('market_ticker','') for l in legs]
 series=sorted({t.split('-')[0] for t in tickers}); fixtures=[t.split('-')[1] if '-' in t else '' for t in tickers]
 starts=[]
 for f in fixtures:
  if re.match(r'^\d{2}[A-Z]{3}\d{6}',f):
   try:starts.append(datetime.strptime(f[:11],'%y%b%d%H%M').replace(tzinfo=ZoneInfo('America/New_York')).timestamp())
   except ValueError:starts.append(None)
  else:starts.append(None)
 return {'nlegs':len(legs),'pure_mlb':len(legs)>=2 and all(t.startswith('KXMLB') for t in tickers),
 'series':series,'fullgame_core':bool(legs) and set(series)<=CORE,'known_player_prop':bool(set(series)&PROP),
 'unknown_family':sorted(set(series)-NONPLAYER-PROP),'distinct_fixtures':len(set(fixtures))==len(fixtures),
 'fixture_tokens':fixtures,'scheduled_start_times':starts,'earliest_scheduled_start':min(starts) if starts and all(x is not None for x in starts) else None,
 'start_basis':'Native ticker embeds scheduled New York clock; snapshot schedule proxy, not point-in-time actual-start verification'}

def index(out):
 db=sqlite3.connect(out/'metadata_index.sqlite')
 db.execute('CREATE TABLE IF NOT EXISTS metadata(ticker TEXT PRIMARY KEY,data TEXT NOT NULL,classification TEXT NOT NULL)')
 db.execute('CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY,sha256 TEXT NOT NULL)')
 files=sorted((ROOT/'data/raw/metadata').glob('*.json.gz'))
 for i,p in enumerate(files):
  h=digest(p); prev=db.execute('SELECT sha256 FROM files WHERE path=?',(str(p),)).fetchone()
  if prev and prev[0]==h:continue
  rows=[]
  for m in load(p)['payload'].get('markets',[]):
   c=classify(m)
   if c['pure_mlb']:rows.append((m['ticker'],json.dumps(m,separators=(',',':')),json.dumps(c,separators=(',',':'))))
  with db:
   db.executemany('INSERT OR REPLACE INTO metadata VALUES(?,?,?)',rows)
   db.execute('INSERT OR REPLACE INTO files VALUES(?,?)',(str(p),h))
  if i%1000==0:print(json.dumps({'stage':'metadata','files':i,'total':len(files)}),flush=True)
 return db

def source_windows():
 manifest=json.loads((ROOT/'data/raw/trades/manifest.json').read_text())
 parts=sorted(manifest['partitions'],key=lambda r:r['start'])
 if len(parts)!=24 or parts[0]['start']!=manifest['start'] or parts[-1]['end']!=manifest['end'] or any(not p['complete'] for p in parts) or any(a['end']!=b['start'] for a,b in zip(parts,parts[1:])):raise ValueError('Incomplete purported census')
 for part in parts:
  p=ROOT/'data/derived/tape'/f"hour_{part['hour']:02d}.json.gz"
  yield p,part['start'],part['end'],'census',load(p)['combos']
 for p in sorted((ROOT/'data/raw/cfb_week_20260831').glob('*/complete.json')):
  d=json.loads(p.read_text());yield p,d['start'],d['end'],'complete_sampled_cell',d['combos']

def fetch_underlying(out,tickers,max_requests):
 import requests
 from rate_limit import pace
 raw=out/'underlying_batches';raw.mkdir(exist_ok=True); session=requests.Session();session.trust_env=False
 result={}; calls=0; inventory=[]
 for offset in range(0,len(tickers),100):
  batch=tickers[offset:offset+100]
  for endpoint in ('/markets','/historical/markets'):
   missing=[t for t in batch if t not in result]
   if not missing:break
   params={'tickers':','.join(missing),'limit':1000};key=hashlib.sha256(json.dumps([endpoint,params],sort_keys=True).encode()).hexdigest();p=raw/(key+'.json.gz')
   if p.exists():env=load(p)
   else:
    if calls>=max_requests:break
    for attempt in range(5):
     if calls>=max_requests:break
     pace();calls+=1
     try:
      r=session.get('https://external-api.kalshi.com/trade-api/v2'+endpoint,params=params,timeout=40,allow_redirects=False)
      env={'request':{'endpoint':endpoint,'params':params},'status':r.status_code,'retrieved_at':time.time(),'payload':r.json()}
     except requests.RequestException:env={'request':{'endpoint':endpoint,'params':params},'status':None,'retrieved_at':time.time(),'error':'transport_failure'}
     if env['status']==200:break
     with gzip.open(raw/(key+f'.attempt{time.time_ns()}.json.gz'),'wt') as f:json.dump(env,f)
     time.sleep(min(8,2**attempt))
    if env.get('status')!=200:continue
    with gzip.open(p,'wt') as f:json.dump(env,f,separators=(',',':'))
   if env.get('status')!=200 or env['payload'].get('cursor'):raise ValueError('Metadata failed or truncated')
   for m in env['payload'].get('markets',[]):
    if m['ticker'] not in missing:raise ValueError('Unexpected metadata ticker')
    result[m['ticker']]=m
   inventory.append({'path':str(p.relative_to(out)),'sha256':digest(p)})
  if offset%1000==0:print(json.dumps({'stage':'underlying','requested':offset+len(batch),'recovered':len(result),'new_GETs':calls}),flush=True)
 session.close()
 with gzip.open(out/'underlying_markets.json.gz','wt') as f:json.dump(result,f,separators=(',',':'))
 write(out/'underlying_acquisition.json',{'requested':len(tickers),'recovered':len(result),'missing':sorted(set(tickers)-result.keys()),'new_GETs':calls,'inventory':inventory})

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,default=ROOT/'runs/mlb_historical_20260907/cohort');p.add_argument('--fetch-underlying',action='store_true');p.add_argument('--max-metadata-requests',type=int,default=200);args=p.parse_args();args.out.mkdir(parents=True,exist_ok=True)
 db=index(args.out);markets={};classes={}
 for t,m,c in db.execute('SELECT ticker,data,classification FROM metadata'):markets[t]=json.loads(m);classes[t]=json.loads(c)
 db.close(); print(json.dumps({'stage':'indexed','pure_mlb_definitions':len(markets)}),flush=True)
 allknown=sqlite3.connect(f'file:{ROOT}/data/raw/cfb_week_20260831/metadata.sqlite?mode=ro',uri=True)
 known={r[0] for r in allknown.execute('SELECT ticker FROM markets')};allknown.close()
 seen={}; sources=[];counts=Counter();by=defaultdict(lambda:defaultdict(float));required=set();alllegs=set();universe_count=0;candidates=0
 with gzip.open(args.out/'universe_trades.jsonl.gz','wt') as universe,gzip.open(args.out/'candidate_trades.jsonl.gz','wt') as cand:
  for path,lo,hi,method,trades in source_windows():
   sources.append({'path':str(path.relative_to(ROOT)),'sha256':digest(path),'start_at':lo,'end_at':hi,'method':method,'sample_weight_in_replay':1})
   for t in trades:
    at=stamp(t['created_time'])
    if not lo<=at<hi:raise ValueError('Print outside retained interval')
    h=hashlib.sha256(json.dumps(t,sort_keys=True).encode()).hexdigest();identifier=t['trade_id']
    if identifier in seen:
     if seen[identifier]!=h:raise ValueError('Conflicting duplicate trade ID')
     counts['duplicate']+=1;continue
    seen[identifier]=h;counts['all_combo_prints']+=1
    if t['ticker'] not in known:counts['missing_definition_prints']+=1
    if t['ticker'] not in classes:continue
    m=markets[t['ticker']];c=classes[t['ticker']];q=Decimal(t['count_fp']);price=Decimal(t['yes_price_dollars'])
    if q<=0 or not 0<=price<=1:raise ValueError('Invalid trade economics')
    start=c['earliest_scheduled_start'];pregame=None if start is None else at<start
    settlement=m.get('settlement_value_dollars');settled=m.get('settlement_ts')
    result=m.get('result');settlement=float(settlement) if settlement not in (None,'') else (1. if result=='yes' else 0. if result=='no' else None)
    fee=float(kalshi_fill_fee(q,1-price,'.035')['net_fee']);net=None if settlement is None else float(q)*(float(price)-settlement)-fee
    row={'trade':t,'classification':c,'sampling_method':method,'pregame_scheduled_proxy':pregame,'settlement_value':settlement,'settlement_at':stamp(settled) if settled else None,'native_status':m.get('status'),'maker_fee_dollars':fee,'seller_pnl_dollars':net,'fee_rate':.035,'fee_basis':'Current native MVE rate; historical effective-date schedule not independently verified','source_window':[lo,hi]}
    universe.write(json.dumps(row,separators=(',',':'))+'\n');universe_count+=1;alllegs.update(l['market_ticker'] for l in m['mve_selected_legs'])
    candidate=c['fullgame_core'] and pregame is True
    if candidate:
     cand.write(json.dumps(row,separators=(',',':'))+'\n');candidates+=1;required.update(l['market_ticker'] for l in m['mve_selected_legs'])
    day=datetime.fromtimestamp(at,ZoneInfo('America/Chicago')).date().isoformat();legs=str(c['nlegs']) if c['nlegs']<5 else '5+'
    for cut in [('all', 'all'),('legs',legs),('structure','distinct_game' if c['distinct_fixtures'] else 'same_game'),('family','fullgame_core' if c['fullgame_core'] else 'other'),('phase','pregame_proxy' if pregame else 'post_start_or_unknown')]:
     k='|'.join((day,method,cut[0],cut[1],t.get('taker_side','unknown')));b=by[k];b['prints']+=1;b['yes_premium_dollars']+=float(q*price);b['payout_notional_dollars']+=float(q);b['fees_dollars']+=fee
     if net is None:b['unknown_settlement_prints']+=1
     else:b['known_seller_pnl_dollars']+=net;b['known_settlement_prints']+=1
   print(json.dumps({'stage':'tape','sources':len(sources),'all_combos':counts['all_combo_prints'],'mlb_prints':universe_count,'fullgame_pregame_proxy':candidates}),flush=True)
 write(args.out/'underlying_tickers.json',sorted(required));write(args.out/'all_universe_underlying_tickers.json',sorted(alllegs))
 with gzip.open(args.out/'combo_markets.json.gz','wt') as f:json.dump(markets,f,separators=(',',':'))
 summary={'counts':dict(counts),'pure_mlb_prints':universe_count,'pure_mlb_definitions':len(markets),'fullgame_pregame_proxy_prints':candidates,'candidate_underlying_tickers':len(required),'all_underlying_tickers':len(alllegs),'cuts':[dict(zip(['date','sampling_method','cut','bucket','taker_side'],k.split('|')),**v) for k,v in sorted(by.items())],'sources':sources,'script_sha256':digest(Path(__file__)),'limits':['Only Sep 5 is a complete day; other dates are retained complete 15-second sampled cells at weight one.','Pregame uses native scheduled ticker time, not historically versioned actual start.','All leg counts, same-game, and non-core families retained in universe; candidate file includes core full-game pregame proxy, all leg counts and structures.','YES seller benchmark must filter taker_side=yes; NO-taker prints are retained but are not inferred maker sales.','Pinnacle MLB entitlement unavailable; this cohort is not a three-source backtest.','Current .035 maker rate is not independently historical-date verified; raw economics support fee sensitivity.']}
 write(args.out/'summary.json',summary)
 if args.fetch_underlying:fetch_underlying(args.out,sorted(required),args.max_metadata_requests)
 print(json.dumps({k:v for k,v in summary.items() if k not in ('cuts','sources')},indent=2))
if __name__=='__main__':main()
