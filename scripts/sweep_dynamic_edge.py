"""Offline dynamic-edge sensitivity over immutable shadow pricing decisions."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3
import statistics
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from combos.dynamic_edge import charge


def run(decisions, out):
    db=sqlite3.connect(decisions.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)
    rows=[]
    for seq,raw in db.execute("SELECT source_seq,result FROM candidate_decisions WHERE json_extract(result,'$.pricing.status')='scenario_priced'"):
        record=json.loads(raw);scenario=next((s for s in record['pricing']['scenarios'] if s['assumed_usd_per_native_unit']==1),None)
        if scenario is None:continue
        rows.append((seq,scenario))
    db.close()
    policies=[]
    for cap in (0.003,0.005,0.01):
        policies.append({'name':f'cap_{cap:g}','base_edge_per_combo':.003,'maximum_edge_per_combo':cap})
    reports=[]
    for policy in policies:
        values=[];components=Counter();increases=[]
        for seq,scenario in rows:
            result=charge(scenario,{k:v for k,v in policy.items() if k!='name'});values.append(result['edge_per_combo'])
            for key in ('disagreement_component','thin_depth_component','stale_padding_component'):
                if result[key]>0:components[key]+=1
            if result['edge_per_combo']>.003:increases.append({'source_seq':seq,**result})
        reports.append({'policy':policy,'priced_records':len(values),
            'mean_edge':statistics.mean(values) if values else None,
            'median_edge':statistics.median(values) if values else None,
            'p95_edge':sorted(values)[int(.95*(len(values)-1))] if values else None,
            'maximum_edge':max(values,default=None),'records_above_base':len(increases),
            'component_record_counts':dict(components),
            'hypothetical_quote_or_fill_count':0})
    result={'decisions_source':str(decisions.resolve()),'policies':reports,
        'limitations':['Immutable observed pricing decisions only; no acceptance, fill or PnL simulation.',
            'This evaluates edge hurdles, not whether additional charge would be competitive.',
            'Parameters remain unfit shadow hypotheses.']}
    out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--decisions',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.decisions,a.out)
