"""Reprice matched RFQs over charges and risk caps; never infer acceptance/P&L."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from combos.research_capacity import CapacityReplay
from combos.research_rfq_quote import solve_quote

CHARGES={'zero':(0,0,False),'0.1c_combo':(.001,0,False),
    '0.3c_combo':(.003,0,False),'0.6c_combo':(.006,0,False),
    '0.3c_leg':(.003,0,True),'quarter_interval_plus_0.3c':(.003,.25,False)}


def run(comparison, source, out):
    inputs=[json.loads(line) for line in (comparison/'priced_decisions.jsonl').open()]
    original={r['source_seq']:r for r in json.loads(source.read_text())}
    models=sorted({r['model'] for r in inputs})
    out.mkdir(parents=True,exist_ok=False);summaries=[]
    with (out/'decisions.jsonl').open('w') as stream:
        for model in models:
            rows=sorted((r for r in inputs if r['model']==model),key=lambda r:r['source_seq'])
            for charge,(edge,reserve,per_leg) in CHARGES.items():
                for cap in (500,1000,2000):
                    for mode,lifetime in [('unfilled_expiry_3s',3),('all_admitted_fill_no_release',None)]:
                        ledger=CapacityReplay(10000,dict.fromkeys(('contract','combo','fixture'),cap),lifetime)
                        counts=Counter();bindings=Counter()
                        identity={'model':model,'charge':charge,'cap':cap,'mode':mode}
                        for row in rows:
                            o=original[row['source_seq']]
                            if o['rfq_id']!=row['rfq_id']:raise ValueError('source RFQ mismatch')
                            s=row['scenario'];p=row['research_policy'];r={**identity,'source_seq':row['source_seq'],'rfq_id':row['rfq_id']}
                            try:
                                if p['creator_status'] in ('blocked','cooldown'):raise ValueError('creator_'+p['creator_status'])
                                guards=[l['pricing_guard'] for l in s['legs']]
                                if not guards or any(g['quote_allowed'] is not True for g in guards):raise ValueError('pricing_guard_halt')
                                multiplier=min(g['risk_multiplier'] for g in guards)
                                q=solve_quote(s['independent_combo_point'],s['independent_marginal_upper'],reserve,
                                    edge*row['nlegs'] if per_leg else edge,contracts=o.get('requested_contracts'),
                                    target_cost=o.get('target_cost_dollars'),rate=p['maker_fee_rate'],ranges=terms_for(row,comparison)['price_ranges'])
                                admission=ledger.admit(row['rfq_id'],row['at'],q['fragmentation_cash_bound'],p['buckets'],risk_multiplier=multiplier)
                                r.update(quote=q,admission=admission,status='admitted' if admission['admitted'] else 'risk_rejected')
                                bindings.update(admission['binding_limits'])
                            except ValueError as exc:r.update(status='excluded',reason=str(exc))
                            counts[r['status']]+=1;stream.write(json.dumps(r,default=str)+'\n')
                        summaries.append({**identity,'counts':dict(counts),'binding_counts':dict(bindings),'peak_committed_dollars':ledger.peak/10000})
    paths=[source,comparison/'priced_decisions.jsonl',comparison/'summary.json',Path(__file__),
        Path('src/combos/research_capacity.py'),Path('src/combos/research_rfq_quote.py')]
    summary={'scenarios':summaries,'rows_per_model':{m:sum(r['model']==m for r in inputs) for m in models},
        'hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        'limitations':['no acceptance probability or outcome observations',
            'higher asks mechanically lower full-size NO-buy cash requirements; not evidence of better execution',
            'quarter interval includes spreads, source disagreement and uncertainty padding; not pure liquidity',
            'all source pricing, fee/grid and native-unit assumptions inherited from research capture']}
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps({'scenarios':len(summaries),'rows_per_model':summary['rows_per_model']}))


_terms_cache={}
def terms_for(row,comparison):
    key=str(comparison)
    if key not in _terms_cache:
        summary=json.loads((comparison/'summary.json').read_text())
        paths=[Path(p) for p in summary['hashes'] if p.endswith('/runtime.json')]
        if len(paths)!=1:raise ValueError('unique captured runtime required')
        path=paths[0]
        if hashlib.sha256(path.read_bytes()).hexdigest()!=summary['hashes'][str(path)]:raise ValueError('runtime changed')
        _terms_cache[key]=json.loads(path.read_text())['combo_terms']
    # The replay's retained fee reference identifies the original series terms.
    candidates=[v for v in _terms_cache[key].values() if v['fee_reference']==row['research_policy']['fee_reference']]
    if not candidates or any(v!=candidates[0] for v in candidates):raise ValueError('ambiguous captured fee/grid terms')
    return candidates[0]


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('comparison','source','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.comparison,a.source,a.out)
