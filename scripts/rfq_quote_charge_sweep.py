"""Quote/size sensitivity on captured three-source scenarios; never simulates fills."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from combos.research_rfq_quote import solve_quote


def run(source, out):
    raw=source.read_bytes(); inputs=json.loads(raw); rows=[]; summaries=[]
    for alpha in (0,.25,1):
        for edge_name in ('zero','0.1c_combo','0.3c_combo','0.3c_leg'):
            subset=[]
            for r in inputs:
                if r['status']!='scenario_priced':continue
                s=next(s for s in r['scenarios'] if s['assumed_usd_per_native_unit']==1)
                edge={'zero':0,'0.1c_combo':.001,'0.3c_combo':.003,'0.3c_leg':.003*r['nlegs']}[edge_name]
                row={'source_seq':r['source_seq'],'rfq_id':r['rfq_id'],'reserve_fraction':alpha,'edge_policy':edge_name,'nlegs':r['nlegs']}
                try:
                    row.update(solve_quote(s['independent_combo_point'],s['independent_marginal_upper'],alpha,edge,
                        contracts=r.get('requested_contracts'),target_cost=r.get('target_cost_dollars')))
                    row['status']='priced'
                except ValueError as exc:row.update(status='excluded',reason=str(exc))
                subset.append(row);rows.append(row)
            ok=[r for r in subset if r['status']=='priced']
            import statistics
            summaries.append({'reserve_fraction':alpha,'edge_policy':edge_name,'counts':dict(Counter(r['status'] for r in subset)),
                'median_yes_ask':float(statistics.median(r['yes_ask'] for r in ok)) if ok else None,
                'median_cash_bound':float(statistics.median(r['fragmentation_cash_bound'] for r in ok)) if ok else None,
                'isolated_cash_bound_over_10k':sum(r['fragmentation_cash_bound']>10000 for r in ok)})
    out.mkdir(parents=True,exist_ok=False)
    summary={'input_sha256':hashlib.sha256(raw).hexdigest(),'input_census':len(inputs),'scenarios':summaries,
             'assumptions':{'grid_tick':'.0001','maker_rate':'.035','balance_precision':'.0001','usd_per_native_stake':1},
             'limitations':['scenario grid and account precision not certified','target size is a conservative bound','no portfolio allocation or creator policy yet','no fills or profitability inferred']}
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    (out/'decisions.json').write_text(json.dumps(rows,default=str))
    return summary

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();print(json.dumps(run(a.source,a.out),indent=2))
