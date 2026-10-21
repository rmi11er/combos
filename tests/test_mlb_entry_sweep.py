from copy import deepcopy
from datetime import datetime, timedelta
import importlib.util
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from combos.backtest import BacktestConfig, run_backtest
from test_backtest import opportunity

spec = importlib.util.spec_from_file_location('mlb_entry_sweep', ROOT / 'scripts/mlb_entry_sweep.py')
study = importlib.util.module_from_spec(spec)
spec.loader.exec_module(study)


def day_data():
    start = datetime(2026, 9, 5, tzinfo=ZoneInfo('America/Chicago')).timestamp()
    end = start + 86400
    rows = []
    for model in ('kalshi', 'polymarket'):
        for index, fair in enumerate((.19, .198, .25)):
            row = opportunity(str(index), at=start + 10 + index, settled=end + 100, model=model,
                              fair_point=fair, stressed_upper=max(fair, .3), maker_fee=.1,
                              source={'nlegs': 2, 'sampling_method': 'census', 'start_at': end + 1000,
                                      'series': ['KXMLBGAME']})
            row['buckets']['fixture'] = ['game-a', 'game-b']
            rows.append(row)
    return {'start_at': start, 'end_at': end, 'opportunities': rows, 'run_id': 'synthetic'}


def test_sell_all_keeps_fair_edge_fees_quote_guard_and_canonical_risk():
    rows = [opportunity('negative', fair_point=.4, stressed_upper=.5),
            opportunity('blocked', at=11, quote_allowed=False), opportunity('capacity', at=12)]
    config = BacktestConfig(entry_basis='point', entry_filter='all_priced')
    unlimited = run_backtest(rows, 0, 50, config, constrained=False)
    assert [d['reason'] for d in unlimited['decisions']] == ['accepted', 'quote_guard', 'accepted']
    first = unlimited['decisions'][0]
    assert first['fair_point'] == .4
    assert first['selected_net_edge'] == -21
    assert first['required_net_edge'] is None
    assert unlimited['fills'][0]['point_edge'] == -21
    assert unlimited['fills'][0]['maker_fee'] == 1
    constrained = run_backtest(rows, 0, 50, config)
    assert constrained['decisions'][2]['reason'] == 'contract_risk_limit'
    premium_capped = run_backtest(rows, 0, 50, BacktestConfig(entry_filter='all_priced', maximum_yes_premium_dollars=10))
    assert all(d['reason'] == 'yes_premium_limit' for d in premium_capped['decisions'])


def test_per_leg_threshold_changes_requirement_without_changing_fair_or_edge():
    row = opportunity(fair_point=.19, stressed_upper=.19, maker_fee=.1, source={'nlegs': 4})
    combo = run_backtest([row], 0, 50, BacktestConfig(entry_basis='point'), constrained=False)
    leg = run_backtest([row], 0, 50, BacktestConfig(entry_basis='point', minimum_net_edge_unit='leg_contract'), constrained=False)
    a, b = combo['decisions'][0], leg['decisions'][0]
    assert a['accepted'] is True and b['accepted'] is False
    assert a['required_net_edge'] == pytest.approx(.3)
    assert b['required_net_edge'] == pytest.approx(1.2)
    assert a['selected_net_edge'] == b['selected_net_edge'] == pytest.approx(.9)
    assert a['fair_point'] == b['fair_point'] == .19
    row.pop('source')
    with pytest.raises(ValueError, match='leg_count_required'):
        run_backtest([row], 0, 50, BacktestConfig(minimum_net_edge_unit='leg_contract'))


def test_unresolved_bounds_fee_and_positive_negative_edge_are_separate():
    rows = [opportunity('won', yes_settlement=0, fair_point=.1),
            opportunity('unknown', settled=None, fair_point=.4, stressed_upper=.5)]
    value = study.metrics(rows)
    assert value['known_net_pnl'] == 19
    assert value['loose_final_pnl_bounds'] == [-62, 38]
    assert value['fees'] == 2
    assert value['positive_net_point_edge'] == 9
    assert value['negative_net_point_edge'] == -21
    assert value['net_point_edge'] == -12
    assert value['pnl_per_known_cumulative_no_cash'] == pytest.approx(19 / 81)


def test_paired_cohort_uses_same_prints_and_rejects_partial_sample_or_mismatch():
    data = day_data()
    data['opportunities'].pop()
    rows, _, _, counts = study.paired_day(data, '2026-09-05')
    assert len(rows) == 4 and counts == {'kalshi': 3, 'polymarket': 2}
    bad = deepcopy(data)
    bad['opportunities'][0]['source']['sampling_method'] = 'sampled_cell'
    with pytest.raises(ValueError, match='non_census'):
        study.paired_day(bad, '2026-09-05')
    bad = deepcopy(data)
    bad['end_at'] -= 1
    with pytest.raises(ValueError, match='complete_calendar_day'):
        study.paired_day(bad, '2026-09-05')
    bad = deepcopy(data)
    bad['opportunities'][-1]['yes_price'] = .3
    with pytest.raises(ValueError, match='inconsistent_paired_yes_price'):
        study.paired_day(bad, '2026-09-05')


def test_fixed_sweep_reruns_portfolios_and_selected_rejected_partition_universe():
    rows, start, end, _ = study.paired_day(day_data(), '2026-09-05')
    results = list(study.sweep(rows, start, end))
    assert len(results) == 24
    for record, decisions, curves in results:
        assert record['selected']['prints'] + record['rejected']['prints'] == 3
        assert record['selected']['known_net_pnl'] + record['rejected']['known_net_pnl'] == pytest.approx(59.7)
        assert record['backtest_summary']['annualized_sharpe'] is None
        assert record['backtest_summary']['daily_return_variance'] is None
        assert sum(d['accepted'] for d in decisions) == record['selected']['prints']
    sell_all = [r for r, _, _ in results if r['variant'] == 'sell_every_priced_print']
    assert {r['selected']['prints'] for r in sell_all if r['regime'] == 'unconstrained'} == {3}
    assert {r['selected']['prints'] for r in sell_all if r['regime'] == 'constrained'} == {1}


@pytest.mark.parametrize('kwargs', [{'entry_filter': 'invented'}, {'minimum_net_edge_unit': 'percent'}])
def test_backtest_rejects_unknown_entry_modes(kwargs):
    with pytest.raises(ValueError, match='unsupported'):
        BacktestConfig(**kwargs)
