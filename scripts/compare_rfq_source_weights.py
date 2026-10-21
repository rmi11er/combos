"""Matched causal source-weight research; no outcomes, executions or promotion."""
import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from combos.event_store import EventStore
from combos.rfq_scenario_consumer import RFQScenarioConsumer
from combos.research_quote_consumer import ResearchQuoteConsumer
from combos.weighted_fair import WeightPolicy


def distribution(values):
    values=sorted(values)
    return {'count':len(values), 'median':statistics.median(values),
            'p05':values[round((len(values)-1)*.05)], 'p95':values[round((len(values)-1)*.95)],
            'min':values[0], 'max':values[-1]} if values else None


def run(capture, catalog_path, config_path, out, runtime_path=None):
    config=json.loads(config_path.read_text())
    runtime=json.loads((runtime_path or (capture/'runtime.json')).read_text())
    weights=json.loads((capture/'weighting.json').read_text())
    catalog=json.loads(catalog_path.read_text())
    consumers={name:ResearchQuoteConsumer(RFQScenarioConsumer(runtime,catalog,
        WeightPolicy(**{**weights,**overrides})),runtime,config['quote_policy'])
        for name,overrides in config['models'].items()}
    baseline=next(iter(consumers))
    out.mkdir(parents=True,exist_ok=False)
    counts={name:Counter() for name in consumers}
    records={name:{} for name in consumers}
    store=EventStore(capture/'events.sqlite');seq=0;rfqs=0;began=time.monotonic()
    with (out/'priced_decisions.jsonl').open('w') as stream:
        try:
            while True:
                events=store.read(seq,1000)
                if not events:break
                for event in events:
                    seq=event['seq'];seen=[]
                    for name,consumer in consumers.items():
                        row=consumer.consume(event)
                        if row is None:continue
                        seen.append(name)
                        counts[name][row.get('reason',row['status'])]+=1
                        if row['status']=='scenario_priced':
                            scenario=next(s for s in row['scenarios'] if s['assumed_usd_per_native_unit']==1)
                            policy=row['research_policy']
                            counts[name]['policy:'+policy['status']]+=1
                            record={'model':name,'source_seq':seq,'rfq_id':row['rfq_id'],'at':row['at'],
                                'nlegs':row['nlegs'],'scenario':scenario,'research_policy':policy}
                            records[name][seq]=record
                            stream.write(json.dumps(record)+'\n')
                    if seen:
                        if len(seen)!=len(consumers):raise ValueError('RFQ census mismatch')
                        rfqs+=1
                (out/'progress.json').write_text(json.dumps({'seq':seq,'rfqs':rfqs,'elapsed_seconds':time.monotonic()-began}))
        finally:store.close()
    common=set.intersection(*(set(rows) for rows in records.values()))
    comparisons={}
    for name,rows in records.items():
        deltas=[];asks=[];changed=0;legweights={venue:[] for venue in ('kalshi','polymarket','pinnacle')}
        for seq in sorted(common):
            row=rows[seq];base=records[baseline][seq]
            deltas.append(100*(row['scenario']['independent_combo_point']-base['scenario']['independent_combo_point']))
            for leg in row['scenario']['legs']:
                for venue in legweights:legweights[venue].append(leg['weights'][venue])
            a,b=row['research_policy'],base['research_policy']
            changed+=(a['status']=='reserved_scenario')!=(b['status']=='reserved_scenario')
            if 'quote' in a and 'quote' in b:
                # Exact quote field discovered/validated by the shared solver.
                asks.append(100*(float(a['quote']['yes_ask'])-float(b['quote']['yes_ask'])))
        comparisons[name]={'priced_rfqs':len(rows),'counts':dict(counts[name]),
            'common_fair_difference_cents':distribution(deltas),
            'common_quote_difference_cents':distribution(asks),
            'common_admission_disagreements':changed,
            'common_leg_weights':{v:distribution(xs) for v,xs in legweights.items()},
            'peak_reserved_dollars':consumers[name].risk.peak/10000}
    paths=[catalog_path,config_path,(runtime_path or (capture/'runtime.json')),capture/'weighting.json',Path(__file__),
        *[Path('src/combos')/p for p in ('rfq_scenario_consumer.py','weighted_fair.py','research_quote_consumer.py','research_rfq_quote.py','research_capacity.py')]]
    summary={'rfqs':rfqs,'common_priced_rfqs':len(common),'last_seq':seq,'baseline':baseline,
        'models':comparisons,'configuration':config,
        'effective_weights':{n:asdict(c.pricing.policy) for n,c in consumers.items()},
        'hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        'limitations':['no settlement outcomes or observed acceptance','two-minute captured slate',
            'all admitted RFQs assumed filled without release; not a fill forecast',
            'Pinnacle unit/payoff and sampled grid assumptions remain research-only',
            'equal score priors still produce unequal liquidity/freshness weights',
            'pricing risk multiplier applied by default; explicit false is legacy ablation']}
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps({k:v for k,v in summary.items() if k in ('rfqs','common_priced_rfqs','models')},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('capture','catalog','config','out'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--runtime', type=Path, default=None,
                        help='optional candidate runtime; defaults to capture/runtime.json')
    args=parser.parse_args();run(args.capture,args.catalog,args.config,args.out,args.runtime)
