"""Conservative as-of reviews, stratified by immutable capture identity."""
import argparse
from collections import Counter,defaultdict
import json
import math
from pathlib import Path
import sqlite3
from review_creator_markouts import grouped


def review(path,asof):
    if not math.isfinite(asof):raise ValueError('finite as-of timestamp required')
    db=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)
    db.execute('BEGIN')
    try:
        strata=defaultdict(list);counts=Counter();available=0
        for source,fixtures,raw,available_by in db.execute('''
            SELECT e.source_id,e.fixtures,e.payload,a.available_by FROM evidence e
            JOIN availability a USING(source_id,decision_seq,horizon)
            WHERE a.available_by<=? ORDER BY e.source_id,e.decision_seq,e.horizon''',(asof,)):
            row=json.loads(raw);counts[row['status']]+=1;available+=1
            assert row['valuation_at']<=available_by<=asof
            if row['status']=='observed':strata[source].append(dict(row,fixtures=json.loads(fixtures)))
        groups=[dict(row,source_id=source) for source,rows in sorted(strata.items()) for row in grouped(rows)]
        return {'as_of':asof,'available_labels':available,'status_counts':dict(counts),
            'excluded_without_receipt':db.execute('''SELECT COUNT(*) FROM evidence e LEFT JOIN availability a
                USING(source_id,decision_seq,horizon) WHERE a.source_id IS NULL''').fetchone()[0],
            'source_strata':len(strata),'reviews':groups,'automatic_sanctions':0,
            'limitations':['Availability is conservatively confirmed after evidence commit; receipt gaps exclude records.',
                'Source strata are kept separate; no cross-model aggregation or automatic sanctions.',
                'Same-model markouts and connected fixture groups do not prove creator toxicity.']}
    finally:
        db.rollback();db.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db',type=Path,required=True);p.add_argument('--as-of',type=float,required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    result=review(a.db,a.as_of)
    with a.out.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='reviews'}))
