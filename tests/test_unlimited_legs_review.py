"""Research extension must not change the production joint-pricing guard."""
import sys
from pathlib import Path
import math
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from review_unlimited_legs_20260915 import research_joint
from combos.pricing import Interval
from combos.joint_pricing import price_joint


def test_original_model_unchanged_and_research_short_parity():
    iv=[Interval(.4,.5,.6)]*4
    assert research_joint(iv,.05)==price_joint(iv,.05)
    with pytest.raises(ValueError,match='two_through_four'):price_joint(iv+[iv[0]],.05)


def test_long_parlay_certificate_and_independent_point():
    iv=[Interval(.2,.3,.4)]*104
    result=research_joint(iv,.05)
    assert result['joint']['point']==pytest.approx(.3**104,rel=1e-12,abs=0)
    assert result['joint']['upper']<=result['stressed_upper']<=.4
    assert result['dependence']['reserve_cents']<23.9065
    assert result['dependence']['model']=='pairwise_certificate'
    assert not result['dependence']['exact']


def test_large_uncertain_bound_is_explicit_not_an_exact_rejection():
    result=research_joint([Interval(.8,.85,.9)]*16,.05)
    assert result['dependence']['model']=='unresolved_conservative_subset_bound'
    assert not result['dependence']['exact']
    assert result['dependence']['reserve_cents']>=23.9065


def test_extended_solver_returns_valid_bound():
    result=research_joint([Interval(.6,.65,.7)]*5,.05)
    assert math.isfinite(result['stressed_upper'])
    assert result['joint']['upper']<=result['stressed_upper']<=.7


def test_single_leg_has_zero_dependence_charge():
    r=research_joint([Interval(.4,.5,.6)],.05)
    assert r['joint']['point']==.5 and r['dependence']['reserve_cents']==0
