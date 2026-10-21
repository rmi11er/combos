"""Counterfactual point-fair quotes using saved three-venue decision features."""
import argparse
from collections import Counter,defaultdict
from copy import deepcopy
from decimal import Decimal, ROUND_CEILING
import datetime as dt
import json
import math
from pathlib import Path
import sqlite3
import sys
import zlib
import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from combos.shadow_engine import quote_price,fee_per_share
from shadow_trade_review import match,stamp,write

def dist(values):
    if not values:return {'n':0}
    x=np.array(values,dtype=float)
    return dict(n=len(x),mean=float(x.mean()),median=float(np.median(x)),p05=float(np.percentile(x,5)),p95=float(np.percentile(x,95)),minimum=float(x.min()),maximum=float(x.max()))

def reconstruct(original,edge):
    q=deepcopy(original);point=q['pricing']['joint']['point'];rate=q['combo_terms']['maker_fee_rate']
    price=quote_price(point,edge,rate,q['combo_terms']['price_ranges'])
    req=q['request'];fixed=req.get('contracts_fp');target=req.get('target_cost_dollars')
    desired=float(fixed) if fixed and float(fixed)>0 else int((Decimal(str(target))/Decimal(str(price))).to_integral_value(rounding=ROUND_CEILING))
    unit_loss=1-price+fee_per_share(price,rate)
    quantity=math.floor(min(desired,q['ticket_liability_cap_dollars']/unit_loss)*100+1e-9)/100
    q['original_yes_ask']=q['yes_ask'];q['original_quantity']=q['quantity']
    q['yes_ask']=price;q['quantity']=quantity;q['required_net_edge_per_share']=edge
    q['quote_reference']=dict(model='three_venue_point_fair_counterfactual',value=point,point=point,reserve_per_share=0.)
    q['economics']=dict(maker_fee=quantity*fee_per_share(price,rate),expected_edge=quantity*(price-point-fee_per_share(price,rate)))
    q['point_economics']=q['economics'].copy();q['quote']={'yes_bid':'0.0000','no_bid':f'{1-price:.4f}'}
    q['no_bid']=1-price
    return q

def funded(fills,qs):
    used=defaultdict(float);accepted=[];rejected=[];total=0.
    for f in fills:
        q=qs[f['quote_key']];mult=q['pricing']['risk_multiplier']
        buckets=[('contract:'+c,500*mult) for c in set(q['pricing']['contracts'])]
        buckets += [('fixture:'+c,1000*mult) for c in set(q['pricing']['fixtures'])]
        buckets += [('combo:'+q['market_ticker'],500*mult)]
        cost=f['liability_dollars']
        if total+cost>10000 or any(used[b]+cost>cap+1e-8 for b,cap in buckets):
            rejected.append(f);continue
        total+=cost
        for b,_ in buckets:used[b]+=cost
        accepted.append(f)
    return dict(fills=accepted,rejected=rejected,total_liability=total,bucket_usage=dict(used))

def fillstats(fills):
    return dict(quote_count=len({f['quote_key'] for f in fills}),trade_count=len({f['trade_id'] for f in fills}),
        market_count=len({f['ticker'] for f in fills}),contracts=sum(f['quantity'] for f in fills),
        model_edge_dollars=sum(f['point_edge_dollars'] for f in fills),
        collateral_dollars=sum(f['liability_dollars'] for f in fills),
        public_price_edge_at_quote_fair_dollars=sum(f['public_price_edge_at_quote_fair_dollars'] for f in fills))

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    original=[json.loads(l) for l in (a.source/'quotes.jsonl').read_text().splitlines()]
    marks=[json.loads(l) for l in (a.source/'markouts.jsonl').read_text().splitlines()]
    tapes={}
    for path in (a.source/'public_tape').glob('*.json'):
        tape=json.loads(path.read_text());tapes[tape['ticker']]=tape
    summary={'basis':'Same recorded priceable quote opportunities, three-venue point fair + edge; retained tail filter. Conditional public-tape participation, not actual fills.', 'original_quotes':len(original)}
    corrected=[reconstruct(q,.003) for q in original];qs={q['quote_key']:q for q in corrected}
    with (a.out/'corrected_quotes.jsonl').open('w') as f:
        for q in corrected:f.write(json.dumps(q)+'\n')
    summary['economics']=dict(old_ask_cents=dist([100*q['original_yes_ask'] for q in corrected]),
        reduction_cents=dist([100*(q['original_yes_ask']-q['yes_ask']) for q in corrected]),
        corrected_edge_cents=dist([100*q['economics']['expected_edge']/q['quantity'] for q in corrected]),
        requested_contracts=sum(q['quantity'] for q in corrected),original_contracts=sum(q['original_quantity'] for q in corrected))
    scenarios={};base=[]
    for edge in (.003,.0035):
        quotes=corrected if edge==.003 else [reconstruct(q,edge) for q in original]
        for delay in (0,.1,.25,.5,1):
            fills=match(quotes,tapes,delay);key=f'edge_{edge}_delay_{delay}'
            scenarios[key]=fillstats(fills);write(a.out/(key+'.json'),fills)
            if edge==.003 and delay==0:base=fills
    summary['scenarios']=scenarios
    original_fills=match(original,tapes,0);summary['original_strict']=fillstats(original_fills)
    # Valid-until is frozen to observed cancellations. Expiry-only is an optimistic sensitivity.
    relaxed=deepcopy(corrected)
    cutoff=stamp(json.loads((a.source/'summary.json').read_text())['cutoff'])
    for q in relaxed:q['valid_until']=min(q['expires_at'],cutoff)
    summary['expiry_only_sensitivity']=fillstats(match(relaxed,tapes,0))
    budget=funded(base,qs);write(a.out/'held_inventory_scenario.json',budget)
    summary['held_inventory_scenario']={**fillstats(budget['fills']),'risk_rejected_allocations':len(budget['rejected'])}
    pairs=[];context=[];window_context={str(h):Counter() for h in (3,10,30,60,300)};first_delays=[]
    for q in corrected:
        after=[t for t in tapes[q['market_ticker']]['trades'] if q['decision_completed_at']<=stamp(t['created_time'])<=cutoff]
        active=[t for t in after if stamp(t['created_time'])<q['valid_until']]
        if after:first_delays.append(min(stamp(t['created_time']) for t in after)-q['decision_completed_at'])
        for h in (3,10,30,60,300):
            rows=[t for t in after if stamp(t['created_time'])<=q['decision_completed_at']+h]
            window_context[str(h)]['fully_observed_quotes']+=q['decision_completed_at']+h<=cutoff
            window_context[str(h)]['quotes_with_public_trade']+=bool(rows)
            window_context[str(h)]['quotes_with_price_compatible_yes_trade']+=any(
                (t.get('taker_outcome_side') or t.get('taker_side'))=='yes' and float(t['yes_price_dollars'])+1e-9>=q['yes_ask'] for t in rows)
        for t in active:
            price=float(t['yes_price_dollars']);fair=q['pricing']['joint']['point']
            pairs.append(dict(quote_key=q['quote_key'],market=q['market_ticker'],trade_id=t['trade_id'],
                at=stamp(t['created_time']),public_price=price,point_fair=fair,old_ask=q['original_yes_ask'],new_ask=q['yes_ask'],
                public_minus_new_cents=100*(price-q['yes_ask']),public_minus_fair_cents=100*(price-fair),
                old_minus_public_cents=100*(q['original_yes_ask']-price),creator=q['creator_id']))
        context.append(dict(quote_key=q['quote_key'],later_trades=len(after),active_trades=len(active)))
    write(a.out/'trade_price_comparisons.json',pairs)
    summary['diagnostic_windows_ignoring_expiry_and_cancellation']={k:dict(v) for k,v in window_context.items()}
    summary['first_later_trade_delay_seconds']=dist(first_delays)
    summary['competitiveness']=dict(quote_trade_pairs=len(pairs),unique_trades=len({r['trade_id'] for r in pairs}),
        unique_markets=len({r['market'] for r in pairs}),quotes_with_active_trades=sum(x['active_trades']>0 for x in context),
        quotes_with_later_trades=sum(x['later_trades']>0 for x in context),
        public_minus_new_cents=dist([r['public_minus_new_cents'] for r in pairs]),
        public_minus_fair_cents=dist([r['public_minus_fair_cents'] for r in pairs]),
        quote_trade_pairs_meeting_price=sum(r['public_minus_new_cents']>=-1e-8 for r in pairs))
    by_market=defaultdict(list)
    for r in pairs:by_market[r['market']].append(r['public_minus_new_cents'])
    means=[float(np.mean(v)) for v in by_market.values()]
    if means:
        rng=np.random.default_rng(42);samples=rng.choice(means,size=(5000,len(means)),replace=True).mean(axis=1)
        summary['competitiveness']['market_equal_weight_gap_mean_cents']=float(np.mean(means))
        summary['competitiveness']['exploratory_market_bootstrap_95pct']=list(map(float,np.percentile(samples,[2.5,97.5])))
    cohort=defaultdict(list)
    for q in corrected:cohort[str(q['leg_count'])].append(q)
    summary['leg_cohorts']={k:dict(quotes=len(v),**fillstats([f for f in base if qs[f['quote_key']]['leg_count']==int(k)])) for k,v in cohort.items()}
    # Model marks: recover point-fair valuation rather than reusing old reserve-net edge.
    markrows=[]
    for m in marks:
        if m['status']!='observed':continue
        q=qs[m['quote_key']];fee=q['economics']['maker_fee']/q['quantity']
        filled=sum(f['quantity'] for f in base if f['quote_key']==m['quote_key'] and f['at']<=m['observed_at'])
        markrows.append(dict(quote_key=m['quote_key'],horizon=m['horizon_seconds'],at=m['observed_at'],
            residual_edge_cents=100*(q['yes_ask']-m['fair']-fee),fair_move_cents=m['adverse_move_cents'],
            matched_quantity=filled,matched_model_value_dollars=filled*(q['yes_ask']-m['fair']-fee)))
    write(a.out/'corrected_model_marks.json',markrows)
    summary['markouts']={}
    for h in (5,30,120):
        ms=[m for m in markrows if m['horizon']==h];fs=[m for m in ms if m['matched_quantity']>0]
        summary['markouts'][str(h)]=dict(observed=len(ms),quote_denominator=len(corrected),
            residual_edge_cents=dist([m['residual_edge_cents'] for m in ms]),negative_residual=sum(m['residual_edge_cents']<0 for m in ms),
            matched_quotes=len(fs),matched_quantity=sum(m['matched_quantity'] for m in fs),
            matched_model_value_dollars=sum(m['matched_model_value_dollars'] for m in fs))
    # Independent public-print marks, first same-ticker trade at/after horizon, 30s grace.
    public_marks=[]
    for f in base:
        for h in (5,30,120):
            candidates=[t for t in tapes[f['ticker']]['trades'] if f['at']+h<=stamp(t['created_time'])<=min(f['at']+h+30,cutoff)]
            if candidates:
                t=min(candidates,key=lambda t:stamp(t['created_time']));price=float(t['yes_price_dollars'])
                public_marks.append(dict(quote_key=f['quote_key'],trade_id=f['trade_id'],horizon=h,benchmark_trade_id=t['trade_id'],
                    observed_delay=stamp(t['created_time'])-f['at'],quantity=f['quantity'],
                    markout_cents=100*(f['hypothetical_yes_price']-price),markout_dollars=f['quantity']*(f['hypothetical_yes_price']-price)))
    write(a.out/'public_print_marks.json',public_marks)
    summary['public_marks']={str(h):dict(allocations_observed=len([r for r in public_marks if r['horizon']==h]),
        allocations_total=len(base),quantity=sum(r['quantity'] for r in public_marks if r['horizon']==h),
        markout_dollars=sum(r['markout_dollars'] for r in public_marks if r['horizon']==h),
        markout_cents=dist([r['markout_cents'] for r in public_marks if r['horizon']==h])) for h in (5,30,120)}
    creator_stats=[]
    for name in sorted({q['run'] for q in corrected}):
        c=sqlite3.connect('file:'+str(ROOT/'runs'/name/'events.sqlite')+'?mode=ro',uri=True)
        transitions=Counter();cooldowns=[];blocked_ids=set()
        for creator,seq,raw in c.execute('SELECT creator,source_seq,state FROM creator_history'):
            state=json.loads(raw);transitions[(state['status'],state.get('reason'))]+=1
            if state['status']=='cooldown':
                at=c.execute('SELECT received_at FROM events WHERE seq=?',(seq,)).fetchone()[0]
                end=min(state['expires_at'],c.execute('SELECT received_at FROM events ORDER BY seq DESC LIMIT 1').fetchone()[0])
                requests=c.execute('SELECT COUNT(*) FROM creator_requests WHERE creator=? AND at>? AND at<=?',(creator,at,end)).fetchone()[0]
                blocked_ids.update(r[0] for r in c.execute('SELECT rfq_id FROM creator_requests WHERE creator=? AND at>? AND at<=?',(creator,at,end)))
                cooldowns.append(dict(creator=creator,at=at,end=end,retained_requests_in_window=requests))
        reasons=Counter()
        for rfq,raw in c.execute('SELECT rfq_id,result FROM decisions'):
            if rfq in blocked_ids:
                d=json.loads(raw);reasons[d.get('reason') or d['status']]+=1
        creator_stats.append(dict(run=name,transitions=[dict(status=k[0],reason=k[1],count=v) for k,v in transitions.items()],cooldowns=cooldowns,affected_rfq_ids=len(blocked_ids),affected_decision_reasons=dict(reasons)))
        if name==sorted({q['run'] for q in corrected})[-1]:
            config=json.loads(c.execute("SELECT value FROM state WHERE owner='runtime' AND key='manifest'").fetchone()[0])['config']
            config['quote_reference']={'model':'independent_marginal_reserve_v1','marginal_fraction':0.0}
            write(a.out/'corrected_runtime_candidate.json',config)
        c.close()
    summary['blacklist']=dict(runs=creator_stats,quoted_policy_states=dict(Counter(q['creator_policy']['status'] for q in corrected)),
        blocked_priceable_quotes=sum(not q['creator_policy_eligible'] for q in corrected))
    creator_fills=defaultdict(list)
    for f in base:creator_fills[qs[f['quote_key']]['creator_id']].append(f)
    summary['matched_creators']={k:fillstats(v) for k,v in creator_fills.items()}
    summary['frozen_tail_filter']=json.loads((a.source/'summary.json').read_text())['runs'][0]['correlation_tail']
    write(a.out/'summary.json',summary);print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
