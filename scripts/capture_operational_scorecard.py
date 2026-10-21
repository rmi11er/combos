"""Saved-capture operational scorecard; no inferred executions or feed guarantees."""
import argparse,json,sqlite3,zlib,statistics
from collections import Counter
from pathlib import Path


def quantiles(values):
    if not values:return None
    values=sorted(values)
    return {'median':statistics.median(values),**{k:values[round((len(values)-1)*p)] for k,p in [('p95',.95),('p99',.99),('max',1)]}}


def run(capture,out):
    db=sqlite3.connect(str((capture/'events.sqlite').resolve()));counts=Counter();states={};episodes=[];latency=[];lag=[];reasons=Counter();backlogs=[];first=None;last=None
    for seq,kind,source,at,raw in db.execute('SELECT seq,kind,source,received_at,payload FROM events ORDER BY seq'):
        counts[kind]+=1;first=at if first is None else min(first,at);last=at if last is None else max(last,at)
        if kind not in ('book_quarantine','book_rebuild','decision','venue_reset'):continue
        p=json.loads(zlib.decompress(raw))
        if kind=='book_quarantine':
            t=p['token']
            if p['status']=='quarantined':states.setdefault(t,{'token':t,'market_key':p['market_key'],'start':at,'source_seq':seq,'rebuilds':0})
            elif p['status']=='recovered':
                if t not in states:raise ValueError('recovery without quarantine')
                old=states.pop(t)
                episodes.append({**old,'end':at,'duration':at-old['start'],'status':'recovered'})
        elif kind=='book_rebuild':
            for t in p['tokens']:
                if t not in states:raise ValueError('rebuild without quarantine')
                states[t]['rebuilds']+=1
        elif kind=='decision':
            reasons[p.get('reason',p['status'])]+=1
            if p.get('decision_at') is not None and p.get('received_at') is not None:latency.append(p['decision_at']-p['received_at'])
            if p.get('processing_lag_seconds') is not None:lag.append(p['processing_lag_seconds'])
            if p.get('reason')=='processing_backlog':backlogs.append({'source_seq':p['source_seq'],'received_at':p['received_at'],'decision_at':p['decision_at']})
    for row in states.values():episodes.append({**row,'end':None,'duration':last-row['start'],'status':'unresolved_at_capture_end'})
    db.close()
    summary={'events':dict(counts),'first_event_at':first,'last_event_at':last,'event_span_seconds':last-first,
        'decision_reasons':dict(reasons),'local_receipt_to_decision_seconds':quantiles(latency),
        'processing_lag_seconds':quantiles(lag),'quarantine_episode_counts':dict(Counter(e['status'] for e in episodes)),
        'recovered_quarantine_seconds':quantiles([e['duration'] for e in episodes if e['status']=='recovered']),
        'unresolved_quarantine_seconds':quantiles([e['duration'] for e in episodes if e['status']!='recovered']),
        'caveats':['latency is local captured receipt to decision; blocked pricing does not measure complete quoting compute','quarantine durations use publication times; unresolved duration is right-censored','no acceptance or execution evidence']}
    if (capture/'readiness.json').exists():summary['processes']=json.loads((capture/'readiness.json').read_text())['processes']
    out.mkdir(parents=True,exist_ok=False);(out/'summary.json').write_text(json.dumps(summary,indent=2));(out/'quarantine_episodes.json').write_text(json.dumps(episodes,indent=2));(out/'backlogs.json').write_text(json.dumps(backlogs));print(json.dumps(summary,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.capture,a.out)
