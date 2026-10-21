"""Funding persists through missing dates; plotted outcomes cannot fund fills."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import mlb_longitudinal_sweep as sweep
from combos.backtest import BacktestConfig, run_backtest


def plan():
    return {'study_id': 'synthetic-longitudinal', 'timezone': 'America/Chicago',
            'dates': {'2026-07-01': 'development', '2026-07-03': 'development'},
            'primary_models': ['kalshi', 'polymarket'], 'entry_basis': 'point',
            'baseline_limits': {'capital_dollars': 10000, 'per_contract_dollars': 100,
                                'per_combo_dollars': 100, 'per_fixture_dollars': 250},
            'evaluation': {'minimum_complete_resolved_slates_for_descriptive_sharpe': 20,
                           'purge_shared_fixtures_between_development_and_validation': True}}


def opportunity(date, identifier, model='kalshi', settlement=None, result=None):
    start, end = sweep.bounds(date, 'America/Chicago')
    return {'model': model, 'evaluation_id': identifier, 'at': start + 3600,
            'quantity': 120., 'yes_price': .3, 'maker_fee': .1, 'fair_point': .2,
            'stressed_upper': .25, 'quote_allowed': True, 'risk_multiplier': 1.,
            'yes_settlement': result, 'settled_at': settlement,
            'buckets': {'contract': ['shared-a', 'shared-b'], 'fixture': ['game-a', 'game-b'], 'combo': ['combo']},
            'source': {'sampling_method': 'census', 'source_window': [start, end], 'nlegs': 2,
                       'series': ['KXMLBGAME'], 'start_at': sweep.bounds('2026-07-04', 'America/Chicago')[0],
                       'fee_basis': {'rate': .035, 'verified': False, 'reference': 'synthetic historical scenario'}}}


def day(date, rows):
    start, end = sweep.bounds(date, 'America/Chicago')
    return {'cohort_description': 'Complete daily census', 'start_at': start, 'end_at': end,
            'identity': {'fee_scenario': {'historical_effective_date_verified': False}}, 'opportunities': rows}


def test_one_ledger_retains_exposure_across_unobserved_day(tmp_path, monkeypatch):
    p = plan(); settlement = sweep.bounds('2026-07-04', p['timezone'])[0] + 10000
    inputs = {date: day(date, [opportunity(date, date, model, settlement, 0.) for model in p['primary_models']])
              for date in p['dates']}
    rows, coverage = sweep.prepare(inputs, p)
    monkeypatch.setattr(sweep, 'VARIANTS', (('edge_0_3c', '0.3c', {'minimum_net_edge_per_share': .003}),))
    result, curves = sweep.evaluate(rows, coverage, p, tmp_path)
    funded = next(row for row in result['records'] if row['model'] == 'kalshi' and row['regime'] == 'funded')
    unlimited = next(row for row in result['records'] if row['model'] == 'kalshi' and row['regime'] == 'unlimited')
    assert funded['selected']['prints'] == 1 and unlimited['selected']['prints'] == 2
    assert funded['rejection_counts'] == {'contract_risk_limit': 1}
    # Independently resetting day three would accept its print; the new evaluator must not reset.
    left, right = sweep.bounds('2026-07-03', p['timezone'])
    isolated = run_backtest([opportunity('2026-07-03', 'isolated', settlement=settlement, result=0.)],
                            left, right, BacktestConfig(entry_basis='point'), True)
    assert isolated['summaries'][0]['fills'] == 1
    assert funded['portfolio']['realized_pnl'] == 0
    assert funded['portfolio']['trade_attributed_pnl'] == pytest.approx(35.9)
    assert funded['portfolio']['ending_committed_cash'] == pytest.approx(84.1)
    assert [row['date'] for row in funded['sampled_statistics']['daily_contributions']] == list(p['dates'])
    assert funded['sampled_statistics']['annualized_sharpe'] is None


def test_actual_settlement_in_gap_releases_capacity_before_next_observed_date(tmp_path, monkeypatch):
    p = plan(); settlement = sweep.bounds('2026-07-02', p['timezone'])[0] + 1000
    late = sweep.bounds('2026-07-04', p['timezone'])[0] + 1000
    inputs = {date: day(date, [opportunity(date, date, model, settlement if date.endswith('01') else late, 0.)
                             for model in p['primary_models']]) for date in p['dates']}
    rows, coverage = sweep.prepare(inputs, p)
    monkeypatch.setattr(sweep, 'VARIANTS', (('edge_0_3c', '0.3c', {'minimum_net_edge_per_share': .003}),))
    result, curves = sweep.evaluate(rows, coverage, p, tmp_path)
    funded = next(row for row in result['records'] if row['model'] == 'kalshi' and row['regime'] == 'funded')
    assert funded['selected']['prints'] == 2
    assert funded['portfolio']['realized_pnl'] == pytest.approx(35.9)
    assert any(row['at'] == settlement and row['committed_cash'] == pytest.approx(0)
               for row in curves['kalshi', 'edge_0_3c', 'funded'])


def test_missing_model_day_never_silently_becomes_kalshi_only():
    p = plan()
    inputs = {'2026-07-01': day('2026-07-01', [opportunity('2026-07-01', 'a')])}
    rows, coverage = sweep.prepare(inputs, p)
    assert not rows
    assert coverage['missing_dates'][0]['reason'] == 'required_primary_models_unavailable'
    assert coverage['missing_dates'][0]['missing_primary_models'] == ['polymarket']
    assert coverage['missing_dates'][1]['reason'] == 'awaiting_completed_day'


def test_cross_source_economic_identity_mismatch_fails():
    p = plan(); k = opportunity('2026-07-01', 'a'); pm = deepcopy(k); pm['model'] = 'polymarket'; pm['quantity'] += 1
    with pytest.raises(ValueError, match='inconsistent_paired_quantity'):
        sweep.prepare({'2026-07-01': day('2026-07-01', [k, pm])}, p)


def test_fold_purge_does_not_recapitalize_validation_day():
    p = plan(); p['dates']['2026-07-03'] = 'validation'
    inputs = {date: day(date, [opportunity(date, date, model) for model in p['primary_models']]) for date in p['dates']}
    rows, coverage = sweep.prepare(inputs, p)
    assert {row['evaluation_id'] for row in rows} == {'2026-07-01'}
    assert coverage['validation_shared_fixture_purged_prints'] == {'2026-07-03': 1}
    assert coverage['observed_dates'] == list(p['dates'])


def test_unknown_pnl_bounds_and_no_synthetic_gap_statistics():
    p = plan(); row = opportunity('2026-07-01', 'unknown')
    stats = sweep.sampled_statistics([row], list(p['dates']), p)
    assert len(stats['daily_contributions']) == 2
    assert stats['daily_contributions'][0]['unknown_outcomes'] == 1
    assert stats['daily_contributions'][0]['loose_final_pnl_bounds'] == pytest.approx([-84.1, 35.9])
    assert stats['fully_resolved_observed_dates'] == 1
    assert stats['observed_date_pnl_variance_dollars2'] is None
    assert stats['daily_return_variance'] is None


def test_discovery_requires_completed_stage_hash_not_file_presence(tmp_path):
    p = plan(); root = tmp_path / 'batch'; root.mkdir(); date = '2026-07-01'
    file = root / date / 'replay/opportunities.json'; file.parent.mkdir(parents=True)
    sweep.save(file, day(date, [opportunity(date, 'a')]))
    state = {'status': 'running', 'days': {date: {'status': 'running'}}, 'stages': {}}
    sweep.save(root / 'batch_status.json', state)
    assert sweep.discover([root], p)[0] == {}
    state['days'][date]['status'] = 'complete'
    state['stages'][date + '/replay'] = {'status': 'complete', 'output_sha256': {str(file.resolve()): sweep.digest(file)}}
    sweep.save(root / 'batch_status.json', state)
    assert sweep.discover([root], p)[0] == {date: file}
    sweep.save(file, {'changed': True})
    with pytest.raises(ValueError, match='hash_certificate'):
        sweep.discover([root], p)


def test_curve_compaction_preserves_cash_peak_and_endpoints():
    rows = [{'at': index, 'trade_attributed_pnl': index, 'accepted_point_edge': index / 10,
             'committed_cash': 10000 if index == 499 else 1} for index in range(1000)]
    compact = sweep.compact_curve(rows, 80)
    assert compact[0]['at'] == 0 and compact[-1]['at'] == 999
    assert max(row['committed_cash'] for row in compact) == 10000
    assert all(a['at'] < b['at'] for a, b in zip(compact, compact[1:]))
