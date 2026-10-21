#!/usr/bin/env python3
"""Full certified native NFL seller benchmark; offline, unlimited, no plots."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal
import itertools
import json
from pathlib import Path
import resource
import sqlite3
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from combos.fees import kalshi_fill_fee
from mlb_dated_universe_report import check_cohort, digest, stamp
from replay_artifact_io import text_reader, text_writer, zstd_identity

RATES = ('0', '0.0175', '0.035', '0.07')
BASE = '0.035'
MONEY = ('known_net_pnl', 'unknown_lower', 'unknown_upper', 'yes_premium',
         'payout_notional', 'maker_fees', 'cumulative_no_cash')
PROP_SERIES = {'KXNFLANYTD', 'KXNFLPASSYDS', 'KXNFLRECYDS', 'KXNFLRSHYDS',
               'KXNFLREC', 'KXNFL2TD', 'KXNFLFIRSTTD'}


def zero():
    return dict(prints=0, known_prints=0, unknown_prints=0,
                **{k: Decimal(0) for k in MONEY})


def add(target, values):
    for key in target:
        target[key] += values[key]


def finish(values):
    money = {k: str(values[k]) for k in MONEY}
    return {**{k: int(values[k]) for k in ('prints', 'known_prints', 'unknown_prints')},
            **{k: float(values[k]) for k in MONEY},
            'final_pnl_lower': float(values['known_net_pnl'] + values['unknown_lower']),
            'final_pnl_upper': float(values['known_net_pnl'] + values['unknown_upper']),
            'exact_decimal': money}


def labels(row):
    c = row['classification']
    n = c['nlegs']
    if c.get('pure_nfl') is not True or type(n) is not int or n < 2:
        raise ValueError('invalid_native_NFL_classification')
    q, p = Decimal(row['trade']['count_fp']), Decimal(row['trade']['yes_price_dollars'])
    premium = q * p
    start = c.get('earliest_scheduled_start')
    # The cohort stores False when it cannot identify a schedule. Do not call that in-play.
    phase = 'Unknown schedule' if start is None else ('Pregame schedule proxy' if row['pregame_scheduled_proxy'] else 'After schedule cutoff')
    primary = c['target_fixtures_only'] and c['fullgame_core'] and c['distinct_fixtures'] and 2 <= n <= 4 and start is not None and row['pregame_scheduled_proxy']
    return {'legs': str(n) if n < 5 else '5+',
            'structure': 'Distinct fixtures' if c['distinct_fixtures'] else 'Contains same-game legs',
            'family': 'Full-game core' if c['fullgame_core'] else 'Includes known player prop' if set(c['series']) & PROP_SERIES else 'Other NFL family',
            'phase': phase,
            'scope': 'Primary structural scope before source pricing' if primary else 'Outside primary structural scope',
            'premium': 'At most $10' if premium <= 10 else '$10–50' if premium <= 50 else '$50–250' if premium <= 250 else 'Above $250'}


def economics(row, rate):
    trade = row['trade']
    q, p = Decimal(trade['count_fp']), Decimal(trade['yes_price_dollars'])
    if not q.is_finite() or not p.is_finite() or q <= 0 or not 0 <= p <= 1:
        raise ValueError('invalid_trade_economics')
    value = row.get('settlement_value_dollars')
    settlement = Decimal(str(value)) if value is not None else None
    if settlement is not None and (not settlement.is_finite() or not 0 <= settlement <= 1):
        raise ValueError('invalid_native_settlement')
    # Preserve actual native scalar settlement, never replace it with result=yes/no.
    fee = kalshi_fill_fee(q, 1-p, rate, action='buy', balance_precision='.0001', accumulator=0)['net_fee']
    known = settlement is not None
    return {'prints': 1, 'known_prints': int(known), 'unknown_prints': int(not known),
            'known_net_pnl': q*(p-settlement)-fee if known else Decimal(0),
            'unknown_lower': q*(p-1)-fee if not known else Decimal(0),
            'unknown_upper': q*p-fee if not known else Decimal(0),
            'yes_premium': q*p, 'payout_notional': q, 'maker_fees': fee,
            'cumulative_no_cash': q*(1-p)+fee}


def certified(root, through):
    state = json.loads((root/'days/state.json').read_text())
    result = []
    for day, entry in sorted(state['days'].items()):
        if day > through or entry.get('status') != 'complete':
            continue
        for path, expected in entry['output_sha256'].items():
            if digest(path) != expected:
                raise ValueError('cohort_certificate_changed:' + path)
        cohort = root/'days'/day/'cohort'
        summary = check_cohort(cohort)
        if summary.get('sport') != 'NFL':
            raise ValueError('NFL_cohort_required')
        result.append((day, cohort, summary, entry['output_sha256']))
    if not result or result[-1][0] != through:
        raise ValueError('requested_end_date_not_complete')
    if any(a[2]['end_at'] != b[2]['start_at'] for a, b in zip(result, result[1:])):
        raise ValueError('noncontiguous_completed_window')
    return result


def emit(handle, row):
    handle.write(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n')


def analyze(root, through, output):
    output.mkdir(parents=True, exist_ok=False)
    began = time.monotonic()
    days = certified(root, through)
    db = sqlite3.connect(output/'sorting.sqlite')
    db.execute('PRAGMA cache_size=-16384')
    db.execute('PRAGMA temp_store=FILE')
    db.execute('CREATE TABLE trades(id TEXT PRIMARY KEY, at REAL, day TEXT, payload TEXT)')
    db.execute('CREATE INDEX trade_order ON trades(at,id)')
    counts = Counter()
    hashes = {}
    provenance = []
    totals = {r: zero() for r in RATES}
    daily = {d: {r: zero() for r in RATES} for d, *_ in days}
    cuts = {key: defaultdict(lambda: {r: zero() for r in RATES}) for key in ('legs', 'structure', 'family', 'phase', 'scope', 'premium')}
    fixtures = defaultdict(lambda: {r: zero() for r in RATES})
    try:
        for day, cohort, summary, manifest in days:
            hashes.update(manifest)
            provenance.append({'date': day, 'cohort': str(cohort), 'summary_sha256': digest(cohort/'summary.json')})
            rows = 0
            with text_reader(cohort/'universe_trades.jsonl.gz') as handle:
                for line in handle:
                    row = json.loads(line)
                    trade = row['trade']
                    at = stamp(trade['created_time'])
                    if row['sampling_method'] != 'census' or not summary['start_at'] <= at < summary['end_at']:
                        raise ValueError('row_outside_completed_day')
                    labels(row)
                    rows += 1
                    counts['native_prints'] += 1
                    side = trade.get('taker_side')
                    if trade.get('taker_outcome_side') not in (None, side):
                        raise ValueError('taker_side_disagreement')
                    counts['taker_side_' + str(side)] += 1
                    if side != 'yes':
                        continue
                    try:
                        db.execute('INSERT INTO trades VALUES(?,?,?,?)', (trade['trade_id'], at, day, line))
                    except sqlite3.IntegrityError:
                        raise ValueError('duplicate_native_seller_print') from None
            if rows != summary['counts']['pure_nfl_prints']:
                raise ValueError('native_universe_count_mismatch')
            db.commit()
        curve_rows = 0
        curve_totals = {r: zero() for r in RATES}
        ordered = db.execute('SELECT at,day,payload FROM trades ORDER BY at,id')
        with text_writer(output/'seller_ledger.jsonl.zst') as ledger, text_writer(output/'full_resolution_curves.jsonl.zst') as curves:
            for at, group in itertools.groupby(ordered, key=lambda r: r[0]):
                for _, day, payload in group:
                    row = json.loads(payload)
                    categories = labels(row)
                    values = {r: economics(row, r) for r in RATES}
                    for rate, econ in values.items():
                        for target in (totals[rate], daily[day][rate], curve_totals[rate]):
                            add(target, econ)
                        for key, label in categories.items():
                            add(cuts[key][label][rate], econ)
                        for fixture in set(row['classification']['fixture_tokens']):
                            add(fixtures[fixture][rate], econ)
                    emit(ledger, {**row, 'trade_at': at, 'date': day, 'categories': categories,
                                  'benchmark_basis': 'Observed YES-taker seller counterfactual; no own fill inference',
                                  'base_maker_rate': BASE,
                                  'economics_by_maker_rate': {r: finish(v) for r, v in values.items()}})
                emit(curves, {'at': at, 'basis': 'cumulative eventual PnL attributed to trade; unlimited exposure',
                              **finish(curve_totals[BASE]),
                              'fee_sensitivity': {r: finish(curve_totals[r]) for r in RATES if r != BASE}})
                curve_rows += 1
        statistics_by_rate = {}
        for rate in RATES:
            known = all(daily[d][rate]['unknown_prints'] == 0 for d in daily)
            pnls = [float(daily[d][rate]['known_net_pnl']) for d in daily]
            statistics_by_rate[rate] = {'annualized_sharpe': None,
                'observed_date_pnl_variance_dollars2': statistics.variance(pnls) if known and len(pnls) > 1 else None,
                'reason': 'Unlimited benchmark has no funded return denominator. Daily PnL variance is descriptive; shared playoff outcomes are not independent trials.'}
        report = {'schema_version': 1, 'sport': 'NFL', 'observed_dates': [d[0] for d in days],
                  'start_at': days[0][2]['start_at'], 'end_at': days[-1][2]['end_at'],
                  'counts': dict(counts), 'curve_rows': curve_rows, 'base_maker_rate': BASE,
                  'totals': {r: finish(v) for r, v in totals.items()},
                  'daily': {d: {r: finish(v) for r, v in rates.items()} for d, rates in daily.items()},
                  'cuts': {k: {label: {r: finish(v) for r, v in rates.items()} for label, rates in sorted(groups.items())} for k, groups in cuts.items()},
                  'fixtures': {f: {r: {**finish(v), 'known_pnl_after_excluding_fixture': float(totals[r]['known_net_pnl'] - v['known_net_pnl'])} for r, v in rates.items()} for f, rates in sorted(fixtures.items())},
                  'statistics': statistics_by_rate, 'input_hashes': hashes, 'provenance': provenance,
                  'fee_scenario': {'effective_dates_verified': False, 'maker_rates': list(RATES), 'base_rate': BASE,
                      'cash_precision': '.0001', 'opening_order_accumulator': 0, 'maker_position': 'buy NO at 1-YES-price',
                      'reference': 'Explicit January scenario, matching existing NFL replay; no certified historical maker fee schedule'},
                  'assumptions': ['Every certified pure-NFL YES-taker print retained, all leg counts, families and phases.',
                      'Numeric native settlement values preserved, including scalar/fractional settlements; unknown outcomes remain bounded.',
                      'Unknown native schedule remains unknown, never classified as in-play.',
                      'No pricing/source availability, capital, concentration, ticket-size or edge filter.',
                      'Public-print seller counterfactual, not evidence of RFQ execution or fill probability.',
                      'Fixture membership overlaps; fixture contributions are not additive.',
                      'Fees are scenarios; no cross-venue fees are charged in this native seller benchmark.'],
                  'resources': {'elapsed_seconds': time.monotonic()-began, 'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},
                  'codec': zstd_identity(),
                  'source_hashes': {str(p): digest(p) for p in (Path(__file__), ROOT/'scripts/replay_artifact_io.py', ROOT/'scripts/mlb_dated_universe_report.py', ROOT/'src/combos/fees.py')}}
        (output/'summary.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    finally:
        db.close()
        (output/'sorting.sqlite').unlink(missing_ok=True)
    files = {p.name: {'sha256': digest(p), 'bytes': p.stat().st_size} for p in output.iterdir() if p.is_file()}
    (output/'complete.json').write_text(json.dumps({'artifacts': files, 'prints': totals[BASE]['prints'], 'curve_rows': curve_rows}, indent=2)+'\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--through', default='2026-01-12')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    report = analyze(args.root, args.through, args.out)
    print(json.dumps({'counts': report['counts'], 'totals': report['totals'], 'resources': report['resources']}, indent=2))


if __name__ == '__main__':
    main()
