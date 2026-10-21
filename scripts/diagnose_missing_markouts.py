"""Reconstruct market state at recorded unavailable-markout source cutoffs."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from combos.rfq_scenario_consumer import RFQScenarioConsumer
from combos.weighted_fair import WeightPolicy


def closed(path):
    return sqlite3.connect(path.resolve().as_uri() + '?mode=ro&immutable=1', uri=True)


def run(a):
    src = closed(a.source)
    marks = closed(a.marks)
    identity = json.loads(marks.execute('SELECT identity FROM checkpoint').fetchone()[0])['identity']
    for path, digest in identity['hashes'].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest, path
    pricing = RFQScenarioConsumer(json.loads(a.runtime.read_text()), json.loads(a.catalog.read_text()),
                                  WeightPolicy(**json.loads(a.weights.read_text())))
    for path in (a.runtime, a.catalog, a.weights):
        assert identity['hashes'][str(path.resolve())] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert identity['source'] == str(a.source.resolve())
    targets = defaultdict(list)
    for raw, in marks.execute("SELECT value FROM labels WHERE json_extract(value,'$.status')='unavailable'"):
        row = json.loads(raw)
        targets[row['available_source_seq']].append(row)
    details = []
    previous_pin = None
    last_pin_reset = None
    kinds = {'observation', 'venue_reset', 'external_raw', 'book_verification'}
    for seq, kind, source, received, raw in src.execute('SELECT seq,kind,source,received_at,payload FROM events ORDER BY seq'):
        if kind in kinds:
            payload = json.loads(zlib.decompress(raw))
            if kind == 'external_raw' and source == 'pinnacle':
                previous_pin = pricing.pin
            if kind == 'venue_reset' and source == 'pinnacle':
                last_pin_reset = {'seq': seq, 'received_at': received, 'reason': payload.get('reason')}
            pricing.consume(dict(seq=seq, kind=kind, source=source, received_at=received, payload=payload), price_rfqs=False)
        for label in targets.pop(seq, []):
            at = label['valuation_at']
            item = {k: label[k] for k in ('decision_seq', 'horizon_seconds', 'available_source_seq', 'reason')}
            failures = []
            if label['reason'] == 'exchange_candidate_coverage_missing':
                for leg in label['entry_scenario']['legs']:
                    key = leg['market_key']
                    native = pricing.pm.books.get(key)
                    reasons = []
                    if key not in pricing.kalshi:
                        reasons.append('kalshi_missing')
                    if not pricing.pm.pair(key, at)['candidate']:
                        if native is None:
                            reasons.append('pm_missing')
                        else:
                            if not native.get('active'):
                                reasons.append('pm_inactive')
                            if native['available_at'] > at:
                                reasons.append('pm_not_available_at_horizon')
                            if min(native.get('yes_bid_size', 0), native.get('yes_ask_size', 0)) <= 0:
                                reasons.append('pm_zero_depth')
                            if not reasons:
                                reasons.append('pm_no_fresh_native_or_verified_book')
                    if reasons:
                        certificate = pricing.pm.certificates.get(key)
                        failures.append({'market_key': key, 'reasons': reasons,
                            'native_invalid_reason': native.get('invalid_reason') if native else None,
                            'native_age_seconds': at-native['observed_at'] if native else None,
                            'native_available_minus_horizon': native['available_at']-at if native else None,
                            'verification_age_seconds': at-certificate['evidence']['verified_at'] if certificate else None})
                assert failures, label
            elif label['reason'] == 'pinnacle_not_yet_available':
                assert pricing.pin is None or pricing.pin['available'] > at
                failures.append({'reasons': ['pinnacle_missing' if pricing.pin is None else 'pinnacle_delivery_after_horizon'],
                    'last_reset': last_pin_reset,
                    'available_minus_horizon': pricing.pin['available']-at if pricing.pin else None,
                    'previous_available_by_horizon': previous_pin is not None and previous_pin['available'] <= at,
                    'previous_observation_age': at-previous_pin['observed'] if previous_pin else None})
            else:
                failures.append({'reasons': ['unclassified:' + label['reason']]})
            item['failures'] = failures
            details.append(item)
    assert not targets
    summary = {'labels': len(details), 'label_reason_counts': dict(Counter(
        reason for row in details for reason in {r for f in row['failures'] for r in f['reasons']})),
        'inactive_label_reasons': dict(Counter(
            reason for row in details for reason in {f.get('native_invalid_reason') or 'unspecified'
                for f in row['failures'] if 'pm_inactive' in f['reasons']})),
        'limitations': ['Counts overlap when multiple failure reasons affect one label.',
                       'Reconstructs existing model state, not independent fair arithmetic.',
                       'Prior Pinnacle availability alone does not certify its freshness or eligibility.']}
    a.out.mkdir(parents=True, exist_ok=False)
    (a.out/'details.json').write_text(json.dumps(details, indent=2))
    (a.out/'summary.json').write_text(json.dumps(summary, indent=2))
    src.close()
    marks.close()
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('source', 'marks', 'runtime', 'catalog', 'weights', 'out'):
        p.add_argument('--'+key, type=Path, required=True)
    run(p.parse_args())
