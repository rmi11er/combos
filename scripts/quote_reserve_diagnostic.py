#!/usr/bin/env python3
"""Compare point and stressed entry eligibility on retained unlimited prints."""
import argparse
from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path


def analyze(paths):
    groups=defaultdict(lambda:defaultdict(float));hashes={}
    for path in paths:
        hashes[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
        with gzip.open(path,'rt') as stream:
            for line in stream:
                r=json.loads(line);q=r['quantity'];fee=r['maker_fee'];hurdle=r['required_net_edge']
                assert r['entry_basis']=='point' and q>0
                point=q*(r['yes_price']-r['fair_point'])-fee
                stressed=q*(r['yes_price']-r['stressed_upper'])-fee
                assert r['stressed_upper']>=r['fair_point']-1e-12
                point_pass=r['quote_allowed'] and point>=hurdle
                stressed_pass=r['quote_allowed'] and stressed>=hurdle
                assert r['accepted']==point_pass, 'requires unlimited point-entry ledger'
                assert not stressed_pass or point_pass
                net=q*(r['yes_price']-r['yes_settlement'])-fee
                g=groups[(r['model'],r['source']['nlegs'])]
                g['prints']+=1;g['quantity']+=q
                g['reserve_contract_dollars']+=q*(r['stressed_upper']-r['fair_point'])
                if point_pass:
                    g['point_pass_prints']+=1;g['point_pass_quantity']+=q;g['point_pass_net']+=net
                    g['point_pass_reserve_contract_dollars']+=q*(r['stressed_upper']-r['fair_point'])
                if stressed_pass:
                    g['stressed_pass_prints']+=1;g['stressed_pass_quantity']+=q;g['stressed_pass_net']+=net
    rows=[]
    for (model,legs),g in sorted(groups.items()):
        row={'model':model,'legs':legs,**g}
        row['quantity_weighted_reserve_cents']=100*g['reserve_contract_dollars']/g['quantity']
        row['point_selected_reserve_cents']=100*g['point_pass_reserve_contract_dollars']/g['point_pass_quantity'] if g['point_pass_quantity'] else None
        row['point_print_retention_under_stress']=g['stressed_pass_prints']/g['point_pass_prints'] if g['point_pass_prints'] else None
        rows.append(row)
    return {'rows':rows,'input_hashes':hashes,'limits':['Recorded historical stress bound versus point, at the same observed price/size/fee; not customer acceptance or a live three-source simulation.',
            'No cash reallocation or capital constraints; subset P&L is an outcome diagnostic, not forecast edge.',
            'Current shadow uses stressed upper plus required edge and fee-aware price-grid rounding; this comparison omits grid rounding and dynamic live reserves.']}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,action='append',required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();r=analyze(a.input);r['script_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r['rows']))


if __name__=='__main__':main()
