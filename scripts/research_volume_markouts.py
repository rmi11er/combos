"""Coverage-checked NFL volume clock and time/volume markout study."""
import argparse
from collections import Counter
from datetime import datetime
import gzip
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from nfl_moneyline_replay import certified_days

TZ=ZoneInfo('America/Chicago')
SPLIT='2026-01-12'


def prior_volume(times, quantities, queries, starts):
    """Sum [start, query), excluding all simultaneous prints at query."""
    times=np.asarray(times); quantities=np.asarray(quantities)
    if np.any(np.diff(times)<0): raise ValueError('unsorted tape')
    sums=np.r_[0.,np.cumsum(quantities)]
    return sums[np.searchsorted(times,queries,side='left')]-sums[np.searchsorted(times,starts,side='left')]


def date_at(at):return datetime.fromtimestamp(at,TZ).date().isoformat()


def describe(f):
    y=f['markout'].to_numpy();q=f['quantity'].to_numpy()
    daily=f.groupby('date').markout.mean().to_numpy()
    # Date clusters preserve within-day dependence but cannot remove cross-day fixture dependence.
    rng=np.random.default_rng(20260910)
    ci=np.quantile(np.mean(rng.choice(daily,size=(2000,len(daily)),replace=True),axis=1),[.025,.975]) if len(daily)>1 else [np.nan,np.nan]
    return {'prints':len(f),'dates':len(daily),'mean_cents':float(np.mean(y)),
        'contract_weighted_cents':float(np.average(y,weights=q)),
        'median_cents':float(np.median(y)), 'positive_fraction':float(np.mean(y>0)),
        'equal_date_mean_cents':float(np.mean(daily)),
        'equal_date_bootstrap_95':[float(x) if np.isfinite(x) else None for x in ci]}


def run(out):
    days=certified_days(ROOT/'runs/nfl_playoffs_history_20260907')
    tape=[];seen=set();scope=Counter()
    for date,cohort,s,_ in days:
        with gzip.open(cohort/'candidate_trades.jsonl.gz','rt') as f:
            for line in f:
                r=json.loads(line);t=r['trade'];c=r['classification']
                scope['fullgame_distinct_2to4_pregame']+=1
                if c['series']!=['KXNFLGAME']:continue
                assert t['trade_id'] not in seen;seen.add(t['trade_id'])
                at=datetime.fromisoformat(t['created_time'].replace('Z','+00:00')).timestamp()
                assert s['start_at']<=at<s['end_at']
                tape.append({'id':t['trade_id'],'at':at,'date':date,'start':c['earliest_scheduled_start'],
                    'quantity':float(t['count_fp']),'principal':float(t['count_fp'])*float(t['yes_price_dollars']),
                    'nlegs':c['nlegs'],'price':float(t['yes_price_dollars']),'taker':t.get('taker_side')})
        print('verified tape',date,len(tape),flush=True)
    tape=pd.DataFrame(tape).sort_values(['at','id']).reset_index(drop=True)
    tape['lead_hours']=(tape.start-tape['at'])/3600
    daily=tape.groupby('date').agg(contracts=('quantity','sum'),principal=('principal','sum'),prints=('id','size'))
    thresholds=np.quantile(daily.loc[daily.index<SPLIT,'contracts'],[1/3,2/3])
    daily['bucket']=np.array(['low','medium','high'])[np.searchsorted(thresholds,daily.contracts,side='right')]
    # Equal observation window avoids mechanically different lifetime totals.
    edges=np.array([1/60,.25,1,3,6,12,24,48,72,120.])
    clocks=[]
    for start,group in tape.groupby('start'):
        if start-120*3600<days[0][2]['start_at'] or start>days[-1][2]['end_at']:continue
        g=group[(group.lead_hours>=edges[0])&(group.lead_hours<=edges[-1])]
        record={'first_start':float(start),'date':date_at(start),'period':'train' if date_at(start)<SPLIT else 'test','bins':[]}
        for lo,hi in zip(edges[:-1],edges[1:]):
            b=g[(g.lead_hours>=lo)&(g.lead_hours<hi)]
            record['bins'].append({'lo_hours':lo,'hi_hours':hi,'prints':len(b),
                'contracts':float(b.quantity.sum()),'principal':float(b.principal.sum()),
                'contracts_per_minute':float(b.quantity.sum()/((hi-lo)*60))})
        for metric in ['contracts','principal','prints']:
            total=sum(b[metric] for b in record['bins']);record[metric]=total
            for b in record['bins']:b[metric+'_share']=b[metric]/total if total else None
        clocks.append(record)
    # Train the clock shape on earlier first-kickoff cohorts. Forecast remaining
    # volume from observed volume / historical elapsed share; no final test totals.
    train=[c for c in clocks if c['period']=='train' and c['contracts']>0]
    forecasts=[]
    for lead in [48,24,12,6,3,1]:
        fractions=[sum(b['contracts_share'] for b in c['bins'] if b['lo_hours']>=lead) for c in train]
        elapsed=float(np.mean(fractions))
        for c in clocks:
            if c['period']!='test' or elapsed<=0:continue
            observed=sum(b['contracts'] for b in c['bins'] if b['lo_hours']>=lead)
            actual=c['contracts']-observed
            forecast=observed*(1-elapsed)/elapsed
            forecasts.append({'date':c['date'],'first_start':c['first_start'],'lead_hours':lead,
                'training_elapsed_share':elapsed,'observed_contracts':observed,'actual_remaining':actual,
                'forecast_remaining':forecast,'absolute_error':abs(forecast-actual),
                'constant_pace_remaining':observed/(120-lead)*(lead-1/60)})
    panel=[json.loads(l) for l in gzip.open(out/'nfl_panel.jsonl.gz','rt')]
    base=pd.DataFrame([{'id':r['evaluation_id'],'at':r['at'],'date':date_at(r['at']),
        'quantity':r['quantity'],'premium':r['yes_price'],'nlegs':r['source']['nlegs'],
        'lead':r['hours_to_first_start'],'spread':r['mean_leg_spread'],'age':r['entry_max_age_seconds'],
        'edge_cents':100*(r['yes_price']-r['fair_point']-r['maker_fee']/r['quantity'])} for r in panel])
    midnight=[datetime.fromisoformat(d).replace(tzinfo=TZ).timestamp() for d in base.date]
    base['prior_hour']=prior_volume(tape['at'],tape.quantity,base['at'],base['at']-3600)
    base['day_so_far']=prior_volume(tape['at'],tape.quantity,base['at'],midnight)
    activity_cuts=np.quantile(base.loc[base.date<SPLIT,'prior_hour'],[1/3,2/3])
    base['activity_bucket']=np.array(['low','medium','high'])[np.searchsorted(activity_cuts,base.prior_hour,side='right')]
    base['daily_bucket']=base.date.map(daily.bucket)
    base['lead_bucket']=pd.cut(base.lead,[0,1,6,24,1e6],labels=['<1h','1-6h','6-24h','24h+'],right=False).astype(str)
    base['premium_bucket']=pd.cut(base.premium,[0,.1,.25,.5,1.01],labels=['<10c','10-25c','25-50c','50c+'],right=False).astype(str)
    base['spread_bucket']=pd.cut(base.spread,[0,.010001,.020001,1.01],labels=['<=1c','1-2c','>2c'],right=False).astype(str)
    base['period']=np.where(base.date<SPLIT,'train','test')
    summaries=[]; regressions=[]
    for horizon in ['60','300','900','3600','close']:
        f=base.copy()
        f['markout']=[r['marks'][horizon].get('seller_net_markout_cents',np.nan) for r in panel]
        f['future_age']=[r['marks'][horizon].get('max_age_seconds',np.nan) for r in panel]
        for selection in ['all','edge03']:
            for freshness in [None,180,600]:
                sub=f[f.markout.notna()]
                if selection=='edge03':sub=sub[sub.edge_cents>=.3]
                if freshness is not None:sub=sub[(sub.age<=freshness)&(sub.future_age<=freshness)]
                for dimensions in [('period',),('period','activity_bucket'),('period','daily_bucket'),('period','lead_bucket'),('period','premium_bucket'),('period','spread_bucket'),('period','nlegs'),('period','activity_bucket','lead_bucket')]:
                    for key,g in sub.groupby(list(dimensions),observed=True):
                        summaries.append({'horizon':horizon,'selection':selection,'max_age':freshness,
                            **dict(zip(dimensions,key if isinstance(key,tuple) else (key,))),**describe(g)})
        # Out-of-period predictive comparison; no in-sample significance claim.
        sub=f[f.markout.notna()&(f.age<=180)&(f.future_age<=180)].copy()
        common=[np.ones(len(sub)),sub.edge_cents,sub.premium,sub.premium**2,sub.nlegs,sub.spread,np.log1p(sub.age)]
        for name,extra in [('controls',[]),('volume',[np.log1p(sub.prior_hour),np.log1p(sub.day_so_far)]),
                           ('time',[np.log1p(sub.lead)]),('volume_time',[np.log1p(sub.prior_hour),np.log1p(sub.day_so_far),np.log1p(sub.lead)])]:
            X=np.column_stack(common+extra); y=sub.markout.to_numpy();tr=(sub.date<SPLIT).to_numpy()
            beta=np.linalg.lstsq(X[tr],y[tr],rcond=None)[0];pred=X[~tr]@beta
            regressions.append({'horizon':horizon,'model':name,'train':int(tr.sum()),'test':int((~tr).sum()),
                'test_mae_cents':float(np.mean(abs(pred-y[~tr]))),'test_rmse_cents':float(np.sqrt(np.mean((pred-y[~tr])**2))),
                'coefficients':beta.tolist()})
    result={'scope_counts':dict(scope),'moneyline_tape_prints':len(tape),'daily':daily.reset_index().to_dict('records'),
        'daily_training_cutpoints':thresholds.tolist(),'causal_hour_training_cutpoints':activity_cuts.tolist(),
        'clocks':clocks,'remaining_volume_forecasts':forecasts,'markouts':summaries,'predictive_checks':regressions,
        'limitations':['Only 14 dates; observed first-kickoff groups listed explicitly and are not independent trials.',
            'Clock is distinct-fixture 2-4-leg moneyline combo tape, both taker sides, final120h to1min before kickoff.',
            'Daily buckets use final daily volume and are descriptive only; causal hour excludes simultaneous prints.',
            'Date bootstrap intervals omit cross-day fixture dependence and are descriptive uncertainty only.',
            'Test period starts Jan12; historical archive previously researched, not an untouched holdout.',
            'Quotes are candle proxies; unavailable depth prevents executable capacity claims.']}
    (out/'volume_markouts.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    base.to_json(out/'volume_features.jsonl.gz',orient='records',lines=True,compression='gzip')
    print(json.dumps({'tape_prints':len(tape),'clock_groups':len(clocks),'summary_cells':len(summaries),'predictive_checks':regressions},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);run(p.parse_args().out)
