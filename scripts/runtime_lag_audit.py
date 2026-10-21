#!/usr/bin/env python3
"""Review receive-to-decision latency without dropping out-of-scope RFQs."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from combos.event_store import EventStore
from combos.rfq_scope import check_legs,check_mappings

def stats(values):
    a=np.array(values,dtype=float)
    if not len(a):return {'count':0}
    return {'count':len(a),'p50':float(np.quantile(a,.5)),'p95':float(np.quantile(a,.95)),
            'p99':float(np.quantile(a,.99)),'max':float(a.max()),'total':float(a.sum())}

def audit(path):
    config=json.loads((path/'runtime.json').read_text());maps={m['kalshi_ticker']:m for m in config['mappings']}
    store=EventStore(path/'events.sqlite');lag=[];complete=[];compute=[];scope=Counter();backlog_scope=Counter();backlog_maps=Counter();reasons=Counter();relevant_lag=[];cursor=0
    while rows:=store.read(cursor,500,payload_kinds={'decision'}):
        for event in rows:
            cursor=event['seq']
            if event['kind']!='decision':continue
            d=event['payload'];reason=d.get('reason',d['status']);reasons[reason]+=1
            lag.append(d['processing_lag_seconds']);complete.append(d['completed_processing_lag_seconds']);compute.append(d['decision_compute_seconds'])
            legs=d['request'].get('mve_selected_legs') or []
            try:check_legs(legs,config);classification='passes_basic_scope'
            except (ValueError,TypeError,KeyError) as exc:classification=str(exc)
            if classification=='passes_basic_scope':
                scope[reason]+=1;relevant_lag.append(d['processing_lag_seconds'])
            if reason=='processing_backlog':
                backlog_scope[classification]+=1
                if classification=='passes_basic_scope':
                    try:check_mappings(legs,[maps.get(l['market_ticker']) for l in legs],config);classification='passes_mapping_and_distinct_fixture'
                    except (ValueError,TypeError,KeyError) as exc:classification=str(exc)
                    backlog_maps[classification]+=1
    end=store.db.execute('SELECT MAX(seq) FROM events').fetchone()[0]
    cursors={r['name']:{'seq':r['seq'],'lag':end-r['seq']} for r in store.db.execute('SELECT name,seq FROM consumers')}
    store.close()
    return {'maximum_processing_lag_seconds':config['maximum_processing_lag_seconds'],'lag_seconds':stats(lag),
            'completed_lag_seconds':stats(complete),'basic_scope_lag_seconds':stats(relevant_lag),
            'decision_compute_seconds':stats(compute),'decision_reasons':dict(reasons),'all_basic_scope_decisions':dict(scope),
            'backlog_basic_scope_classification':dict(backlog_scope),'backlog_after_basic_scope_mapping_checks':dict(backlog_maps),
            'consumer_cursors':cursors,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'scope_of_compute_measurement':'Includes current observed paths only; excludes decision serialization/database commit, and blocked mappings do not benchmark healthy three-source pricing.'}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True);a=p.parse_args()
    r=audit(a.capture);(a.capture/'processing_lag_audit.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
if __name__=='__main__':main()
