"""Causal exchange coverage and conditional moneyline source agreement."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics
from dataclasses import asdict
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from combos.event_store import EventStore
from combos.verified_book_state import VerifiedBookState
from combos.pinnacle_feed import fixture_index,same_native_market_identity
from combos.snapshot_age import delivery_observation_time
from combos.observations import Observation
from combos.pricing import pinnacle_fair


def run(capture,out):
    runtime=json.loads((capture/'runtime.json').read_text());mappings={m['market_key']:m for m in runtime['mappings']}
    pm=VerifiedBookState();kalshi={};pin=None;checkpoints=[];comparisons=[];exclusions=Counter()
    store=EventStore(capture/'events.sqlite');seq=0
    try:
        while True:
            events=store.read(seq,1000)
            if not events:break
            for event in events:
                seq=event['seq'];r=event['payload'];kind=event['kind'];at=event['received_at']
                pm.consume(event)
                if kind=='venue_reset' and event['source']=='kalshi':kalshi.clear()
                if kind=='venue_reset' and event['source']=='pinnacle':pin=None
                if kind=='observation' and r.get('venue')=='kalshi':kalshi[r['market_key']]=r
                if kind=='external_raw' and event['source']=='pinnacle':
                    observed,context=delivery_observation_time(r,r['retrieved_at'],30,runtime['pinnacle_freshness_policy'])
                    pin={'fixtures':fixture_index(r['payload']),'observed_at':observed,'available_at':max(at,r['retrieved_at']),'seq':seq}
                if kind!='heartbeat' or event['source']!='polymarket':continue
                baseline,candidate=set(),set()
                for key,k in kalshi.items():
                    if not k.get('active') or k['available_at']>at or not 0<=at-k['observed_at']<=15 or min(k['yes_bid_size'],k['yes_ask_size'])<=0:continue
                    pair=pm.pair(key,at)
                    if pair['baseline']:baseline.add(key)
                    if pair['candidate']:candidate.add(key)
                checkpoints.append({'seq':seq,'at':at,'paired_baseline_keys':len(baseline),'paired_candidate_keys':len(candidate)})
                if not pin or pin['available_at']>at or not 0<=at-pin['observed_at']<=90:continue
                for key in sorted(candidate):
                    mapping=mappings[key]
                    if mapping['market_type']!='moneyline' or mapping.get('period','full_game')!='full_game':continue
                    try:
                        if at>=mapping['start_at']-60:raise ValueError('pregame_cutoff')
                        spec=mapping['pinnacle'];fixture=pin['fixtures'][spec['fixture_id']];book=fixture['bookmakerOdds']['pinnacle+30']
                        market=book['markets'][spec['market_id']]
                        if fixture.get('statusId')!=0 or book.get('bookmakerIsActive') is not True or book.get('suspended') is not False or market.get('marketActive') is not True:raise ValueError('inactive_pinnacle')
                        if not same_native_market_identity(spec['bookmaker_market_id'],market['bookmakerMarketId'],fixture,book,spec):raise ValueError('changed_pinnacle_identity')
                        prices=[];limits=[]
                        for side in ('yes','no'):
                            selector=spec[side];value=market['outcomes'][selector['outcome_id']]['players']['0']
                            if value.get('active') is not True or value['bookmakerOutcomeId']!=selector['bookmaker_outcome_id']:raise ValueError('inactive_or_changed_outcome')
                            prices.append(float(value['price']))
                            limits.append(float(value['limit']))
                        q=pinnacle_fair(*prices).point
                        k=Observation.from_record(kalshi[key]);p=Observation.from_record(pm.pair(key,at)['candidate'])
                        pm_gap=100*(p.interval.point-k.interval.point);pin_gap=100*(q-k.interval.point)
                        comparisons.append({'checkpoint_seq':seq,'decision_at':at,'market_key':key,'pinnacle_seq':pin['seq'],
                            'exchange_observations':[asdict(k),asdict(p)],'pinnacle_decimal_odds':prices,
                            'pinnacle_native_stake_limits':limits,'pinnacle_observed_at':pin['observed_at'],
                            'pinnacle_available_at':pin['available_at'],'mapping_reference':mapping['mapping_reference'],
                            'kalshi_point':k.interval.point,'polymarket_point':p.interval.point,'pinnacle_conditional_point':q,
                            'pm_minus_k_cents':pm_gap,'pin_minus_k_cents':pin_gap,
                            'sharp_agreement_vs_k':abs(100*(q-p.interval.point))<=1 and pm_gap*pin_gap>0 and min(abs(pm_gap),abs(pin_gap))>=.5,
                            'kalshi_fee_expanded_width_cents':100*(k.interval.upper-k.interval.lower),
                            'polymarket_fee_expanded_width_cents':100*(p.interval.upper-p.interval.lower)})
                    except (ValueError,KeyError,TypeError) as exc:exclusions[str(exc)]+=1
    finally:store.close()
    out.mkdir(parents=True,exist_ok=False)
    summary={'checkpoints':len(checkpoints),'mean_paired_baseline_keys':statistics.mean(r['paired_baseline_keys'] for r in checkpoints),
        'mean_paired_candidate_keys':statistics.mean(r['paired_candidate_keys'] for r in checkpoints),
        'moneyline_comparisons':len(comparisons),'unique_moneyline_keys':len({r['market_key'] for r in comparisons}),
        'sharp_agreement_observations':sum(r['sharp_agreement_vs_k'] for r in comparisons),'exclusions':dict(exclusions),
        'limitations':['repeated observations are not independent','Pinnacle conditional moneyline versus exchange tie payoff unadjusted',
                       'no liquidity-weighted three-source fair or profitability test','coverage baseline also includes Kalshi refresh snapshots'],
        'hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (capture/'runtime.json',capture/'readiness.json',Path(__file__))}}
    for name,value in (('summary',summary),('checkpoints',checkpoints),('comparisons',comparisons)):
        (out/(name+'.json')).write_text(json.dumps(value,indent=2))
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capture',required=True,type=Path);p.add_argument('--out',required=True,type=Path)
    a=p.parse_args();print(json.dumps(run(a.capture,a.out)))
