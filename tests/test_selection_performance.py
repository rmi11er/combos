from combos.backtest import BacktestConfig, run_backtest
from combos.selection_performance import selection_performance


def test_selection_benchmark_reconciles_and_keeps_unknown_outcomes_separate():
    base = {'model': 'm', 'at': 10, 'quantity': 100, 'yes_price': .2, 'maker_fee': 1,
            'fair_point': .1, 'stressed_upper': .15, 'quote_allowed': True, 'risk_multiplier': 1,
            'settled_at': 80, 'yes_settlement': 0,
            'buckets': {'contract': ['a'], 'fixture': ['a'], 'combo': ['a']}}
    rows = [{**base, 'evaluation_id': 'winner'},
            {**base, 'evaluation_id': 'loser', 'fair_point': .3, 'stressed_upper': .4, 'yes_settlement': 1},
            {**base, 'evaluation_id': 'unknown', 'settled_at': None, 'yes_settlement': None},
            {**base, 'evaluation_id': 'too_large', 'quantity': 1000}]
    config = BacktestConfig(maximum_yes_premium_dollars=50)
    bt = run_backtest(rows, 0, 50, config, constrained=False)
    result = selection_performance(rows, bt['decisions'], 0, 50, config)
    s = {r['group']: r for r in result['summaries']}
    assert s['all_priced']['prints'] == 3
    assert s['all_priced']['pnl'] == s['selected']['pnl'] + s['rejected']['pnl'] == -62
    assert s['selected']['pnl'] == bt['summaries'][0]['trade_attributed_pnl'] == 19
    assert s['selected']['unresolved'] == 1
    assert s['rejected']['unresolved'] == 0
