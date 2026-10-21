"""Audit imported payload census and availability timing after writers stop."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import statistics


def closed(path):
    return sqlite3.connect(path.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)


def metrics(values):
    values=sorted(values)
    return {'count':len(values),'median_ms':statistics.median(values)*1000,
        'p99_ms':values[round((len(values)-1)*.99)]*1000,'max_ms':max(values)*1000} if values else None


def audit(path):
    db=closed(path);sources=[]
    for source_id,location,raw_identity,_ in db.execute('SELECT * FROM sources ORDER BY source_id'):
        source=closed(Path(location));identity=source.execute('SELECT identity FROM checkpoint WHERE id=1').fetchone()[0]
        assert identity==raw_identity
        assert hashlib.sha256(identity.encode()).hexdigest()==source_id
        expected={(seq,h):(computed,raw) for seq,h,computed,raw in source.execute('SELECT decision_seq,horizon,computed_at,value FROM labels')}
        source.close();gaps=[];seen=0
        for seq,h,computed,first_seen,record_hash,raw,available in db.execute('''
            SELECT e.decision_seq,e.horizon,e.computed_at,e.first_seen_at,e.record_hash,e.payload,a.available_by
            FROM evidence e LEFT JOIN availability a USING(source_id,decision_seq,horizon) WHERE e.source_id=?''',(source_id,)):
            assert expected.pop((seq,h))==(computed,raw)
            assert hashlib.sha256(json.dumps([computed,raw],separators=(',',':')).encode()).hexdigest()==record_hash
            assert available is not None and computed<=first_seen<=available
            gaps.append(available-computed);seen+=1
        assert not expected
        sources.append({'source_id':source_id,'labels':seen,'exact_payload_census':True,
            'computed_to_confirmed_available':metrics(gaps)})
    orphan=db.execute('''SELECT COUNT(*) FROM availability a LEFT JOIN evidence e
        USING(source_id,decision_seq,horizon) WHERE e.source_id IS NULL''').fetchone()[0]
    assert orphan==0;db.close()
    return {'sources':sources,'all_labels_and_receipts_reconciled':True,
        'limitations':['Run after writers stop. Computed-to-available includes importer scheduling and historical import delay.',
            'Source fair arithmetic and creator toxicity are not validated by this storage audit.']}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--db',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();result=audit(a.db)
    with a.out.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2))
