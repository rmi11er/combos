from copy import deepcopy
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from mlb_validation_report import dated_rows, purge_validation, common_rows, scores, return_stats, evaluate


def row(model='kalshi', identifier='a', at=1782928800):
    return {'model': model, 'evaluation_id': identifier, 'at': at, 'quantity': 10,
            'yes_price': .3, 'maker_fee': .1, 'yes_settlement': 0, 'fair_point': .2,
            'source': {'sampling_method': 'census'}, 'buckets': {'fixture': ['shared']}}


def test_census_only_and_duplicate_integrity():
    plan = {'timezone': 'America/Chicago', 'dates': {'2026-07-01': 'development'}}
    a = row(); sampled = deepcopy(a); sampled['source']['sampling_method'] = 'complete_sampled_cell'
    data, coverage = dated_rows([{'opportunities': [a, a, sampled]}], plan)
    assert len(data['2026-07-01']) == 1
    assert coverage['2026-07-01']['kalshi'] == 1
    bad = {**a, 'fair_point': .4}
    with pytest.raises(ValueError, match='conflicting_duplicate'):
        dated_rows([{'opportunities': [a, bad]}], plan)


def test_shared_fixture_purging_and_common_intersection():
    a = row(); p = row('polymarket'); other = row('kalshi', 'b')
    assert len(common_rows([a, p, other], ['kalshi', 'polymarket'])) == 2
    assert common_rows([a, p], ['kalshi', 'polymarket', 'pinnacle']) == []
    dates = {'2026-07-01': [a], '2026-08-12': [p]}
    plan = {'dates': {'2026-07-01': 'development', '2026-08-12': 'validation'}}
    assert purge_validation(dates, plan) == {'2026-08-12': 1}
    assert dates['2026-08-12'] == []


def test_unknowns_and_sampled_date_statistics():
    a = row(); unknown = {**a, 'yes_settlement': None}
    m = scores([a, unknown])
    assert m['brier_equal_print'] == pytest.approx(.04)
    assert m['known_net_pnl'] == pytest.approx(2.9)
    assert m['pnl_per_known_cumulative_no_cash'] == pytest.approx(2.9/7.1)
    assert m['unknown_outcomes'] == 1
    stats = return_stats([m], 20)
    assert stats['sampled_slate_return_variance'] is None
    assert stats['unannualized_sampled_slate_sharpe'] is None
    daily = [{'unknown_outcomes': 0, 'known_net_pnl': x} for x in (100, -100)]
    stats = return_stats(daily, 20)
    assert stats['sampled_slate_return_variance'] == pytest.approx(.0002)
    assert stats['unannualized_sampled_slate_sharpe'] is None
    assert stats['annualized_sharpe'] is None


def full_row(model='kalshi', at=1782928800):
    r = row(model=model, at=at)
    r.update(stressed_upper=.25, quote_allowed=True, risk_multiplier=1., settled_at=at+3600)
    r['buckets'].update(contract=['leg-a', 'leg-b'], combo=['combo-a'])
    r['source'].update(nlegs=2, start_at=at+1800, series=['KXMLBGAME'],
                       fee_basis={'rate': .035, 'verified': False, 'reference': 'dated explicit scenario'})
    return r


def plan(fold='development'):
    return {'study_id': 'synthetic', 'timezone': 'America/Chicago',
            'dates': {'2026-07-01': fold}, 'primary_models': ['kalshi', 'polymarket'],
            'entry_basis': 'point', 'minimum_net_edge_per_share': .003,
            'baseline_limits': {'capital_dollars': 10000, 'per_contract_dollars': 100,
                                'per_fixture_dollars': 250, 'per_combo_dollars': 100},
            'evaluation': {'minimum_complete_resolved_slates_for_descriptive_sharpe': 20,
                           'purge_shared_fixtures_between_development_and_validation': True}}


def test_primary_pairing_cannot_change_economics_between_models():
    k = full_row(); p = full_row('polymarket'); p['maker_fee'] += .01
    with pytest.raises(ValueError, match='different_trade_economics'):
        common_rows([k, p], ['kalshi', 'polymarket'])


def test_evaluate_accepts_structured_fee_provenance_and_reports_all_regimes(tmp_path):
    inputs = [{'opportunities': [full_row(), full_row('polymarket')]}]
    result = evaluate(inputs, plan(), tmp_path)
    day = result['daily'][0]
    assert day['fee_basis'] == [full_row()['source']['fee_basis']]
    assert day['comparison_basis'] == 'all_required_primary_models_paired' and not day['diagnostic_only']
    assert len(day['results']) == 6
    assert not result['missing_dates']
    assert all(m['planned_slates'] == 1 for m in result['fold_metrics'])


def test_missing_primary_model_is_missing_validation_not_renormalized_cohort(tmp_path):
    result = evaluate([{'opportunities': [full_row()]}], plan('validation'), tmp_path)
    assert result['daily'] == []
    assert result['missing_dates'][0]['reason'] == 'required_primary_models_unavailable'
    assert result['missing_dates'][0]['missing_primary_models'] == ['polymarket']
    assert result['validation_status'] == 'incomplete_planned_dates_or_models'


def test_previous_reference_can_be_explicit_available_model_diagnostic(tmp_path):
    result = evaluate([{'opportunities': [full_row()]}], plan('previously_inspected_reference'), tmp_path)
    assert result['daily'][0]['diagnostic_only']
    assert result['daily'][0]['comparison_basis'] == 'available_model_reference_diagnostic'
    assert result['daily'][0]['missing_primary_models'] == ['polymarket']


def test_gap_days_suppress_sharpe_and_unlimited_variance_is_not_funded_return():
    daily = [{'unknown_outcomes': 0, 'known_net_pnl': x} for x in (100, 200)]
    complete = return_stats(daily, 2, capital=20000, planned_slates=2)
    assert complete['sampled_slate_return_variance'] == pytest.approx(.0000125)
    assert complete['unannualized_sampled_slate_sharpe'] is not None
    missing = return_stats(daily, 2, planned_slates=3)
    assert missing['unannualized_sampled_slate_sharpe'] is None
    assert not missing['all_planned_slates_observed']
    unlimited = return_stats(daily, 2, regime='unconstrained', planned_slates=2)
    assert unlimited['sampled_slate_return_variance'] is None
    assert unlimited['sampled_slate_pnl_variance'] == pytest.approx(5000)
    assert unlimited['unannualized_sampled_slate_sharpe'] is None
    assert unlimited['unannualized_sampled_slate_pnl_ratio'] is not None
