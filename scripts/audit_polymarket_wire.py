"""Independent Decimal replay of the wire records behind REST mismatches."""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from combos.event_store import EventStore


def run(capture,audit,out):
    targets={}
    for row in json.loads((audit/'rows.json').read_text()):
        targets.setdefault(row['rest_event_seq'],{})[row['token']]=row
    tokens={token for group in targets.values() for token in group}
    ladders={};origins={};findings=[];store=EventStore(capture/'events.sqlite');seq=0
    try:
        while True:
            events=store.read(seq,1000)
            if not events:break
            for e in events:
                seq=e['seq'];r=e['payload']
                if e['kind']=='venue_reset' and e['source']=='polymarket':ladders.clear();origins.clear()
                if e['kind']=='polymarket':
                    if r.get('event_type')=='book' and r['asset_id'] in tokens:
                        token=r['asset_id'];ladders[token]={'bid':{},'ask':{}};origins[token]={}
                        for side,field in (('bid','bids'),('ask','asks')):
                            for level in r[field]:
                                p,q=Decimal(level['price']),Decimal(level['size'])
                                if q:ladders[token][side][p]=q
                                origins[token][(side,p)]={'kind':'snapshot','seq':seq}
                    elif r.get('event_type')=='price_change':
                        for change in r['price_changes']:
                            token=change['asset_id']
                            if token not in tokens:continue
                            if token not in ladders:raise ValueError('wire delta precedes snapshot')
                            side={'BUY':'bid','SELL':'ask'}[change['side']]
                            p,q=Decimal(change['price']),Decimal(change['size'])
                            if q:ladders[token][side][p]=q
                            else:ladders[token][side].pop(p,None)
                            origins[token][(side,p)]={'kind':'delta','seq':seq}
                if seq in targets:
                    snapshots={s['asset_id']:s for s in r['payload']}
                    for token,prior in targets[seq].items():
                        snapshot=snapshots[token];differences=[]
                        for side,field in (('bid','bids'),('ask','asks')):
                            rest={Decimal(x['price']):Decimal(x['size']) for x in snapshot[field] if Decimal(x['size'])}
                            ws=ladders[token][side]
                            for price in sorted(set(rest)|set(ws)):
                                if rest.get(price,Decimal(0))!=ws.get(price,Decimal(0)):
                                    differences.append({'side':side,'price':str(price),'rest_size':str(rest.get(price,0)),
                                        'ws_size':str(ws.get(price,0)),'last_wire_origin':origins[token].get((side,price),{'kind':'absent_since_snapshot'})})
                        expected={(d['side'],Decimal(d['price']),Decimal(d['rest_size']),Decimal(d['ws_size'])) for d in prior['differing_levels']}
                        actual={(d['side'],Decimal(d['price']),Decimal(d['rest_size']),Decimal(d['ws_size'])) for d in differences}
                        if actual!=expected:raise ValueError('independent wire replay differs from production reconstruction')
                        findings.append({'token':token,'rest_event_seq':seq,'differences':differences})
    finally:store.close()
    if len(findings)!=sum(len(g) for g in targets.values()):raise ValueError('incomplete wire audit')
    counts=Counter(d['last_wire_origin']['kind'] for row in findings for d in row['differences'])
    summary={'checks':len(findings),'all_production_differences_reproduced':True,
        'differing_level_origins':dict(counts),'limits':'validates captured-wire reconstruction, not upstream completeness',
        'hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (audit/'rows.json',capture/'readiness.json',Path(__file__))}}
    out.mkdir(parents=True,exist_ok=False)
    (out/'summary.json').write_text(json.dumps(summary,indent=2));(out/'rows.json').write_text(json.dumps(findings,indent=2))
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('capture','audit','out'):p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args();print(json.dumps(run(a.capture,a.audit,a.out)))
