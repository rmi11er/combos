#!/usr/bin/env python3
"""Produce a compact, repeatable report for an NFL shadow event database.

This is deliberately read-only.  It separates scope coverage and feed
freshness rejections from pricing outcomes so a short session cannot be
mistaken for a profitability result.
"""
from collections import Counter, defaultdict
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sqlite3
import time
import zlib


def _decode(payload):
    return json.loads(zlib.decompress(payload))


def summarize(decisions, observations, mappings, event_count=None):
    mapping_by_ticker = {m.get('kalshi_ticker'): m for m in mappings}
    reasons = Counter()
    statuses = Counter()
    legs = Counter()
    scope = Counter()
    minutes = defaultdict(Counter)
    quotes = []
    for p in decisions:
        status = p.get('status', 'unknown')
        reason = p.get('reason') or status
        statuses[status] += 1
        reasons[reason] += 1
        n = int(p.get('leg_count') or len(p.get('request', {}).get('mve_selected_legs') or []))
        legs[str(n)] += 1
        at = float(p.get('received_at') or p.get('decision_at') or 0)
        bucket = str(int(at // 60) * 60)
        minutes[bucket]['rfqs'] += 1
        request_legs = p.get('request', {}).get('mve_selected_legs') or []
        found = [mapping_by_ticker.get(leg.get('market_ticker')) for leg in request_legs]
        nonplayer_nfl = (2 <= n <= 4 and len(found) == n and all(found)
                         and all(m.get('sport') == 'NFL' and not m.get('player_prop', False) for m in found))
        if nonplayer_nfl:
            scope['two_to_four_nonplayer_nfl'] += 1
            if len({m.get('fixture_key') for m in found}) == n:
                scope['mapped_cross_fixture'] += 1
        if status == 'shadow_quote':
            economics = p.get('economics') or {}
            quote = {'rfq_id': p.get('rfq_id'), 'at': at, 'leg_count': n,
                     'quantity': p.get('quantity'),
                     'customer_premium': economics.get('customer_premium'),
                     'expected_edge': economics.get('expected_edge'),
                     'maximum_loss': economics.get('maximum_loss'),
                     'yes_ask': p.get('yes_ask')}
            quotes.append(quote)
            minutes[bucket]['quotes'] += 1
            for key in ('customer_premium', 'expected_edge', 'maximum_loss'):
                if isinstance(quote[key], (int, float)):
                    minutes[bucket][key] += quote[key]
    obs = Counter()
    for p in observations:
        venue = p.get('venue', 'unknown')
        obs[venue + (':active' if p.get('active') else ':inactive')] += 1
    freshness = {k: v for k, v in reasons.items() if any(x in k for x in ('stale', 'future', 'observation_missing'))}
    return {
        'schema_version': 1,
        'generated_at': time.time(),
        'event_count': event_count,
        'decisions': len(decisions),
        'decision_statuses': dict(statuses),
        'decision_reasons': dict(reasons),
        'leg_counts': dict(legs),
        'scope': dict(scope),
        'freshness_rejections': freshness,
        'observations': dict(obs),
        'quotes': quotes,
        'quote_count': len(quotes),
        'minutes': [{'minute_epoch': int(k), **dict(v)} for k, v in sorted(minutes.items(), key=lambda x: int(x[0]))],
        'interpretation': 'Quote and edge totals are hypothetical shadow outputs; no fill or realized P&L inference is made.',
        'input_mapping_sha256': hashlib.sha256(json.dumps(mappings, sort_keys=True).encode()).hexdigest(),
    }


def report(db_path, mapping_path, out):
    mappings = json.loads(Path(mapping_path).read_text())['mappings']
    db = sqlite3.connect('file:' + str(Path(db_path).resolve()) + '?mode=ro', uri=True)
    decisions, observations = [], []
    for kind, payload in db.execute("SELECT kind,payload FROM events WHERE kind IN ('decision','observation') ORDER BY seq"):
        (decisions if kind == 'decision' else observations).append(_decode(payload))
    event_count = db.execute('SELECT COUNT(*) FROM events').fetchone()[0]
    db.close()
    result = summarize(decisions, observations, mappings, event_count)
    out = Path(out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + '\n')
    minute_path = out.with_name(out.stem + '_minutes.csv')
    fields = sorted({key for row in result['minutes'] for key in row}) if result['minutes'] else ['minute_epoch']
    with minute_path.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(result['minutes'])
    print(json.dumps({k: result[k] for k in ('event_count', 'decisions', 'scope', 'freshness_rejections', 'quote_count', 'observations')}, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--mapping-config', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    report(args.db, args.mapping_config, args.out)
