#!/usr/bin/env python3
"""Research-only fixed risk grid; preserve entry model, chronology and printed sizes.

Every scenario starts from a fresh $10k portfolio on the same complete common
cohort. No configuration is selected by realized P&L and no live policy is read
or changed. Public-print fills remain hypothetical.
"""
import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timedelta
from decimal import Decimal
import gzip
import hashlib
import heapq
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from combos.backtest import BacktestConfig, run_backtest
from combos.risk import units


# Fixed before looking at sweep outcomes. Isolated relaxations diagnose which
# controls bind; balanced rows describe concentration/capacity tradeoffs.
SCENARIOS = (
    ('baseline', 100, 100, 250),
    ('fixture_only', 100, 100, 1000),
    ('underlying_only', 500, 100, 250),
    ('combo_only', 100, 500, 250),
    ('balanced_250', 250, 250, 500),
    ('balanced_500', 500, 500, 1000),
    ('balanced_1000', 1000, 1000, 2000),
    ('capital_only', 10000, 10000, 10000),
)


def common_cohort(data, start, end):
    rows = [r for r in data['opportunities'] if start <= r['at'] < end
            and r['source']['sampling_method'] == 'census']
    ids = defaultdict(set)
    for row in rows:
        ids[row['model']].add(row['evaluation_id'])
    common = set.intersection(*ids.values()) if ids else set()
    return [r for r in rows if r['evaluation_id'] in common]


def outcome_metrics(rows):
    known = [r for r in rows if r['yes_settlement'] is not None]
    unknown = [r for r in rows if r['yes_settlement'] is None]
    pnl = sum(r['quantity'] * (r['yes_price'] - r['yes_settlement']) - r['maker_fee'] for r in known)
    return {'known_outcome_pnl': pnl, 'known_outcomes': len(known), 'unknown_outcomes': len(unknown),
            'loose_final_pnl_bounds': [pnl + sum(r['quantity'] * (r['yes_price'] - 1) - r['maker_fee'] for r in unknown),
                                       pnl + sum(r['quantity'] * r['yes_price'] - r['maker_fee'] for r in unknown)]}


def exposure_audit(decisions, config):
    """Independently reconcile ledger and count *all* binding controls.

    Exposure is integer 1/10000 dollars exactly as in RiskLedger. Each combo's
    full cost belongs to every distinct underlying/fixture bucket; cash is
    charged only once. Equal fixture allocation is an attribution diagnostic,
    never a replacement risk test or hedge credit.
    """
    used = defaultdict(int)
    allocated = defaultdict(float)
    pending = []
    committed = pnl = 0
    peak = {'committed_cash': 0., 'at': None, 'fixture_exposures': [], 'fixture_count': 0,
            'gross_fixture_incidence_sum': 0., 'largest_fixture_incident_fraction_of_cash': 0.,
            'equal_allocation_hhi': 0.}
    max_bucket = defaultdict(int)
    all_binding = Counter()
    standalone_oversize = Counter()
    binding_sets = Counter()
    for row in sorted(decisions, key=lambda r: (r['at'], r['evaluation_id'])):
        while pending and pending[0][0] <= row['at']:
            _, _, old_cost, payout, buckets = heapq.heappop(pending)
            committed -= old_cost
            pnl += payout - old_cost
            for family, keys in buckets.items():
                for key in set(keys):
                    used[family + ':' + key] -= old_cost
            for key in set(buckets['fixture']):
                allocated[key] -= old_cost / len(set(buckets['fixture']))
        if 'risk' not in row:
            continue
        cost = units(row['quantity'] * (1 - row['yes_price']) + row['maker_fee'])
        available = units(config.capital_dollars) + pnl - committed
        binding = set()
        if cost > available:
            binding.add('capital')
        for family, keys in row['buckets'].items():
            cap = int(Decimal(str(getattr(config, 'per_' + family + '_dollars'))) *
                      Decimal(str(row['risk_multiplier'])) * 10000)
            if cost > cap:
                standalone_oversize[family] += 1
            if any(used[family + ':' + key] + cost > cap for key in set(keys)):
                binding.add(family)
        all_binding.update(binding)
        if binding:
            binding_sets['+'.join(sorted(binding))] += 1
        if row['accepted'] != (not binding):
            raise AssertionError('independent_risk_reconciliation_failed:' + row['evaluation_id'])
        if not row['accepted']:
            continue
        committed += cost
        for family, keys in row['buckets'].items():
            for key in set(keys):
                bucket = family + ':' + key
                used[bucket] += cost
                max_bucket[family] = max(max_bucket[family], used[bucket])
        for key in set(row['buckets']['fixture']):
            allocated[key] += cost / len(set(row['buckets']['fixture']))
        if row['settled_at'] is not None:
            payout = units(row['quantity'] * (1 - row['yes_settlement']))
            heapq.heappush(pending, (row['settled_at'] + config.settlement_delay_seconds,
                                    row['evaluation_id'], cost, payout, row['buckets']))
        if committed > round(peak['committed_cash'] * 10000):
            fixtures = [{'fixture': k.removeprefix('fixture:'), 'gross_incident_cash': v / 10000,
                         'equal_allocation_cash': allocated[k.removeprefix('fixture:')] / 10000}
                        for k, v in used.items() if k.startswith('fixture:') and v > 0]
            fixtures.sort(key=lambda r: r['gross_incident_cash'], reverse=True)
            peak = {'committed_cash': committed / 10000, 'at': row['at'], 'fixture_exposures': fixtures,
                    'fixture_count': len(fixtures),
                    'gross_fixture_incidence_sum': sum(r['gross_incident_cash'] for r in fixtures),
                    'largest_fixture_incident_fraction_of_cash': max(r['gross_incident_cash'] for r in fixtures) / (committed / 10000),
                    'equal_allocation_hhi': sum((r['equal_allocation_cash'] / (committed / 10000)) ** 2 for r in fixtures)}
    return {'all_binding_limits_nonexclusive': dict(all_binding), 'binding_limit_combinations': dict(binding_sets),
            'standalone_print_exceeds_limit_nonexclusive': dict(standalone_oversize),
            'maximum_single_bucket_cash': {k: v / 10000 for k, v in max_bucket.items()},
            'at_peak_cash': peak, 'independent_integer_ledger_reconciled': True}


def save_rows(path, rows):
    with gzip.open(path, 'wt') as handle:
        for row in rows:
            handle.write(json.dumps(row, allow_nan=False, separators=(',', ':')) + '\n')


def pregame_fixture_context(rows, at):
    """Observed priceable fixture inventory, not a claim of live RFQ liquidity.

    A fixture enters this context only once a priced print containing it has
    appeared. Started games may still consume risk through unexpired positions,
    so the currently-pregame count is NOT an upper bound on total held cash.
    """
    seen = {f for r in rows if r['at'] <= at for f in r['buckets']['fixture']}
    future = []
    for fixture in seen:
        token = fixture.removeprefix('mlb:')
        scheduled = datetime.strptime(token[:11], '%y%b%d%H%M').replace(tzinfo=ZoneInfo('America/New_York')).timestamp()
        if at < scheduled - 60:
            future.append(fixture)
    return {'seen_priceable_fixture_count': len(seen), 'seen_still_pregame_fixture_count': len(future),
            'seen_still_pregame_fixtures': sorted(future)}


def plot(rows, out, day):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    plt.style.use('dark_background')
    plt.rcParams['text.parse_math'] = False
    models = sorted({r['model'] for r in rows})
    fig, axes = plt.subplots(3, 1, figsize=(14, 11), sharex=True)
    positions = np.arange(len(SCENARIOS))
    colors = {'kalshi': '#73a0c4', 'polymarket': '#84c9be',
              'exchange_blend_equal': '#d2bd69', 'exchange_blend_pm75': '#c78aca'}
    width = .75 / len(models)
    for i, model in enumerate(models):
        subset = [next(r for r in rows if r['model'] == model and r['scenario'] == scenario[0]) for scenario in SCENARIOS]
        x = positions + (i - (len(models) - 1) / 2) * width
        axes[0].bar(x, [r['peak_committed_cash'] for r in subset], width, label=model, color=colors.get(model))
        axes[1].plot(x, [r['known_outcome_pnl'] for r in subset], 'o-', label=model, color=colors.get(model))
        for pos, r in zip(x, subset):
            axes[1].vlines(pos, *r['loose_final_pnl_bounds'], color=colors.get(model), linewidth=3, alpha=.55)
        axes[2].plot(x, [r['at_peak_cash']['largest_fixture_incident_fraction_of_cash'] * 100 for r in subset], 'o-', label=model, color=colors.get(model))
    axes[0].axhline(10000, color='#aaaaaa', linestyle='--', linewidth=1, label='$10k starting capital')
    axes[1].axhline(0, color='#aaaaaa', linewidth=1)
    for ax, label in zip(axes, ('Peak committed cash ($)', 'Known P&L; unresolved bounds ($)', 'Largest fixture / peak cash (%)')):
        ax.set_ylabel(label); ax.grid(axis='y', alpha=.2); ax.legend(fontsize=9)
        ax.ticklabel_format(axis='y', style='plain', useOffset=False)
    axes[2].set_xticks(positions, [name.replace('_', '\n') + f'\n{a}/{b}/{c}' for name, a, b, c in SCENARIOS], fontsize=9)
    axes[2].set_xlabel('Scenario and caps: underlying / combo / fixture ($); initial capital is $10,000')
    fig.suptitle(f'MLB risk capacity sensitivity · {day}\nSame common cohort and fixed 0.3c net point-entry threshold; full printed quantities', fontsize=13)
    fig.text(.07, .018, 'Research-only hypothetical public-print fills; no acceptance model. P&L is attributed to trade time; only settlement releases funding.\n'
             'Largest fixture fraction counts full incident combo cash; fixture fractions overlap. Grid is not optimized by P&L.\n'
             'One complete day: daily Sharpe and variance unavailable. No live limits changed.', fontsize=9)
    fig.tight_layout(rect=(0, .085, 1, .945))
    for ext in ('png', 'svg'):
        fig.savefig(out / ('risk_capacity.' + ext), dpi=155)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT / 'runs/mlb_historical_20260907/replay/opportunities.json')
    parser.add_argument('--out', type=Path, default=ROOT / 'runs/mlb_historical_20260907/risk_capacity')
    parser.add_argument('--date', default='2026-09-05')
    parser.add_argument('--no-plot', action='store_true')
    args = parser.parse_args()
    raw = args.input.read_bytes(); data = json.loads(raw)
    day = datetime.strptime(args.date, '%Y-%m-%d').replace(tzinfo=ZoneInfo('America/Chicago'))
    start, end = day.timestamp(), (day + timedelta(days=1)).timestamp()
    cohort = common_cohort(data, start, end)
    if not cohort:
        raise ValueError('no_complete_common_cohort')
    args.out.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, contract, combo, fixture in SCENARIOS:
        config = BacktestConfig(entry_basis='point', per_contract_dollars=contract,
                                per_combo_dollars=combo, per_fixture_dollars=fixture)
        result = run_backtest(cohort, start, end, config, constrained=True)
        save_rows(args.out / (name + '_decisions.jsonl.gz'), result['decisions'])
        save_rows(args.out / (name + '_curves.jsonl.gz'), result['curves'])
        for summary in result['summaries']:
            decisions = [r for r in result['decisions'] if r['model'] == summary['model']]
            accepted = [r for r in decisions if r['accepted']]
            summary = {**summary, 'scenario': name, 'config': asdict(config), **outcome_metrics(accepted),
                       **exposure_audit(decisions, config)}
            if summary['at_peak_cash']['at'] is not None:
                summary['at_peak_cash'].update(pregame_fixture_context(decisions, summary['at_peak_cash']['at']))
            rows.append(summary)
            print(json.dumps({key: summary[key] for key in ('scenario', 'model', 'fills', 'peak_committed_cash',
                                                           'known_outcome_pnl', 'loose_final_pnl_bounds')}, allow_nan=False), flush=True)
    fixtures = {f for r in cohort for f in r['buckets']['fixture']}
    minimum_fixtures = min(len(set(r['buckets']['fixture'])) for r in cohort)
    manifest = {'date': args.date, 'input_sha256': hashlib.sha256(raw).hexdigest(), 'run_id': data['run_id'],
                'models': sorted({r['model'] for r in cohort}), 'common_prints': len(cohort) // len({r['model'] for r in cohort}),
                'fixture_count': len(fixtures), 'minimum_distinct_fixtures_per_combo': minimum_fixtures,
                'baseline_loose_fixture_cash_ceiling': len(fixtures) * 250 / minimum_fixtures,
                'selection': 'complete census day; common available-model intersection',
                'scenarios_prespecified_before_sweep': SCENARIOS,
                'funding': 'Each scenario/model has separate $10k initial capital; only settled P&L may finance later trades.',
                'size_assumption': 'Full observed print quantity; no resizing or actual quote-win inference.',
                'live_policy_changed': False, 'daily_sharpe': None, 'daily_variance': None,
                'statistics_reason': 'one complete calendar day; fixtures shared across prints',
                'code_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in
                                (Path(__file__), ROOT / 'src/combos/backtest.py', ROOT / 'src/combos/risk.py', ROOT / 'src/combos/performance.py')}}
    (args.out / 'summary.json').write_text(json.dumps(rows, indent=2, allow_nan=False) + '\n')
    (args.out / 'manifest.json').write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')
    if not args.no_plot:
        plot(rows, args.out, args.date)


if __name__ == '__main__':
    main()
