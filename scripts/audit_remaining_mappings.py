"""Classify remaining mapping rejects without changing the trading universe."""
import json,sqlite3,zlib
from pathlib import Path
from collections import Counter,defaultdict
ROOT=Path(__file__).resolve().parents[1]
active=json.loads((ROOT/'config/runtime_nfl_authorized_shadow_20260910.json').read_text())['mappings']
mapped={m['kalshi_ticker'] for m in active}
catalog={m['kalshi_ticker']:m for m in json.loads((ROOT/'runs/morning_research_20260908/pinnacle_delivery_mapping_review/runtime_reviewed_candidates.json').read_text())['mappings']}
reviews={r['market_key']:r['review'] for r in json.loads((ROOT/'runs/nfl_all_payoff_enumeration_20260909/rows.json').read_text())}
fixtures={m['fixture_key'] for m in active}
eventkeys={t.rsplit('-',1)[0] for t in catalog}
classes=Counter();families=Counter();combinations=Counter();legcounts=Counter();examples=defaultdict(list);total=0
for run in ('shadow_20260909_161131','shadow_20260909_172437'):
    c=sqlite3.connect(f'file:{ROOT}/runs/{run}/events.sqlite?mode=ro',uri=True)
    query="SELECT e.payload FROM decisions d JOIN events e ON e.seq=d.source_seq WHERE json_extract(d.result,'$.reason')='reviewed_mapping_missing'"
    for raw, in c.execute(query):
        q=json.loads(zlib.decompress(raw))['msg']
        absent={l['market_ticker'] for l in q['mve_selected_legs'] if l['market_ticker'] not in mapped}
        if not absent:continue
        total+=1;causes=set()
        for ticker in absent:
            legcounts[ticker]+=1
            if ticker in catalog:
                m=catalog[ticker];r=reviews.get(m['market_key'],{})
                cause='catalog:'+r.get('status','unreviewed')
            elif ticker.rsplit('-',1)[0] in eventkeys:
                cause='strike_absent_from_candidate_catalog'
            else:cause='event_or_family_absent_from_candidate_catalog'
            causes.add(cause)
            if len(examples[cause])<8 and ticker not in examples[cause]:examples[cause].append(ticker)
        classes.update(causes)
        families.update({t.split('-')[0] for t in absent})
        combinations[' + '.join(sorted(causes))]+=1
    c.close()
out=dict(remaining_rfqs=total,rfqs_by_cause_overlapping=dict(classes),rfqs_by_missing_family_overlapping=dict(families),
    mutually_exclusive_cause_combinations=dict(combinations),examples=dict(examples),top_missing_legs=legcounts.most_common(25))
folder=ROOT/'runs/shadow_consensus_replay_20260909/results'
(folder/'remaining_mapping_rejects.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
