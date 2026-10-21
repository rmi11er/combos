"""Complete-census parity and compute timing for stateful RFQ research pricing."""
import argparse,json,sys,time,hashlib,statistics
from pathlib import Path
from collections import Counter,defaultdict
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from combos.rfq_scenario_consumer import RFQScenarioConsumer
from combos.event_store import EventStore
from combos.weighted_fair import WeightPolicy


def metrics(v):
    v=sorted(v)
    return {'count':len(v),'median_ms':statistics.median(v)*1000,'p99_ms':v[round((len(v)-1)*.99)]*1000,'maximum_ms':max(v)*1000} if v else None


def run(capture,catalog,expected,out):
    runtime=json.loads((capture/'runtime.json').read_text());policy=WeightPolicy(**json.loads((capture/'weighting.json').read_text()));consumer=RFQScenarioConsumer(runtime,json.loads(catalog.read_text()),policy)
    baseline=json.loads(expected.read_text());store=EventStore(capture/'events.sqlite');seq=0;index=0;timings=defaultdict(list);counts=Counter();began=time.perf_counter()
    try:
        while True:
            events=store.read(seq,1000)
            if not events:break
            for event in events:
                seq=event['seq'];start=time.perf_counter();r=consumer.consume(event);elapsed=time.perf_counter()-start
                if r is not None:
                    if index>=len(baseline) or r!=baseline[index]:raise ValueError('decision parity mismatch at '+str(seq))
                    index+=1;counts[r.get('reason',r['status'])]+=1;timings[r['status']].append(elapsed)
                elif event['kind']=='external_raw' and event['source']=='pinnacle':timings['pinnacle_snapshot_rebind'].append(elapsed)
    finally:store.close()
    if index!=len(baseline):raise ValueError('incomplete RFQ census')
    result={'exact_decision_parity':True,'rfqs':index,'counts':dict(counts),'compute':{k:metrics(v) for k,v in timings.items()},'total_replay_seconds':time.perf_counter()-began,
        'limitations':['replay timing excludes arrival queue and persistence','scenario computation excludes quote sizing, risk and creator decisions','not production payoff approval'],
        'hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [expected,capture/'runtime.json',catalog,Path('src/combos/rfq_scenario_consumer.py'),Path(__file__)]}}
    out.mkdir(parents=True,exist_ok=False);(out/'verification.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='hashes'},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('capture','catalog','expected','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.capture,a.catalog,a.expected,a.out)
