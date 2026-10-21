"""Durable follower of source events and committed research pricing decisions."""
import hashlib
import heapq
import json
import sqlite3
import time

from .event_store import rfq_payload
from .research_markout import ResearchMarkouts
from .scenario_worker import encoded, advance


class MarkoutWorker:
    def __init__(self, source, decisions, output, pricing, identity, horizons=(10,30,60)):
        self.source=source;self.decisions=decisions;self.pricing=pricing;self.poisoned=False
        self.scheduler=ResearchMarkouts(pricing,horizons)
        self.db=sqlite3.connect(output)
        self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS checkpoint(id INTEGER PRIMARY KEY CHECK(id=1),seq INTEGER,chain TEXT,identity TEXT,watermark REAL);
            CREATE TABLE IF NOT EXISTS input_decisions(source_seq INTEGER PRIMARY KEY,digest TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS pending(decision_seq INTEGER,horizon REAL,value TEXT NOT NULL,PRIMARY KEY(decision_seq,horizon));
            CREATE TABLE IF NOT EXISTS labels(decision_seq INTEGER,horizon REAL,source_seq INTEGER,computed_at REAL,value TEXT NOT NULL,PRIMARY KEY(decision_seq,horizon));
            CREATE TABLE IF NOT EXISTS commit_receipts(source_seq INTEGER PRIMARY KEY,commit_returned_at REAL);
        ''')
        frozen=encoded({'identity':identity,'horizons':list(horizons)})
        row=self.db.execute('SELECT seq,chain,identity,watermark FROM checkpoint WHERE id=1').fetchone()
        if row and row[2]!=frozen:raise ValueError('markout worker identity changed')
        if row is None:
            self.db.execute('INSERT INTO checkpoint VALUES(1,0,?,?,NULL)',('',frozen));self.db.commit();row=(0,'',frozen,None)
        self.seq=0;self.chain='';self.watermark=float('-inf') if row[3] is None else row[3]
        while self.seq<row[0]:
            events=self.source.read(self.seq,min(1000,row[0]-self.seq))
            if not events:raise ValueError('source truncated before markout checkpoint')
            for event in events:
                if event['seq']>row[0]:raise ValueError('missing markout checkpoint event')
                if rfq_payload(event) is not None:
                    raw=self.decision(event)
                    old=self.db.execute('SELECT digest FROM input_decisions WHERE source_seq=?',(event['seq'],)).fetchone()
                    if raw is None or old is None or old[0]!=self.digest(raw):raise ValueError('committed decision evidence changed')
                pricing.consume(event,price_rfqs=False)
                self.chain=advance(self.chain,event);self.seq=event['seq']
        if self.chain!=row[1]:raise ValueError('markout source prefix changed')
        self.scheduler.pending=[tuple(json.loads(r[0])) for r in self.db.execute('SELECT value FROM pending')]
        heapq.heapify(self.scheduler.pending)
        self.scheduler.seen={r[1] for r in self.scheduler.pending}

    @staticmethod
    def digest(raw):return hashlib.sha256(raw.encode()).hexdigest()

    def decision(self,event):
        row=self.decisions.execute('SELECT rfq_id,result FROM candidate_decisions WHERE source_seq=?',(event['seq'],)).fetchone()
        if row is None:return None
        msg=rfq_payload(event);p=json.loads(row[1])['pricing']
        if row[0]!=msg['id'] or p['rfq_id']!=msg['id'] or p['source_seq']!=event['seq']:
            raise ValueError('markout decision identity mismatch')
        return row[1]

    def step(self,limit=250,clock=time.time):
        if self.poisoned:raise RuntimeError('failed markout worker must be reconstructed')
        staged=[];new_pending=[];decision_hashes=[];processed=0;seq=self.seq;chain=self.chain;watermark=self.watermark
        try:
            for event in self.source.read(self.seq,limit):
                msg=rfq_payload(event);raw=self.decision(event) if msg is not None else None
                # Hold this event until the pricing worker's transaction is visible.
                if msg is not None and raw is None:break
                watermark=max(watermark,event['received_at'])
                staged.extend(self.scheduler.advance(watermark,seq))
                self.pricing.consume(event,price_rfqs=False)
                seq=event['seq'];chain=advance(chain,event);processed+=1
                if raw is not None:
                    decision_hashes.append((seq,self.digest(raw)));record=json.loads(raw);p=record['pricing']
                    if p['status']=='scenario_priced':
                        scenario=next(s for s in p['scenarios'] if s['assumed_usd_per_native_unit']==1)
                        entry={'source_seq':seq,'rfq_id':msg['id'],'at':p['at'],'nlegs':p['nlegs'],
                            'scenario':scenario,'research_policy':p.get('research_policy',{})}
                        self.scheduler.schedule(msg,entry)
                        new_pending.extend((seq,h,encoded((entry['at']+h,seq,h,msg,entry))) for h in self.scheduler.horizons)
            if not processed:return 0
            with self.db:
                self.db.executemany('INSERT INTO input_decisions VALUES(?,?)',decision_hashes)
                self.db.executemany('INSERT INTO pending VALUES(?,?,?)',new_pending)
                for label in staged:
                    self.db.execute('INSERT INTO labels VALUES(?,?,?,?,?)',(label['decision_seq'],label['horizon_seconds'],seq,clock(),encoded(label)))
                    self.db.execute('DELETE FROM pending WHERE decision_seq=? AND horizon=?',(label['decision_seq'],label['horizon_seconds']))
                self.db.execute('UPDATE checkpoint SET seq=?,chain=?,watermark=? WHERE id=1',(seq,chain,watermark))
            self.seq=seq;self.chain=chain;self.watermark=watermark
            # Diagnostic commit-return time; computed_at is not publication time.
            with self.db:self.db.execute('INSERT INTO commit_receipts VALUES(?,?)',(seq,clock()))
        except BaseException:
            self.poisoned=True;raise
        return processed

    def close(self):self.db.close()
