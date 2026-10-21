"""Reconcile a completed live candidate worker with its captured RFQ census."""
import argparse,hashlib,json,sqlite3,zlib,statistics,bisect
from pathlib import Path
from collections import Counter,defaultdict


def metrics(v):
    v=sorted(v)
    return {'count':len(v),'median_ms':statistics.median(v)*1000,'p99_ms':v[round((len(v)-1)*.99)]*1000,'max_ms':max(v)*1000} if v else None


def run(capture,worker,out):
    src=sqlite3.connect(str(capture/'events.sqlite'));db=sqlite3.connect(str(worker/'decisions.sqlite'));checkpoint=db.execute('select seq,chain from checkpoint where id=1').fetchone();expected={};chain='';max_seq=0
    for seq,kind,at,digest,raw in src.execute('select seq,kind,received_at,digest,payload from events order by seq'):
        max_seq=seq
        if seq>checkpoint[0]:continue
        chain=hashlib.sha256((chain+digest).encode()).hexdigest()
        if kind not in ('kalshi','rfq'):continue
        p=json.loads(zlib.decompress(raw));msg=p if kind=='rfq' else p.get('msg') if p.get('type')=='rfq_created' else None
        if msg is not None:expected[seq]=(msg['id'],at)
    if chain!=checkpoint[1]:raise ValueError('source prefix differs')
    observed=set();counts=Counter();timings=defaultdict(list);leg_counts=Counter();policy_counts=Counter();committed_late=0;missing_receipts=0
    receipts=[]
    if db.execute("SELECT 1 FROM sqlite_master WHERE name='commit_receipts'").fetchone():
        receipts=db.execute('SELECT first_seq,last_seq,commit_started_at,commit_returned_at FROM commit_receipts ORDER BY last_seq').fetchall()
    ends=[r[1] for r in receipts]
    for seq,rfq_id,raw in db.execute('select source_seq,rfq_id,result from candidate_decisions order by source_seq'):
        if seq not in expected or seq in observed:raise ValueError('unexpected/duplicate RFQ')
        observed.add(seq);r=json.loads(raw);p=r['pricing'];identity,at=expected[seq]
        if identity!=rfq_id or r['received_at']!=at or p['source_seq']!=seq:raise ValueError('RFQ identity mismatch')
        if r['live_authorized'] is not False:raise ValueError('unexpected execution authority')
        if r['quote_sizing_and_risk_applied']!=('research_policy' in p):raise ValueError('incorrect policy label')
        if 'research_policy' in p:policy_counts[p['research_policy'].get('reason',p['research_policy']['status'])]+=1
        i=bisect.bisect_left(ends,seq)
        if i<len(receipts) and receipts[i][0]<=seq<=receipts[i][1]:
            commit=receipts[i][3]
            if commit<r['completed_at']:raise ValueError('commit precedes computation')
            if p['status']=='scenario_priced':
                timings['priced_receipt_to_durable_commit'].append(commit-at)
                committed_late+=int(commit-at>2)
        else:missing_receipts+=1
        if r['candidate_timely']!=(0<=r['completion_lag_seconds']<=2):raise ValueError('timeliness label mismatch')
        if abs(r['completed_at']-at-r['completion_lag_seconds'])>1e-9:raise ValueError('latency arithmetic mismatch')
        counts[p.get('reason',p['status'])]+=1;timings['all_queue_and_compute'].append(r['completion_lag_seconds'])
        if p['status']=='scenario_priced':
            if p['at']!=r['evaluation_at'] or r['evaluation_at']<at:raise ValueError('wrong pricing evaluation clock')
            timings['priced_compute'].append(r['compute_seconds']);timings['priced_queue_and_compute'].append(r['completion_lag_seconds']);leg_counts[p['nlegs']]+=1
    if observed!=set(expected):raise ValueError('incomplete checkpoint RFQ census')
    result={'status':'passed','rfqs':len(observed),'checkpoint_seq':checkpoint[0],'input_max_seq':max_seq,'fully_caught_up':checkpoint[0]==max_seq,'counts':dict(counts),'priced_leg_counts':dict(leg_counts),'research_policy_counts':dict(policy_counts),'priced_committed_after_2s':committed_late,'decisions_without_commit_receipt':missing_receipts,'timing':{k:metrics(v) for k,v in timings.items()},'limitations':['compute latency excludes commit; receipt-to-durable-commit is separately reported when receipts exist','fair values and source payoffs not independently rederived','research reservations are scenarios, not live acceptance or fills']}
    out.mkdir(parents=True,exist_ok=False);(out/'verification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));src.close();db.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('capture','worker','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.capture,a.worker,a.out)
