"""Research sweep must preserve live ledger semantics and causal funding."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))
from combos.backtest import BacktestConfig, run_backtest
from mlb_risk_capacity import common_cohort, exposure_audit, outcome_metrics, pregame_fixture_context, SCENARIOS


def row(identifier, at=100., quantity=100., settlement=0., settled_at=300.):
    return {'model': 'kalshi', 'evaluation_id': identifier, 'at': at, 'quantity': quantity,
            'yes_price': .3, 'maker_fee': 0., 'fair_point': .2, 'stressed_upper': .25,
            'quote_allowed': True, 'risk_multiplier': 1., 'yes_settlement': settlement,
            'settled_at': settled_at if settlement is not None else None,
            'buckets': {'contract': ['a', 'b'], 'combo': [identifier], 'fixture': ['x', 'y']},
            'source': {'sampling_method': 'census'}}


def test_cash_charged_once_but_fixture_incidence_charged_twice_and_all_limits_counted():
    config = BacktestConfig(entry_basis='point', capital_dollars=100, per_contract_dollars=100,
                            per_combo_dollars=100, per_fixture_dollars=100)
    result = run_backtest([row('a'), row('b', at=110.)], 90, 200, config, True)
    audit = exposure_audit(result['decisions'], config)
    assert audit['at_peak_cash']['committed_cash'] == 70
    assert audit['at_peak_cash']['gross_fixture_incidence_sum'] == 140
    assert sum(r['equal_allocation_cash'] for r in audit['at_peak_cash']['fixture_exposures']) == 70
    assert audit['all_binding_limits_nonexclusive'] == {'capital': 1, 'contract': 1, 'fixture': 1}
    assert result['decisions'][1]['reason'] == 'capital_exhausted'


def test_eventual_profit_does_not_fund_later_print_before_settlement():
    config = BacktestConfig(entry_basis='point', capital_dollars=100,
                            per_contract_dollars=1000, per_combo_dollars=1000, per_fixture_dollars=1000)
    result = run_backtest([row('a'), row('before', at=200.), row('after', at=301., settled_at=500.)],
                          90, 400, config, True)
    assert [r['accepted'] for r in result['decisions']] == [True, False, True]
    audit = exposure_audit(result['decisions'], config)
    assert audit['independent_integer_ledger_reconciled']
    assert audit['at_peak_cash']['committed_cash'] == 70
    assert audit['all_binding_limits_nonexclusive'] == {'capital': 1}


def test_unknown_settlement_keeps_cash_locked_and_explicit_final_bounds():
    config = BacktestConfig(entry_basis='point', capital_dollars=100,
                            per_contract_dollars=1000, per_combo_dollars=1000, per_fixture_dollars=1000)
    unknown = row('unknown', settlement=None)
    result = run_backtest([unknown, row('later', at=400., settled_at=500.)], 90, 450, config, True)
    assert [r['accepted'] for r in result['decisions']] == [True, False]
    assert exposure_audit(result['decisions'], config)['all_binding_limits_nonexclusive'] == {'capital': 1}
    metrics = outcome_metrics([unknown])
    assert metrics['known_outcome_pnl'] == 0
    assert metrics['loose_final_pnl_bounds'] == [-70, 30]


def test_common_intersection_is_applied_before_funding():
    a = row('only-kalshi'); b = row('common'); c = dict(b, model='polymarket')
    sampled = dict(row('sample'), source={'sampling_method': 'sample'})
    result = common_cohort({'opportunities': [a, b, c, sampled]}, 90, 200)
    assert {(r['model'], r['evaluation_id']) for r in result} == {('kalshi', 'common'), ('polymarket', 'common')}


def test_full_print_size_and_risk_multiplier_have_exact_ledger_behavior():
    config = BacktestConfig(entry_basis='point')
    large = row('large', quantity=200)
    reduced = row('reduced', at=101.); reduced['risk_multiplier'] = .5
    result = run_backtest([large, reduced], 90, 200, config, True)
    assert not any(r['accepted'] for r in result['decisions'])
    audit = exposure_audit(result['decisions'], config)
    assert audit['standalone_print_exceeds_limit_nonexclusive'] == {'contract': 2, 'combo': 2}
    assert audit['at_peak_cash']['committed_cash'] == 0
    assert SCENARIOS[0] == ('baseline', 100, 100, 250)


def test_reconciliation_detects_changed_or_noncausal_acceptance():
    config = BacktestConfig(entry_basis='point')
    result = run_backtest([row('large', quantity=200)], 90, 200, config, True)
    result['decisions'][0]['accepted'] = True
    with pytest.raises(AssertionError, match='independent_risk_reconciliation_failed'):
        exposure_audit(result['decisions'], config)


def test_fixture_context_excludes_not_yet_seen_and_started_priceable_fixtures():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    at = datetime(2026, 9, 5, 14, 0, tzinfo=ZoneInfo('America/New_York')).timestamp()
    rows = [{'at': at - 100, 'buckets': {'fixture': ['mlb:26SEP051305NYYBAL', 'mlb:26SEP051840SDCIN']}},
            {'at': at + 100, 'buckets': {'fixture': ['mlb:26SEP052110WSHLAD']}}]
    result = pregame_fixture_context(rows, at)
    assert result['seen_priceable_fixture_count'] == 2
    assert result['seen_still_pregame_fixtures'] == ['mlb:26SEP051840SDCIN']
