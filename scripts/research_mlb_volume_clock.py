"""MLB July-to-August replication of the final-six-hour combo volume clock."""
import argparse
from collections import defaultdict
from datetime import datetime
import gzip
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def run(out):
    clocks=[];hashes={};seen=set();counts=[];edges=[1/60,.25,.5,1,2,3,4,5,6]
    for path in sorted((ROOT/'runs/mlb_historical_20260907/dated_fee_primary').glob('2026-0[78]-*/cohort/summary.json')):
        summary=json.loads(path.read_text());assert summary['complete_census']
        spans=[]
        for source in summary['sources']:
            p=Path(source['path']);h=hashlib.sha256(p.read_bytes()).hexdigest();assert h==source['sha256']
            hashes[str(p.relative_to(ROOT))]=h;spans.append((source['start_at'],source['end_at']))
            assert source['method']=='census'
        spans.sort();assert len(spans)==24 and spans[0][0]==summary['start_at'] and spans[-1][1]==summary['end_at']
        assert all(a[1]==b[0] for a,b in zip(spans,spans[1:]))
        tape=path.parent/'candidate_trades.jsonl.gz';hashes[str(tape.relative_to(ROOT))]=hashlib.sha256(tape.read_bytes()).hexdigest()
        groups=defaultdict(list);n=0
        with gzip.open(tape,'rt') as f:
            for line in f:
                r=json.loads(line);c=r['classification'];t=r['trade']
                if not (c['series']==['KXMLBGAME'] and c['distinct_fixtures'] and 2<=c['nlegs']<=4 and r['pregame_scheduled_proxy']):continue
                assert t['trade_id'] not in seen;seen.add(t['trade_id']);n+=1
                at=datetime.fromisoformat(t['created_time'].replace('Z','+00:00')).timestamp();start=c['earliest_scheduled_start']
                assert summary['start_at']<=at<summary['end_at']
                # A complete intraday final-six-hour window; no bridging missing dates.
                if start-6*3600<summary['start_at'] or start>summary['end_at']:continue
                lead=(start-at)/3600
                if not edges[0]<=lead<edges[-1]:continue
                q=float(t['count_fp']);groups[start].append((lead,q,q*float(t['yes_price_dollars']),c['nlegs'],float(t['yes_price_dollars'])))
        for start,rows in sorted(groups.items()):
            values=np.array(rows);bins=[]
            for lo,hi in zip(edges[:-1],edges[1:]):
                g=values[(values[:,0]>=lo)&(values[:,0]<hi)]
                bins.append({'lo_hours':lo,'hi_hours':hi,'prints':len(g),'contracts':float(g[:,1].sum()),'principal':float(g[:,2].sum()),
                    'contracts_per_minute':float(g[:,1].sum()/((hi-lo)*60))})
            total=sum(b['contracts'] for b in bins)
            for b in bins:b['contracts_share']=b['contracts']/total
            clocks.append({'date':summary['date'],'first_start':start,'period':'train' if summary['date']<'2026-08' else 'test',
                'contracts':total,'prints':len(rows),'bins':bins})
        counts.append({'date':summary['date'],'scoped_tape_prints':n,'clock_prints':sum(len(g) for g in groups.values()),'clock_groups':len(groups)})
        print(counts[-1],flush=True)
    forecasts=[];train=[c for c in clocks if c['period']=='train']
    # Equal-day training prevents a day with many kickoff slots dominating shape.
    for lead in [.25,.5,1,2,3,4,5]:
        byday=defaultdict(list)
        for c in train:byday[c['date']].append(sum(b['contracts_share'] for b in c['bins'] if b['lo_hours']>=lead))
        elapsed=float(np.mean([np.mean(v) for v in byday.values()]))
        for c in clocks:
            if c['period']!='test':continue
            observed=sum(b['contracts'] for b in c['bins'] if b['lo_hours']>=lead);actual=c['contracts']-observed
            forecast=observed*(1-elapsed)/elapsed;constant=observed/(6-lead)*(lead-1/60)
            forecasts.append({'date':c['date'],'first_start':c['first_start'],'lead_hours':lead,'actual_remaining':actual,
                'forecast_remaining':forecast,'constant_pace_remaining':constant,'training_elapsed_share':elapsed,
                'observed_contracts':observed,'absolute_error':abs(forecast-actual)})
    result={'dates':counts,'clocks':clocks,'forecasts':forecasts,'hashes':hashes,'limitations':[
        'Retained complete dates listed individually, not complete July/August. Only same-day fully observed final6h to1min windows.',
        'Pure 2-4 distinct-fixture MLB moneyline combos, both taker sides; no fair-price conditioning.',
        'Native scheduled New York clock is a proxy, not verified actual first pitch.',
        'First-start groups with no observed eligible prints are absent; active-group conditional curves, not a listed-universe census.',
        'July-trained equal-day shape; August later-period replication previously available to research.',
        'Observed total volume does not identify directionally offsetting future fills.']}
    (out/'mlb_volume_clock.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);run(p.parse_args().out)
