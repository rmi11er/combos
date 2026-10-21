"""Group durable same-model markouts for review; never publish sanctions."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sqlite3
import statistics


def components(groups):
    parents={}
    def root(x):
        parents.setdefault(x,x)
        while parents[x]!=x:
            parents[x]=parents[parents[x]];x=parents[x]
        return x
    for fixtures in groups:
        for fixture in fixtures:
            parents[root(fixture)]=root(fixtures[0])
    return len({root(x) for x in parents})


def grouped(rows):
    by=defaultdict(list)
    for row in rows:
        by[(row['creator_id'],row['horizon_seconds'])].append(row)
    result=[]
    for (creator,horizon),values in sorted(by.items()):
        fixture_groups=defaultdict(list)
        for row in values:
            fixture_groups[tuple(row['fixtures'])].append(row)
        first=[min(v,key=lambda r:(r['entry_at'],r['rfq_id'])) for v in fixture_groups.values()]
        result.append({'creator_id':creator,'horizon_seconds':horizon,'raw_observed_labels':len(values),
            'fixture_sets':len(first),'overlapping_fixture_components':components(fixture_groups),
            'raw_mean_adverse_cents':statistics.mean(r['adverse_move_cents'] for r in values),
            'first_per_fixture_set_mean_adverse_cents':statistics.mean(r['adverse_move_cents'] for r in first),
            'first_per_fixture_set_positive_fraction':sum(r['adverse_move_cents']>0 for r in first)/len(first),
            'representatives':[{'rfq_id':r['rfq_id'],'fixtures':r['fixtures'],'entry_at':r['entry_at'],
                'adverse_move_cents':r['adverse_move_cents']} for r in first],
            'action':'review_only'})
    return result


def run(plan,out):
    spec=json.loads(plan.read_text());seen={};rows=[];statuses=Counter();sources=[];pending=0;source_hashes=set()
    for item in spec['captures']:
        marks=Path(item['marks']).resolve();runtime=Path(item['runtime']).resolve()
        mappings={m['market_key']:m['fixture_key'] for m in json.loads(runtime.read_text())['mappings']}
        db=sqlite3.connect(marks.as_uri()+'?mode=ro&immutable=1',uri=True)
        identity=json.loads(db.execute('SELECT identity FROM checkpoint').fetchone()[0])
        assert identity['identity']['hashes'][str(runtime)]==hashlib.sha256(runtime.read_bytes()).hexdigest()
        source_hash=hashlib.sha256(marks.read_bytes()).hexdigest()
        if source_hash in source_hashes:raise ValueError('duplicate capture database')
        source_hashes.add(source_hash)
        sources.append({'marks':str(marks),'sha256':source_hash,'runtime':str(runtime)})
        pending+=db.execute('SELECT COUNT(*) FROM pending').fetchone()[0]
        for raw, in db.execute('SELECT value FROM labels'):
            row=json.loads(raw);key=(row['rfq_id'],row['horizon_seconds'])
            digest=hashlib.sha256(raw.encode()).hexdigest()
            if key in seen:
                if seen[key]!=digest:raise ValueError('conflicting overlapping RFQ/horizon labels')
                continue
            seen[key]=digest;statuses[row['status']]+=1
            if row['status']!='observed':continue
            if not row.get('creator_id'):raise ValueError('observed label lacks creator')
            fixtures=sorted({mappings[leg['market_key']] for leg in row['entry_scenario']['legs']})
            if not fixtures:raise ValueError('fixture group missing')
            rows.append(dict(row,fixtures=fixtures))
        db.close()
    review=grouped(rows)
    summary={'label_statuses':dict(statuses),'pending_horizons':pending,'creators_with_observed_marks':len({r['creator_id'] for r in rows}),
        'creator_horizon_groups':len(review),'fixture_sets_total':sum(r['fixture_sets'] for r in review),
        'maximum_components_per_creator_horizon':max((r['overlapping_fixture_components'] for r in review),default=0),
        'automatic_sanctions':0,'sources':sources,
        'limitations':['Same-model marks include freshness-weight changes; not independent fair validation.',
            'First entry per creator/fixture-set/horizon limits repeated-RFQ influence but is not a causal toxicity estimate.',
            'Connected fixture components are dependence diagnostics, not independent sample-size estimates.',
            'Missing marks can select the observed sample; pending source horizons are not treated as zero.',
            'No fill weighting, realized PnL or blacklist profitability claim.']}
    out.mkdir(parents=True,exist_ok=False);(out/'summary.json').write_text(json.dumps(summary,indent=2));(out/'creators.json').write_text(json.dumps(review,indent=2));print(json.dumps(summary,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();run(a.plan,a.out)
