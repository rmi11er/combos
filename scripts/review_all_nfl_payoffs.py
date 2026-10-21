"""Score-enumerate reviewed selector candidates, preserving all pricing blocks."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from combos.payoff_enumeration import review
from combos.pinnacle_feed import fixture_index

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runtime', required=True, type=Path)
    p.add_argument('--snapshot', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    a = p.parse_args()
    paths = (a.runtime, a.snapshot, Path(__file__), Path(__file__).resolve().parents[1]/'src/combos/payoff_enumeration.py')
    hashes = {str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    runtime = json.loads(a.runtime.read_text())
    with gzip.open(a.snapshot, 'rt') as handle:
        fixtures = fixture_index(json.load(handle)['payload'])
    rows = []
    for mapping in runtime['mappings']:
        fixture = fixtures.get(mapping.get('pinnacle', {}).get('fixture_id'))
        try:
            result = review(mapping, fixture)
        except (KeyError, ValueError, TypeError) as exc:
            result = {'status':'invalid_mapping', 'reason':str(exc)}
        rows.append({'market_key':mapping['market_key'], 'review':result})
    a.out.mkdir(parents=True, exist_ok=False)
    summary = {'input_hashes':hashes, 'counts':dict(Counter(r['review']['status'] for r in rows)),
               'mappings':len(rows), 'pricing_authorized':False}
    for path, digest in hashes.items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != digest:
            raise ValueError('source changed during review')
    (a.out/'rows.json').write_text(json.dumps(rows, indent=2))
    (a.out/'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary['counts']))
