"""Describe dynamic edge charges against observed short-horizon markouts."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import sqlite3
import statistics
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from combos.dynamic_edge import charge


def run(decisions, marks, out):
    d=sqlite3.connect(decisions.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)
    pricing={seq:json.loads(raw) for seq,raw in d.execute("SELECT source_seq,result FROM candidate_decisions WHERE json_extract(result,'$.pricing.status')='scenario_priced'")};d.close()
    m=sqlite3.connect(marks.resolve().as_uri()+'?mode=ro&immutable=1',uri=True);groups=defaultdict(list);total=0;observed=0
    for raw, in m.execute("SELECT value FROM labels WHERE json_extract(value,'$.status')='observed'"):
        row=json.loads(raw);total+=1;record=pricing.get(row['decision_seq'])
        if record is None:continue
        scenario=row['entry_scenario'];edge=charge(scenario);bucket='base' if edge['edge_per_combo']<=.003+1e-12 else 'widened'
        groups[(row['horizon_seconds'],bucket)].append(row['adverse_move_cents']);observed+=1
    m.close()
    report=[]
    for (horizon,bucket),values in sorted(groups.items()):
        report.append({'horizon_seconds':horizon,'bucket':bucket,'labels':len(values),
            'mean_adverse_move_cents':statistics.mean(values),'median_adverse_move_cents':statistics.median(values),
            'positive_adverse_fraction':sum(v>0 for v in values)/len(values),
            'max_adverse_move_cents':max(values)})
    result={'decision_count':len(pricing),'observed_label_count':observed,'total_labels':total,
        'groups':report,'hypothetical_quote_or_fill_count':0,
        'limitations':['Descriptive same-window markouts, not an out-of-sample test.',
            'Observed RFQs overlap fixtures and fair changes are mostly weight-driven.',
            'A charge cannot be judged by markout alone; acceptance and fill selection are absent.']}
    out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--decisions',type=Path,required=True);p.add_argument('--marks',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.decisions,a.marks,a.out)
