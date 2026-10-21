#!/usr/bin/env python3
"""Audit OddsPapi Pinnacle limit fields without assigning currency or units."""
import argparse
import gzip
import json
import math
from collections import Counter
from pathlib import Path


def audit(raw_dir):
    files = sorted(Path(raw_dir).glob('**/*.json.gz'))
    fixtures = markets = outcomes = 0
    limits = []
    currency_fields, unit_fields = Counter(), Counter()
    for path in files:
        payload = json.loads(gzip.open(path, 'rt').read()).get('payload')
        rows = payload if isinstance(payload, list) else [payload]
        for fixture in rows:
            if not isinstance(fixture, dict):
                continue
            book = (fixture.get('bookmakerOdds') or {}).get('pinnacle+30')
            if not book:
                continue
            fixtures += 1
            for market in (book.get('markets') or {}).values():
                markets += 1
                for outcome in (market.get('outcomes') or {}).values():
                    value = (outcome.get('players') or {}).get('0')
                    if not value:
                        continue
                    outcomes += 1
                    if 'limit' in value:
                        limits.append(value['limit'])
                    for key, target in (("currency", currency_fields), ("limitCurrency", currency_fields),
                                        ("limitUnit", unit_fields), ("unit", unit_fields)):
                        if key in value:
                            target[f'{key}={value[key]}'] += 1
    numeric = [x for x in limits if isinstance(x, (int, float)) and math.isfinite(x)]
    return {
        'files': len(files), 'bookmaker_fixtures': fixtures, 'markets': markets,
        'outcomes': outcomes, 'limit_fields': len(limits), 'numeric_limits': len(numeric),
        'currency_fields': dict(currency_fields), 'unit_fields': dict(unit_fields),
        'minimum_limit': min(numeric) if numeric else None,
        'maximum_limit': max(numeric) if numeric else None,
        'currency_and_unit_verified': bool(currency_fields and unit_fields),
        'provider_documentation': {
            'docs_limit_definition': 'maximum stake allowed for the odds',
            'docs_url': 'https://oddspapi.io/us/docs/get-historical-odds',
            'provider_blog_pinnacle_definition': 'Pinnacle limit may cap bookmaker maximum loss rather than customer stake',
            'blog_url': 'https://oddspapi.io/blog/betting-limits-api-stake-sizing/',
            'semantics_conflict_requires_provider_confirmation': True,
        },
        'interpretation': 'Numeric limit fields are present; currency, stake/loss basis and unit semantics are not inferred. Conflicting provider documentation keeps pricing fail-closed.',
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-dir', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.raw_dir)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
