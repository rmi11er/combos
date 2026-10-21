"""Independent artifact reconciliation for the off-session inventory study."""
import json, math, hashlib
from collections import Counter
from decimal import Decimal, ROUND_CEILING
from offsession_inventory_study import ROOT, OUT, load

def run():
    qs,trades=load();qs={q['key']:q for q in qs};trades={t['id']:t for t in trades}
    checks={(r['quote_key'],r['trade_id']):r for r in json.loads((OUT/'inventory_fill_checks.json').read_text())}
    summary=json.loads((OUT/'inventory_summary.json').read_text());allfills={};audits=[]
    for s in summary['scenarios']:
        fills=json.loads((OUT/(s['name']+'_fills.json')).read_text());allfills[s['name']]=fills
        used=Counter();quoteused=Counter()
        for f in fills:
            q=qs[f['quote_key']];t=trades[f['trade_id']];v=checks[f['quote_key'],f['trade_id']]
            used[f['trade_id']]+=f['quantity'];quoteused[f['quote_key']]+=f['quantity']
            assert q['at']+s['delay_seconds']<=f['at']<q['expiry']
            assert t['ticker']==q['ticker']==f['ticker'] and f['ask']<=t['price']+1e-9
            assert v['available'] and v['allowed'] and v['risk_multiplier']>=q['mult']
            edge=s['discount_edge_cents']/100 if f['discounted'] else .003
            assert f['ask']-v['point']+1e-12>=edge
            assert abs(v['point']-q['fair'])<=.01+1e-12
            assert abs(f['model_edge']-f['quantity']*(f['ask']-q['fair']))<1e-8
            assert abs(f['collateral']-f['quantity']*(1-f['ask']))<1e-8
            fixed=q['fixed'];requested=float(fixed) if fixed and float(fixed)>0 else float((Decimal(str(q['target']))/Decimal(str(f['ask']))).to_integral_value(rounding=ROUND_CEILING))
            assert requested*(1-f['ask'])<=250+1e-8
            assert quoteused[f['quote_key']]<=requested+1e-8
            if f['discounted']:
                assert q['ml'] and f['incremental_variance_upper']<=1e-8
                if s['name'].startswith('payoff_bound'):
                    assert any(before>=1000*s['trigger']*q['mult'] and f['fixture_risk_after'][k]<before-1e-8 for k,before in f['fixture_risk_before'].items())
        assert all(n<=trades[k]['qty']+1e-8 for k,n in used.items())
        assert s['filled_quotes']==len(quoteused) and s['trades']==len(used)
        for key,field in [('contracts','quantity'),('collateral','collateral'),('model_edge','model_edge')]:
            assert math.isclose(s[key],sum(f[field] for f in fills),abs_tol=1e-8)
        audits.append({'scenario':s['name'],'passed':True,'allocations':len(fills)})
    model=allfills['payoff_bound_inventory_0.05c'];discounts=[f for f in model if f['discounted']]
    control={(f['quote_key'],f['trade_id']):f for f in allfills['payoff_bound_0.30c']}
    same=[f for f in discounts if (f['quote_key'],f['trade_id']) in control]
    tenth=allfills['payoff_bound_inventory_0.10c']
    fifth_signature={(f['quote_key'],f['trade_id']):f['quantity'] for f in model}
    tenth_signature={(f['quote_key'],f['trade_id']):f['quantity'] for f in tenth}
    analysis={'audits':audits,'discount_contracts':sum(f['quantity'] for f in discounts),
        '0.05c_and_0.10c_identical_quote_trade_allocations_and_quantity':fifth_signature==tenth_signature,
        'discount_collateral':sum(f['collateral'] for f in discounts),
        'discount_actual_average_charge_cents':100*sum(f['model_edge'] for f in discounts)/sum(f['quantity'] for f in discounts),
        'discount_exact_quote_trade_matches_already_in_control':len(same),
        'edge_concession_on_same_quote_trade_overlapping_quantity':sum(min(f['quantity'],control[f['quote_key'],f['trade_id']]['quantity'])*(control[f['quote_key'],f['trade_id']]['ask']-f['ask']) for f in same),
        'discount_examples':[dict(quote_key=f['quote_key'],at=f['at'],quantity=f['quantity'],
            legs=[{'fixture':l[0],'selected_team':l[0].rsplit(':',1)[-1].split('-')[0 if l[2]==1 else 1]} for l in qs[f['quote_key']]['legs']],
            before=f['fixture_risk_before'],after=f['fixture_risk_after'],variance_delta_upper=f['incremental_variance_upper']) for f in discounts]}
    (OUT/'inventory_audit.json').write_text(json.dumps(analysis,indent=2)+'\n')
    files=[OUT/'inventory_summary.json',OUT/'inventory_fill_checks.json',OUT/'candidate_census/summary.json',
        ROOT/'config/runtime_nfl_authorized_shadow_20260910.json',ROOT/'config/weighting.json',
        *[ROOT/'scripts'/n for n in ('offsession_inventory_study.py','offsession_inventory_fill_checks.py','offsession_candidate_census.py','audit_offsession_inventory.py')]]
    (OUT/'inventory_provenance.json').write_text(json.dumps({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},indent=2)+'\n')
    print(json.dumps(analysis,indent=2))

if __name__=='__main__':run()
