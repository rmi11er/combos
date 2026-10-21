"""Audit captured exchange age/depth and causal coverage at Pinnacle receipts."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from combos.event_store import EventStore


def run(capture, out):
    store=EventStore(capture/'events.sqlite')
    latest={'kalshi':{},'polymarket':{}}
    ages={v:[] for v in latest};counts={v:Counter() for v in latest}
    checkpoints=[];seq=0
    try:
        while True:
            events=store.read(seq,1000)
            if not events:break
            for event in events:
                seq=event['seq'];row=event['payload'];venue=event['source']
                if event['kind']=='venue_reset' and venue in latest:
                    latest[venue].clear()
                if event['kind']=='observation' and row.get('venue') in latest:
                    venue=row['venue'];at=event['received_at']
                    if row['available_at']>at:raise ValueError('observation available after event receipt')
                    latest[venue].setdefault(row['market_key'],[]).append((seq,row))
                    age=at-row['observed_at'];ages[venue].append(age)
                    counts[venue]['observations']+=1
                    counts[venue]['over_15_seconds_at_receipt']+=int(age>15)
                    counts[venue]['over_120_seconds_at_receipt']+=int(age>120)
                if event['kind']=='external_raw' and venue=='pinnacle':
                    at=event['received_at'];valid={};reasons={}
                    for exchange, books in latest.items():
                        valid[exchange]=set();reasons[exchange]=Counter()
                        for key,history in books.items():
                            causal=[(source_seq,book) for source_seq,book in history
                                    if source_seq<seq and book['available_at']<=at]
                            if not causal:
                                reasons[exchange]['not_available_at_snapshot_receipt']+=1
                                continue
                            source_seq,book=causal[-1]
                            if not book.get('active'):reason='inactive'
                            elif min(book.get('yes_bid_size',0),book.get('yes_ask_size',0))<=0:reason='missing_two_sided_depth'
                            elif not 0<=at-book['observed_at']<=15:reason='outside_15_second_age'
                            else:reason='eligible';valid[exchange].add(key)
                            reasons[exchange][reason]+=1
                    checkpoints.append({'pinnacle_event_seq':seq,'received_at':at,
                        'exchange_reasons':{v:dict(c) for v,c in reasons.items()},
                        'paired_fresh_depth_keys':len(valid['kalshi']&valid['polymarket'])})
    finally:store.close()
    result={'source_capture':str(capture),'exchange_max_age_seconds':15,
        'observation_age_at_receipt':{v:{**dict(counts[v]),'median_seconds':statistics.median(a),
            'maximum_seconds':max(a),'minimum_seconds':min(a)} for v,a in ages.items() if a},
        'pinnacle_receipt_checkpoints':checkpoints,
        'interpretation':'native timestamp age under current adapter; not proof a quiet book is obsolete',
        'source_hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
            (capture/'readiness.json',capture/'runtime.json',Path(__file__))}}
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x') as handle:json.dump(result,handle,indent=2)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capture',required=True,type=Path);p.add_argument('--out',required=True,type=Path)
    a=p.parse_args();print(json.dumps(run(a.capture,a.out),indent=2))
