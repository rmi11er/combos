#!/usr/bin/env python3
"""Offline comparison of legacy consumer scheduling with optimized scheduling."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import statistics

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from combos.creator_service import CreatorService
from combos.event_store import EventStore, encode, rfq_payload
from combos.shadow_engine import ShadowEngine
from combos.weighted_fair import WeightPolicy

DERIVED={'creator_policy','creator_diagnostic','consumer_error','decision','risk_transition','markout',
         'quote_invalidated','simulation_fill_rejected','simulation_fill_confirmed'}
TIMING={'evaluated_at','processing_lag_seconds','decision_compute_seconds',
        'decision_completed_at','completed_processing_lag_seconds'}

class LegacyCreator(CreatorService):
    """Pre-optimization step; apply and policy are identical in both arms."""
    def step(self,limit=250):
        processed=0
        with self.store.transaction():
            for event in self.store.read(self.store.cursor(self.name),limit):
                try:self.apply(event)
                except (KeyError,ValueError,TypeError) as exc:
                    self.store.append('consumer_error',self.name,{'source_seq':event['seq'],'reason':str(exc)},f'creator_error:{event["seq"]}',event['received_at'])
                self.store.checkpoint(self.name,event['seq']);processed+=1
        return processed

class LegacyShadow(ShadowEngine):
    def step(self,limit=250):
        processed=0
        with self.store.transaction():
            for event in self.store.read(self.store.cursor(self.name),limit):
                if rfq_payload(event) is not None and self.store.cursor('creators')<event['seq']:break
                at=max(event['received_at'],self.store.get(self.name,'clock',0)) if self.replay else time.time()
                try:
                    self.risk.expire(at,event['seq'])
                    self.apply(event,at)
                    if event['kind'] in ('observation','heartbeat','rfq','kalshi'):self.markouts(at,event['seq'])
                except (KeyError,ValueError,TypeError) as exc:
                    self.store.append('consumer_error',self.name,{'source_seq':event['seq'],'reason':str(exc)},f'shadow_error:{event["seq"]}',at)
                self.store.put(self.name,'clock',at)
                self.store.checkpoint(self.name,event['seq']);processed+=1
        return processed

def clean(value):
    if isinstance(value,dict):return {k:clean(v) for k,v in value.items() if k not in TIMING}
    if isinstance(value,list):return [clean(v) for v in value]
    return value

def fingerprint(store):
    digest=hashlib.sha256();counts={};after=0
    while rows:=store.read(after,500):
        for event in rows:
            after=event['seq']
            if event['kind'] not in DERIVED:continue
            counts[event['kind']]=counts.get(event['kind'],0)+1
            digest.update(encode([event['seq'],event['kind'],event['source'],event['received_at'],event['event_key'],clean(event['payload'])]).encode())
    states={}
    for table in ('state','creator_requests','creator_history','creator_active','creator_markout_groups','decisions','shadow_seen','reservations','exposure','markouts'):
        states[table]=sorted([list(row) for row in store.db.execute(f'SELECT * FROM {table}')],key=encode)
    return {'events_sha256':digest.hexdigest(),'state_sha256':hashlib.sha256(encode(states).encode()).hexdigest(),'counts':counts}

def run(source,out,legacy):
    out.mkdir(parents=True,exist_ok=False)
    store=EventStore(out/'events.sqlite')
    store.db.execute('ATTACH DATABASE ? AS captured',(str((source / 'events.sqlite').resolve()),))
    with store.transaction():
        placeholders=','.join('?' for _ in DERIVED)
        store.db.execute(f'INSERT INTO events SELECT * FROM captured.events WHERE kind NOT IN ({placeholders}) ORDER BY seq',tuple(sorted(DERIVED)))
    store.db.execute('DETACH DATABASE captured')
    inputs=store.db.execute('SELECT COUNT(*) FROM events').fetchone()[0]
    c=json.loads((source/'runtime.json').read_text());w=WeightPolicy(**json.loads((source/'weighting.json').read_text()))
    creator=(LegacyCreator if legacy else CreatorService)(store)
    shadow=(LegacyShadow if legacy else ShadowEngine)(store,c,w,replay=True)
    started=time.perf_counter();steps=0;creator_times=[];shadow_times=[]
    while True:
        before=time.perf_counter();a=creator.step();creator_times.append(time.perf_counter()-before)
        before=time.perf_counter();b=shadow.step();shadow_times.append(time.perf_counter()-before);steps+=1
        if not a and not b:break
    elapsed=time.perf_counter()-started
    result={'mode':'legacy' if legacy else 'optimized','input_events':inputs,'elapsed_seconds':elapsed,
            'input_events_per_second':inputs/elapsed,'batch_rounds':steps,
            'creator_seconds':sum(creator_times),'shadow_seconds':sum(shadow_times),
            'creator_batch_p95_seconds':sorted(creator_times)[int(.95*(len(creator_times)-1))],
            'shadow_batch_p95_seconds':sorted(shadow_times)[int(.95*(len(shadow_times)-1))],
            'fingerprint':fingerprint(store),
            'note':'Sequential offline drain, replay clock, original blocked mappings. Not a live latency or healthy pricing benchmark.'}
    store.close();(out/'result.json').write_text(json.dumps(result,indent=2));return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--capture',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=False)
    results=[run(a.capture,a.out/'legacy',True),run(a.capture,a.out/'optimized',False)]
    equivalent=results[0]['fingerprint']==results[1]['fingerprint']
    report={'results':results,'semantic_equivalence':equivalent,'speedup':results[0]['elapsed_seconds']/results[1]['elapsed_seconds'],
            'excluded_comparison_fields':sorted(TIMING),'source_capture':str(a.capture),
            'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'src/combos/event_store.py',ROOT/'src/combos/creator_service.py',ROOT/'src/combos/shadow_engine.py',Path(__file__).resolve()]}}
    (a.out/'benchmark.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
    if not equivalent:raise SystemExit('semantic mismatch')

if __name__=='__main__':main()
