"""Audit durable markout census, source cutoffs, decision identity and timing."""
import argparse,hashlib,json,sqlite3,statistics
import bisect
from collections import Counter
from pathlib import Path


def open_closed(path):return sqlite3.connect(path.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)
def metrics(v):
    v=sorted(v)
    return {'count':len(v),'median_ms':statistics.median(v)*1000,'p99_ms':v[round((len(v)-1)*.99)]*1000,'max_ms':max(v)*1000} if v else None


def run(source,decisions,marks,out):
    src=open_closed(source);entries=open_closed(decisions);db=open_closed(marks)
    seq,chain,identity,watermark=db.execute('SELECT seq,chain,identity,watermark FROM checkpoint').fetchone()
    horizons=json.loads(identity)['horizons'];prefix={0:float('-inf')};computed_chain='';last=float('-inf')
    for s,at,digest in src.execute('SELECT seq,received_at,digest FROM events WHERE seq<=? ORDER BY seq',(seq,)):
        last=max(last,at);prefix[s]=last;computed_chain=hashlib.sha256((computed_chain+digest).encode()).hexdigest()
    assert computed_chain==chain and last==watermark
    source_events=list(src.execute('SELECT seq,kind,source,received_at FROM events WHERE seq<=? ORDER BY seq',(seq,)))
    source_watermarks=[prefix[event[0]] for event in source_events]
    stops=[event for event in source_events if event[1]=='capture_timing']
    first_stop=min((event[3] for event in stops),default=None)
    slow=[];before_stop=[];after_stop=[]
    expected={};observed_inputs={s:d for s,d in db.execute('SELECT source_seq,digest FROM input_decisions')};entry_count=0
    for s,raw in entries.execute('SELECT source_seq,result FROM candidate_decisions WHERE source_seq<=?',(seq,)):
        assert hashlib.sha256(raw.encode()).hexdigest()==observed_inputs.pop(s)
        p=json.loads(raw)['pricing']
        if p['status']=='scenario_priced':
            entry_count+=1
            for h in horizons:expected[(s,h)]=p
    assert not observed_inputs
    receipts=dict(db.execute('SELECT source_seq,commit_returned_at FROM commit_receipts'))
    keys=set();statuses=Counter();compute_delay=[];commit_delay=[];missing_receipts=0
    for s,h,batch_seq,at,raw in db.execute('SELECT decision_seq,horizon,source_seq,computed_at,value FROM labels'):
        key=(s,h);assert key in expected and key not in keys;keys.add(key)
        p=expected[key];label=json.loads(raw);statuses[label['status']]+=1
        assert label['rfq_id']==p['rfq_id'] and label['entry_at']==p['at']
        assert label['valuation_at']==p['at']+h
        assert s<=label['available_source_seq']<=batch_seq<=seq
        assert prefix[label['available_source_seq']]<=label['valuation_at']
        assert at>=label['valuation_at'];compute_delay.append(at-label['valuation_at'])
        delay=at-label['valuation_at']
        if first_stop is not None:
            (after_stop if label['valuation_at']>=first_stop else before_stop).append(delay)
        if delay>.5:
            trigger_index=bisect.bisect_right(source_watermarks,label['valuation_at'])
            trigger=source_events[trigger_index] if trigger_index<len(source_events) else None
            slow.append({'decision_seq':s,'horizon':h,'status':label['status'],
                'valuation_at':label['valuation_at'],'computed_at':at,'delay_seconds':delay,
                'after_first_reported_stop':None if first_stop is None else label['valuation_at']>=first_stop,
                'first_watermark_beyond_horizon':trigger})
        assert label['entry_scenario']==next(v for v in p['scenarios'] if v['assumed_usd_per_native_unit']==1)
        if batch_seq in receipts:
            assert receipts[batch_seq]>=at
            commit_delay.append(receipts[batch_seq]-label['valuation_at'])
        else:missing_receipts+=1
    pending=0
    for s,h,raw in db.execute('SELECT decision_seq,horizon,value FROM pending'):
        key=(s,h);assert key in expected and key not in keys;keys.add(key);pending+=1
        due,origin,horizon,msg,entry=json.loads(raw)
        assert origin==s and horizon==h and due==expected[key]['at']+h
        assert msg['id']==expected[key]['rfq_id'] and entry['at']==expected[key]['at']
        assert due>=watermark
    assert keys==set(expected)
    result={'priced_entries':entry_count,'labels':sum(statuses.values()),'pending':pending,
        'complete_entry_horizon_census':True,'source_cutoffs_verified':True,'statuses':dict(statuses),
        'missing_commit_receipts':missing_receipts,'horizon_to_computed':metrics(compute_delay),
        'horizon_to_commit_return':metrics(commit_delay),'checkpoint_seq':seq,
        'source_max_seq':src.execute('SELECT MAX(seq) FROM events').fetchone()[0],
        'timing_diagnosis':{'reported_stops':stops,'slow_over_500ms':slow,
            'before_first_reported_stop':metrics(before_stop),
            'after_first_reported_stop':metrics(after_stop),
            'interpretation':'Stop receipts can follow socket shutdown. Timing split is descriptive, not proof of active feed health or causal latency attribution.'},
        'limitations':['closed immutable databases required','fair arithmetic not independently rederived',
            'commit-return timestamps are diagnostics; publication follows committed-row visibility']}
    for connection in (src,entries,db):connection.close()
    out.mkdir(parents=True,exist_ok=False);(out/'verification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('source','decisions','marks','out'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();run(a.source,a.decisions,a.marks,a.out)
