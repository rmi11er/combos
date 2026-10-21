"""Bounded durable markout follower; pending horizons survive process exits."""
import argparse,fcntl,hashlib,json,sqlite3,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from combos.event_store import EventStore
from combos.rfq_scenario_consumer import RFQScenarioConsumer
from combos.weighted_fair import WeightPolicy
from combos.markout_worker import MarkoutWorker


def run(a):
    if not 1<=a.seconds<=3600:raise ValueError('bounded worker duration required')
    if not a.source.is_file() or not a.decisions.is_file():raise ValueError('existing source and decisions required')
    a.out.mkdir(parents=True,exist_ok=True)
    lock=(a.out/'worker.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    decisions=sqlite3.connect(str(a.decisions));decisions.execute('PRAGMA query_only=ON')
    prior=json.loads(decisions.execute('SELECT identity FROM checkpoint WHERE id=1').fetchone()[0])
    # Verify the source/config/code used for entry pricing is still available.
    for name,digest in prior['inputs']['hashes'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:raise ValueError('entry pricing implementation changed')
    paths=[a.runtime,a.weights,a.catalog,Path(__file__),*sorted((Path(__file__).resolve().parents[1]/'src/combos').glob('*.py'))]
    identity={'source':str(a.source.resolve()),'decisions':str(a.decisions.resolve()),'entry_identity':prior,
        'hashes':{str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
    if prior['inputs']['source']!=str(a.source.resolve()):raise ValueError('entry source differs')
    for p in (a.runtime,a.weights,a.catalog):
        if prior['inputs']['hashes'].get(str(p.resolve()))!=identity['hashes'][str(p.resolve())]:raise ValueError('entry pricing inputs differ')
    pricing=RFQScenarioConsumer(json.loads(a.runtime.read_text()),json.loads(a.catalog.read_text()),WeightPolicy(**json.loads(a.weights.read_text())))
    source=EventStore(a.source);worker=MarkoutWorker(source,decisions,str(a.out/'markouts.sqlite'),pricing,identity)
    started=time.monotonic()
    try:
        while time.monotonic()-started<a.seconds:
            n=worker.step()
            if not n:
                if a.drain:break
                time.sleep(.05)
        result={'source_seq':worker.seq,'labels':worker.db.execute('SELECT COUNT(*) FROM labels').fetchone()[0],
            'pending':worker.db.execute('SELECT COUNT(*) FROM pending').fetchone()[0],
            'statuses':dict(worker.db.execute("SELECT json_extract(value,'$.status'),COUNT(*) FROM labels GROUP BY 1")),
            'elapsed_seconds':time.monotonic()-started,'no_automatic_creator_sanctions':True}
        (a.out/'summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
    finally:worker.close();source.close();decisions.close();lock.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('source','decisions','runtime','weights','catalog','out'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--seconds',type=float,default=60);p.add_argument('--drain',action='store_true')
    run(p.parse_args())
