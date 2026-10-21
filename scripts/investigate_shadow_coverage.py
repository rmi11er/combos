"""Read-only retained-RFQ coverage audit."""
import json,sqlite3,zlib
from collections import Counter,defaultdict
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'runs/shadow_consensus_replay_20260909/results'
tz=ZoneInfo('America/Chicago')
result={}; reasons=Counter(); missing=Counter(); missing_series=Counter(); tickers=set(); ids=set(); sessions=[]
for run in ('shadow_20260909_161131','shadow_20260909_172437'):
    c=sqlite3.connect(f'file:{ROOT}/runs/{run}/events.sqlite?mode=ro',uri=True)
    manifest=json.loads(c.execute("SELECT value FROM state WHERE owner='runtime' AND key='manifest'").fetchone()[0])
    mapped={m['kalshi_ticker'] for m in manifest['config']['mappings']}
    events={t.rsplit('-',1)[0] for t in mapped}
    lo=c.execute('SELECT received_at FROM events ORDER BY seq LIMIT 1').fetchone()[0]
    hi=c.execute('SELECT received_at FROM events ORDER BY seq DESC LIMIT 1').fetchone()[0]
    local=Counter();localtickers=set();missingclasses=Counter()
    for raw,payload in c.execute('SELECT d.result,e.payload FROM decisions d JOIN events e ON e.seq=d.source_seq ORDER BY d.source_seq'):
        d=json.loads(raw);reason=d.get('reason') or d['status'];local[reason]+=1
        source=json.loads(zlib.decompress(payload));q=source.get('msg',source)
        ticker=q.get('market_ticker');rid=q.get('id')
        if ticker:tickers.add(ticker);localtickers.add(ticker)
        if rid:ids.add(rid)
        if reason=='reviewed_mapping_missing':
            absent=[l['market_ticker'] for l in q.get('mve_selected_legs',[]) if l['market_ticker'] not in mapped]
            for t in absent:missing[t]+=1;missing_series[t.split('-')[0]]+=1
            missingclasses['contains_unmapped_event_or_family' if any(t.rsplit('-',1)[0] not in events for t in absent) else 'only_missing_strikes_in_mapped_events']+=1
    reasons.update(local)
    sessions.append(dict(run=run,start=datetime.fromtimestamp(lo,tz).isoformat(),end=datetime.fromtimestamp(hi,tz).isoformat(),
        decisions=dict(local),distinct_rfq_tickers=len(localtickers),mappings=len(mapped),missing_classes=dict(missingclasses)))
    c.close();print(run,dict(local),flush=True)
qs=[json.loads(l) for l in (ROOT/'runs/shadow_review_20260909_1920/quotes.jsonl').read_text().splitlines()]
lifetimes=[q['valid_until']-q['decision_completed_at'] for q in qs]
result=dict(sessions=sessions,decision_counts=dict(reasons),total_decisions=sum(reasons.values()),
    distinct_retained_rfq_ids=len(ids),distinct_retained_rfq_tickers=len(tickers),quoted_tickers=len({q['market_ticker'] for q in qs}),
    missing_leg_series_counts=dict(missing_series),top_missing_legs=missing.most_common(20),
    quote_lifetime_seconds=dict(minimum=min(lifetimes),mean=sum(lifetimes)/len(lifetimes),maximum=max(lifetimes)))
(out/'coverage_audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
