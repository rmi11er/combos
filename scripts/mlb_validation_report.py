#!/usr/bin/env python3
"""Frozen-date MLB comparisons without inventing returns in unobserved gaps.

Each observed complete day starts a separate $10k portfolio. This is deliberately
not a continuous July–September equity curve or an annualized Sharpe estimate.
"""
import argparse
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timedelta
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from combos.backtest import BacktestConfig, run_backtest
from mlb_model_report import metrics, cuts, gziprows


def bounds(date, timezone):
    start = datetime.fromisoformat(date).replace(tzinfo=ZoneInfo(timezone))
    return start.timestamp(), (start+timedelta(days=1)).timestamp()


def dated_rows(inputs, plan):
    """Keep census rows and fail on conflicting repeated evaluations."""
    by_date = defaultdict(dict)
    coverage = defaultdict(lambda: defaultdict(int))
    for data in inputs:
        for row in data['opportunities']:
            date = datetime.fromtimestamp(row['at'], ZoneInfo(plan['timezone'])).date().isoformat()
            if date not in plan['dates'] or row['source']['sampling_method'] != 'census':
                continue
            key = (row['model'], row['evaluation_id'])
            if key in by_date[date]:
                if by_date[date][key] != row:
                    raise ValueError('conflicting_duplicate_evaluation')
                continue
            by_date[date][key] = row
            coverage[date][row['model']] += 1
    return {date: list(rows.values()) for date, rows in by_date.items()}, dict(coverage)


def purge_validation(rows_by_date, plan):
    development = {fixture for date, rows in rows_by_date.items() if plan['dates'][date] == 'development'
                   for row in rows for fixture in row['buckets']['fixture']}
    purged = {}
    for date, rows in rows_by_date.items():
        if plan['dates'][date] == 'validation':
            retained = [r for r in rows if not development.intersection(r['buckets']['fixture'])]
            purged[date] = len({r['evaluation_id'] for r in rows})-len({r['evaluation_id'] for r in retained})
            rows_by_date[date] = retained
    return purged


def common_rows(rows, models):
    ids = [{r['evaluation_id'] for r in rows if r['model'] == model} for model in models]
    common = set.intersection(*ids) if ids else set()
    result = [r for r in rows if r['model'] in models and r['evaluation_id'] in common]
    identities = {}
    for row in result:
        # Every source must price the same observed economics and eventual payoff.
        identity = {key: row.get(key) for key in ('at', 'quantity', 'yes_price', 'maker_fee',
                                                'yes_settlement', 'settled_at', 'buckets', 'source')}
        previous = identities.setdefault(row['evaluation_id'], identity)
        if previous != identity:
            raise ValueError('paired_sources_have_different_trade_economics_or_provenance')
    return result


def scores(rows):
    known = [r for r in rows if r['yes_settlement'] is not None]
    q = sum(r['quantity'] for r in known)
    cash = sum(r['quantity']*(1-r['yes_price'])+r['maker_fee'] for r in known)
    pnl = sum(r['quantity']*(r['yes_price']-r['yes_settlement'])-r['maker_fee'] for r in known)
    def logloss(r):
        p = min(1-1e-12, max(1e-12, r['fair_point'])); y = r['yes_settlement']
        return -y*math.log(p)-(1-y)*math.log(1-p)
    return {**metrics(rows),
            'brier_equal_print': statistics.mean((r['fair_point']-r['yes_settlement'])**2 for r in known) if known else None,
            'brier_quantity_weighted': sum(r['quantity']*(r['fair_point']-r['yes_settlement'])**2 for r in known)/q if q else None,
            'log_loss_equal_print': statistics.mean(logloss(r) for r in known) if known else None,
            'log_loss_quantity_weighted': sum(r['quantity']*logloss(r) for r in known)/q if q else None,
            'known_cumulative_no_cash': cash,
            'pnl_per_known_cumulative_no_cash': pnl/cash if cash else None}


def return_stats(daily, minimum_slates, capital=10000., regime='constrained', planned_slates=None):
    resolved = [r for r in daily if r['unknown_outcomes'] == 0]
    profits = [r['known_net_pnl'] for r in resolved]
    values = [value/capital for value in profits]
    var = statistics.variance(values) if len(values) >= 2 else None
    planned_complete = planned_slates is None or len(daily) == planned_slates
    ratio = statistics.mean(values)/math.sqrt(var) if len(values) >= minimum_slates and var and len(resolved) == len(daily) and planned_complete else None
    return {'sampled_slates': len(daily), 'fully_resolved_slates': len(resolved),
            'planned_slates': planned_slates, 'all_planned_slates_observed': planned_complete,
            'sampled_slate_pnl_variance': statistics.variance(profits) if len(profits) >= 2 else None,
            'sampled_slate_return_variance': var if regime == 'constrained' else None,
            'unannualized_sampled_slate_sharpe': ratio if regime == 'constrained' else None,
            'unannualized_sampled_slate_pnl_ratio': ratio,
            'return_basis': 'net_pnl_divided_by_reset_funded_capital' if regime == 'constrained' else 'no_funded_return_defined_for_unlimited_capacity',
            'variance_basis': 'fully_resolved_observed_slates_only; unobserved gaps omitted',
            'sharpe_reason': 'descriptive_only' if ratio is not None else 'insufficient_complete_resolved_slates_or_zero_variance',
            'annualized_sharpe': None}


def evaluate(inputs, plan, output):
    by_date, coverage = dated_rows(inputs, plan)
    purged = purge_validation(by_date, plan) if plan['evaluation'].get('purge_shared_fixtures_between_development_and_validation', True) else {}
    config = BacktestConfig(entry_basis=plan['entry_basis'], minimum_net_edge_per_share=plan['minimum_net_edge_per_share'],
                            **plan['baseline_limits'])
    reports = []; missing = []; all_daily = defaultdict(list)
    for date, fold in plan['dates'].items():
        raw = by_date.get(date, [])
        available = sorted({r['model'] for r in raw})
        if not raw:
            missing.append({'date': date, 'fold': fold, 'reason': 'no_complete_day_priced_input'})
            continue
        missing_models = sorted(set(plan['primary_models'])-set(available))
        diagnostic = bool(missing_models) and fold == 'previously_inspected_reference'
        if missing_models and not diagnostic:
            missing.append({'date': date, 'fold': fold, 'reason': 'required_primary_models_unavailable',
                            'available_models': available, 'missing_primary_models': missing_models})
            continue
        models = [m for m in plan['primary_models'] if m in available]
        rows = common_rows(raw, models)
        if not rows:
            missing.append({'date': date, 'fold': fold, 'reason': 'empty_common_source_intersection'})
            continue
        start, end = bounds(date, plan['timezone'])
        entry = {'date': date, 'fold': fold, 'models': models,
                 'missing_primary_models': missing_models, 'diagnostic_only': diagnostic,
                 'comparison_basis': 'available_model_reference_diagnostic' if diagnostic else 'all_required_primary_models_paired',
                 'common_prints': len({r['evaluation_id'] for r in rows}), 'results': [], 'strata': [],
                 'fee_basis': [json.loads(value) for value in sorted({json.dumps(r['source']['fee_basis'], sort_keys=True) for r in rows})]}
        day_out = output/date; day_out.mkdir(parents=True, exist_ok=True)
        for regime in ('all_priced', 'unconstrained', 'constrained'):
            summaries = {}
            if regime == 'all_priced':
                selected = rows
            else:
                result = run_backtest(rows, start, end, config, regime == 'constrained')
                gziprows(day_out/(regime+'_decisions.jsonl.gz'), result['decisions'])
                gziprows(day_out/(regime+'_curves.jsonl.gz'), result['curves'])
                gziprows(day_out/(regime+'_fills.jsonl.gz'), result['fills'])
                summaries = {s['model']: s for s in result['summaries']}
                selected = [d for d in result['decisions'] if d['accepted']]
            for model in models:
                subset = [r for r in selected if r['model'] == model]
                m = {'date': date, 'model': model, 'regime': regime, **scores(subset)}
                if model in summaries:
                    m['portfolio'] = summaries[model]
                entry['results'].append(m)
                all_daily[fold, model, regime].append(m)
                strata = defaultdict(list)
                for row in subset:
                    for dimension, value in cuts(row).items():
                        strata[dimension, value].append(row)
                entry['strata'].extend({'model': model, 'regime': regime, 'dimension': d, 'value': v, **scores(rs)}
                                       for (d, v), rs in sorted(strata.items()))
        reports.append(entry)
    return {'study_id': plan['study_id'], 'config': asdict(config), 'daily': reports, 'missing_dates': missing,
            'coverage_before_common_and_purge': coverage, 'validation_purged_shared_fixture_prints': purged,
            'fold_metrics': [{'fold': fold, 'model': model, 'regime': regime,
                              **return_stats(rs, plan['evaluation']['minimum_complete_resolved_slates_for_descriptive_sharpe'],
                                             config.capital_dollars, regime,
                                             sum(value == fold for value in plan['dates'].values()))}
                             for (fold, model, regime), rs in sorted(all_daily.items())],
            'validation_status': 'incomplete_planned_dates_or_models' if missing else 'planned_priced_inputs_present_not_a_promotion_decision',
            'development_fixture_purge_status': 'provisional_until_all_development_dates_present' if any(m['fold'] == 'development' for m in missing) else 'all_priced_development_dates_present',
            'interpretation': ['Each constrained date independently resets its funded capital; no zero returns inserted in date gaps.',
                               'Separate accounting portfolios do not make shared-game outcomes statistically independent.',
                               'All/unlimited use observed print sizes and can exceed $10k capacity.',
                               'Known eventual outcomes attributed to trade time; unknown outcomes bounded.',
                               'Sampled-slate variance is descriptive; not calendar daily variance or proof of stability.',
                               'Historical fee basis is retained; unverified assumptions require sensitivity analysis.',
                               'Missing planned dates/models remain visible; no claim of completed validation.']}


def plot(result, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    days = result['daily']
    if not days:
        return
    models = sorted({m for day in days for m in day['models']})
    fig, axes = plt.subplots(3, 1, figsize=(13, 11), sharex=True)
    width = .8/max(1, len(models))
    for ax, regime in zip(axes, ('all_priced', 'unconstrained', 'constrained')):
        for index, model in enumerate(models):
            values = [next((r['known_net_pnl'] for r in day['results'] if r['model'] == model and r['regime'] == regime), float('nan')) for day in days]
            ax.bar([i-.4+width*(index+.5) for i in range(len(days))], values, width, label=model)
        ax.axhline(0, color='gray', linewidth=.7); ax.grid(axis='y', alpha=.2)
        ax.set_ylabel('Known net P&L ($)'); ax.set_title(regime.replace('_', ' ')); ax.legend(fontsize=8)
    axes[-1].set_xticks(range(len(days)), [day['date']+'\n'+day['fold'].replace('_', ' ') for day in days])
    fig.suptitle('MLB frozen-date validation · independent sampled-day experiments\nSharpe: unavailable until sufficient fully resolved slates; variance and coverage in JSON')
    fig.text(.08, .02, 'Public-print execution scenarios, including fees. Unknown outcomes excluded from bars and bounded in JSON.\n'
             'Every date resets its own $10k portfolio. Date gaps are unobserved. Missing planned dates: '+str(len(result['missing_dates'])), fontsize=9)
    fig.tight_layout(rect=(0, .065, 1, .94))
    for extension in ('png', 'svg'):
        fig.savefig(output/('sampled_days.'+extension), dpi=150)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, nargs='+', required=True)
    parser.add_argument('--plan', type=Path, default=ROOT/'config/mlb_validation_20260907.json')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(); args.out.mkdir(parents=True, exist_ok=True)
    plan = json.loads(args.plan.read_text())
    result = evaluate([json.loads(p.read_text()) for p in args.input], plan, args.out)
    result['input_sha256'] = {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in args.input+[args.plan]}
    result['code_sha256'] = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in
                             (Path(__file__), ROOT/'src/combos/backtest.py', ROOT/'src/combos/risk.py', ROOT/'scripts/mlb_model_report.py')}
    (args.out/'validation.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    plot(result, args.out)
    print(json.dumps({'complete_priced_dates': [r['date'] for r in result['daily']], 'missing_dates': result['missing_dates']}))


if __name__ == '__main__':
    main()
