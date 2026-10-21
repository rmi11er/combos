#!/usr/bin/env python3
"""Audit exact Pinnacle selector coverage for a candidate runtime's raw snapshots."""
import argparse
import copy
import gzip
import json
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from combos.pinnacle_matching import bind_selectors
from combos.pinnacle_feed import fixture_index


def audit(runtime_path, catalog_path, raw_dir):
    runtime = json.loads(Path(runtime_path).read_text())
    catalog = json.loads(Path(catalog_path).read_text())
    rows = []
    for path in sorted(Path(raw_dir).glob('**/*.json.gz')):
        envelope = json.loads(gzip.open(path, 'rt').read())
        payload = envelope.get('payload')
        candidates = payload if isinstance(payload, list) else [payload]
        if not any(isinstance(row, dict) and 'fixtureId' in row for row in candidates):
            continue
        fixtures = fixture_index(payload)
        mappings = copy.deepcopy(runtime['mappings'])
        result = bind_selectors(mappings, list(fixtures.values()), catalog)
        missing = [m['market_key'] for m in mappings if m.get('pinnacle_selector_status') != 'exact_candidate']
        rows.append({'file': str(path), 'fixtures': len(fixtures),
                     'matched': result['candidate_mappings'],
                     'unmatched': result['unmatched_mappings'],
                     'missing_market_keys': missing,
                     'rejected_native_reasons': dict(Counter(r['reason'] for r in result['rejected_native_markets']))})
    return {'runtime': str(runtime_path), 'snapshots': rows,
            'minimum_matched': min((r['matched'] for r in rows), default=0),
            'all_snapshots_exact': bool(rows) and all(r['unmatched'] == 0 for r in rows),
            'interpretation': 'Selector coverage only; no payoff, limit-unit or exception approval.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--catalog', type=Path, required=True)
    parser.add_argument('--raw-dir', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.runtime, args.catalog, args.raw_dir)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
