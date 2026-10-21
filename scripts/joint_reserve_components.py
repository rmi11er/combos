#!/usr/bin/env python3
"""Separate marginal uncertainty from the retained joint moment reserve."""
import argparse
from collections import defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path

MODELS=('kalshi','polymarket','exchange_blend_equal','exchange_blend_pm75')


def independent_upper(legs,contexts,model):
    if len(legs)!=len(contexts):raise ValueError('leg/context mismatch')
    values=[]
    for leg,context in zip(legs,contexts):
        interval=context[model]['interval']
        if leg['side']=='yes':value=interval['upper']
        elif leg['side']=='no':value=1-interval['lower']
        else:raise ValueError('invalid side')
        if not 0<=value<=1:raise ValueError('invalid marginal bound')
        values.append(value)
    return math.prod(values)


def analyze(cohorts):
    groups=defaultdict(lambda:defaultdict(float));hashes={}
    for cohort in cohorts:
        context_path=cohort/'replay/pricing_context.jsonl.gz'
        decision_path=cohort/'common_model_report/unconstrained_decisions.jsonl.gz'
        for path in (context_path,decision_path):hashes[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
        bounds={}
        with gzip.open(context_path,'rt') as stream:
            for line in stream:
                row=json.loads(line)
                if not row['context'] or any(any(m not in c for m in MODELS) for c in row['context']):continue
                if row['evaluation_id'] in bounds:raise ValueError('duplicate context')
                bounds[row['evaluation_id']]={m:independent_upper(row['legs'],row['context'],m) for m in MODELS}
        with gzip.open(decision_path,'rt') as stream:
            for line in stream:
                r=json.loads(line);q=r['quantity'];upper=bounds[r['evaluation_id']][r['model']]
                assert r['fair_point']<=upper+1e-10 and upper<=r['stressed_upper']+1e-8
                g=groups[(r['model'],r['source']['nlegs'])];g['prints']+=1;g['quantity']+=q
                g['marginal_reserve_dollars']+=q*(upper-r['fair_point'])
                g['joint_reserve_dollars']+=q*(r['stressed_upper']-upper)
                for name,reference in (('point',r['fair_point']),('independent_upper',upper),('stressed',r['stressed_upper'])):
                    edge=q*(r['yes_price']-reference)-r['maker_fee']
                    passes=r['quote_allowed'] and edge>=r['required_net_edge']
                    if name=='point':assert passes==r['accepted'] and r['entry_basis']=='point'
                    if passes:
                        g[name+'_prints']+=1;g[name+'_quantity']+=q
                        g[name+'_net']+=q*(r['yes_price']-r['yes_settlement'])-r['maker_fee']
                        g[name+'_edge']+=edge
        del bounds
    rows=[]
    for (model,legs),g in sorted(groups.items()):
        for mode in ('point','independent_upper','stressed'):
            for field in ('prints','quantity','net','edge'):g[mode+'_'+field]+=0
        rows.append({'model':model,'legs':legs,**g,
                     'marginal_reserve_cents':100*g['marginal_reserve_dollars']/g['quantity'],
                     'additional_joint_reserve_cents':100*g['joint_reserve_dollars']/g['quantity']})
    return {'rows':rows,'input_hashes':hashes,'limits':['Independence with marginal upper endpoints is an explicit alternative assumption, not a dependence-robust bound.',
        'Same observed prices/full quantities and retained fees/hurdles; no capital reallocation, actual fills or price-grid simulation.',
        'Exchange-only recorded intervals; not a live three-source fair validation.']}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cohort',type=Path,action='append',required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();r=analyze(a.cohort);r['script_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(r,indent=2)+'\n');print('completed',len(a.cohort),'dates')


if __name__=='__main__':main()
