#!/usr/bin/env python3
"""Loose capital-use ceiling implied by gross per-bucket risk accounting."""
import argparse
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path


def ceiling(rows, model='kalshi', limits=None):
    limits=limits or {'contract':100,'fixture':250}
    keys={k:set() for k in limits};minimum={k:None for k in limits};n=0
    for row in rows:
        if row['model']!=model:continue
        if not 0 < row.get('risk_multiplier',1) <= 1:
            raise ValueError('ceiling_requires_non_increasing_limit_multiplier')
        n+=1
        for kind in limits:
            buckets=set(row['buckets'][kind])
            if not buckets:raise ValueError('empty_risk_bucket_family')
            keys[kind].update(buckets)
            minimum[kind]=len(buckets) if minimum[kind] is None else min(minimum[kind],len(buckets))
    families={}
    for kind,limit in limits.items():
        cap=Decimal(str(limit))*10000
        if not cap.is_finite() or cap<0 or cap!=int(cap):raise ValueError('invalid_cash_unit_limit')
        bound=(len(keys[kind])*int(cap)//minimum[kind])/10000 if n else 0
        families[kind]={'distinct_buckets':len(keys[kind]),'minimum_buckets_charged_per_position':minimum[kind],
                        'limit_dollars':limit,'loose_committed_cash_ceiling_dollars':bound}
    return {'model':model,'input_prints':n,'families':families,
            'risk_only_committed_cash_ceiling_dollars':min(v['loose_committed_cash_ceiling_dollars'] for v in families.values()),
            'proof':'Each open reservation charges its full rounded NO cost including fees to every distinct bucket. If every position charges at least m buckets, m times total committed cash cannot exceed the sum of all bucket caps.',
            'limitations':['Only positions drawn from the supplied cohort; excludes any preexisting or future positions outside this input.',
                           'Union across the whole input window overstates concurrently available capacity; this is a loose ceiling, not achievable volume.',
                           'Per-combo caps, price filters, temporal availability and lower limit multipliers can reduce utilization further.',
                           'No assumption that starting capital is a permanent ceiling: realized profits may fund later trades; bucket bounds still apply.']}


def read_rows(path):
    if path.name.endswith('.jsonl.gz'):
        with gzip.open(path,'rt') as f:
            yield from (json.loads(line) for line in f)
    else:
        with (gzip.open(path,'rt') if path.suffix=='.gz' else path.open()) as f:
            data=json.load(f)
        yield from data.get('opportunities',data.get('decisions',[]))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--model',default='kalshi');a=p.parse_args()
    result=ceiling(read_rows(a.input),a.model)
    result['input']=str(a.input.resolve());result['input_sha256']=hashlib.sha256(a.input.read_bytes()).hexdigest()
    result['script_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'out':str(a.out),'ceiling':result['risk_only_committed_cash_ceiling_dollars']}))


if __name__=='__main__':main()
