from dataclasses import replace
import math
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from combos.delayed_anchor import ProbabilitySnapshot, ProbabilityHistory, DelayedAnchorEstimator, DelayedAnchorPolicy
from combos.pricing import Interval


def snapshot(venue, at, point, **kwargs):
    return ProbabilitySnapshot('game:payoff','mapping-v1',venue,Interval(point-.01,point,point+.01),
        at,at,'native:'+venue+':'+str(at),'verified_test_information_clock',True,
        two_sided_depth=1000 if venue!='pinnacle' else None, **kwargs)


def case(beta=1):
    history = ProbabilityHistory()
    for venue in ('kalshi','polymarket'):
        history.append(snapshot(venue,69,.5))
    anchor = replace(snapshot('pinnacle',70,.4), available_at=100)
    current = [snapshot(venue,100,.6) for venue in ('kalshi','polymarket')]
    return DelayedAnchorEstimator(history,DelayedAnchorPolicy(beta=beta)), anchor, current


def test_common_exchange_move_is_not_double_counted():
    model, anchor, current = case()
    r=model.estimate(anchor,current,100,1000)
    expected=1/(1+math.exp(-(math.log(.4/.6)+math.log(.6/.4))))
    assert r['fair_point']==pytest.approx(expected)
    assert sum(r['exchange_weights'].values())==pytest.approx(1)
    assert r['fair_point']==pytest.approx(.5)
    assert not r['quote_authorized'] and r['uncertainty_bound'] is None


def test_beta_zero_preserves_anchor_and_half_shrinks_innovation():
    model,anchor,current=case(0)
    assert model.estimate(anchor,current,100,1000)['fair_point']==pytest.approx(.4)
    model,anchor,current=case(.5)
    assert .4<model.estimate(anchor,current,100,1000)['fair_point']<.5


def test_future_received_baseline_is_not_used_even_if_information_time_is_old():
    model,anchor,current=case()
    model.history.append(replace(snapshot('kalshi',69.5,.7),available_at=75))
    r=model.estimate(anchor,current,100,1000)
    assert r['exchange_context']['kalshi']['baseline']['interval']['point']==.5


def test_young_anchor_cannot_use_exchange_information_from_before_anchor():
    history = ProbabilityHistory()
    for venue in ('kalshi', 'polymarket'):
        history.append(snapshot(venue, 94, .5))
    model = DelayedAnchorEstimator(history)
    anchor = replace(snapshot('pinnacle', 95, .4), available_at=100)
    current = [replace(snapshot(venue, 94, .6), available_at=100)
               for venue in ('kalshi', 'polymarket')]
    with pytest.raises(ValueError, match='current_information_precedes_anchor'):
        model.estimate(anchor, current, 100, 1000)


def test_suspension_or_mapping_change_cannot_be_skipped_for_earlier_valid_data():
    model,anchor,current=case()
    model.history.append(replace(snapshot('kalshi',70,.5),active=False))
    with pytest.raises(ValueError,match='inactive_latest_state'):model.estimate(anchor,current,100,1000)
    model,anchor,current=case()
    current[0]=replace(current[0],mapping_reference='mapping-v2')
    with pytest.raises(ValueError,match='mapping_version'):model.estimate(anchor,current,100,1000)


@pytest.mark.parametrize('change,reason',[
    ({'information_time_verified':False},'unverified'),
    ({'historical_imputed':True},'imputed'),
    ({'two_sided_depth':None},'depth_missing'),
    ({'available_at':101},'future_or_stale')])
def test_unverified_imputed_depthless_or_future_data_blocks(change,reason):
    model,anchor,current=case();current[0]=replace(current[0],**change)
    with pytest.raises(ValueError,match=reason):model.estimate(anchor,current,100,1000)


def test_unverified_anchor_clock_and_disagreeing_moves_block():
    model,anchor,current=case()
    with pytest.raises(ValueError,match='unverified'):
        model.estimate(replace(anchor,information_time_verified=False),current,100,1000)
    current[0]=snapshot('kalshi',100,.4)
    with pytest.raises(ValueError,match='disagreement'):model.estimate(anchor,current,100,1000)
    with pytest.raises(ValueError,match='pregame_cutoff'):model.estimate(anchor,current,100,160)
