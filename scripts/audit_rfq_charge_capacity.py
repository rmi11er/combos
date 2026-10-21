"""Independent Decimal quote and integer capacity checks for zero-maker-fee sweep."""
import argparse
from collections import Counter
from decimal import Decimal as D, ROUND_CEILING, ROUND_FLOOR
import hashlib
import json
from pathlib import Path


def run(comparison,source,folder):
    summary=json.loads((folder/'summary.json').read_text())
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in summary['hashes'].items())
    originals={r['source_seq']:r for r in json.loads(source.read_text())}
    base={}
    for line in (comparison/'priced_decisions.jsonl').open():
        r=json.loads(line);base[(r['model'],r['source_seq'])]=r
    states={};n=0;parity=0
    charges={'zero':(0,0,False),'0.1c_combo':(.001,0,False),'0.3c_combo':(.003,0,False),
        '0.6c_combo':(.006,0,False),'0.3c_leg':(.003,0,True),'quarter_interval_plus_0.3c':(.003,.25,False)}
    for line in (folder/'decisions.jsonl').open():
        r=json.loads(line);n+=1;key=(r['model'],r['charge'],r['cap'],r['mode'])
        state=states.setdefault(key,{'active':{},'seen':set(),'seqs':set(),'peak':0,'counts':Counter(),'at':float('-inf')})
        assert r['source_seq'] not in state['seqs'];state['seqs'].add(r['source_seq'])
        b=base[(r['model'],r['source_seq'])];o=originals[r['source_seq']];p=b['research_policy'];q=r['quote']
        assert D(str(p['maker_fee_rate']))==0, 'this independent audit explicitly covers zero maker fees'
        edge,alpha,perleg=charges[r['charge']]
        point=D(str(b['scenario']['independent_combo_point']));upper=D(str(b['scenario']['independent_marginal_upper']))
        ref=point+D(str(alpha))*(upper-point)
        assert D(q['quote_reference'])==ref
        ask=D(q['yes_ask']);no=D(q['no_bid']);qty=D(q['quantity_bound'])
        assert ask+no==1 and 0<ask<1
        if o.get('requested_contracts') is not None:assert qty==D(o['requested_contracts'])
        else:assert qty==(D(o['target_cost_dollars'])/ask).quantize(D('.01'),rounding=ROUND_CEILING)
        fee=(qty*no/D('.0001')).to_integral_value(rounding=ROUND_CEILING)*D('.0001')-qty*no
        assert D(q['single_fill_fee'])==fee
        assert qty*(ask-ref)-fee>=qty*D(str(edge*b['nlegs'] if perleg else edge))
        hold=(qty*no+qty/D('.01')*D('.0001')).quantize(D('.0001'),rounding=ROUND_CEILING)
        assert D(q['fragmentation_cash_bound'])==hold
        assert D(q['single_fill_cash'])==qty*no+fee
        assert D(q['point_compensation'])==qty*(ask-point)-fee
        at=b['at'];assert at>=state['at'];state['at']=at
        state['active']={k:v for k,v in state['active'].items() if r['mode']!='unfilled_expiry_3s' or at<v['at']+3}
        used=sum(v['units'] for v in state['active'].values());units=int(hold*10000)
        reasons=[]
        if r['rfq_id'] in state['seen']:reasons.append('duplicate_rfq')
        state['seen'].add(r['rfq_id'])
        if used+units>100000000:reasons.append('capital')
        multiplier=min(D(str(l['pricing_guard']['risk_multiplier'])) for l in b['scenario']['legs'])
        cap=int((D(r['cap'])*10000*multiplier).to_integral_value(rounding=ROUND_FLOOR))
        for kind,keys in p['buckets'].items():
            if any(units+sum(v['units'] for v in state['active'].values() if k in v['buckets'][kind])>cap for k in keys):reasons.append(kind)
        admitted=not reasons
        if admitted:
            state['active'][r['rfq_id']]={'units':units,'at':at,'buckets':p['buckets']};used+=units
        a=r['admission']
        assert a['admitted']==admitted and set(a['binding_limits'])==set(reasons)
        assert a['committed_units']==used and a['active_reservations']==len(state['active'])
        assert r['status']==('admitted' if admitted else 'risk_rejected')
        state['counts'][r['status']]+=1;state['peak']=max(state['peak'],used)
        if r['charge']=='0.3c_combo' and r['cap']==1000 and r['mode']=='all_admitted_fill_no_release':
            assert q==p['quote'] and a==p['admission'];parity+=1
    for r in summary['scenarios']:
        state=states[(r['model'],r['charge'],r['cap'],r['mode'])]
        assert len(state['seqs'])==summary['rows_per_model'][r['model']]
        assert dict(state['counts'])==r['counts'] and state['peak']/10000==r['peak_committed_dollars']
    result={'decision_rows':n,'independently_reconciled_portfolios':len(states),
        'exact_prior_policy_rows':parity,'scope':'zero-maker-fee economics and integer risk; no acceptance/outcome validation'}
    (folder/'verification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('comparison','source','folder'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();run(a.comparison,a.source,a.folder)
