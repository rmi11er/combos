"""Separate, append-only creator behavior review; never applies sanctions."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3


DEFAULTS={'minimum_observed':20,'pickoff_horizon_seconds':30,
          'pickoff_adverse_cents':0.3,'pickoff_fraction':0.7,
          'spam_window_seconds':60,'spam_window_count':50,'wide_leg_count':5,
          'review_score':5}


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def _max_window(times, width):
    left=0;best=0
    for right,at in enumerate(times):
        while at-times[left]>width:left+=1
        best=max(best,right-left+1)
    return best


def extract(evidence_db, asof):
    db=sqlite3.connect(evidence_db.resolve().as_uri()+'?mode=ro',uri=True)
    try:
        db.execute('BEGIN')
        rows=[]
        for raw,available in db.execute('''SELECT e.payload,a.available_by FROM evidence e
            JOIN availability a USING(source_id,decision_seq,horizon)
            WHERE a.available_by<=? AND json_extract(e.payload,'$.status')='observed' ORDER BY e.source_id,e.decision_seq,e.horizon''',(asof,)):
            row=json.loads(raw);scenario=row.get('entry_scenario',{});legs=scenario.get('legs',[])
            rows.append({'creator_id':row.get('creator_id'),'rfq_id':row.get('rfq_id'),
                'entry_at':row.get('entry_at'),'horizon_seconds':row.get('horizon_seconds'),
                'adverse_move_cents':row.get('adverse_move_cents'),'nlegs':len(legs),
                'fixtures':row.get('fixtures',[]),'source_available_by':available})
        return rows
    finally:
        db.rollback();db.close()


def initialize(path):
    db=sqlite3.connect(path);db.execute('PRAGMA journal_mode=WAL');db.execute('PRAGMA synchronous=FULL')
    db.executescript('''CREATE TABLE IF NOT EXISTS runs(
      run_id TEXT PRIMARY KEY, started_at REAL NOT NULL, asof REAL NOT NULL,
      source_path TEXT NOT NULL, source_sha256 TEXT NOT NULL, parameters TEXT NOT NULL,
      recommendation_count INTEGER NOT NULL);
      CREATE TABLE IF NOT EXISTS creator_reviews(
      run_id TEXT NOT NULL, creator_id TEXT NOT NULL, observed_labels INTEGER NOT NULL,
      unique_rfqs INTEGER NOT NULL, max_legs INTEGER NOT NULL, max_rfqs_per_window INTEGER NOT NULL,
      pickoff_labels INTEGER NOT NULL, pickoff_fraction REAL NOT NULL, score INTEGER NOT NULL,
      recommendation TEXT NOT NULL, reasons TEXT NOT NULL, evidence_refs TEXT NOT NULL,
      PRIMARY KEY(run_id,creator_id));''')
    return db


def run(evidence_db, blacklist_db, asof, parameters=None):
    p={**DEFAULTS,**(parameters or {})};rows=extract(evidence_db,asof);by=defaultdict(list)
    for row in rows:
        if not row['creator_id']:continue
        by[row['creator_id']].append(row)
    reviews=[]
    for creator,values in sorted(by.items()):
        values.sort(key=lambda r:(r['entry_at'],r['rfq_id']))
        refs=sorted({r['rfq_id'] for r in values if r['rfq_id']})
        times=[r['entry_at'] for r in values if isinstance(r['entry_at'],(int,float))]
        pick=[r for r in values if r['horizon_seconds']==p['pickoff_horizon_seconds'] and r['adverse_move_cents']>=p['pickoff_adverse_cents']]
        fraction=len(pick)/len([r for r in values if r['horizon_seconds']==p['pickoff_horizon_seconds']]) if any(r['horizon_seconds']==p['pickoff_horizon_seconds'] for r in values) else 0
        maxlegs=max((r['nlegs'] for r in values),default=0);spam=_max_window(times,p['spam_window_seconds'])
        reasons=[];score=0
        if maxlegs>=p['wide_leg_count']:reasons.append('excessive_leg_count');score+=3
        if spam>=p['spam_window_count']:reasons.append('rfq_burst');score+=3
        if len(pick)>=p['minimum_observed'] and fraction>=p['pickoff_fraction']:
            reasons.append('repeated_short_horizon_adverse_move');score+=4
        recommendation='review' if score>=p['review_score'] else 'monitor'
        reviews.append({'creator_id':creator,'observed_labels':len(values),'unique_rfqs':len(refs),
            'max_legs':maxlegs,'max_rfqs_per_window':spam,'pickoff_labels':len(pick),
            'pickoff_fraction':fraction,'score':score,'recommendation':recommendation,
            'reasons':reasons,'evidence_refs':refs[:500]})
    run_id=hashlib.sha256(json.dumps({'asof':asof,'source':str(evidence_db.resolve()),'parameters':p},sort_keys=True).encode()).hexdigest()
    db=initialize(blacklist_db)
    try:
        with db:
            db.execute('INSERT OR IGNORE INTO runs VALUES(?,?,?,?,?,?,?)',(run_id,asof,asof,str(evidence_db.resolve()),digest(evidence_db),json.dumps(p,sort_keys=True),sum(r['recommendation']=='review' for r in reviews)))
            for r in reviews:db.execute('INSERT OR IGNORE INTO creator_reviews VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(run_id,r['creator_id'],r['observed_labels'],r['unique_rfqs'],r['max_legs'],r['max_rfqs_per_window'],r['pickoff_labels'],r['pickoff_fraction'],r['score'],r['recommendation'],json.dumps(r['reasons']),json.dumps(r['evidence_refs'])))
    finally:db.close()
    return {'run_id':run_id,'observed_labels':len(rows),'creators':len(reviews),'review_recommendations':sum(r['recommendation']=='review' for r in reviews),'automatic_sanctions':0,'source_sha256':digest(evidence_db),'parameters':p}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--evidence-db',type=Path,required=True);p.add_argument('--blacklist-db',type=Path,required=True);p.add_argument('--as-of',type=float,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();result=run(a.evidence_db,a.blacklist_db,a.as_of);a.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
