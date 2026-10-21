#!/usr/bin/env python3
"""Independently reconstruct exchange-only points from retained pricing context."""
import argparse
from collections import Counter
from decimal import Decimal as D
import gzip
import hashlib
import json
from pathlib import Path

MODELS={'kalshi':D(0),'polymarket':D(1),'exchange_blend_equal':D('.5'),'exchange_blend_pm75':D('.75')}


def close(actual,expected):
    if abs(D(str(actual))-expected)>D('0.0000000001'):
        raise ValueError(f'fair arithmetic differs: {actual} versus {expected}')


def leg_points(context,at):
    k,p=context['kalshi'],context['polymarket']
    for source in (k,p):
        if source['available_at']>at:
            raise ValueError('future source availability')
    close(k['available_at'],k['source_at']+D(60))
    close(p['available_at'],p['state_at']+D(60))
    bid,ask=k['yes_bid'],k['yes_ask']
    if not D(0)<=bid<=ask<=D(1):raise ValueError('invalid Kalshi book')
    kp=(bid+ask)/2
    rate=k['fee_basis']['taker_rate']
    expected={'lower':max(D(0),bid-rate*bid*(1-bid)), 'point':kp,
              'upper':min(D(1),ask+rate*ask*(1-ask))}
    for key,value in expected.items():close(k['interval'][key],value)
    pp=p['interval']['point']
    if not D(0)<=pp<=D(1):raise ValueError('invalid PM probability')
    half=min((ask-bid)/2,pp,1-pp)
    pb,pa=pp-half,pp+half
    rate=p['fee_rate']
    close(p['interval']['lower'],max(D(0),pb-rate*pb*(1-pb)))
    close(p['interval']['upper'],min(D(1),pa+rate*pa*(1-pa)))
    for model,weight in MODELS.items():
        if model in ('kalshi','polymarket'):continue
        for key in ('lower','point','upper'):
            close(context[model]['interval'][key],k['interval'][key]*(1-weight)+p['interval'][key]*weight)
    return {model:kp*(1-weight)+pp*weight for model,weight in MODELS.items()}


def audit(context_path,decisions_path):
    points={};context_count=0
    with gzip.open(context_path,'rt') as stream:
        for line in stream:
            r=json.loads(line,parse_float=D);context_count+=1
            if not r['context'] or any('kalshi' not in c or 'polymarket' not in c for c in r['context']):continue
            if len(r['legs'])!=len(r['context']):raise ValueError('leg/context mismatch')
            product={m:D(1) for m in MODELS}
            for leg,c in zip(r['legs'],r['context']):
                if leg['side'] not in ('yes','no'):raise ValueError('unknown leg orientation')
                for model,point in leg_points(c,r['at']).items():
                    product[model]*=point if leg['side']=='yes' else 1-point
            if r['evaluation_id'] in points:raise ValueError('duplicate context')
            points[r['evaluation_id']]=(r['at'],product)
    counts=Counter();seen=set()
    with gzip.open(decisions_path,'rt') as stream:
        for line in stream:
            r=json.loads(line,parse_float=D)
            key=(r['evaluation_id'],r['model'])
            if key in seen:raise ValueError('duplicate decision')
            seen.add(key)
            at,product=points[r['evaluation_id']]
            if r['at']!=at:raise ValueError('decision/context time mismatch')
            close(r['fair_point'],product[r['model']]);counts[r['model']]+=1
    if set(counts)!=set(MODELS) or len(set(counts.values()))!=1:raise ValueError('unequal or empty model cohort')
    return {'passed':True,'context_rows':context_count,'verified_decisions':dict(counts),
            'limitations':['Recorded context arithmetic, not independent reconstruction from raw venue responses.',
                          'PM point semantics, payoff parity and historical fee applicability remain unverified here.',
                          'Independence point only; stressed joint upper bounds and live liquidity weighting are not certified.']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('context','decisions','out'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();result=audit(args.context,args.decisions)
    result['hashes']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (args.context,args.decisions,Path(__file__))}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':main()
