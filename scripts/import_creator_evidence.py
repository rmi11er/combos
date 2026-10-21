"""Bounded follower importing durable markout labels into a persistent review store."""
import argparse
import fcntl
import json
from pathlib import Path
import time
from creator_evidence_store import CreatorEvidenceStore


def run(a):
    if not 0<=a.seconds<=3600:raise ValueError('bounded duration required')
    plan=json.loads(a.plan.read_text());a.out.mkdir(parents=True,exist_ok=True)
    lock=(a.out/'worker.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    store=CreatorEvidenceStore(a.out/'evidence.sqlite');start=time.monotonic();passes=0;added=0
    try:
        while True:
            receipts=[store.import_source(item['marks'],item['runtime']) for item in plan['captures']]
            added+=sum(r['added'] for r in receipts);passes+=1
            result={'passes':passes,'added_this_run':added,'sources':receipts,
                'total_labels':store.db.execute('SELECT COUNT(*) FROM evidence').fetchone()[0],
                'automatic_sanctions':0,'publication_basis':'committed evidence-row visibility; first_seen_at is observation time'}
            (a.out/'status.json').write_text(json.dumps(result,indent=2))
            if time.monotonic()-start>=a.seconds:break
            time.sleep(min(1,max(0,a.seconds-(time.monotonic()-start))))
        print(json.dumps(result,indent=2))
    finally:
        store.close();lock.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--seconds',type=float,default=0)
    run(p.parse_args())
