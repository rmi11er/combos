#!/usr/bin/env python3
"""Frozen MLB entry-policy comparison on complete, paired public-print days."""
import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timedelta
import gzip
import hashlib
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from combos.backtest import BacktestConfig, run_backtest


# These alternatives are fixed before running the new historical dates. This
# script deliberately contains no optimizer or best-performing-policy selection.
VARIANTS = (
    ('sell_every_priced_print', 'Sell all', {'entry_filter': 'all_priced', 'minimum_net_edge_per_share': 0.}),
    ('edge_0c', '0c', {'minimum_net_edge_per_share': 0.}),
    ('edge_0_1c', '0.1c', {'minimum_net_edge_per_share': .001}),
    ('edge_0_3c', '0.3c', {'minimum_net_edge_per_share': .003}),
    ('edge_0_5c', '0.5c', {'minimum_net_edge_per_share': .005}),
    ('edge_0_3c_per_leg', '0.3c / leg', {'minimum_net_edge_per_share': .003, 'minimum_net_edge_unit': 'leg_contract'}),
)


def write(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')


def paired_day(data, date):
    day = datetime.strptime(date, '%Y-%m-%d').replace(tzinfo=ZoneInfo('America/Chicago'))
    start, end = day.timestamp(), (day + timedelta(days=1)).timestamp()
    if data['start_at'] > start or data['end_at'] < end:
        raise ValueError('input_does_not_cover_complete_calendar_day')
    models = sorted({row['model'] for row in data['opportunities']})
    by_model = {model: {} for model in models}
    for row in data['opportunities']:
        if not start <= row['at'] < end:
            continue
        if row['source']['sampling_method'] != 'census':
            raise ValueError('requested_day_contains_non_census_source')
        if type(row['source']['nlegs']) is not int or not 2 <= row['source']['nlegs'] <= 4:
            raise ValueError('study_requires_two_through_four_legs')
        if len(set(row['buckets']['fixture'])) != row['source']['nlegs']:
            raise ValueError('study_requires_distinct_fixtures')
        if row['at'] >= row['source']['start_at'] - 60:
            raise ValueError('study_requires_sixty_second_pregame_cutoff')
        if not set(row['source']['series']) <= {'KXMLBGAME', 'KXMLBSPREAD', 'KXMLBTOTAL'}:
            raise ValueError('study_requires_fullgame_non_player_MLB')
        target = by_model[row['model']]
        if row['evaluation_id'] in target:
            raise ValueError('duplicate_model_evaluation')
        target[row['evaluation_id']] = row
    common = set.intersection(*(set(rows) for rows in by_model.values())) if models else set()
    if not common:
        raise ValueError('no_common_priced_complete_day_data')
    rows = []
    for identifier in sorted(common):
        reference = by_model[models[0]][identifier]
        for model in models:
            row = by_model[model][identifier]
            for key in ('at', 'quantity', 'yes_price', 'maker_fee', 'yes_settlement', 'settled_at', 'buckets', 'source'):
                if row[key] != reference[key]:
                    raise ValueError('inconsistent_paired_' + key)
            rows.append(row)
    return rows, start, end, {model: len(rs) for model, rs in by_model.items()}


def metrics(rows):
    known = [r for r in rows if r['yes_settlement'] is not None]
    unknown = [r for r in rows if r['yes_settlement'] is None]
    pnl = sum(r['quantity'] * (r['yes_price'] - r['yes_settlement']) - r['maker_fee'] for r in known)
    cash = sum(r['quantity'] * (1 - r['yes_price']) + r['maker_fee'] for r in rows)
    known_cash = sum(r['quantity'] * (1 - r['yes_price']) + r['maker_fee'] for r in known)
    edges = [r['quantity'] * (r['yes_price'] - r['fair_point']) - r['maker_fee'] for r in rows]
    fixture_pnl, fixture_cash, combo_cash = defaultdict(float), defaultdict(float), defaultdict(float)
    for r in rows:
        spent = r['quantity'] * (1 - r['yes_price']) + r['maker_fee']
        for fixture in set(r['buckets']['fixture']):
            fixture_cash[fixture] += spent
            if r['yes_settlement'] is not None:
                fixture_pnl[fixture] += r['quantity'] * (r['yes_price'] - r['yes_settlement']) - r['maker_fee']
        # A combo bucket is a canonical payoff identity; valid opportunities
        # have one. Refuse multiple identities instead of doubling concentration.
        combos = set(r['buckets']['combo'])
        if len(combos) != 1:
            raise ValueError('single_canonical_combo_identity_required')
        combo_cash[next(iter(combos))] += spent
    return {'prints': len(rows), 'known_outcomes': len(known), 'unknown_outcomes': len(unknown),
            'known_net_pnl': pnl,
            'loose_final_pnl_bounds': [pnl + sum(r['quantity'] * (r['yes_price'] - outcome) - r['maker_fee'] for r in unknown)
                                     for outcome in (1., 0.)],
            'fees': sum(r['maker_fee'] for r in rows),
            'yes_premium': sum(r['quantity'] * r['yes_price'] for r in rows),
            'payout_notional': sum(r['quantity'] for r in rows), 'cumulative_no_cash_including_fees': cash,
            'known_cumulative_no_cash_including_fees': known_cash,
            'pnl_per_known_cumulative_no_cash': pnl / known_cash if known_cash else None,
            'net_point_edge': sum(edges), 'positive_net_point_edge': sum(max(0., edge) for edge in edges),
            'negative_net_point_edge': sum(min(0., edge) for edge in edges),
            'positive_edge_prints': sum(edge > 0 for edge in edges),
            'unique_fixtures': len(fixture_cash), 'unique_combos': len(combo_cash),
            'largest_fixture_cumulative_cash_share': max(fixture_cash.values(), default=0.) / cash if cash else None,
            'largest_combo_cumulative_cash_share': max(combo_cash.values(), default=0.) / cash if cash else None,
            'known_pnl_after_removing_one_fixture_range': [min((pnl - fixture_pnl[k] for k in fixture_cash), default=pnl),
                                                         max((pnl - fixture_pnl[k] for k in fixture_cash), default=pnl)],
            'fixture_contributions': [{'fixture': fixture, 'known_net_pnl': fixture_pnl[fixture],
                                       'cumulative_no_cash_including_fees': fixture_cash[fixture]}
                                      for fixture in sorted(fixture_cash)],
            'concentration_basis': 'Any-leg fixture membership overlaps; cumulative cash is not simultaneous exposure or a funded return.'}


def sweep(rows, start, end):
    """Yield one full independent portfolio run per fixed policy and regime."""
    for name, label, overrides in VARIANTS:
        config = BacktestConfig(entry_basis='point', **overrides)
        for constrained in (True, False):
            result = run_backtest(rows, start, end, config, constrained)
            regime = 'constrained' if constrained else 'unconstrained'
            for summary in result['summaries']:
                model = summary['model']
                decisions = [r for r in result['decisions'] if r['model'] == model]
                curves = [r for r in result['curves'] if r['model'] == model]
                mean_cash = sum(a['committed_cash'] * (b['at'] - a['at']) for a, b in zip(curves, curves[1:])) / (end - start)
                record = {'model': model, 'regime': regime, 'variant': name, 'label': label,
                          'config': asdict(config), 'selected': metrics([r for r in decisions if r['accepted']]),
                          'rejected': metrics([r for r in decisions if not r['accepted']]),
                          'backtest_summary': summary, 'time_weighted_mean_committed_cash': mean_cash,
                          'peak_committed_cash_fraction_of_10k': summary['peak_committed_cash'] / config.capital_dollars,
                          'rejection_counts': dict(Counter(r['reason'] for r in decisions if not r['accepted']))}
                yield record, decisions, curves


def plot(records, out, date):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    plt.style.use('dark_background')
    plt.rcParams['text.parse_math'] = False
    colors = {'kalshi': '#73a0c4', 'polymarket': '#84c9be', 'pinnacle': '#e7b078',
              'blend': '#b497d6', 'stronger_pinnacle': '#e493af',
              'exchange_blend_equal': '#d2bd69', 'exchange_blend_pm75': '#c78aca'}
    labels = [label for _, label, _ in VARIANTS]
    x = list(range(len(VARIANTS)))
    formatter = FuncFormatter(lambda value, _: f'${value / 1e6:.2f}m' if abs(value) >= 1e6 else f'${value / 1000:.1f}k' if abs(value) >= 1000 else f'${value:.0f}')
    for regime in ('constrained', 'unconstrained'):
        fig, axes = plt.subplots(2, 2, figsize=(13, 9), sharex=True)
        axes = axes.ravel()
        models = sorted({r['model'] for r in records})
        for model in models:
            group = {r['variant']: r for r in records if r['regime'] == regime and r['model'] == model}
            rs = [group[name] for name, _, _ in VARIANTS]
            color = colors.get(model)
            axes[0].plot(x, [r['selected']['known_net_pnl'] for r in rs], marker='o', color=color, label=model)
            axes[0].fill_between(x, [r['selected']['loose_final_pnl_bounds'][0] for r in rs],
                                 [r['selected']['loose_final_pnl_bounds'][1] for r in rs], color=color, alpha=.12)
            axes[1].plot(x, [r['backtest_summary']['peak_committed_cash'] for r in rs], marker='o', color=color, label=model)
            axes[2].plot(x, [r['selected']['yes_premium'] for r in rs], marker='o', color=color, label=model)
            axes[3].plot(x, [r['selected']['net_point_edge'] for r in rs], marker='o', color=color, label=model)
        for ax, title in zip(axes, ('Known seller P&L after fees; shading = final outcome bounds',
                                   'Peak simultaneous committed cash', 'Selected YES premium at observed prints',
                                   'Selected net point-model edge after fees')):
            ax.set_title(title, fontsize=10)
            ax.set_xticks(x, labels, rotation=20)
            ax.grid(alpha=.2)
            ax.yaxis.set_major_formatter(formatter)
            ax.legend(fontsize=9)
            ax.axhline(0, color='#aaaaaa', linewidth=.5)
        if regime == 'constrained':
            axes[1].axhline(10000, color='#aaaaaa', linestyle=':', label='$10k initial funding reference')
            axes[1].legend(fontsize=9)
        title = '$10k; $100 underlying/combo; $250 fixture' if regime == 'constrained' else 'Unlimited funding and concentration'
        fig.suptitle(f'MLB {date} · fixed entry-policy sweep · {title}\nSame complete-day model intersection; 2–4 distinct-game pregame legs', fontsize=12)
        fig.text(.07, .027, 'Thresholds are cents per combo contract after fees, except the explicit per-leg variant. Sell all bypasses only the edge test.\n'
                 'Known settlement P&L is attributed to trade time; spendable cash releases at settlement. Full-print quantities; no RFQ acceptance model.\n'
                 'One complete day: daily Sharpe / variance N/A. Comparison is exploratory, with no automatic threshold or model selection.', fontsize=8)
        fig.tight_layout(rect=(0, .105, 1, .94))
        for ext in ('png', 'svg'):
            fig.savefig(out / (regime + '.' + ext), dpi=155)
        plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--date', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    raw = args.input.read_bytes()
    data = json.loads(raw)
    rows, start, end, counts = paired_day(data, args.date)
    args.out.mkdir(parents=True, exist_ok=True)
    # A stale successful manifest must not survive a failed rerun.
    manifest_path = args.out / 'manifest.json'
    if manifest_path.exists():
        manifest_path.unlink()
    summaries = []
    with gzip.open(args.out / 'decisions.jsonl.gz', 'wt') as decisions_file, gzip.open(args.out / 'curves.jsonl.gz', 'wt') as curves_file:
        for record, decisions, curves in sweep(rows, start, end):
            summaries.append(record)
            tag = {key: record[key] for key in ('model', 'regime', 'variant')}
            for decision in decisions:
                compact = {key: decision[key] for key in ('evaluation_id', 'at', 'accepted', 'reason', 'selected_net_edge', 'required_net_edge', 'entry_filter', 'minimum_net_edge_unit')}
                decisions_file.write(json.dumps({**tag, **compact}, separators=(',', ':'), allow_nan=False) + '\n')
            for row in curves:
                curves_file.write(json.dumps({**tag, **row}, separators=(',', ':'), allow_nan=False) + '\n')
    write(args.out / 'summary.json', summaries)
    plot(summaries, args.out, args.date)
    code_paths = [Path(__file__), ROOT / 'src/combos/backtest.py', ROOT / 'src/combos/risk.py', ROOT / 'src/combos/performance.py']
    write(manifest_path, {'schema_version': 1, 'complete_calendar_days': 1, 'date': args.date,
          'cohort_basis': 'common_available_model_intersection', 'source_run_id': data['run_id'],
          'input': str(args.input.resolve()), 'input_sha256': hashlib.sha256(raw).hexdigest(),
          'start_at': start, 'end_at': end, 'source_counts': counts,
          'common_prints_per_model': len(rows) // len(counts), 'models': sorted(counts),
          'variants': [{'name': name, 'label': label, 'overrides': overrides} for name, label, overrides in VARIANTS],
          'code_sha256': {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in code_paths},
          'daily_sharpe': None, 'daily_return_variance': None,
          'sample_completeness_basis': 'Full input window and upstream census attestation; no sampled cells accepted.',
          'parameter_selection': 'Fixed alternatives; no outcome-based optimizer; current September results are exploratory.',
          'sell_all_basis': 'Bypasses edge only; valid input, quote guards, premium configuration and funded risk remain binding.',
          'entry_price_basis': 'Observed public print price; thresholds select prints and do not reprice them or establish RFQ fills.',
          'orders_enabled': False})
    print(json.dumps({'out': str(args.out), 'common_prints_per_model': len(rows) // len(counts), 'model_policy_regimes': len(summaries)}))


if __name__ == '__main__':
    main()
