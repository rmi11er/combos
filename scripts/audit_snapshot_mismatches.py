"""Reconstruct rejected REST/WS ladder checks from the captured raw stream."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from combos.event_store import EventStore
from combos.live_books import Books


def events(store):
    seq=0
    while True:
        rows=store.read(seq,1000)
        if not rows:return
        for event in rows:
            seq=event['seq'];yield event


def top(book):
    return {side:([str(p),str(levels[p])] if levels else None)
        for side,levels in book.items() for p in ([max(levels) if side=='bid' else min(levels)] if levels else [None])}


def run(capture,out):
    store=EventStore(capture/'events.sqlite');targets={}
    runtime=json.loads((capture/'runtime.json').read_text());books=Books('polymarket',runtime['mappings'])
    rows=[];last_frame={}
    try:
        for e in events(store):
            r=e['payload']
            if e['kind']=='book_verification_status' and r.get('reason')=='REST and WebSocket ladders differ':
                targets[(r['source_reference'],r['token'])]=e['seq']
        for e in events(store):
            r=e['payload'];kind=e['kind']
            if kind=='venue_reset' and e['source']=='polymarket':
                books=Books('polymarket',runtime['mappings']);last_frame={}
            elif kind=='polymarket':
                books.consume(r,e['received_at'],e['event_key'])
                touched=[r['asset_id']] if r.get('event_type')=='book' else [x['asset_id'] for x in r.get('price_changes',[])]
                for token in touched:last_frame[token]={'seq':e['seq'],'at':e['received_at'],'type':r['event_type'],'native_timestamp':r.get('timestamp')}
            elif kind=='book_verification_raw' and isinstance(r.get('payload'),list):
                for snapshot in r['payload']:
                    token=snapshot['asset_id']
                    if (e['event_key'],token) not in targets:continue
                    rest={side:books.levels((x['price'],x['size']) for x in snapshot[field]) for side,field in (('bid','bids'),('ask','asks'))}
                    current=books.books[token];differences=[]
                    for side in ('bid','ask'):
                        for price in sorted(set(rest[side])|set(current[side])):
                            if rest[side].get(price)!=current[side].get(price):
                                differences.append({'side':side,'price':str(price),'rest_size':str(rest[side].get(price,0)),
                                                    'ws_size':str(current[side].get(price,0))})
                    rows.append({'token':token,'rest_event_seq':e['seq'],'rejection_seq':targets[(e['event_key'],token)],
                        'last_ws_frame':last_frame.get(token),'request_started_at':r['request_started_at'],
                        'received_at':r['received_at'],'rest_timestamp':snapshot['timestamp'],
                        'rest_top':top(rest),'ws_top':top(current),'top_equal':top(rest)==top(current),
                        'differing_levels':differences})
    finally:store.close()
    if len(rows)!=len(targets):raise ValueError('missing rejection reconstruction')
    summary={'rejections':len(rows),'unique_tokens':len({r['token'] for r in rows}),
        'top_equal':sum(r['top_equal'] for r in rows),'top_different':sum(not r['top_equal'] for r in rows),
        'reproduced_mismatches':sum(bool(r['differing_levels']) for r in rows),
        'differing_level_count_histogram':dict(Counter(len(r['differing_levels']) for r in rows)),
        'hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (capture/'runtime.json',capture/'readiness.json',Path(__file__),Path(__file__).resolve().parents[1]/'src/combos/live_books.py')}}
    out.mkdir(parents=True,exist_ok=False)
    (out/'summary.json').write_text(json.dumps(summary,indent=2));(out/'rows.json').write_text(json.dumps(rows,indent=2))
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capture',required=True,type=Path);p.add_argument('--out',required=True,type=Path)
    a=p.parse_args();print(json.dumps(run(a.capture,a.out)))
