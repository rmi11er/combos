"""Attach causal future marks to archived candidates; never publishes blacklist state."""
import argparse
from collections import Counter,defaultdict
import hashlib,json,statistics,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from combos.event_store import EventStore,rfq_payload
from combos.rfq_scenario_consumer import RFQScenarioConsumer
from combos.research_markout import ResearchMarkouts
from combos.weighted_fair import WeightPolicy


def run(capture,catalog,comparison,out):
    runtime=json.loads((capture/'runtime.json').read_text());weights=json.loads((capture/'weighting.json').read_text())
    pricing=RFQScenarioConsumer(runtime,json.loads(catalog.read_text()),WeightPolicy(**weights))
    wanted={}
    for line in (comparison/'priced_decisions.jsonl').open():
        r=json.loads(line)
        if r['model']=='captured_sharp_peer':wanted[r['source_seq']]=r
    scheduler=ResearchMarkouts(pricing);store=EventStore(capture/'events.sqlite')
    out.mkdir(parents=True,exist_ok=False);counts=Counter();moves=defaultdict(list);seq=0;watermark=float('-inf');scheduled=0
    with (out/'labels.jsonl').open('w') as stream:
        def save(rows):
            for r in rows:
                counts[(r['horizon_seconds'],r['status'],r.get('reason'))]+=1
                if r['status']=='observed':moves[r['horizon_seconds']].append(r['adverse_move_cents'])
                stream.write(json.dumps(r)+'\n')
        try:
            while True:
                events=store.read(seq,1000)
                if not events:break
                for event in events:
                    watermark=max(watermark,event['received_at'])
                    save(scheduler.advance(watermark,seq))
                    pricing.consume(event,price_rfqs=False);seq=event['seq']
                    if seq in wanted:
                        entry=wanted[seq];msg=rfq_payload(event)
                        # Ensure entry source/model identity before any later marks.
                        original=pricing.revalue(msg,entry['at'],seq)
                        assert original['status']=='scenario_priced'
                        assert next(s for s in original['scenarios'] if s['assumed_usd_per_native_unit']==1)==entry['scenario']
                        scheduler.schedule(msg,entry);scheduled+=1
            save(scheduler.advance(watermark,seq,inclusive=True));save(scheduler.finish())
        finally:store.close()
    assert scheduled==len(wanted) and sum(counts.values())==len(wanted)*3
    summary={'entries':scheduled,'counts':[{'horizon':h,'status':s,'reason':r,'count':n} for (h,s,r),n in counts.items()],
        'adverse_move_cents':{str(h):{'count':len(v),'mean':statistics.mean(v),'median':statistics.median(v),'min':min(v),'max':max(v)} for h,v in moves.items()},
        'limitations':['candidate marks are not fills or realized P&L','same-model marks can reflect blend/freshness changes',
            'right-censored and stale/unmapped future marks remain explicit','no automatic creator sanctions','short single-slate capture'],
        'hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [catalog,capture/'runtime.json',capture/'weighting.json',comparison/'priced_decisions.jsonl',Path(__file__),Path('src/combos/research_markout.py'),Path('src/combos/rfq_scenario_consumer.py')]}}
    (out/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps({k:v for k,v in summary.items() if k!='hashes'},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('capture','catalog','comparison','out'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();run(a.capture,a.catalog,a.comparison,a.out)
