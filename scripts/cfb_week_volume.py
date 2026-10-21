"""Stratified public-tape estimate by trade weekday, with a saved Saturday census.

Four randomly selected nonoverlapping 15-second cells per hour outside Saturday.
Every print within a sampled cell is collected, not just a first-page sample.
Horvitz-Thompson totals and within-hour cluster sampling variances are reported.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
import gzip
import json
import math
from pathlib import Path
import random
import sqlite3
import time
from zoneinfo import ZoneInfo
import requests
from rate_limit import pace

ROOT=Path(__file__).resolve().parents[1]
BASE='https://external-api.kalshi.com/trade-api/v2'
ZONE=ZoneInfo('America/Chicago')


def classify(market):
    legs=market.get('mve_selected_legs') or []
    flags=[l.get('event_ticker',l.get('market_ticker','')).startswith('KXNCAAF') for l in legs]
    return {'nlegs':len(legs),'pure_cfb':len(legs)>=2 and all(flags),'any_cfb':any(flags)}


def fetch_window(task):
    start,end,folder=task;folder.mkdir(parents=True,exist_ok=True)
    complete=folder/'complete.json'
    if complete.exists():return json.loads(complete.read_text())
    session=requests.Session();cursor='';seen=set();trades={};pages=0;raw_count=0
    while True:
        p=folder/f'{pages:05d}.json.gz'
        if p.exists():
            with gzip.open(p,'rt') as f:envelope=json.load(f)
        else:
            params={'min_ts':start-1,'max_ts':end+1,'limit':1000}
            if cursor:params['cursor']=cursor
            for attempt in range(9):
                pace()
                try:r=session.get(BASE+'/markets/trades',params=params,timeout=40)
                except requests.RequestException:
                    if attempt==8:raise
                    time.sleep(min(16,2**attempt));continue
                if r.status_code==429 or r.status_code>=500:
                    time.sleep(min(16,2**attempt));continue
                r.raise_for_status();break
            else:raise RuntimeError('trade retries exhausted')
            envelope={'url':r.url,'retrieved_at':time.time(),'payload':r.json()}
            with gzip.open(p.with_suffix('.tmp'),'wt') as f:json.dump(envelope,f,separators=(',',':'))
            p.with_suffix('.tmp').replace(p)
        payload=envelope['payload'];raw_count+=len(payload['trades'])
        for t in payload['trades']:
            ts=datetime.fromisoformat(t['created_time'].replace('Z','+00:00')).timestamp()
            if start<=ts<end and t['ticker'].startswith('KXMVE'):
                if t['trade_id'] in trades and trades[t['trade_id']]!=t:raise ValueError('conflicting trade')
                trades[t['trade_id']]=t
        pages+=1;cursor=payload.get('cursor','')
        if not cursor:break
        if cursor in seen:raise ValueError('repeated cursor')
        seen.add(cursor)
    out={'start':start,'end':end,'pages':pages,'raw_rows':raw_count,'combos':list(trades.values())}
    complete.write_text(json.dumps(out,separators=(',',':')))
    return out


def metadata_index(path):
    db=sqlite3.connect(path)
    db.execute('CREATE TABLE IF NOT EXISTS markets(ticker TEXT PRIMARY KEY, classification TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY)')
    for p in sorted((ROOT/'data/raw/metadata').glob('*.json.gz')):
        if db.execute('SELECT 1 FROM files WHERE path=?',(str(p),)).fetchone():continue
        with gzip.open(p,'rt') as f:env=json.load(f)
        with db:
            db.executemany('INSERT OR REPLACE INTO markets VALUES(?,?)',[(m['ticker'],json.dumps(classify(m))) for m in env['payload']['markets']])
            db.execute('INSERT INTO files VALUES(?)',(str(p),))
    return db


def measures(trades, classifications, cohort):
    sums=defaultdict(Decimal)
    for t in trades:
        c=classifications[t['ticker']]
        eligible=(c['pure_cfb'] if cohort=='all_pure_cfb' else c['pure_cfb'] and c['nlegs']==2)
        if not eligible:continue
        q=Decimal(t['count_fp']);p=Decimal(t['yes_price_dollars'])
        if q<=0 or not 0<=p<=1:raise ValueError('invalid trade units')
        sums['prints']+=1;sums['payout_notional_dollars']+=q;sums['yes_premium_dollars']+=q*p
    return {k:float(sums[k]) for k in ('prints','payout_notional_dollars','yes_premium_dollars')}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start',default='2026-08-31');parser.add_argument('--seed',type=int,default=20260831)
    parser.add_argument('--cells-per-hour',type=int,default=4)
    args=parser.parse_args()
    if not 2<=args.cells_per_hour<=240:raise ValueError('need 2..240 sampled cells per hour')
    start=datetime.fromisoformat(args.start).replace(tzinfo=ZONE)
    directory=ROOT/'data/raw'/('cfb_week_'+args.start.replace('-',''));directory.mkdir(parents=True,exist_ok=True)
    out=ROOT/'runs'/('cfb_week_'+args.start.replace('-',''));out.mkdir(parents=True,exist_ok=True)
    rng=random.Random(args.seed);tasks=[];byday=defaultdict(list)
    census_day='2026-09-05'
    for day in range(7):
        date=start+timedelta(days=day)
        if date.date().isoformat()==census_day:continue
        for hour in range(24):
            base=int((date+timedelta(hours=hour)).timestamp())
            for cell in sorted(rng.sample(range(240),args.cells_per_hour)):
                lo=base+cell*15;tasks.append((lo,lo+15,directory/str(lo)))
    plan={'start':args.start,'timezone':'America/Chicago','seed':args.seed,'cell_seconds':15,
          'cells_per_hour':args.cells_per_hour,'windows':[[a,b] for a,b,_ in tasks],
          'complete':False,'census_day':census_day,'scope':'KXMVE-prefix executed combos; all legs CFB; any leg count, plus two-leg subset'}
    prior=out/'sampling_plan.json'
    if prior.exists() and json.loads(prior.read_text())!=plan:raise ValueError('sampling plan mismatch')
    prior.write_text(json.dumps(plan,indent=2))
    windows=[]
    with ThreadPoolExecutor(max_workers=6) as pool:
        for i,w in enumerate(pool.map(fetch_window,tasks)):
            windows.append(w)
            if i%24==0:print(json.dumps({'stage':'tape','windows':i+1,'total':len(tasks)}),flush=True)
    census=[]
    if start.date().isoformat()<=census_day<(start+timedelta(days=7)).date().isoformat():
        manifest=json.loads((ROOT/'data/raw/trades/manifest.json').read_text())
        if len(manifest['partitions'])!=24 or not all(p['complete'] for p in manifest['partitions']):raise ValueError('incomplete Saturday census')
        for p in sorted((ROOT/'data/derived/tape').glob('hour_*.json.gz')):
            with gzip.open(p,'rt') as f:census.extend(json.load(f)['combos'])
        if len({t['trade_id'] for t in census})!=len(census):raise ValueError('duplicate census prints')
    needed={t['ticker'] for w in windows for t in w['combos']}|{t['ticker'] for t in census}
    print(json.dumps({'stage':'metadata_index','needed':len(needed)}),flush=True)
    db=metadata_index(directory/'metadata.sqlite')
    known={r[0] for r in db.execute('SELECT ticker FROM markets')};missing=sorted(needed-known)
    from build_catalog import fetch_batch
    batches=[missing[i:i+100] for i in range(0,len(missing),100)]
    with ThreadPoolExecutor(max_workers=6) as pool:
        for i,env in enumerate(pool.map(fetch_batch,batches)):
            with db:db.executemany('INSERT OR REPLACE INTO markets VALUES(?,?)',[(m['ticker'],json.dumps(classify(m))) for m in env['payload']['markets']])
            if i%50==0:print(json.dumps({'stage':'metadata','batches':i+1,'total':len(batches)}),flush=True)
    classifications={t:json.loads(c) for t,c in db.execute('SELECT ticker,classification FROM markets') if t in needed};db.close()
    if needed-classifications.keys():raise ValueError('unclassified combo tickers remain')
    results=[]
    for cohort in ('all_pure_cfb','two_leg_pure_cfb'):
        for day in range(7):
            date=start+timedelta(days=day);name=date.date().isoformat()
            totals=defaultdict(float);variances=defaultdict(float)
            if name==census_day:
                totals.update(measures(census,classifications,cohort));method='census'
            else:
                method='stratified_estimate'
                for hour in range(24):
                    lo=int((date+timedelta(hours=hour)).timestamp())
                    cells=[measures(w['combos'],classifications,cohort) for w in windows if lo<=w['start']<lo+3600]
                    n=len(cells)
                    if n!=args.cells_per_hour:raise ValueError('missing sampled window')
                    for metric in ('prints','payout_notional_dollars','yes_premium_dollars'):
                        values=[c[metric] for c in cells];mean=sum(values)/n
                        variance=sum((v-mean)**2 for v in values)/(n-1)
                        totals[metric]+=240*mean
                        variances[metric]+=240**2*(1-n/240)*variance/n
            results.append({'date':name,'weekday':date.strftime('%A'),'cohort':cohort,'method':method,
                'totals':dict(totals),'standard_errors':{k:math.sqrt(variances[k]) for k in totals},
                'approximate_95_intervals':{k:[max(0,v-1.96*math.sqrt(variances[k])),v+1.96*math.sqrt(variances[k])] for k,v in totals.items()}})
    summary={'complete':True,'plan':plan,'results':results,'classified_tickers':len(classifications),
        'limitations':['Non-Saturday days are random time-cluster estimates, not exact totals. Normal intervals can understate heavy-tail uncertainty.',
        'Public completed trades, not RFQ or quoted volume. Premium is YES price times shares, not both sides added together.',
        'Pure CFB means all legs start KXNCAAF; includes futures/props if present. Mixed-sport combos excluded.',
        'Not filtered to pregame; weekday is trade time, not fixture date.']}
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(12,4.5))
    for ax,metric,title in zip(axes,('yes_premium_dollars','payout_notional_dollars'),('YES premium traded','Payout notional traded')):
        for offset,cohort,label in ((-.19,'all_pure_cfb','All CFB leg counts'),(.19,'two_leg_pure_cfb','Two-leg CFB')):
            rows=[r for r in results if r['cohort']==cohort]
            ax.bar([i+offset for i in range(7)],[r['totals'][metric]/1e6 for r in rows],width=.38,label=label,
                yerr=[1.96*r['standard_errors'][metric]/1e6 for r in rows],capsize=2)
        ax.set_xticks(range(7),['Mon','Tue','Wed','Thu','Fri','Sat*','Sun']);ax.set_ylabel('$ millions');ax.set_title(title);ax.legend(fontsize=8)
    fig.suptitle('CFB combo executions · Aug 31–Sep 6, 2026 · Chicago trade time')
    fig.text(.5,.01,'*Saturday census; other days stratified estimates with approximate 95% error bars. Mixed-sport combos excluded.',ha='center',fontsize=8)
    fig.tight_layout(rect=(0,.035,1,.94));fig.savefig(out/'weekday_volume.png',dpi=170);plt.close(fig)
    print(json.dumps({'stage':'complete','output':str(out)}),flush=True)


if __name__=='__main__':main()
