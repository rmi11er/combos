"""Bounded public REST/WS book comparison; never renews production book state."""
import argparse
import asyncio
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import time
import uuid
import requests
from websockets.asyncio.client import connect
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from combos.live_books import Books
from combos.event_store import EventStore
from combos.book_verification import verify_snapshot,candidate_time


def ladder(book):
    return {side:sorted((str(p),str(q)) for p,q in levels.items()) for side,levels in book.items()}


async def run(runtime, capture, out, selected_tokens=None):
    mappings=json.loads(runtime.read_text())['mappings']
    ages={};s=EventStore(capture/'events.sqlite');seq=0
    try:
        while True:
            rows=s.read(seq,1000)
            if not rows:break
            for e in rows:
                seq=e['seq'];r=e['payload']
                if e['kind']=='observation' and r.get('venue')=='polymarket':
                    ages[r['market_key']]=max(ages.get(r['market_key'],0),r['available_at']-r['observed_at'])
    finally:s.close()
    if selected_tokens is None:
        selected=sorted(mappings,key=lambda m:ages.get(m['market_key'],-1),reverse=True)[:8]
    else:
        if not isinstance(selected_tokens,list) or not 1<=len(selected_tokens)<=16 or len(set(selected_tokens))!=len(selected_tokens):
            raise ValueError('one to sixteen distinct known tokens required')
        selected=[m for m in mappings if m.get('polymarket_yes_token') in selected_tokens]
        if {m['polymarket_yes_token'] for m in selected}!=set(selected_tokens):raise ValueError('unknown selected token')
    tokens=[m['polymarket_yes_token'] for m in selected]
    out.mkdir(parents=True,exist_ok=False)
    (out/'selection.json').write_text(json.dumps([{'market_key':m['market_key'],'token':m['polymarket_yes_token'],'prior_max_age':ages.get(m['market_key'])} for m in selected],indent=2))
    books=Books('polymarket',selected);frames=[];counts={t:0 for t in tokens}
    async with connect('wss://ws-subscriptions-clob.polymarket.com/ws/market',open_timeout=10,close_timeout=2,ping_interval=10) as ws:
        generation=uuid.uuid4().hex
        await ws.send(json.dumps({'assets_ids':tokens,'type':'market','custom_feature_enabled':True}))
        async def receive():
            async for raw in ws:
                at=time.time()
                if raw in ('PONG',b'PONG'):continue
                value=json.loads(raw)
                for payload in value if isinstance(value,list) else [value]:
                    frames.append({'received_at':at,'payload':payload})
                    outputs=books.consume(payload,at,'snapshot_check:'+str(len(frames)))
                    for _,r in outputs:
                        for m in selected:
                            if r.get('market_key')==m['market_key']:counts[m['polymarket_yes_token']]+=1
        task=asyncio.create_task(receive())
        try:
            deadline=time.monotonic()+10
            while len(books.books)<len(tokens) and time.monotonic()<deadline:
                if task.done():await task
                await asyncio.sleep(.05)
            before=deepcopy(books.books);before_counts=dict(counts)
            def fetch():
                began=time.time()
                with requests.Session() as session:
                    session.trust_env=False
                    response=session.post('https://clob.polymarket.com/books',
                        json=[{'token_id':t} for t in tokens],timeout=(5,10),allow_redirects=False)
                return {'request_started_at':began,'received_at':time.time(),
                    'http_status':response.status_code,'headers':{k:v for k,v in response.headers.items() if k.lower() in ('date','age','cf-cache-status')},
                    'payload':response.json()}
            rest=await asyncio.to_thread(fetch)
            after=deepcopy(books.books);after_counts=dict(counts)
            if task.done():await task
        finally:
            task.cancel()
            try:await task
            except asyncio.CancelledError:pass
    (out/'frames.json').write_text(json.dumps(frames))
    (out/'rest.json').write_text(json.dumps(rest,indent=2))
    if rest['http_status']!=200 or not isinstance(rest['payload'],list):raise ValueError('REST snapshot failed')
    if sorted(r['asset_id'] for r in rest['payload'])!=sorted(tokens):raise ValueError('REST asset census differs')
    comparisons=[];verifications=[]
    for r in rest['payload']:
        token=r['asset_id'];rest_book={side:books.levels((x['price'],x['size']) for x in r[field]) for side,field in (('bid','bids'),('ask','asks'))}
        comparisons.append({'token':token,'native_age_at_rest_receipt':rest['received_at']-float(r['timestamp'])/1000,
            'ws_updates_during_request':after_counts[token]-before_counts[token],
            'full_ladder_matches_before':rest_book==before.get(token),
            'full_ladder_matches_after':rest_book==after.get(token),
            'rest_ladder':ladder(rest_book),'ws_before':ladder(before.get(token,{})),
            'ws_after':ladder(after.get(token,{}))})
        try:
            evidence=verify_snapshot(token=token,snapshot=r,before=ladder(before.get(token,{})),
                after=ladder(after.get(token,{})),generation_before=generation,generation_after=generation,
                revision_before=before_counts[token],revision_after=after_counts[token],
                request_started_at=rest['request_started_at'],received_at=rest['received_at'],
                response_headers=rest['headers'],source_reference=str(out/'rest.json')+'#'+token)
            candidate=candidate_time(evidence,token=token,generation=generation,revision=after_counts[token],
                current_book=ladder(after[token]),now=rest['received_at'])
            verifications.append({'token':token,'status':'verified_at_receipt','evidence':evidence,'candidate':candidate})
        except (ValueError,KeyError,TypeError) as exc:
            verifications.append({'token':token,'status':'rejected','reason':str(exc)})
    (out/'verifications.json').write_text(json.dumps(verifications,indent=2))
    (out/'comparisons.json').write_text(json.dumps(comparisons,indent=2))
    summary={'books':len(tokens),'full_ladder_matches_before':sum(r['full_ladder_matches_before'] for r in comparisons),
        'full_ladder_matches_after':sum(r['full_ladder_matches_after'] for r in comparisons),
        'quiet_during_request':sum(r['ws_updates_during_request']==0 for r in comparisons),
        'native_ages_seconds':[r['native_age_at_rest_receipt'] for r in comparisons],
        'production_book_times_renewed':False,'rest_requests':1,
        'verified_at_receipt':sum(r['status']=='verified_at_receipt' for r in verifications),
        'connection_closed_after_check':True,
        'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('runtime','capture','out'):p.add_argument('--'+name,required=True,type=Path)
    p.add_argument('--tokens',type=Path)
    a=p.parse_args();print(json.dumps(asyncio.run(run(a.runtime,a.capture,a.out,
        json.loads(a.tokens.read_text()) if a.tokens else None))))
