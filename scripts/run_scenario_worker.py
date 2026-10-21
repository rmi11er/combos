"""Bounded durable research pricing worker attached to an existing event stream."""
import argparse,fcntl,hashlib,json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from combos.event_store import EventStore
from combos.rfq_scenario_consumer import RFQScenarioConsumer
from combos.scenario_worker import ScenarioWorker
from combos.weighted_fair import WeightPolicy


def run(a):
    if not a.db.is_file():raise ValueError('existing input event database required')
    if not 1<=a.seconds<=3600:raise ValueError('bounded worker duration required')
    a.out.mkdir(parents=True,exist_ok=True)
    lock=(a.out/'worker.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    paths=[a.runtime,a.catalog,a.weights,*sorted((Path(__file__).resolve().parents[1]/'src/combos').glob('*.py')),Path(__file__)]
    if a.policy:paths.append(a.policy)
    identity={'source':str(a.db.resolve()),'hashes':{str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
    runtime=json.loads(a.runtime.read_text());consumer=RFQScenarioConsumer(runtime,json.loads(a.catalog.read_text()),WeightPolicy(**json.loads(a.weights.read_text())))
    if a.policy:
        from combos.research_quote_consumer import ResearchQuoteConsumer
        consumer=ResearchQuoteConsumer(consumer,runtime,json.loads(a.policy.read_text()))
    source=EventStore(a.db);worker=ScenarioWorker(source,str(a.out/'decisions.sqlite'),consumer,identity);start=time.monotonic();batches=0
    try:
        while time.monotonic()-start<a.seconds:
            count=worker.step()
            if count:batches+=1
            else:time.sleep(.02)
        summary={'last_source_seq':worker.seq,'batches':batches,'elapsed_seconds':time.monotonic()-start,
            'decisions':worker.db.execute('SELECT COUNT(*) FROM candidate_decisions').fetchone()[0],
            'pricing_statuses':dict(worker.db.execute("SELECT json_extract(result,'$.pricing.status'),COUNT(*) FROM candidate_decisions GROUP BY 1")),
            'live_authorized':False,'quote_sizing_and_risk_applied':a.policy is not None}
        (a.out/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
    finally:worker.close();source.close();lock.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('db','runtime','catalog','weights','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--policy',type=Path)
    p.add_argument('--seconds',type=float,default=120);run(p.parse_args())
