import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from combos.backtest import BacktestConfig, run_backtest, daily_statistics


def opportunity(identifier='a', at=10, settled=30, **overrides):
    return {'model': 'm', 'evaluation_id': identifier, 'at': at, 'quantity': 100., 'yes_price': .2,
            'maker_fee': 1., 'fair_point': .1, 'stressed_upper': .15, 'quote_allowed': True,
            'risk_multiplier': 1., 'settled_at': settled, 'yes_settlement': 0. if settled is not None else None,
            'buckets': {'contract': ['lions-bengals:canonical'], 'fixture': ['game'], 'combo': [identifier]},
            **overrides}


def test_settlement_recycles_cash_and_canonical_underlying_exposure():
    # Different ticker/side representations must arrive with the same canonical risk key.
    rows = [opportunity(), opportunity('before', 20, 35), opportunity('after', 31, 40)]
    result = run_backtest(rows, 0, 50, BacktestConfig(capital_dollars=100))
    assert [d['accepted'] for d in result['decisions']] == [True, False, True]
    assert result['decisions'][1]['reason'] == 'capital_exhausted'
    assert result['summaries'][0]['realized_pnl'] == 38
    assert result['summaries'][0]['ending_equity'] == 138
    assert result['summaries'][0]['peak_committed_cash'] == 81
    result = run_backtest(rows, 0, 50)
    assert result['decisions'][1]['reason'] == 'contract_risk_limit'


def test_constraints_removed_without_changing_entry_or_quote_guard():
    rows = [opportunity(), opportunity('b', 20), opportunity('noedge', fair_point=.3, stressed_upper=.4),
            opportunity('guard', quote_allowed=False)]
    limited = run_backtest(rows, 0, 50)
    unlimited = run_backtest(rows, 0, 50, constrained=False)
    assert len(limited['fills']) == 1 and len(unlimited['fills']) == 2
    assert sorted(d['reason'] for d in unlimited['decisions']) == ['accepted', 'accepted', 'insufficient_edge', 'quote_guard']
    assert unlimited['summaries'][0]['realized_pnl'] == 38


def test_defensive_multiplier_and_no_ticket_clipping():
    rows = [opportunity(risk_multiplier=.5)]
    result = run_backtest(rows, 0, 50)
    assert not result['fills'] and result['decisions'][0]['reason'] == 'contract_risk_limit'
    assert run_backtest(rows, 0, 50, constrained=False)['fills'][0]['quantity'] == 100


def test_yes_premium_limit_filters_whole_print_in_both_portfolio_regimes():
    rows = [opportunity('over', at=10, quantity=100.01, yes_price=.5),
            opportunity('boundary', at=11, quantity=100, yes_price=.5),
            opportunity('cheap_yes_large_liability', at=12, quantity=1000, yes_price=.01,
                        fair_point=.001, stressed_upper=.002, maker_fee=.1)]
    config = BacktestConfig(maximum_yes_premium_dollars=50)
    limited = run_backtest(rows, 0, 50, config)
    unlimited = run_backtest(rows, 0, 50, config, constrained=False)
    for result in (limited, unlimited):
        assert result['decisions'][0]['reason'] == 'yes_premium_limit'
        assert result['decisions'][1]['accepted']
        assert result['fills'][0]['quantity'] == 100
    assert limited['decisions'][2]['reason'] == 'contract_risk_limit'
    assert unlimited['decisions'][2]['accepted']
    assert unlimited['fills'][1]['quantity'] == 1000
    with pytest.raises(ValueError, match='premium'):
        BacktestConfig(maximum_yes_premium_dollars=0)


def test_future_or_unknown_settlement_never_releases_cash_or_books_pnl():
    for settled in (None, 100):
        result = run_backtest([opportunity(settled=settled), opportunity('b', 40, 100)], 0, 50)
        assert len(result['fills']) == 1
        assert result['summaries'][0]['realized_pnl'] == 0
        assert result['summaries'][0]['ending_committed_cash'] == 81


def test_settlement_delay_is_cash_availability_delay():
    rows = [opportunity(), opportunity('b', 31, 50)]
    result = run_backtest(rows, 0, 60, BacktestConfig(settlement_delay_seconds=5))
    assert len(result['fills']) == 1 and result['fills'][0]['settled_at'] == 35
    assert result['summaries'][0]['realized_pnl'] == 19


def test_no_side_fee_loss_and_unlimited_funding_are_explicit():
    rows = [opportunity(yes_settlement=1.), opportunity('b', 20, 40, yes_settlement=.5)]
    result = run_backtest(rows, 0, 50, BacktestConfig(capital_dollars=100), constrained=False)
    s = result['summaries'][0]
    assert s['realized_pnl'] == -112
    assert s['minimum_starting_funding_for_path'] == 162
    assert s['additional_funding_above_reporting_base'] == 62


def test_point_diagnostic_separates_reservation_price_from_fair_quality():
    row = opportunity(stressed_upper=.3)
    assert not run_backtest([row], 0, 50)['fills']
    assert len(run_backtest([row], 0, 50, BacktestConfig(entry_basis='point'))['fills']) == 1


def test_daily_variance_includes_idle_days_and_sharpe_undefined_for_no_trades():
    config = BacktestConfig(timezone='UTC', capital_dollars=100)
    start = datetime(2026, 7, 1, tzinfo=timezone.utc).timestamp()
    fills = [{'settled_at': start+3600, 'quantity': 100, 'yes_price': .2, 'yes_settlement': 0, 'maker_fee': 0}]
    rows, stats = daily_statistics(fills, start, start+3*86400, config)
    assert [r['pnl_dollars'] for r in rows] == [20, 0, 0]
    assert stats['daily_return_variance'] == pytest.approx(.0133333333333)
    assert stats['annualized_sharpe'] == pytest.approx((365/3)**.5)
    _, empty = daily_statistics([], start, start+3*86400, config)
    assert empty['annualized_sharpe'] is None and empty['daily_return_variance'] == 0
    rows, _ = daily_statistics(fills, start+1, start+3*86400-1, config)
    assert len(rows) == 1  # partial boundary days excluded


def test_input_rejects_duplicates_future_settlement_mismatch_and_weighted_paths():
    with pytest.raises(ValueError, match='duplicate'):
        run_backtest([opportunity(), opportunity()], 0, 50)
    with pytest.raises(ValueError, match='precedes'):
        run_backtest([opportunity(settled=5)], 0, 50)
    with pytest.raises(ValueError, match='equals'):
        run_backtest([opportunity(settled=10)], 0, 50)
    with pytest.raises(ValueError, match='canonical risk buckets'):
        run_backtest([opportunity(buckets={'contract': 'bad', 'fixture': ['game'], 'combo': ['a']})], 0, 50)
    with pytest.raises(ValueError, match='paired'):
        run_backtest([opportunity(settled=None, yes_settlement=1)], 0, 50)
    with pytest.raises(ValueError, match='unweighted'):
        run_backtest([opportunity(sampling_weight=60)], 0, 50)


def test_eventual_pnl_and_edge_are_attributed_at_trade_without_funding_later_trades():
    rows = [opportunity(settled=100), opportunity('b', at=20, settled=110)]
    result = run_backtest(rows, 0, 50, BacktestConfig(capital_dollars=100))
    assert len(result['fills']) == 1
    at_trade = next(r for r in result['curves'] if r['at'] == 10)
    assert at_trade['trade_attributed_pnl'] == 19
    assert at_trade['trade_attributed_equity'] == 119
    assert at_trade['accepted_point_edge'] == pytest.approx(9)
    assert at_trade['accepted_stressed_edge'] == pytest.approx(4)
    assert at_trade['realized_pnl'] == 0 and at_trade['available_cash'] == 19
    assert result['decisions'][1]['reason'] == 'capital_exhausted'
    assert result['summaries'][0]['realized_pnl'] == 0
    assert result['summaries'][0]['trade_attributed_pnl'] == 19


def test_unresolved_outcomes_do_not_fabricate_pnl_but_still_book_expected_edge():
    for config, settled in ((BacktestConfig(), None), (BacktestConfig(outcome_as_of=50), 100)):
        result = run_backtest([opportunity(settled=settled)], 0, 50, config)
        summary = result['summaries'][0]
        assert summary['trade_attributed_pnl'] == 0 and summary['unresolved_outcomes'] == 1
        assert result['curves'][-1]['accepted_point_edge'] == pytest.approx(9)
        assert result['fills'][0]['eventual_net_pnl'] is None


def test_trade_daily_pnl_uses_entry_day_including_midnight_not_settlement_day():
    config = BacktestConfig(timezone='UTC', capital_dollars=100)
    start = datetime(2026, 7, 1, tzinfo=timezone.utc).timestamp()
    fill = {'filled_at': start, 'settled_at': start+4*86400, 'quantity': 100,
            'yes_price': .2, 'yes_settlement': 0, 'maker_fee': 0}
    rows, stats = daily_statistics([fill], start, start+3*86400, config, attribution='trade')
    assert [r['pnl_dollars'] for r in rows] == [20, 0, 0]
    assert stats['active_pnl_days'] == 1 and stats['pnl_attribution'] == 'trade'
    assert stats['annualized_sharpe'] == pytest.approx((365/3)**.5)
    settlement, _ = daily_statistics([fill], start, start+3*86400, config)
    assert all(r['pnl_dollars'] == 0 for r in settlement)
