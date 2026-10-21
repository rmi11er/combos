#!/usr/bin/env python3
"""Paired, descriptive source disagreement audit; no inferred RFQ acceptance.

Use unconstrained decisions to isolate price selection from inventory ordering.
Positive PM-minus-Kalshi means PM assigns a greater combo YES probability.
"""
import argparse
from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path


def pair_rows(rows):
    models = {'kalshi': {}, 'polymarket': {}}
    for row in rows:
        if row['model'] not in models:
            continue
        target = models[row['model']]
        key = row['evaluation_id']
        if key in target:
            raise ValueError('duplicate_model_evaluation')
        target[key] = row
    paired = []
    for key in sorted(models['kalshi'].keys() & models['polymarket'].keys()):
        k, p = models['kalshi'][key], models['polymarket'][key]
        for field in ('at', 'quantity', 'yes_price', 'maker_fee', 'yes_settlement', 'buckets', 'source'):
            if k[field] != p[field]:
                raise ValueError('inconsistent_paired_' + field)
        for row in (k, p):
            if row['reason'] not in ('accepted', 'insufficient_edge'):
                raise ValueError('requires_unconstrained_price_only_decisions')
        paired.append((k, p))
    return paired, {name: len(rs) for name, rs in models.items()}


def metrics(pairs):
    known = [(k, p) for k, p in pairs if k['yes_settlement'] is not None]
    unknown = [(k, p) for k, p in pairs if k['yes_settlement'] is None]
    quantity = sum(k['quantity'] for k, _ in known)
    cash = sum(k['quantity'] * (1-k['yes_price']) + k['maker_fee'] for k, _ in known)
    pnl = sum(k['quantity'] * (k['yes_price']-k['yes_settlement'])-k['maker_fee'] for k, _ in known)
    result = {
        'prints': len(pairs), 'known_outcomes': len(known), 'unknown_outcomes': len(unknown),
        'unique_combos': len({b for k, _ in pairs for b in k['buckets']['combo']}),
        'unique_fixtures': len({b for k, _ in pairs for b in k['buckets']['fixture']}),
        'known_net_seller_pnl': pnl, 'known_cumulative_no_cash_including_fees': cash,
        'pnl_per_known_cumulative_no_cash': pnl/cash if cash else None,
        'loose_final_pnl_bounds': [pnl + sum(k['quantity']*(k['yes_price']-outcome)-k['maker_fee']
                                           for k, _ in unknown) for outcome in (1, 0)],
    }
    for index, name in enumerate(('kalshi', 'polymarket')):
        result[name] = {
            'brier_equal_print': sum((pair[index]['fair_point']-pair[index]['yes_settlement'])**2
                                     for pair in known)/len(known) if known else None,
            'brier_quantity_weighted': sum(pair[index]['quantity']*(pair[index]['fair_point']-pair[index]['yes_settlement'])**2
                                          for pair in known)/quantity if quantity else None,
            'quantity_weighted_fair_minus_outcome': sum(pair[index]['quantity']*(pair[index]['fair_point']-pair[index]['yes_settlement'])
                                                       for pair in known)/quantity if quantity else None,
        }
    result['pm_minus_kalshi_brier_quantity_weighted'] = (
        result['polymarket']['brier_quantity_weighted']-result['kalshi']['brier_quantity_weighted'] if quantity else None)
    return result


def summarize(pairs):
    groups = defaultdict(list)
    for k, p in pairs:
        difference = 100*(p['fair_point']-k['fair_point'])
        direction = 'pm_lower' if difference < -0.5 else 'pm_higher' if difference > 0.5 else 'within_0.5_cent'
        magnitude = '<=0.5c' if abs(difference) <= 0.5 else '0.5-2c' if abs(difference) <= 2 else '>2c'
        selection = 'both' if k['accepted'] and p['accepted'] else 'kalshi_only' if k['accepted'] else 'polymarket_only' if p['accepted'] else 'neither'
        premium = k['quantity']*k['yes_price']
        family = 'moneyline_only' if k['source']['series'] == ['KXMLBGAME'] else 'other_game_markets'
        for dimension, value in (('direction', direction), ('magnitude', magnitude), ('selection', selection),
                                 ('legs', str(k['source']['nlegs'])), ('family', family),
                                 ('premium', '<=10' if premium <= 10 else '10-50' if premium <= 50 else '>50'),
                                 ('direction_and_selection', direction + ':' + selection)):
            groups[dimension, value].append((k, p))
    fixtures = sorted({b for k, _ in pairs for b in k['buckets']['fixture']})
    return {
        'all_common': metrics(pairs),
        'groups': [{'dimension': d, 'value': v, **metrics(rs)} for (d, v), rs in sorted(groups.items())],
        'leave_one_fixture_out': [{'removed_fixture': fixture, **metrics([(k, p) for k, p in pairs
                                    if fixture not in k['buckets']['fixture']])} for fixture in fixtures],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--sport', required=True, choices=('mlb',))
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    with gzip.open(args.input, 'rt') as stream:
        pairs, counts = pair_rows(json.loads(line) for line in stream)
    if not pairs:
        raise ValueError('empty_common_cohort')
    result = summarize(pairs)
    result['manifest'] = {
        'sport': args.sport, 'input': str(args.input.resolve()),
        'input_sha256': hashlib.sha256(args.input.read_bytes()).hexdigest(),
        'code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'source_print_counts': counts, 'first_trade_at': min(k['at'] for k, _ in pairs),
        'last_trade_at': max(k['at'] for k, _ in pairs),
        'interpretation': [
            'Combo probability disagreement, not a leg-level sharpness test.',
            'PM minus Kalshi Brier below zero favors PM on the same known outcomes.',
            'Repeated combos and shared fixtures make prints statistically dependent.',
            'Leave-one-fixture-out is overlapping sensitivity analysis, not a confidence interval.',
            'Cumulative NO cash ratio is an exposure diagnostic, not a funded portfolio return.',
            'Public-print sells at observed prices do not establish RFQ fill probability.',
            'Bands fixed for this exploratory audit; current outcomes have already been inspected.',
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'output': str(args.out), 'all_common': result['all_common']}, indent=2))


if __name__ == '__main__':
    main()
