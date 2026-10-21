"""Reusable causal marginal-uncertainty features for a certified development index."""
import argparse
import gzip
import json
import math
from pathlib import Path
import sqlite3
from mlb_disk_index import file_digest

MODELS = ('kalshi', 'polymarket', 'exchange_blend_equal', 'exchange_blend_pm75')


def features(row):
    legs, contexts = row['legs'], row['context']
    if len(legs) != len(contexts) or not 2 <= len(legs) <= 4:
        raise ValueError('leg_context_shape')
    for c in contexts:
        for venue in ('kalshi', 'polymarket'):
            at = c[venue]['available_at']
            if not math.isfinite(at) or at > row['at']:
                raise ValueError('future_source_availability')
    result = {}
    for model in MODELS:
        points, upper, widths = [], [], []
        for leg, c in zip(legs, contexts):
            interval = c[model]['interval']
            lo, point, hi = (interval[k] for k in ('lower', 'point', 'upper'))
            if not all(math.isfinite(x) for x in (lo, point, hi)) or not 0 <= lo <= point <= hi <= 1:
                raise ValueError('invalid_interval')
            if leg['side'] == 'yes':
                points.append(point); upper.append(hi)
            elif leg['side'] == 'no':
                points.append(1-point); upper.append(1-lo)
            else:
                raise ValueError('invalid_leg_side')
            widths.append(100*(hi-lo))
        result[model] = {'point': math.prod(points), 'independent_upper': math.prod(upper),
                         'summed_marginal_interval_cents': sum(widths), 'nlegs': len(legs)}
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--index', type=Path, required=True)
    p.add_argument('--batch-root', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    index = sqlite3.connect(a.index.resolve().as_uri()+'?mode=ro', uri=True)
    meta = {k: json.loads(v) for k, v in index.execute('SELECT key,value FROM metadata')}
    assert set(meta['plan']['dates'].values()) == {'development'}
    a.out.mkdir(parents=True, exist_ok=False)
    index_hash = file_digest(a.index)
    db = sqlite3.connect(a.out/'features.sqlite')
    db.execute('CREATE TABLE features(evaluation_id TEXT, model TEXT, point REAL, independent_upper REAL, summed_marginal_interval_cents REAL, nlegs INTEGER, PRIMARY KEY(evaluation_id,model))')
    sources, dates = {}, {}
    for date in sorted(meta['coverage']['observed_dates']):
        expected = {(eid, model): (at, json.loads(payload)) for eid, at, model, payload in index.execute(
            'SELECT p.evaluation_id,p.at,m.model,m.payload FROM prints p JOIN models m ON m.print_id=p.id WHERE p.date=?', (date,))}
        eligible = {eid for eid, _ in expected}
        path = a.batch_root/date/'replay/pricing_context.jsonl.gz'
        before = file_digest(path)
        seen = set()
        with gzip.open(path, 'rt') as handle:
            for line in handle:
                row = json.loads(line)
                eid = row['evaluation_id']
                if eid not in eligible:
                    continue
                assert eid not in seen, ('duplicate_context', eid)
                seen.add(eid)
                for model, value in features(row).items():
                    at, original = expected[eid, model]
                    assert row['at'] == at, ('decision_time_mismatch', eid)
                    assert abs(value['point']-original['fair_point']) < 1e-9, ('point_mismatch', eid, model)
                    assert value['independent_upper'] <= original['stressed_upper']+1e-9, ('joint_bound_mismatch', eid, model)
                    db.execute('INSERT INTO features VALUES(?,?,?,?,?,?)', (eid, model, value['point'], value['independent_upper'], value['summed_marginal_interval_cents'], value['nlegs']))
        assert seen == eligible, ('missing_contexts', date, len(eligible-seen))
        assert file_digest(path) == before
        sources[str(path)] = before
        dates[date] = len(seen)
        db.commit()
        print('indexed', date, len(seen), flush=True)
    count = db.execute('SELECT COUNT(*) FROM features').fetchone()[0]
    assert count == index.execute('SELECT COUNT(*) FROM models').fetchone()[0]
    assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    db.close(); index.close()
    assert index_hash == file_digest(a.index)
    (a.out/'complete.json').write_text(json.dumps({'complete': True, 'rows': count, 'prints_by_date': dates,
        'index_sha256': index_hash, 'database_sha256': file_digest(a.out/'features.sqlite'), 'sources': sources,
        'script_sha256': file_digest(Path(__file__)),
        'semantics': 'No outcomes stored. Marginal intervals are historical scenario inputs, not measured live spreads/depth. Independent upper assumes independent leg payoffs; it is not a dependence-robust bound.'}, indent=2)+'\n')


if __name__ == '__main__':
    main()
