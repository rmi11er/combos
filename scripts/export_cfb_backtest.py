#!/usr/bin/env python3
"""Adapt a completed CFB fair-model run to the reusable backtester schema."""
import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def export(run, output):
    source = json.loads((run / 'performance_input.json').read_text())
    data_run = Path(source['identity']['data_run'])
    spec = importlib.util.spec_from_file_location('cfb_pilot', ROOT / 'scripts/cfb_fair_pilot.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.DATA = data_run
    pilot = module.Pilot(source['identity']['configuration'])
    tape = module.extract_tape(pilot)
    trades = {r['trade']['trade_id']: r['trade'] for r in tape['trades']}
    rows = []
    for row in csv.DictReader((run / 'combo_comparisons.csv').open()):
        trade = trades[row['trade_id']]; market = tape['markets'][trade['ticker']]
        legs = market['mve_selected_legs']
        q, p = float(row['quantity']), float(row['yes_price'])
        event = market['event_ticker']
        if event.startswith('KXMVECROSSCATEGORY-SHARD1-'):
            rate = .035
        elif event.startswith('KXMVECROSSCATEGORY0-SHARD1-'):
            rate = 0.
        else:
            raise ValueError('unreviewed fee series')
        settled = module.timestamp(market['settlement_ts']) if market.get('settlement_ts') else None
        rows.append({'model': row['model'], 'evaluation_id': row['trade_id'], 'at': float(row['at']),
                     'quantity': q, 'yes_price': p, 'maker_fee': module.short_yes_economics(q, p, 0, rate)['maker_fee'],
                     'fair_point': float(row['fair_point']), 'stressed_upper': float(row['stressed_upper']),
                     'quote_allowed': row['quote_allowed'] == 'True', 'risk_multiplier': float(row['risk_multiplier']),
                     'sampling_weight': float(row['sampling_weight']), 'settled_at': settled,
                     'yes_settlement': float(market['settlement_value_dollars']) if settled is not None else None,
                     'buckets': {'contract': sorted({pilot.maps[l['market_ticker']]['risk_key'] for l in legs}),
                                 'fixture': sorted({pilot.maps[l['market_ticker']]['fixture']['fixtureId'] for l in legs}),
                                 'combo': [trade['ticker']]},
                     'source_context': {'legs': legs, 'combo_ticker': trade['ticker'], 'maker_fee_rate': rate}})
    identity = {**source['identity'], 'adapter_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'source_performance_sha256': hashlib.sha256((run / 'performance_input.json').read_bytes()).hexdigest(),
                'source_comparisons_sha256': hashlib.sha256((run / 'combo_comparisons.csv').read_bytes()).hexdigest()}
    result = {'schema_version': 1, 'run_id': source['run_id'], 'display_name': source['display_name'],
              'start_at': source['start_at'], 'end_at': source['end_at'], 'identity': identity,
              'cohort_description': f'{len({r["evaluation_id"] for r in rows})} comparable YES-taker prints from preselected CFB fixtures; not a census of the reporting window',
              'opportunities': rows}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(f'Exported {len(rows)} model evaluations to {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(); export(args.run, args.out)
