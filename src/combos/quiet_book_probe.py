"""Opt-in shadow REST verification alongside a continuously consumed WS stream."""
import asyncio
from copy import deepcopy
import time
import requests
from .book_verification import verify_snapshot
from .refresh_demand import choose


class BookResyncRequired(ValueError):
    pass


class SnapshotRecoveryExhausted(RuntimeError):
    pass


def serial(book):
    return {side:[(str(p),str(q)) for p,q in levels.items()] for side,levels in book.items()}


def fetch(tokens):
    began=time.time()
    try:
        with requests.Session() as session:
            session.trust_env=False
            response=session.post('https://clob.polymarket.com/books',
                json=[{'token_id':t} for t in tokens],timeout=(2,3),allow_redirects=False)
        return {'request_started_at':began,'received_at':time.time(),'http_status':response.status_code,
                'response_headers':{k:v for k,v in response.headers.items() if k.lower() in ('date','age','cf-cache-status')},
                'payload':response.json()}
    except (requests.RequestException,ValueError) as exc:
        return {'request_started_at':began,'received_at':time.time(),'error_type':type(exc).__name__}


class QuietBookProbe:
    def __init__(self, config, mode):
        if mode!='shadow':raise ValueError('snapshot verification is shadow only')
        self.interval=config.get('interval_seconds',5)
        self.batch=config.get('maximum_books_per_request',100)
        self.budget=config.get('maximum_requests',3)
        self.maximum_resyncs=config.get('maximum_resyncs',2)
        if type(self.maximum_resyncs) is not int or not 0<=self.maximum_resyncs<=5:
            raise ValueError('invalid snapshot recovery budget')
        if type(self.interval) not in (int,float) or not 5<=self.interval<=300:
            raise ValueError('invalid verification interval')
        if type(self.batch) is not int or not 1<=self.batch<=100 or type(self.budget) is not int or not 1<=self.budget<=100:
            raise ValueError('invalid verification budget')
        self.task=None;self.requests=0;self.last_request=0;self.attempted={}
        self.generation=None;self.revisions={};self.observations={}
        self.resyncs=0;self.mismatch_tokens=set()
        self.demand_priority=config.get('demand_priority',False)
        if type(self.demand_priority) is not bool:raise ValueError('invalid demand priority')
        self.demand={}
        self.token_quarantine=config.get('token_quarantine',False)
        if type(self.token_quarantine) is not bool:raise ValueError('invalid token quarantine')
        self.quarantined=set();self.recovery_attempts={}
        self.token_rebuild=config.get('token_rebuild',False)
        if type(self.token_rebuild) is not bool or self.token_rebuild and not self.token_quarantine:
            raise ValueError('token rebuild requires quarantine')
        self.rebuilt=set();self.awaiting_rebuild=set()
        self.maximum_token_rechecks=config.get('maximum_token_rechecks',3)
        if type(self.maximum_token_rechecks) is not int or not 1<=self.maximum_token_rechecks<=10:
            raise ValueError('invalid token recheck budget')

    def reset(self, generation):
        self.generation=generation;self.revisions={};self.observations={}
        self.mismatch_tokens.clear()
        self.awaiting_rebuild.clear()

    def rebuild_targets(self, books):
        if not self.token_rebuild or self.task is not None:return []
        tokens=sorted(self.quarantined-self.rebuilt)[:20]
        for token in tokens:
            self.rebuilt.add(token);self.awaiting_rebuild.add(token)
            books.books.pop(token,None)
        return tokens

    def filter_rebuild_frame(self, payload):
        if payload.get("event_type")=="book":
            self.awaiting_rebuild.discard(payload.get("asset_id"))
        if payload.get("event_type")=="price_change" and self.awaiting_rebuild:
            return dict(payload,price_changes=[c for c in payload.get("price_changes",[]) if c.get("asset_id") not in self.awaiting_rebuild])
        return payload

    def observe(self, token, row):
        self.revisions[token]=self.revisions.get(token,0)+1
        self.observations[token]=dict(row)
        return {'connection_generation':self.generation,'book_revision':self.revisions[token],
                **({'active':False,'invalid_reason':'snapshot_depth_quarantine'} if token in self.quarantined else {})}

    def tick(self, books, emit):
        if self.task is not None and self.task.done():
            envelope=self.task.result();self.task=None
            reference=emit('book_verification_raw',envelope,envelope['received_at'])
            payload=envelope.get('payload')
            if envelope.get('http_status')!=200 or not isinstance(payload,list):
                emit('book_verification_status',{'status':'request_failed','source_reference':reference})
            elif sorted(r.get('asset_id','') for r in payload)!=sorted(self.before):
                emit('book_verification_status',{'status':'asset_census_mismatch','source_reference':reference})
            else:
                for snapshot in payload:
                    token=snapshot['asset_id']
                    try:
                        evidence=verify_snapshot(token=token,snapshot=snapshot,before=serial(self.before[token]),
                            after=serial(books.books.get(token,{})),generation_before=self.request_generation,
                            generation_after=self.generation,revision_before=self.before_revisions[token],
                            revision_after=self.revisions.get(token,-1),request_started_at=envelope['request_started_at'],
                            received_at=envelope['received_at'],response_headers=envelope['response_headers'],source_reference=reference)
                        row=self.observations[token]
                        if token in self.quarantined:
                            self.quarantined.remove(token)
                            row=dict(row,connection_generation=self.generation,book_revision=self.revisions[token])
                            emit('observation',row,time.time())
                            emit('book_quarantine',{'token':token,'market_key':row['market_key'],'status':'recovered',
                                'source_reference':reference,'basis':'matching_rest_ws_full_depth_v1'})
                        emit('book_verification',{'market_key':row['market_key'],'venue':'polymarket',
                            'evidence':evidence,'baseline_observation':row},time.time())
                    except (ValueError,KeyError,TypeError) as exc:
                        emit('book_verification_status',{'token':token,'status':'rejected','reason':str(exc),'source_reference':reference})
                        if str(exc)=='REST and WebSocket ladders differ':self.mismatch_tokens.add(token)
        if self.mismatch_tokens and self.token_quarantine:
            for token in sorted(self.mismatch_tokens):
                self.quarantined.add(token)
                row=dict(self.observations[token],connection_generation=self.generation,
                         book_revision=self.revisions[token],active=False,invalid_reason='snapshot_depth_quarantine')
                emit('observation',row,time.time())
                emit('book_quarantine',{'token':token,'market_key':row['market_key'],'status':'quarantined',
                    'rechecks_used':self.recovery_attempts.get(token,0),'maximum_rechecks':self.maximum_token_rechecks})
            self.mismatch_tokens.clear()
        if self.mismatch_tokens:
            emit('book_resync_required',{'tokens':sorted(self.mismatch_tokens),'generation':self.generation,
                'completed_resyncs':self.resyncs,'maximum_resyncs':self.maximum_resyncs})
            if self.resyncs>=self.maximum_resyncs:
                raise SnapshotRecoveryExhausted('snapshot_recovery_budget_exhausted')
            self.resyncs+=1
            raise BookResyncRequired('snapshot_depth_mismatch_requires_fresh_stream')
        now=time.monotonic()
        if self.token_rebuild and self.quarantined-self.rebuilt:return
        if self.task is not None or self.requests>=self.budget or now-self.last_request<self.interval:
            return
        candidates=[token for token,row in self.observations.items() if row.get('active')
                    and token in books.books and token not in self.awaiting_rebuild and (time.time()-row['observed_at']>15 or token in self.quarantined)
                    and (token not in self.quarantined or self.recovery_attempts.get(token,0)<self.maximum_token_rechecks)]
        candidates.sort(key=lambda token:(self.attempted.get(token,0),self.observations[token]['observed_at']))
        tokens=choose(candidates,self.attempted,self.demand,now,self.batch) if self.demand_priority else candidates[:self.batch]
        if not tokens:return
        emit('book_verification_selection',{'tokens':tokens,'demanded_tokens':[t for t in tokens if t in self.demand],
            'demand_priority':self.demand_priority,'request_number':self.requests+1})
        self.before={token:deepcopy(books.books[token]) for token in tokens}
        self.before_revisions={token:self.revisions[token] for token in tokens}
        self.request_generation=self.generation
        self.requests+=1;self.last_request=now
        for token in tokens:
            self.attempted[token]=now
            if token in self.quarantined:self.recovery_attempts[token]=self.recovery_attempts.get(token,0)+1
        self.task=asyncio.create_task(asyncio.to_thread(fetch,tokens))

    async def close(self):
        if self.task is not None:
            self.task.cancel()
            try:await self.task
            except asyncio.CancelledError:pass
