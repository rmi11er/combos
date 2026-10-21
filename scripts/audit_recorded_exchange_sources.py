#!/usr/bin/env python3
"""Verify recorded Kalshi states and PM as-of selections against raw captures."""
import argparse
from bisect import bisect_right
from collections import Counter
from decimal import Decimal as D
import gzip
import hashlib
import json
import math
from pathlib import Path


def read(path):
    with gzip.open(path,'rt') as f:return json.load(f,parse_float=D)


def price(obj,schema):
    if 'close_dollars' in obj:return D(str(obj['close_dollars']))
    value=obj['close']
    if schema=='historical_decimal_dollars' and isinstance(value,str) and '.' in value:return D(value)
    if schema=='legacy_integer_cents' and type(value) is int:return D(value)/100
    raise ValueError('unverified raw price encoding')


def audit(context_path,exchange):
    cache={};hashes={};counts=Counter()
    max_pm_rounding=D(0)
    def load(path):
        path=Path(path).resolve()
        if path not in cache:
            hashes[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
            cache[path]=read(path)
        return cache[path]
    pm_indexes={};k_indexes={}
    with gzip.open(context_path,'rt') as f:
        for line in f:
            row=json.loads(line,parse_float=D);counts['context_rows']+=1
            if len(row['legs'])!=len(row['context']):
                if row.get('pricing_block_reason'):continue
                raise ValueError('context length mismatch')
            for leg,c in zip(row['legs'],row['context']):
                if 'kalshi' in c:
                    k=c['kalshi'];prov=k['source_provenance'];path=Path(prov['file']).resolve();env=load(path)
                    assert hashes[str(path)]==prov['sha256']
                    assert env.get('status',200)==200
                    assert env['payload'].get('ticker',leg['market_ticker'])==leg['market_ticker']
                    if path not in k_indexes:
                        index={}
                        for value in env['payload']['candlesticks']:
                            index.setdefault(value['end_period_ts'],[]).append(value)
                        k_indexes[path]=index
                    matches=k_indexes[path].get(k['source_at'],[])
                    valid=[]
                    for value in matches:
                        try:valid.append((price(value['yes_bid'],prov['candle_price_schema']),price(value['yes_ask'],prov['candle_price_schema'])))
                        except (KeyError,TypeError,ValueError):pass
                    assert (k['yes_bid'],k['yes_ask']) in valid
                    assert k['source_at']+60<=row['at']
                    counts['kalshi_states_matched']+=1
                if 'polymarket' in c:
                    p=c['polymarket'];path=(exchange/'polymarket'/(p['mapping']['token']+'.json.gz')).resolve();env=load(path)
                    assert env['status']==200
                    assert env['params']['startTs']<=row['at']-60<=env['params']['endTs']
                    if path not in pm_indexes:
                        values={}
                        for v in env['payload']['history']:
                            if v['t'] in values:assert values[v['t']]==v
                            values[v['t']]=v
                        times=sorted(values);pm_indexes[path]=(times,values)
                    times,values=pm_indexes[path];i=bisect_right(times,row['at']-60)-1
                    assert i>=0 and times[i]==p['state_at']
                    native=values[times[i]];assert native.get('active') is not False
                    native_point=D(str(native['p']))
                    delta=abs(native_point-p['interval']['point'])
                    # Symmetric synthetic bid/ask construction can shift their
                    # float midpoint by one ULP; retain and bound that error.
                    assert delta<=D(str(math.ulp(float(native_point))))*2
                    max_pm_rounding=max(max_pm_rounding,delta)
                    counts['pm_nonzero_rounding_differences']+=int(delta!=0)
                    counts['polymarket_asof_states_matched']+=1
    if not counts['kalshi_states_matched'] or not counts['polymarket_asof_states_matched']:raise ValueError('empty venue evidence')
    return {'passed':True,'counts':dict(counts),'max_pm_rounding_difference':str(max_pm_rounding),'raw_source_hashes':hashes,
            'limits':['Kalshi verifies cited native state membership and availability; does not independently resolve all overlapping capture intervals.',
                      'PM verifies latest archived point at modeled cutoff, not historical executable midpoint or depth.',
                      'Payoff mapping and real publication latency remain unverified by this audit.']}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('context','exchange','out'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();result=audit(a.context,a.exchange)
    result['audit_hashes']={str(v):hashlib.sha256(v.read_bytes()).hexdigest() for v in (a.context,Path(__file__))}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'passed':True,'counts':result['counts'],'raw_sources':len(result['raw_source_hashes'])}))


if __name__=='__main__':main()
