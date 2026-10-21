"""Durable research consumer; separate output DB, no quote transport."""
import hashlib,json,sqlite3,time,math
from .event_store import rfq_payload


def encoded(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)
def advance(chain,event):return hashlib.sha256((chain+event['digest']).encode()).hexdigest()


class ScenarioWorker:
    def __init__(self, source, output, consumer, identity, maximum_lag=2):
        if not math.isfinite(maximum_lag) or maximum_lag<=0:raise ValueError('invalid maximum lag')
        self.source=source;self.consumer=consumer;self.maximum_lag=maximum_lag;self.poisoned=False
        self.db=sqlite3.connect(output);self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('CREATE TABLE IF NOT EXISTS checkpoint(id INTEGER PRIMARY KEY CHECK(id=1),seq INTEGER,chain TEXT,identity TEXT); CREATE TABLE IF NOT EXISTS candidate_decisions(source_seq INTEGER PRIMARY KEY,rfq_id TEXT,result TEXT);')
        self.db.execute('CREATE TABLE IF NOT EXISTS commit_receipts(last_seq INTEGER PRIMARY KEY,first_seq INTEGER,commit_started_at REAL,commit_returned_at REAL)')
        identity=encoded({'inputs':identity,'maximum_lag':maximum_lag})
        row=self.db.execute('SELECT seq,chain,identity FROM checkpoint WHERE id=1').fetchone()
        if row and row[2]!=identity:raise ValueError('worker identity changed')
        if not row:
            self.db.execute('INSERT INTO checkpoint VALUES(1,0,?,?)',('',identity));self.db.commit();row=(0,'',identity)
        self.seq=0;self.chain=''
        while self.seq<row[0]:
            events=self.source.read(self.seq,min(1000,row[0]-self.seq))
            if not events:raise ValueError('source truncated before checkpoint')
            for event in events:
                if event['seq']>row[0]:raise ValueError('source checkpoint missing')
                self.consumer.consume(event,price_rfqs=False)
                if rfq_payload(event) is not None and hasattr(self.consumer,'restore_record'):
                    saved=self.db.execute('SELECT result FROM candidate_decisions WHERE source_seq=?',(event['seq'],)).fetchone()
                    if not saved:raise ValueError('checkpoint RFQ decision missing')
                    self.consumer.restore_record(event,json.loads(saved[0]))
                self.chain=advance(self.chain,event);self.seq=event['seq']
        if self.chain!=row[1]:raise ValueError('source prefix changed')

    def step(self, limit=250, clock=time.time):
        if self.poisoned:raise RuntimeError('failed worker must be reconstructed')
        events=self.source.read(self.seq,limit)
        if not events:return 0
        staged=[];chain=self.chain
        try:
            for event in events:
                msg=rfq_payload(event);began=clock();compute=time.perf_counter()
                if msg is not None and not 0<=began-event['received_at']<=self.maximum_lag:
                    self.consumer.consume(event,price_rfqs=False)
                    result={'source_seq':event['seq'],'rfq_id':msg.get('id'),'status':'excluded','reason':'processing_lag_or_future_receipt'}
                else:result=self.consumer.consume(event,evaluation_at=began if msg is not None else None)
                chain=advance(chain,event)
                if result is not None:
                    finished=clock();result={'pricing':result,'received_at':event['received_at'],'evaluation_at':began,'completed_at':finished,
                        'compute_seconds':time.perf_counter()-compute,'completion_lag_seconds':finished-event['received_at'],
                        'candidate_timely':0<=finished-event['received_at']<=self.maximum_lag,
                        'live_authorized':False,'quote_sizing_and_risk_applied':'research_policy' in result}
                    staged.append((event['seq'],msg.get('id'),encoded(result)))
            commit_started=time.time()
            with self.db:
                self.db.executemany('INSERT INTO candidate_decisions VALUES(?,?,?)',staged)
                self.db.execute('UPDATE checkpoint SET seq=?,chain=? WHERE id=1',(events[-1]['seq'],chain))
        except BaseException:
            self.poisoned=True;raise
        self.seq=events[-1]['seq'];self.chain=chain
        # Receipt records the already-durable decision/checkpoint commit. A crash
        # before this diagnostic write leaves valid decisions without a receipt.
        returned=time.time()
        try:
            with self.db:self.db.execute('INSERT INTO commit_receipts VALUES(?,?,?,?)',(self.seq,events[0]['seq'],commit_started,returned))
        except BaseException:
            self.poisoned=True;raise
        return len(events)

    def close(self):self.db.close()
