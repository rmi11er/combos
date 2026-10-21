"""Exact binary-scenario inventory relief replay; research only, full prints.

Gross collateral is never netted. All retained legs are distinct fixtures.
"""
import argparse
from collections import Counter
import gzip
import heapq
import json
from pathlib import Path
from decimal import Decimal,ROUND_CEILING
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from combos.fees import kalshi_fill_fee


def hurdle_quote(row,edge,rate='.035'):
    """Fixed-size hypothetical quote, 0.1c grid and explicit maker fee scenario."""
    fair=Decimal(str(row['fair_point']));q=Decimal(str(row['quantity']));h=Decimal(str(edge))
    first=int(((fair+h)/Decimal('.001')).to_integral_value(rounding=ROUND_CEILING))
    for tick in range(max(1,first),1000):
        price=Decimal(tick)/1000
        fee=kalshi_fill_fee(q,1-price,rate)['net_fee']
        if price-fair-fee/q>=h:
            return {**row,'yes_price':float(price),'maker_fee':float(fee)}
    return None


def scenario_grid(fixtures):
    if len(fixtures)>16:raise ValueError('exact scenario bound exceeded')
    return ((np.arange(2**len(fixtures))[:,None]>>np.arange(len(fixtures)))&1).astype(bool)


def ticket_loss(row,grid,index):
    payout=np.ones(len(grid),dtype=bool)
    for fixture,side in row['selected_fixture_bits']:
        payout &= grid[:,index[fixture]]==side
    return row['quantity']*(payout.astype(float)-row['yes_price'])+row['maker_fee']


def sensitivities(loss,fixtures,feasible=None):
    # Adjacent blocks differing in exactly one fixture, all other states fixed.
    values=[]
    for j in range(len(fixtures)):
        pairs=loss.reshape(-1,2,2**j)
        moves=np.abs(pairs[:,1,:]-pairs[:,0,:])
        if feasible is not None:
            allowed=feasible.reshape(-1,2,2**j)
            moves=moves[allowed[:,1,:]&allowed[:,0,:]]
        values.append(float(np.max(moves)) if moves.size else 0.)
    return np.array(values)


def revealed_outcomes(rows):
    """A settled binary winning conjunction reveals each selected fixture side.

    NO settlements are deliberately not used to infer an individual winner.
    No outcome is available before its recorded combo settlement timestamp.
    """
    events={}
    for r in rows:
        if r['yes_settlement']!=1 or r['settled_at'] is None:continue
        for fixture,side in r['selected_fixture_bits']:
            previous=events.get(fixture)
            if previous is not None and previous[1]!=side:raise ValueError('conflicting revealed winner')
            events[fixture]=(min(r['settled_at'],previous[0]) if previous else r['settled_at'],side)
    return events


def relief_gate(before,after,loss_before,loss_after,cap,trigger):
    constrained=before>=cap*trigger-1e-9
    return bool(np.any(constrained & (after<before-1e-8)) and
                max(0,float(np.max(loss_after)))<=max(0,float(np.max(loss_before)))+1e-8 and
                np.all(after<=cap+1e-8))


def replay(rows,arm,trigger=.9,relief_edge=.001,contract_cap=100.,combo_cap=100.,condition_settled=False,quote_at_hurdle=False):
    fixtures=sorted({f for r in rows for f,_ in r['selected_fixture_bits']});index={f:i for i,f in enumerate(fixtures)}
    grid=scenario_grid(fixtures);loss=np.zeros(len(grid));sens=np.zeros(len(fixtures))
    active={};heap=[];contracts=Counter();combos=Counter();grossfixtures=Counter()
    feasible=np.ones(len(grid),dtype=bool)
    reveals={-(j+1):(fixture,side) for j,(fixture,(at,side)) in enumerate(sorted(revealed_outcomes(rows).items()))} if condition_settled else {}
    if condition_settled:
        for j,(fixture,(at,side)) in enumerate(sorted(revealed_outcomes(rows).items())):heapq.heappush(heap,(at,-(j+1)))
    cash=10000.;gross=0.;accepted=[];rejected=Counter();peakgross=0.;peakworst=0.;peaksens=0.;released=0.;realized=0.
    constrained_seconds=0.;last=rows[0]['at']; seq=0;peak_entry_sensitivity=0.;settlement_breaches=[]
    def settle(pos):
        nonlocal loss,cash,gross,realized
        r,vector,liability=pos
        loss-=vector;gross-=liability
        pnl=r['quantity']*(r['yes_price']-r['yes_settlement'])-r['maker_fee']
        cash+=liability+pnl;realized+=pnl
        for c in r['buckets']['contract']:contracts[c]-=liability
        combos[r['buckets']['combo'][0]]-=liability
        for f,_ in r['selected_fixture_bits']:grossfixtures[f]-=liability
    def event(k):
        nonlocal feasible
        if k<0:
            fixture,side=reveals[k];feasible &= grid[:,index[fixture]]==side
            assert feasible.any()
        else:settle(active.pop(k))
    for row in rows:
        observed=row
        at=row['at']
        # Integrate utilization through settlement events, not only print times.
        while heap and heap[0][0]<=at:
            when,k=heapq.heappop(heap)
            constrained_seconds+=max(0,when-last)*int(np.any(sens>=250*trigger-1e-9));last=when
            event(k);sens=sensitivities(loss,fixtures,feasible)
            peakworst=max(peakworst,float(max(loss[feasible])));peaksens=max(peaksens,float(max(sens)))
            if k>=0 and max(sens)>250+1e-8:settlement_breaches.append({'at':when,'sensitivity':float(max(sens)),'remaining_positions':len(active),'feasible_scenarios':int(feasible.sum())})
        constrained_seconds+=max(0,at-last)*int(np.any(sens>=250*trigger-1e-9));last=at
        edge=row['yes_price']-row['fair_point']-row['maker_fee']/row['quantity']
        minimum=.001 if arm=='flat01' else .003
        if not row['quote_allowed'] or edge<min(minimum,relief_edge if arm=='relief' else minimum)-1e-12:
            rejected['edge_or_guard']+=1;continue
        if quote_at_hurdle:
            base=hurdle_quote(row,minimum)
            discounted=hurdle_quote(row,relief_edge) if arm=='relief' else None
            discount_reduces=False
            if discounted is not None:
                dl=loss+ticket_loss(discounted,grid,index)
                discount_reduces=relief_gate(sens,sensitivities(dl,fixtures,feasible),loss[feasible],dl[feasible],250,trigger)
            chosen=discounted if discount_reduces else base
            if chosen is None or chosen['yes_price']>observed['yes_price']+1e-12:
                rejected['quote_above_observed_execution']+=1;continue
            row=chosen
            edge=row['yes_price']-row['fair_point']-row['maker_fee']/row['quantity']
        vector=ticket_loss(row,grid,index);after=loss+vector;nextsens=sensitivities(after,fixtures,feasible)
        reducing=relief_gate(sens,nextsens,loss[feasible],after[feasible],250,trigger)
        low=arm=='relief' and reducing
        if edge<(relief_edge if low else minimum)-1e-12:
            rejected['not_certified_relief']+=1;continue
        liability=row['quantity']*(1-row['yes_price'])+row['maker_fee']
        if cash<liability-1e-8:
            rejected['cash']+=1;continue
        if any(contracts[c]+liability>contract_cap+1e-8 for c in row['buckets']['contract']):
            rejected['contract']+=1;continue
        if combos[row['buckets']['combo'][0]]+liability>combo_cap+1e-8:
            rejected['combo']+=1;continue
        if arm=='gross':fits=all(grossfixtures[f]+liability<=250+1e-8 for f,_ in row['selected_fixture_bits'])
        else:fits=np.all(nextsens<=250+1e-8)
        if not fits:rejected['fixture']+=1;continue
        assert row['settled_at'] is None or row['settled_at']>at
        record={'id':row['evaluation_id'],'at':at,'quantity':row['quantity'],'edge_cents':100*edge,
            'observed_price':observed['yes_price'],'charged_price':row['yes_price'],'charged_fee':row['maker_fee'],
            'discount_admitted':bool(low and edge<.003-1e-12),'certified_reducing':reducing,
            'before_max_sensitivity':float(max(sens)),'after_max_sensitivity':float(max(nextsens)),
            'worst_loss_before':max(0,float(max(loss[feasible]))),'worst_loss_after':max(0,float(max(after[feasible]))),
            'pnl':None if row['yes_settlement'] is None else row['quantity']*(row['yes_price']-row['yes_settlement'])-row['maker_fee'],
            'markouts':{h:(None if m.get('seller_net_markout_cents') is None else m['seller_net_markout_cents']+100*(row['yes_price']-observed['yes_price']+(observed['maker_fee']-row['maker_fee'])/row['quantity'])) for h,m in row['marks'].items()}}
        accepted.append(record);loss=after;sens=nextsens;cash-=liability;gross+=liability
        for c in row['buckets']['contract']:contracts[c]+=liability
        combos[row['buckets']['combo'][0]]+=liability
        for f,_ in row['selected_fixture_bits']:grossfixtures[f]+=liability
        active[seq]=(row,vector,liability)
        if row['settled_at'] is not None and row['yes_settlement'] is not None:heapq.heappush(heap,(row['settled_at'],seq))
        seq+=1;peakgross=max(peakgross,gross);peakworst=max(peakworst,float(max(loss[feasible])));peaksens=max(peaksens,float(max(sens)))
        peak_entry_sensitivity=max(peak_entry_sensitivity,float(max(sens)))
    # Settlement evaluation does not create any new entry decisions.
    while heap:
        when,k=heapq.heappop(heap)
        constrained_seconds+=max(0,when-last)*int(np.any(sens>=250*trigger-1e-9));last=when
        event(k);sens=sensitivities(loss,fixtures,feasible)
        peakworst=max(peakworst,float(max(loss[feasible])));peaksens=max(peaksens,float(max(sens)))
        if k>=0 and max(sens)>250+1e-8:settlement_breaches.append({'at':when,'sensitivity':float(max(sens)),'remaining_positions':len(active),'feasible_scenarios':int(feasible.sum())})
    discounts=[r for r in accepted if r['discount_admitted']]
    summary={'arm':arm,'trigger':trigger,'contract_cap':contract_cap,'combo_cap':combo_cap,'relief_edge_cents':100*relief_edge,'candidates':len(rows),'fills':len(accepted),
        'discount_fills':len(discounts),'pnl':sum(r['pnl'] for r in accepted if r['pnl'] is not None),
        'discount_pnl':sum(r['pnl'] for r in discounts if r['pnl'] is not None),'unknown':sum(r['pnl'] is None for r in accepted),
        'accepted_edge':sum(r['quantity']*r['edge_cents']/100 for r in accepted),'peak_gross_cash':peakgross,
        'peak_positive_scenario_loss':peakworst,'peak_fixture_sensitivity':peaksens,
        'hours_above_trigger':constrained_seconds/3600,'ending_cash':cash,'realized_pnl':realized,
        'rejections':dict(rejected),'fixtures':len(fixtures),'scenarios':len(grid)}
    summary['condition_settled']=condition_settled
    summary['quote_at_hurdle']=quote_at_hurdle
    summary['revealed_fixture_events']=len(reveals)
    summary['peak_entry_sensitivity']=peak_entry_sensitivity
    summary['settlement_stress_above_fixture_cap']=settlement_breaches
    assert abs(cash+gross-(10000+realized))<1e-6
    return summary,accepted


def main(out,contract_cap=100.,combo_cap=100.,tag='',condition_settled=False):
    rows=sorted([json.loads(l) for l in gzip.open(out/'nfl_panel.jsonl.gz','rt')],key=lambda r:(r['at'],r['evaluation_id']))
    results=[]
    for name,subset in [('full',rows),('later', [r for r in rows if r['at']>=1768197600])]:
        # Later period is a separate fresh-bankroll replication, not a midstream reset.
        baselines={}
        for arm,trigger,edge in [('gross',.9,.001),('net',.9,.001),('flat01',.9,.001)]+[('relief',t,e) for t in [.8,.9,1.] for e in [.001,.002]]:
            summary,fills=replay(subset,arm,trigger,edge,contract_cap,combo_cap,condition_settled);summary['period']=name
            if arm=='net':baselines={r['id']:r for r in fills}
            if arm=='relief':
                current={r['id']:r for r in fills};added=[r for k,r in current.items() if k not in baselines];removed=[r for k,r in baselines.items() if k not in current]
                summary['added_normal_fills']=sum(not r['discount_admitted'] for r in added)
                summary['added_normal_pnl']=sum(r['pnl'] or 0 for r in added if not r['discount_admitted'])
                summary['removed_baseline_fills']=len(removed);summary['removed_baseline_pnl']=sum(r['pnl'] or 0 for r in removed)
            results.append(summary)
            with gzip.open(out/f'inventory{tag}_{name}_{arm}_{trigger}_{edge}.json.gz','wt') as f:json.dump(fills,f,allow_nan=False)
            print(json.dumps(summary),flush=True)
    (out/f'inventory_relief{tag}.json').write_text(json.dumps({'results':results,'limitations':[
        'Binary mapped distinct-fixture NFL moneylines only; all joint binary outcomes enumerated, no probability assumption for risk.',
        'Fixture sensitivity is max loss change from flipping that fixture, not exchange collateral.',
        'Gross cash retained; contract/combo caps specified per result; scenario fixture cap $250.',
        'All public prints are hypothetical full-size fills at original price; no demand elasticity.',
        'Archived maker fee scenario .035; no depth or queue proof.',
        'Unconditioned scenarios are a conservative sensitivity; condition_settled fixes sides revealed by winning binary combos only at their recorded settlement timestamps. Public availability latency is not verified.',
        'Later period starts Jan12 with fresh cash; not an untouched holdout.']},indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
    p.add_argument('--contract-cap',type=float,default=100);p.add_argument('--combo-cap',type=float,default=100)
    p.add_argument('--tag',default='');p.add_argument('--condition-settled',action='store_true');a=p.parse_args()
    if a.contract_cap<=0 or a.combo_cap<=0 or '/' in a.tag:raise ValueError('invalid research configuration')
    main(a.out,a.contract_cap,a.combo_cap,a.tag,a.condition_settled)
