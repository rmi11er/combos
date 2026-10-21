"""Identify exact Pinnacle selector loss using only captured raw snapshots."""
import json,sqlite3,zlib,sys
from pathlib import Path
from copy import deepcopy
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from combos.pinnacle_matching import bind_selectors
from combos.pinnacle_feed import fixture_index
from combos.event_store import rfq_payload


def run(capture,scenarios,catalog,out):
    runtime=json.loads((capture/'runtime.json').read_text());definitions=json.loads(catalog.read_text());wanted={r['source_seq'] for r in json.loads(scenarios.read_text()) if r.get('reason')=='exact_pinnacle_selector_missing'}
    db=sqlite3.connect(str((capture/'events.sqlite').resolve()));snapshots=[];rows=[];current=None;maps={}
    for seq,kind,source,at,raw in db.execute("select seq,kind,source,received_at,payload from events where kind in ('external_raw','kalshi','rfq') order by seq"):
        if not (kind=='external_raw' and source=='pinnacle') and seq not in wanted:continue
        p=json.loads(zlib.decompress(raw))
        if kind=='external_raw':
            candidate=deepcopy(runtime['mappings']);result=bind_selectors(candidate,list(fixture_index(p['payload']).values()),definitions);maps={m['kalshi_ticker']:m for m in candidate};current=seq
            snapshots.append({'seq':seq,'at':at,'matched':result['candidate_mappings'],'rejected_native_reasons':dict(Counter(r['reason'] for r in result['rejected_native_markets']))})
        else:
            msg=rfq_payload({'kind':kind,'payload':p});missing=[maps[l['market_ticker']] for l in msg['mve_selected_legs'] if not maps[l['market_ticker']].get('pinnacle')]
            assert missing and current<seq
            rows.append({'rfq_seq':seq,'pinnacle_seq':current,'missing':[{'market_key':m['market_key'],'status':m['pinnacle_selector_status']} for m in missing]})
    db.close();assert len(rows)==len(wanted)
    summary={'rfqs':len(rows),'snapshots':snapshots,'missing_keys':dict(Counter(m['market_key'] for r in rows for m in r['missing'])),'missing_statuses':dict(Counter(m['status'] for r in rows for m in r['missing']))}
    out.mkdir(parents=True,exist_ok=False);(out/'summary.json').write_text(json.dumps(summary,indent=2));(out/'decisions.json').write_text(json.dumps(rows));print(json.dumps(summary,indent=2))

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('capture','scenarios','catalog','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.capture,a.scenarios,a.catalog,a.out)
