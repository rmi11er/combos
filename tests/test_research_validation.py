from dataclasses import replace

import pytest

from src.combos.research_validation import (
    Forecast, Fold, CalibrationPolicy, purged_fold, fit_shrunk_calibration,
    exposure_metrics, PricePoint, CausalPriceSeries, score_markout,
)


def forecast(identifier='one', at=10, fixtures=('A', 'B'), label_at=20, outcome=1, **kwargs):
    return Forecast(identifier, 'fixed', at, .2, fixtures, identifier, 10, .25, .01,
                    outcome, label_at, True, at, **kwargs)


def test_purge_entire_combo_and_require_label_known_strictly_before_fit():
    rows = [forecast('shared', fixtures=('A', 'C')),
            forecast('safe', fixtures=('D', 'E')),
            forecast('future_label', fixtures=('F', 'G'), label_at=101),
            forecast('equal_label', fixtures=('H', 'I'), label_at=100),
            forecast('unknown', fixtures=('J', 'K'), label_at=None, outcome=None),
            forecast('test', at=100, fixtures=('A', 'B'), label_at=210),
            forecast('after_test', at=201, fixtures=('D', 'E'), label_at=300)]
    train, test, counts = purged_fold(rows, Fold('test', 100, 200))
    assert [r.identifier for r in train] == ['safe']
    assert [r.identifier for r in test] == ['test']
    assert counts['purged_training_rows'] == 1
    assert counts['unknown_or_not_yet_available_labels'] == 3
    assert not {f for r in train for f in r.fixtures} & {f for r in test for f in r.fixtures}


def test_small_sample_identity_is_explicit_and_future_labels_cannot_fit():
    fit = fit_shrunk_calibration([forecast()], 100)
    assert fit.adjustment == 0
    assert fit.predict(.2) == .2
    assert set(fit.fallback_reasons) == {
        'insufficient_training_fixtures', 'insufficient_training_payoffs', 'insufficient_training_days'}
    with pytest.raises(ValueError, match='chronology'):
        fit_shrunk_calibration([forecast(label_at=100)], 100)


def test_shrunk_fit_ignores_test_outcomes_and_duplicate_print_frequency():
    policy = CalibrationPolicy(1, 1, 1, 2., .5)
    known = forecast('train')
    test = forecast('test', at=110, fixtures=('C', 'D'), label_at=210)
    first, _, _ = purged_fold([known, test], Fold('test', 100, 200))
    second, _, _ = purged_fold([known, replace(test, outcome=0)], Fold('test', 100, 200))
    a = fit_shrunk_calibration(first, 100, policy)
    b = fit_shrunk_calibration(second, 100, policy)
    assert a == b
    assert a.adjustment == pytest.approx(.4)
    duplicate = replace(known, identifier='duplicate_print', quantity=10000)
    assert fit_shrunk_calibration([known, duplicate], 100, policy).adjustment == a.adjustment


def test_exposure_metrics_selection_accounting_and_known_label_cutoff():
    good = forecast()
    bad = replace(forecast('negative_edge', fixtures=('C', 'D')), probability=.4)
    guarded = replace(forecast('guarded'), quote_allowed=False)
    selected = exposure_metrics([good, bad, guarded], selected_only=True)
    assert selected['observations'] == 1
    assert selected['expected_net_edge'] == pytest.approx(.49)
    assert selected['known_outcome_hypothetical_profit'] == pytest.approx(-7.51)
    assert selected['quantity_weighted_outcome_minus_forecast'] == pytest.approx(.8)
    assert exposure_metrics([good], outcome_as_of=19)['known_outcomes'] == 0
    with pytest.raises(ValueError, match='one model'):
        exposure_metrics([good, replace(bad, model='different')])


def test_asof_respects_availability_and_never_reverts_to_late_old_state():
    old = PricePoint(.1, 10, 20)
    new = PricePoint(.3, 30, 40)
    late_old = PricePoint(.2, 15, 50)
    inactive = PricePoint(None, 60, 65, active=False)
    series = CausalPriceSeries([inactive, late_old, new, old])
    with pytest.raises(ValueError, match='no_available'):
        series.asof(19)
    assert series.asof(39) == old
    assert series.asof(50) == new
    with pytest.raises(ValueError, match='too_old'):
        series.asof(60, maximum_source_age=29)
    with pytest.raises(ValueError, match='inactive'):
        series.asof(65)
    with pytest.raises(ValueError, match='conflicting'):
        CausalPriceSeries([old, replace(old, probability=.5)])


def test_markout_requires_post_decision_information_and_correct_no_sign():
    entry = PricePoint(.2, 80, 90)
    target = PricePoint(.3, 120, 150)
    result = score_markout(entry, target, 100, 60, .25, 10, .01)
    assert result['maker_NO_mark_change'] == pytest.approx(-1)
    assert result['net_value_at_target'] == pytest.approx(-.51)
    with pytest.raises(ValueError, match='entry_price_unavailable'):
        score_markout(replace(entry, available_at=101), target, 100, 60, .25, 10)
    with pytest.raises(ValueError, match='target_price_unavailable'):
        score_markout(entry, replace(target, available_at=161), 100, 60, .25, 10)
    with pytest.raises(ValueError, match='no_new_future'):
        score_markout(entry, entry, 100, 60, .25, 10)
    # A one-minute candle available after its extra minute delay describes
    # information from at/before entry: it is not a forward 60-second mark.
    with pytest.raises(ValueError, match='target_source_not_after_decision'):
        score_markout(entry, PricePoint(.25, 100, 160), 100, 60, .25, 10)
