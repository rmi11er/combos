#!/usr/bin/env python3
"""Summarize confirmation-time shadow fill edge and fair components."""
import argparse, csv, json, math
from collections import defaultdict
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from combos.event_store import EventStore
from combos.pricing import short_yes_economics


def fill_markouts(fill, marks):
    """Quote-time horizons, resized to the actual paper allocation and fees."""
    result={}
    for horizon,mark in marks.items():
        mark=dict(mark)
        if mark.get('status')=='observed' and fill.get('maker_fee_rate') is not None:
            economics=short_yes_economics(fill['quantity'],fill['fill_price'],mark['reference']['value'],fill['maker_fee_rate'])
            mark.update(markout_net_edge_dollars=economics['expected_edge'],
                        markout_net_edge_per_share=economics['expected_edge']/fill['quantity'],
                        quantity_basis='allocated_paper_fill',horizon_basis='quote_decision_time')
        result[horizon]=mark
    return result


def bucket(value):
    for upper,label in ((0.,'negative'),(.1,'0-.1c'),(.3,'.1-.3c'),(.5,'.3-.5c'),(1.,'.5-1c'),(math.inf,'1c+')):
        if value < upper: return label


def components(pricing):
    legs=(pricing or {}).get('legs',[])
    weights=defaultdict(float); spreads=[]; gaps=[]
    for leg in legs:
        for venue,detail in (leg.get('venues') or {}).items():
            weights[venue] += float(detail.get('weight',0.))
        spreads.append(float(leg.get('venue_point_range_cents',0.)))
        guard=leg.get('guard') or {}
        gaps.append(float(guard.get('maximum_interval_gap_cents',0.)))
    n=max(1,len(legs))
    return {'leg_count':len(legs),'avg_source_disagreement_cents':sum(spreads)/n,
            'max_interval_gap_cents':max(gaps,default=0.),
            'kalshi_weight':weights['kalshi']/n,'polymarket_weight':weights['polymarket']/n,
            'pinnacle_weight':weights['pinnacle']/n}


def main():
    p=argparse.ArgumentParser();p.add_argument('--events',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True); args=p.parse_args()
    store=EventStore(args.events)
    rows=[]; pending_rows=[]; markouts=defaultdict(dict); settlements={}; after=0
    while True:
        events=store.read(after,1000)
        if not events: break
        for event in events:
            after=event['seq']
            if event['kind']=='markout':
                payload=event['payload']
                markouts[payload.get('decision_seq')][str(payload.get('horizon_seconds'))]=payload
                continue
            if event['kind']=='risk_transition' and event['payload'].get('new_status')=='simulated_settled':
                settlements[event['payload'].get('reservation_id')]=event['payload']
                continue
            if event['kind']!='simulation_fill_confirmed': continue
            x=dict(event['payload']); x.update(components(x.get('confirmation_pricing')))
            x['edge_bucket']=bucket(float(x['fill_net_edge_cents']))
            x['event_seq']=event['seq']; pending_rows.append(x)
    for x in pending_rows:
        x['markouts']=fill_markouts(x,markouts.get(x.get('decision_source_seq'),{}))
        settlement=settlements.get(x['reservation_id'])
        x['settlement_pnl_dollars']=None if settlement is None else settlement.get('pnl_dollars')
        x['settlement_payout_dollars']=None if settlement is None else settlement.get('payout_dollars')
        x['settlement_cohort']=('pending' if settlement is None else
            ('maker_win' if settlement.get('pnl_dollars',0)>0 else
             'maker_loss' if settlement.get('pnl_dollars',0)<0 else 'break_even'))
        rows.append(x)
    store.close(); args.out.mkdir(parents=True,exist_ok=False)
    horizon_keys=sorted({h for row in rows for h in row.get('markouts',{})}, key=float)
    for row in rows:
        for h in horizon_keys:
            mark=row.get('markouts',{}).get(h,{})
            row[f'markout_{h}_status']=mark.get('status')
            row[f'markout_{h}_net_edge_dollars']=mark.get('markout_net_edge_dollars')
            row[f'markout_{h}_net_edge_cents']=None if mark.get('markout_net_edge_per_share') is None else 100*mark.get('markout_net_edge_per_share')
    fields=['event_seq','reservation_id','creator_id','confirmed_at','leg_count','quantity','fill_price',
            'quote_gross_edge_cents','fill_gross_edge_cents','fill_net_edge_cents','fill_net_edge_dollars',
            'fair_move_cents','avg_source_disagreement_cents','max_interval_gap_cents',
            'kalshi_weight','polymarket_weight','pinnacle_weight','too_tight_at_confirmation','edge_bucket',
            'settlement_cohort','settlement_pnl_dollars']
    fields.append('settlement_payout_dollars')
    fields.extend(['public_trade_id','actual_exchange_fill','fill_assumption','required_net_edge_per_share'])
    for h in horizon_keys:
        fields.extend([f'markout_{h}_status',f'markout_{h}_net_edge_dollars',f'markout_{h}_net_edge_cents'])
    with (args.out/'fills.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows({k:r.get(k) for k in fields} for r in rows)
    groups=defaultdict(list)
    for row in rows:
        groups[('edge_bucket',row['edge_bucket'])].append(row)
        groups[('leg_count',str(row['leg_count']))].append(row)
        groups[('creator_id',str(row['creator_id']))].append(row)
        groups[('settlement_cohort',str(row['settlement_cohort']))].append(row)
    summary=[]
    for (kind,key),values in sorted(groups.items()):
        def mean(k): return sum(float(v.get(k,0) or 0) for v in values)/len(values)
        observed_markouts=[v for v in values if v.get('markouts')]
        horizon_summary={}
        for horizon in sorted({h for v in observed_markouts for h in v['markouts']}):
            hrows=[v['markouts'][horizon] for v in values if horizon in v.get('markouts',{}) and
                   v['markouts'][horizon].get('status')=='observed']
            horizon_summary[horizon]={'observations':len(hrows),
                'markout_net_edge_dollars':sum(float(x.get('markout_net_edge_dollars',0) or 0) for x in hrows),
                'mean_markout_net_edge_cents':(100*sum(float(x.get('markout_net_edge_per_share',0) or 0) for x in hrows)/len(hrows) if hrows else None)}
        settled=[float(v['settlement_pnl_dollars']) for v in values if v.get('settlement_pnl_dollars') is not None]
        summary.append({'group':kind,'key':key,'fills':len(values),
                        'net_edge_dollars':sum(float(v.get('fill_net_edge_dollars',0) or 0) for v in values),
                        'settled_fills':len(settled),'settlement_pnl_dollars':sum(settled),
                        'mean_settlement_pnl_dollars':sum(settled)/len(settled) if settled else None,
                        'mean_net_edge_cents':mean('fill_net_edge_cents'),
                        'mean_fair_move_cents':mean('fair_move_cents'),
                        'mean_source_disagreement_cents':mean('avg_source_disagreement_cents'),
                        'too_tight_count':sum(bool(v.get('too_tight_at_confirmation')) for v in values),
                        'markouts':horizon_summary})
    settled=[r for r in rows if r.get('settlement_pnl_dollars') is not None]
    report={'fills':len(rows),'settled_fills':len(settled),'pending_settlement_fills':len(rows)-len(settled),
            'groups':summary,
            'interpretation':'markout values are interim mark-to-model diagnostics; do not add them to terminal settlement PnL as a second economic cash flow'}
    (args.out/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'fills':len(rows),'out':str(args.out)},indent=2))


if __name__=='__main__': main()
