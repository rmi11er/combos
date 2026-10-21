"""Independent Decimal quote arithmetic and integer reservation audit.

Does not import the quote solver, fee helper, or capacity ledger. Canonical risk
identities and three-source fair inputs are upstream evidence, not rederived here.
"""
import argparse,hashlib,json
from pathlib import Path
from decimal import Decimal as D,ROUND_CEILING,ROUND_FLOOR
from collections import Counter


def load(p):return json.loads(p.read_text())
def require(condition,message):
    if not condition:raise ValueError(message)


def audit(capture,scenarios,terms,capacity,out):
    inputs=load(scenarios/'decisions.json');source={r['source_seq']:r for r in inputs}
    require(len(source)==len(inputs),'duplicate source sequence')
    eligible={k for k,v in source.items() if v['status']=='scenario_priced'}
    quotes=load(terms/'decisions.json');quote_index={(r['source_seq'],r['reserve_fraction']):r for r in quotes}
    require(len(quote_index)==len(quotes)==len(eligible)*3,'quote census')
    require(set(quote_index)=={(seq,alpha) for seq in eligible for alpha in (0,.25,1)},'quote policy census')
    runtime=load(capture/'runtime.json')
    for (seq,alpha),r in quote_index.items():
        require(r['status']=='priced','audit requires fully priced quote input')
        original=source[seq];s=next(v for v in original['scenarios'] if v['assumed_usd_per_native_unit']==1)
        terms_row=next(v for k,v in sorted(runtime['combo_terms'].items(),key=lambda kv:-len(kv[0])) if original['market_ticker'].startswith(k))
        require(terms_row['verified_at']<=original['at']<terms_row['valid_until'],'noncausal terms')
        point,upper=D(str(s['independent_combo_point'])),D(str(s['independent_marginal_upper']))
        ref=point+D(str(alpha))*(upper-point);price=D(r['yes_ask']);q=D(r['quantity_bound']);rate=D(str(terms_row['maker_fee_rate']));unit=D('.0001')
        require(D(str(r['maker_rate']))==rate,'fee rate mismatch')
        require(any(D(g['start'])<=price<D(g['end']) and (price-D(g['start']))%D(g['step'])==0 for g in terms_row['price_ranges']),'invalid grid')
        fixed=original.get('requested_contracts');target=original.get('target_cost_dollars')
        require((fixed is None)!=(target is None),'ambiguous size')
        if fixed is not None:require(q==D(fixed),'fixed size changed')
        else:require((q-D('.01'))*price<D(target)<=q*price,'target bound incorrect')
        raw_fee=(q*rate*price*(1-price)).quantize(D('.000001'),rounding=ROUND_CEILING)
        debit=q*(1-price);aligned=(((-debit-raw_fee)/unit).to_integral_value(rounding=ROUND_FLOOR))*unit
        fee=-aligned-debit
        require(D(r['single_fill_fee'])==fee,'fee alignment mismatch')
        require(D(r['quote_reference'])==ref,'reference mismatch')
        require(D(r['reference_compensation'])==q*(price-ref)-fee>=q*D('.003'),'edge mismatch')
        require(D(r['point_compensation'])==q*(price-point)-fee,'point compensation mismatch')
        require(D(r['single_fill_cash'])==debit+fee,'cash mismatch')
        hold=(debit+q*rate*price*(1-price)+q/D('.01')*unit).quantize(unit,rounding=ROUND_CEILING)
        require(D(r['fragmentation_cash_bound'])==hold,'fragmentation bound mismatch')
        require(len(r['leg_risks'])==original['nlegs'],'leg census')
        require(r['creator_publication_seq'] is None or r['creator_publication_seq']<seq,'future creator state')
    rows=load(capacity/'decisions.json');portfolios={};limits={'original':[100,100,250],'500_each':[500]*3,'1000_each':[1000]*3,'2000_each':[2000]*3,'cash_only':[10000]*3}
    for r in rows:
        group=(r['reserve_fraction'],r['policy'],r['mode']);state=portfolios.setdefault(group,{'held':[],'seen':set(),'seqs':set(),'last_at':float('-inf'),'peak':0,'counts':Counter(),'bindings':Counter()})
        seq=r['source_seq'];require(seq not in state['seqs'],'duplicate portfolio row');state['seqs'].add(seq)
        s=source[seq];t=quote_index[(seq,r['reserve_fraction'])];at=s['at'];require(at>=state['last_at'],'noncausal risk order');state['last_at']=at
        held=state['held'];held[:]=[h for h in held if r['mode']=='all_admitted_fill_no_release' or at<h[0]+3]
        cost=int((D(t['fragmentation_cash_bound'])*10000).to_integral_value(rounding=ROUND_CEILING));b=[set(l['key'] for l in t['leg_risks']),{s['market_ticker']},set(t['fixtures'])]
        reasons=[]
        if s['rfq_id'] in state['seen']:reasons.append('duplicate_rfq')
        state['seen'].add(s['rfq_id'])
        if cost+sum(h[1] for h in held)>100000000:reasons.append('capital')
        for i,(kind,cap) in enumerate(zip(['contract','combo','fixture'],limits[r['policy']])):
            if any(cost+sum(h[1] for h in held if k in h[2][i])>cap*10000 for k in b[i]):reasons.append(kind)
        require(reasons==r['binding_limits'] and r['admitted']==(not reasons),'risk decision mismatch')
        if not reasons:held.append((at,cost,b))
        committed=sum(h[1] for h in held);require(committed==r['committed_units']<=100000000,'reservation cash mismatch')
        require(len(held)==r['active_reservations'],'active reservation mismatch')
        state['peak']=max(state['peak'],committed);state['counts']['admitted' if not reasons else 'rejected']+=1;state['bindings'].update(reasons)
    expected_groups={(a,p,m) for a in (0,.25,1) for p in limits for m in ('unfilled_expiry_3s','all_admitted_fill_no_release')}
    require(set(portfolios)==expected_groups and all(s['seqs']==eligible for s in portfolios.values()),'portfolio census')
    summaries=load(capacity/'summary.json')['scenarios'];require(len(summaries)==30 and {(s['reserve_fraction'],s['policy'],s['mode']) for s in summaries}==expected_groups,'summary census')
    for s in summaries:
        v=portfolios[(s['reserve_fraction'],s['policy'],s['mode'])]
        require(s['counts']==dict(v['counts']) and s['binding_counts']==dict(v['bindings']) and D(str(s['peak_committed_dollars']))==D(v['peak'])/10000,'portfolio summary mismatch')
    paths=[scenarios/'decisions.json',terms/'decisions.json',capacity/'decisions.json',capacity/'summary.json',capture/'runtime.json',Path(__file__)]
    result={'quotes_audited':len(quotes),'risk_decisions_audited':len(rows),'portfolios_audited':len(portfolios),'status':'passed','scope':'fee arithmetic, sizing, grids, references, edge, causal terms, publication-sequence bound, reservation decisions and summaries','upstream_not_rederived':['three-source fair','canonical payoff identities','creator policy substance','fee metadata authenticity'],'hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
    out.mkdir(parents=True,exist_ok=False);(out/'verification.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='hashes'},indent=2));return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('capture','scenarios','terms','capacity','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();audit(a.capture,a.scenarios,a.terms,a.capacity,a.out)
