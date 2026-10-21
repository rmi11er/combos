"""Add auditable hourly aggregates and Thursday-evening share to the week study."""
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]


def report(directory):
    summary=json.loads((directory/'summary.json').read_text());plan=summary['plan']
    raw=ROOT/'data/raw'/('cfb_week_'+plan['start'].replace('-',''))
    db=sqlite3.connect(raw/'metadata.sqlite')
    cfbs={t:json.loads(c) for t,c in db.execute("SELECT ticker,classification FROM markets WHERE json_extract(classification,'$.pure_cfb')=1")};db.close()
    metrics=('yes_premium_dollars','payout_notional_dollars','prints')
    def counts(trades,cohort):
        totals=defaultdict(Decimal)
        for t in trades:
            c=cfbs.get(t['ticker'])
            if not c or cohort=='two_leg_pure_cfb' and c['nlegs']!=2:continue
            q=Decimal(t['count_fp']);p=Decimal(t['yes_price_dollars'])
            totals['prints']+=1;totals['yes_premium_dollars']+=q*p;totals['payout_notional_dollars']+=q
        return {k:float(totals[k]) for k in metrics}
    strata=defaultdict(list);zone=ZoneInfo('America/Chicago')
    for start,end in plan['windows']:
        w=json.loads((raw/str(start)/'complete.json').read_text())
        key=datetime.fromtimestamp(start,zone).replace(minute=0,second=0,microsecond=0).isoformat()
        for cohort in ('all_pure_cfb','two_leg_pure_cfb'):strata[(key,cohort)].append(counts(w['combos'],cohort))
    hourly=[]
    for (key,cohort),cells in sorted(strata.items()):
        n=len(cells);N=3600/plan['cell_seconds']
        for metric in metrics:
            values=[c[metric] for c in cells];mean=sum(values)/n
            variance=N*N*(1-n/N)*sum((v-mean)**2 for v in values)/(n-1)/n
            hourly.append({'hour':key,'cohort':cohort,'metric':metric,'total':N*mean,'variance':variance,'method':'stratified_estimate'})
    for p in sorted((ROOT/'data/derived/tape').glob('hour_*.json.gz')):
        with gzip.open(p,'rt') as f:w=json.load(f)
        key=f"{plan['census_day']}T{w['hour']:02d}:00:00-05:00"
        for cohort in ('all_pure_cfb','two_leg_pure_cfb'):
            for metric,total in counts(w['combos'],cohort).items():
                hourly.append({'hour':key,'cohort':cohort,'metric':metric,'total':total,'variance':0.,'method':'census'})
    with (directory/'hourly.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(hourly[0]));writer.writeheader();writer.writerows(sorted(hourly,key=lambda r:(r['hour'],r['cohort'],r['metric'])))
    segments=[]
    for cohort in ('all_pure_cfb','two_leg_pure_cfb'):
        for metric in metrics:
            rows=[r for r in hourly if r['cohort']==cohort and r['metric']==metric]
            expected=sum(r['totals'][metric] for r in summary['results'] if r['cohort']==cohort)
            if not math.isclose(sum(r['total'] for r in rows),expected,rel_tol=1e-10):raise ValueError('hourly/daily totals disagree')
            for label,start in (('Thursday through Saturday','2026-09-03T00:00:00-05:00'),
                                ('Thursday 6pm through Saturday midnight','2026-09-03T18:00:00-05:00')):
                inside=[r for r in rows if start<=r['hour']<'2026-09-06T00:00:00-05:00']
                outside=[r for r in rows if r not in inside]
                a=sum(r['total'] for r in inside);b=sum(r['total'] for r in outside)
                va=sum(r['variance'] for r in inside);vb=sum(r['variance'] for r in outside)
                share=a/(a+b);se=math.sqrt(b*b*va+a*a*vb)/(a+b)**2
                segments.append({'cohort':cohort,'metric':metric,'window':label,'share':share,
                    'approximate_95_share_interval':[max(0,share-1.96*se),min(1,share+1.96*se)]})
    artifact={'segments':segments,'code_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
              for p in (Path(__file__).resolve(),ROOT/'scripts/cfb_week_volume.py')},
              'hourly_sha256':hashlib.sha256((directory/'hourly.csv').read_bytes()).hexdigest()}
    (directory/'timing_summary.json').write_text(json.dumps(artifact,indent=2))
    print(json.dumps(segments,indent=2))


if __name__=='__main__':report(ROOT/'runs/cfb_week_20260831')
