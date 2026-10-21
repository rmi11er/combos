"""Enrich recorded decisions and attribute observed markouts to prices and weights."""
import argparse
from collections import defaultdict
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import sys
import zlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from combos.rfq_scenario_consumer import RFQScenarioConsumer
from combos.weighted_fair import WeightPolicy
from combos.event_store import rfq_payload
from fair_change_attribution import decompose, weight_drivers


def without_trace(p):
    p=deepcopy(p)
    for scenario in p.get('scenarios',[]):
        for leg in scenario['legs']:leg.pop('venue_components',None)
    return p


def closed(path):return sqlite3.connect(path.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)


def run(a):
    runtime=json.loads((a.capture/'runtime.json').read_text());runtime['record_venue_components']=True
    pricing=RFQScenarioConsumer(runtime,json.loads(a.catalog.read_text()),WeightPolicy(**json.loads((a.capture/'weighting.json').read_text())))
    src=closed(a.capture/'events.sqlite');dec=closed(a.worker/'worker/decisions.sqlite');marks=closed(a.worker/'markouts/markouts.sqlite')
    labels=defaultdict(list);needed=set()
    for raw, in marks.execute("SELECT value FROM labels WHERE json_extract(value,'$.status')='observed'"):
        row=json.loads(raw);labels[row['available_source_seq']].append(row);needed.add(row['decision_seq'])
    entries={};rows=[];checked=0;screen_rows=[]
    screen_policy=json.loads(a.consensus_screen.read_text())['policy'] if getattr(a,'consensus_screen',None) else None
    decisions=iter(dec.execute('SELECT source_seq,result FROM candidate_decisions ORDER BY source_seq'));next_decision=next(decisions,None)
    for seq,kind,source,at,raw in src.execute('SELECT seq,kind,source,received_at,payload FROM events ORDER BY seq'):
        event=dict(seq=seq,kind=kind,source=source,received_at=at,payload=json.loads(zlib.decompress(raw)))
        pricing.consume(event,price_rfqs=False)
        if next_decision and seq==next_decision[0]:
            record=json.loads(next_decision[1]);expected={k:v for k,v in record['pricing'].items() if k!='research_policy'}
            if expected.get('reason')!='processing_lag_or_future_receipt':
                p=pricing.revalue(rfq_payload(event),record['evaluation_at'],seq)
                assert (p if runtime.get('record_venue_components') and any('venue_components' in l for s in expected.get('scenarios',[]) for l in s['legs']) else without_trace(p))==expected,seq;checked+=1
                if screen_policy and p.get('scenarios'):
                    from consensus_price_screen import screen_leg, combo_lean_sensitivity
                    scenario=next(s for s in p['scenarios'] if s['assumed_usd_per_native_unit']==1)
                    screened=[screen_leg(l,screen_policy) for l in scenario['legs']]
                    screen_rows.append({'decision_seq':seq,'legs':screened,
                        'maximum_fraction_sensitivity':combo_lean_sensitivity(screened,screen_policy['maximum_lean_fraction'])})
                if seq in needed:entries[seq]=(rfq_payload(event),next(s for s in p['scenarios'] if s['assumed_usd_per_native_unit']==1))
            next_decision=next(decisions,None)
        for label in labels.pop(seq,[]):
            msg,entry=entries[label['decision_seq']]
            future=pricing.revalue(msg,label['valuation_at'],label['decision_seq'])
            expected_future=label['future_pricing']
            assert (future if any('venue_components' in l for s in expected_future.get('scenarios',[]) for l in s['legs']) else without_trace(future))==expected_future
            s=next(s for s in future['scenarios'] if s['assumed_usd_per_native_unit']==1)
            parts=decompose(entry,s)
            assert abs(parts['total_change_cents']-label['adverse_move_cents'])<1e-9
            row={'decision_seq':label['decision_seq'],'horizon':label['horizon_seconds'],**parts}
            if getattr(a,'weight_drivers',False):row['weight_drivers']=weight_drivers(entry,s)
            rows.append(row)
    assert next_decision is None and not labels
    by=defaultdict(list)
    for row in rows:by[row['horizon']].append(row)
    summary={'baseline_pricing_records_exact':checked,'observed_markouts_reconciled':len(rows),
        'horizons':{str(h):{'count':len(v),**{key:sum(r[key] for r in v)/len(v) for key in ('price_component_cents','weight_component_cents','total_change_cents')},
            'zero_price_component':sum(abs(r['price_component_cents'])<1e-10 for r in v)} for h,v in by.items()},
        'limitations':['Algebraic symmetric attribution, not a causal intervention: weights depend on prices, depth and freshness.',
            'Unweighted, overlapping RFQs and observed marks only; missing marks can select the sample.',
            'Venue-price changes are not independently validated truth or evidence of creator toxicity.']}
    if getattr(a,'weight_drivers',False):
        fields=('two_sided_depth_payout_dollars','fee_expanded_spread_cents','freshness','score_multiplier','weight')
        summary['marks_with_changed_input']={field:sum(any(field in d['changed_fields'] for d in r['weight_drivers']) for r in rows) for field in fields}
        summary['freshness_only_score_input_marks']=sum(
            any('freshness' in d['changed_fields'] for d in r['weight_drivers']) and
            not any(set(d['changed_fields']) & {'two_sided_depth_payout_dollars','fee_expanded_spread_cents','score_multiplier'} for d in r['weight_drivers'])
            for r in rows)
    if screen_policy:
        legs=[l for row in screen_rows for l in row['legs']]
        summary['consensus_price_screen']={'priced_rfqs':len(screen_rows),'leg_occurrences':len(legs),
            'unique_market_sides':len({(l['market_key'],l['side']) for l in legs}),
            'passing_leg_occurrences':sum(l['price_screen_passes'] for l in legs),
            'rfqs_with_passing_leg':sum(any(l['price_screen_passes'] for l in r['legs']) for r in screen_rows),
            'scope':'All baseline priced RFQs, including those without observed future marks.',
            'limitations':'Recorded baseline relative liquidity scores; not the separately gated consensus model. Mapping/fee/stake-currency gates are not certified. No outcomes or execution evidence.'}
    a.out.mkdir(parents=True,exist_ok=False);(a.out/'summary.json').write_text(json.dumps(summary,indent=2));(a.out/'rows.json').write_text(json.dumps(rows,indent=2))
    if screen_policy:(a.out/'consensus_price_screen.json').write_text(json.dumps(screen_rows,indent=2))
    for db in (src,dec,marks):db.close()
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('capture','worker','catalog','out'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--weight-drivers',action='store_true')
    p.add_argument('--consensus-screen',type=Path)
    run(p.parse_args())
