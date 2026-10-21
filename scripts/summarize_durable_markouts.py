"""Describe a completed markout capture without treating RFQs as independent fills."""
import argparse
import collections
import json
import sqlite3
import statistics
from pathlib import Path


def summarize(path):
    db = sqlite3.connect(path.resolve().as_uri() + '?mode=ro&immutable=1', uri=True)
    try:
        groups = collections.defaultdict(list)
        for raw, in db.execute('SELECT value FROM labels'):
            row = json.loads(raw)
            groups[row['horizon_seconds']].append(row)
        pending = dict(db.execute('SELECT horizon,COUNT(*) FROM pending GROUP BY horizon'))
        out = {}
        for horizon in sorted(set(groups) | set(pending)):
            rows = groups[horizon]
            observed = [r for r in rows if r['status'] == 'observed']
            moves = [r['adverse_move_cents'] for r in observed]
            leg_sets = {
                tuple(sorted((leg['market_key'], leg['side']) for leg in r['entry_scenario']['legs']))
                for r in observed
            }
            out[horizon] = {
                'observed': len(observed),
                'unavailable_reasons': dict(collections.Counter(
                    r.get('reason', r['status']) for r in rows if r['status'] != 'observed')),
                'pending': pending.get(horizon, 0),
                'mean_adverse_cents_unweighted': statistics.mean(moves) if moves else None,
                'median_adverse_cents_unweighted': statistics.median(moves) if moves else None,
                'unique_creators_observed': len({r['creator_id'] for r in observed}),
                'unique_leg_sets_observed': len(leg_sets),
            }
        return {'horizons': out, 'limitations': [
            'Use only closed databases; immutable reads do not observe an active WAL.',
            'Overlapping RFQs and shared fixtures are dependent observations.',
            'Same-model marks include freshness-driven weight changes, not independent forecast validation.',
            'Pending horizons remain unresolved when source collection ends before valuation.',
            'No acceptance, fills, realized profit or automatic creator sanction is inferred.',
        ]}
    finally:
        db.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--marks', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = summarize(args.marks)
    with args.out.open('x') as handle:
        json.dump(result, handle, indent=2)
    print(json.dumps(result, indent=2))
