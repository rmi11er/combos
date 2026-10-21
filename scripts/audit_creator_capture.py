"""Audit recorded creator burst evidence and publication-causal RFQ exposure."""
import argparse
from collections import Counter,defaultdict
import hashlib,json,sqlite3,zlib
from pathlib import Path


def run(capture,scenarios,out):
    priced={r['source_seq'] for r in json.loads(scenarios.read_text()) if r['status']=='scenario_priced'}
    path=(capture/'events.sqlite').resolve()
    db=sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1',uri=True)
    requests={};by_creator=defaultdict(list);states={};exposure=Counter();priced_exposure=Counter()
    transitions=[];observed_creators=set();leg_counts=Counter();first=None;last=None;burst_times=defaultdict(list)
    for seq,kind,at,blob in db.execute("SELECT seq,kind,received_at,payload FROM events WHERE kind IN ('kalshi','rfq','creator_policy') ORDER BY seq"):
        p=json.loads(zlib.decompress(blob))
        if kind=='creator_policy':
            creator=p['creator_id'];state=p['state'];source=state['evidence_source_seq']
            assert source<seq and source in requests
            msg,source_at=requests[source];assert msg['creator_id']==creator and source_at==at
            window=p['evidence'].get('window')
            if state['reason'] in ('duplicate_request_burst','repeated_duplicate_bursts'):
                assert window
                if burst_times[creator]:assert at-burst_times[creator][-1]>=60
                burst_times[creator].append(at)
                if state['reason']=='repeated_duplicate_bursts':
                    assert len(burst_times[creator])>=3 and state['status']=='cooldown'
                    assert state['expires_at']==at+3600
                    burst_times[creator]=[]
                else:assert state['status']=='watch'
                relevant=[r for r in by_creator[creator] if window['start_exclusive']<r[1]<=window['end_inclusive'] and r[0]<=source]
                assert len(relevant)==window['distinct_requests']
                repeated=sum(signature==p['evidence']['signature'] for _,_,signature in relevant)
                assert repeated==window['same_leg_set_requests']
                assert repeated/len(relevant)==window['duplicate_fraction']>=window['required_duplicate_fraction']
                assert len(relevant)>=window['minimum_requests']
            states[creator]={**state,'publication_seq':seq}
            transitions.append({'creator_hash':hashlib.sha256(creator.encode()).hexdigest()[:16],
                'source_seq':source,'publication_seq':seq,'sequence_delay':seq-source,'status':state['status'],
                'reason':state['reason'],'window_verified':bool(window)})
            continue
        msg=p if kind=='rfq' else p.get('msg') if p.get('type')=='rfq_created' else None
        if msg is None:continue
        first=at if first is None else first;last=at
        creator=msg.get('creator_id');observed_creators.add(creator)
        legs=msg.get('mve_selected_legs') or [];leg_counts[len(legs)]+=1
        valid=bool(legs) and all(l.get('market_ticker') and l.get('side') in ('yes','no') for l in legs)
        sig=hashlib.sha256(json.dumps(sorted((l['market_ticker'],l['side']) for l in legs),sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest() if valid else 'unusable'
        requests[seq]=(msg,at);by_creator[creator].append((seq,at,sig))
        state=states.get(creator,{'status':'clear'});status=state['status']
        if status=='cooldown' and at>=state['expires_at']:status='watch'
        exposure[status]+=1
        if seq in priced:priced_exposure[status]+=1
    count=db.execute('SELECT COUNT(*) FROM creator_requests').fetchone()[0]
    assert count==len(requests)
    assert sum(priced_exposure.values())==len(priced)
    result={'rfqs':len(requests),'creators':len(observed_creators),'duration_seconds':last-first,
        'transitions':len(transitions),'transition_creators':len({r['creator_hash'] for r in transitions}),
        'transition_status_counts':dict(Counter(r['status'] for r in transitions)),
        'publication_causal_rfq_states':dict(exposure),'publication_causal_priced_states':dict(priced_exposure),
        'markout_groups':db.execute('SELECT COUNT(*) FROM creator_markout_groups').fetchone()[0],
        'leg_counts':dict(leg_counts),'limitations':['request patterns do not prove economic toxicity',
            'fresh capture has no imported creator history','creator state applied only after publication sequence',
            'sequence delay is not wall-clock latency; publications reuse source receipt timestamps',
            'closed immutable SQLite input required']}
    db.close();out.mkdir(parents=True,exist_ok=False)
    (out/'summary.json').write_text(json.dumps(result,indent=2))
    (out/'transitions.json').write_text(json.dumps(transitions,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='leg_counts'},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('capture','scenarios','out'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();run(a.capture,a.scenarios,a.out)
