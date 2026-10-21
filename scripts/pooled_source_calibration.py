"""Stream matched development cohorts into source-score and fixture diagnostics."""
import argparse
from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path


def blank():return [0,0.,0.,0.,0.,0.]


def add(t,r):
    q=r['quantity'];e=r['fair_point']-r['yes_settlement']
    for i,v in enumerate((1,q,e*e,q*e*e,q*(r['yes_price']-r['fair_point'])-r['maker_fee'],q*e)):t[i]+=v


def metrics(t):
    return dict(prints=t[0],quantity=t[1],equal_print_brier=t[2]/t[0] if t[0] else None,
                quantity_weighted_brier=t[3]/t[1] if t[1] else None,
                compensation_dollars=t[4],settlement_residual_dollars=t[5],net_dollars=t[4]+t[5])


def analyze(paths):
    totals=defaultdict(blank);fixtures=defaultdict(lambda:defaultdict(blank));hashes={};seen=set()
    for path in paths:
        rawhash=hashlib.sha256(path.read_bytes()).hexdigest();hashes[str(path)]=rawhash
        paired={}
        with gzip.open(path,'rt') as f:
            for line in f:
                r=json.loads(line);key=r['evaluation_id'];model=r['model']
                if r['yes_settlement'] is None:raise ValueError('unresolved matched outcome')
                economics=tuple(r[k] for k in ('at','quantity','yes_price','maker_fee','yes_settlement'))
                pair=paired.setdefault(key,[economics,set()])
                if pair[0]!=economics or model in pair[1]:raise ValueError('unpaired or duplicate model row')
                pair[1].add(model);add(totals[model],r)
                for fixture in set(r['buckets']['fixture']):add(fixtures[fixture][model],r)
        expected={'kalshi','polymarket','exchange_blend_equal','exchange_blend_pm75'}
        if any(v[1]!=expected for v in paired.values()):raise ValueError('incomplete four-model cohort')
        if seen.intersection(paired):raise ValueError('duplicate print across inputs')
        seen.update(paired)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=rawhash:raise ValueError('input changed')
    scores={m:metrics(t) for m,t in totals.items()}
    omissions=[]
    for fixture,groups in sorted(fixtures.items()):
        remaining={m:metrics([a-b for a,b in zip(t,groups.get(m,blank()))]) for m,t in totals.items()}
        k=remaining['kalshi']['quantity_weighted_brier'];p=remaining['polymarket']['quantity_weighted_brier']
        omissions.append({'fixture':fixture,'remaining':remaining,'pm_minus_k_brier':None if k is None or p is None else p-k})
    return {'models':scores,'fixture_omissions':omissions,'input_hashes':hashes,'common_prints':len(seen),
            'limits':['Matched four-model exchange-only cohorts; no Pinnacle or live depth validation.',
                      'Fixture omissions overlap; influence diagnostics, not confidence intervals.',
                      'Brier combines calibration and discrimination. Historical fees and source semantics inherited.']}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',action='append',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    r=analyze(a.input);r['source_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps({'common_prints':r['common_prints'],'models':r['models']}))


if __name__=='__main__':main()
