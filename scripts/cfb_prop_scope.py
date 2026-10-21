"""Compare full-game CFB combo volume with team-total/period extensions.

Uses the identical sampled windows and Saturday census from cfb_week_volume.py.
All leg counts and all phases; no trading/model configuration is changed.
"""
import argparse
from collections import defaultdict
import csv
from datetime import datetime
from decimal import Decimal
import gzip
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import sys
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from combos.cfb_market_scope import classify_combo

SCOPES=('full_game_only','team_total_extension','period_extension','team_total_and_period')
LEG_BUCKETS=('2','3','4','5+')
BIN_SCOPES=tuple(base+':legs_'+bucket for base in ('full_game_only','all_cfb') for bucket in LEG_BUCKETS)
METRICS=('yes_premium_dollars','payout_notional_dollars','prints')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study',type=Path,default=ROOT/'runs/cfb_week_20260831')
    args=parser.parse_args();study=args.study
    prior=json.loads((study/'summary.json').read_text());plan=prior['plan']
    raw=ROOT/'data/raw'/('cfb_week_'+plan['start'].replace('-',''))
    db=sqlite3.connect(raw/'metadata.sqlite')
    required={t for t, in db.execute("SELECT ticker FROM markets WHERE json_extract(classification,'$.pure_cfb')=1")};db.close()
    classified={};evidence={}
    for p in sorted((ROOT/'data/raw/metadata').glob('*.json.gz')):
        with gzip.open(p,'rt') as f:env=json.load(f)
        used=False
        for m in env['payload']['markets']:
            t=m['ticker']
            if t not in required:continue
            classification=classify_combo(m)
            if t in classified and classification!=classified[t]:raise ValueError('conflicting composition')
            classified[t]=classification;used=True
        if used:evidence[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
    if required-classified.keys():raise ValueError('CFB composition missing')
    with gzip.open(study/'prop_classifications.json.gz','wt') as f:json.dump(classified,f,separators=(',',':'))
    zone=ZoneInfo(plan['timezone']);cells=defaultdict(list);hourly=[]
    def measure(trades):
        totals={scope:{k:Decimal(0) for k in METRICS} for scope in SCOPES}
        bins={scope:{k:Decimal(0) for k in METRICS} for scope in BIN_SCOPES}
        seen=set()
        for t in trades:
            if t['trade_id'] in seen:raise ValueError('duplicate print within partition')
            seen.add(t['trade_id'])
            c=classified.get(t['ticker'])
            if c is None:continue
            q,p=Decimal(t['count_fp']),Decimal(t['yes_price_dollars'])
            if not q.is_finite() or q<=0 or not p.is_finite() or not 0<=p<=1:raise ValueError('invalid trade')
            target=totals[c['scope']];target['prints']+=1;target['payout_notional_dollars']+=q;target['yes_premium_dollars']+=q*p
            bucket=str(c['nlegs']) if c['nlegs']<5 else '5+'
            for base in ('full_game_only','all_cfb'):
                if base=='full_game_only' and c['scope']!='full_game_only':continue
                target=bins[base+':legs_'+bucket]
                target['prints']+=1;target['payout_notional_dollars']+=q;target['yes_premium_dollars']+=q*p
        output={s:{k:float(v) for k,v in values.items()} for s,values in totals.items()}
        output['extended_only']={k:sum(output[s][k] for s in SCOPES if s!='full_game_only') for k in METRICS}
        output['all_cfb']={k:sum(output[s][k] for s in SCOPES) for k in METRICS}
        output.update({s:{k:float(v) for k,v in values.items()} for s,values in bins.items()})
        return output
    def stamp(ts):return datetime.fromtimestamp(ts,zone).replace(minute=0,second=0,microsecond=0).isoformat()
    for start,end in plan['windows']:
        p=raw/str(start)/'complete.json';w=json.loads(p.read_text())
        evidence[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
        if (w['start'],w['end'])!=(start,end):raise ValueError('sample boundary mismatch')
        cells[stamp(start)].append(measure(w['combos']))
    scopes=(*SCOPES,'extended_only','all_cfb',*BIN_SCOPES)
    for hour,values in sorted(cells.items()):
        n=len(values);N=3600/plan['cell_seconds']
        if n!=plan['cells_per_hour']:raise ValueError('incomplete sampled hour')
        for scope in scopes:
            for metric in METRICS:
                xs=[v[scope][metric] for v in values];mean=sum(xs)/n
                variance=N*N*(1-n/N)*sum((v-mean)**2 for v in xs)/(n-1)/n
                hourly.append({'hour':hour,'scope':scope,'metric':metric,'total':N*mean,'variance':variance,'method':'stratified_estimate'})
    for p in sorted((ROOT/'data/derived/tape').glob('hour_*.json.gz')):
        with gzip.open(p,'rt') as f:w=json.load(f)
        evidence[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
        hour=datetime.fromisoformat(plan['census_day']).replace(hour=w['hour'],tzinfo=zone).isoformat()
        for scope,values in measure(w['combos']).items():
            for metric,total in values.items():hourly.append({'hour':hour,'scope':scope,'metric':metric,'total':total,'variance':0.,'method':'census'})
    days=sorted({r['hour'][:10] for r in hourly});daily=[];weekly=[]
    def aggregate(rows):
        total=sum(r['total'] for r in rows);variance=sum(r['variance'] for r in rows)
        return {'total':total,'standard_error':math.sqrt(variance),
                'approximate_95_interval':[max(0,total-1.96*math.sqrt(variance)),total+1.96*math.sqrt(variance)]}
    for scope in scopes:
        for metric in METRICS:
            weekly.append({'scope':scope,'metric':metric,**aggregate([r for r in hourly if r['scope']==scope and r['metric']==metric])})
            for day in days:
                daily.append({'date':day,'scope':scope,'metric':metric,
                    **aggregate([r for r in hourly if r['hour'][:10]==day and r['scope']==scope and r['metric']==metric])})
    for metric in METRICS:
        expected=sum(r['totals'][metric] for r in prior['results'] if r['cohort']=='all_pure_cfb')
        total=next(r['total'] for r in weekly if r['scope']=='all_cfb' and r['metric']==metric)
        if not math.isclose(expected,total,rel_tol=1e-10):raise ValueError('scope totals fail prior-week reconciliation')
    def get(scope,metric):return next(r['total'] for r in weekly if r['scope']==scope and r['metric']==metric)
    for base in ('full_game_only','all_cfb'):
        for metric in METRICS:
            if not math.isclose(sum(get(base+':legs_'+b,metric) for b in LEG_BUCKETS),get(base,metric),rel_tol=1e-10):
                raise ValueError('leg buckets do not reconcile')
    for metric in METRICS:
        expected=sum(r['totals'][metric] for r in prior['results'] if r['cohort']=='two_leg_pure_cfb')
        if not math.isclose(get('all_cfb:legs_2',metric),expected,rel_tol=1e-10):
            raise ValueError('two-leg totals fail prior-week reconciliation')
    comparisons={k:{'full_game_only':get('full_game_only',k),'incremental_extended':get('extended_only',k),
        'including_extended':get('all_cfb',k),'increase_fraction':get('extended_only',k)/get('full_game_only',k),
        'extended_share':get('extended_only',k)/get('all_cfb',k)} for k in METRICS}
    result={'complete':True,'week_start':plan['start'],'timezone':plan['timezone'],'classified_cfb_markets':len(classified),
        'observed_player_prop_markets':sum(c['has_player_prop'] for c in classified.values()),
        'weekly':weekly,'daily':daily,'comparisons':comparisons,
        'limitations':['Player props absent from analyzed all-CFB combinations; zero observed is not a full-week census claim.',
            'Team totals and period outcomes are additional game markets, not player props.',
            'All leg counts/phases; pure CFB only; same Saturday census and random-time estimates as prior analysis.',
            'Executed volume, not fair-value edge, addressable fills or strategy profit.']}
    (study/'prop_scope_summary.json').write_text(json.dumps(result,indent=2))
    for name,rows in (('prop_scope_daily',daily),('prop_scope_hourly',hourly)):
        with (study/(name+'.csv')).open('w') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    code=[Path(__file__).resolve(),ROOT/'src/combos/cfb_market_scope.py']
    manifest={'inputs':evidence,'code_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in code},
        'sampling_plan_sha256':hashlib.sha256((study/'sampling_plan.json').read_bytes()).hexdigest(),
        'summary_sha256':hashlib.sha256((study/'prop_scope_summary.json').read_bytes()).hexdigest()}
    (study/'prop_scope_manifest.json').write_text(json.dumps(manifest,indent=2))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(12,4.5))
    for ax,metric,title in zip(axes,METRICS[:2],('YES premium traded','Payout notional traded')):
        base=[next(r['total'] for r in daily if r['date']==day and r['scope']=='full_game_only' and r['metric']==metric)/1e6 for day in days]
        extra=[next(r['total'] for r in daily if r['date']==day and r['scope']=='extended_only' and r['metric']==metric)/1e6 for day in days]
        ax.bar(range(7),base,label='Full-game ML / spread / total')
        ax.bar(range(7),extra,bottom=base,label='Includes team total or period',color='#e69f00')
        errs=[next(r['standard_error'] for r in daily if r['date']==day and r['scope']=='all_cfb' and r['metric']==metric)*1.96/1e6 for day in days]
        ax.errorbar(range(7),[a+b for a,b in zip(base,extra)],yerr=errs,fmt='none',color='black',capsize=2)
        ax.set_xticks(range(7),['Mon','Tue','Wed','Thu','Fri','Sat*','Sun']);ax.set_ylabel('$ millions');ax.set_title(title);ax.legend(fontsize=8)
    fig.suptitle('CFB combo market coverage · Aug 31–Sep 6, 2026 · All leg counts and phases')
    fig.text(.5,.01,'*Saturday census; other days sampled estimates with approximate 95% total error bars. No player-prop legs observed.',ha='center',fontsize=8)
    fig.tight_layout(rect=(0,.04,1,.94));fig.savefig(study/'prop_scope_volume.png',dpi=170);plt.close(fig)
    print(json.dumps({'observed_player_prop_markets':result['observed_player_prop_markets'],'comparisons':comparisons},indent=2))


if __name__=='__main__':main()
