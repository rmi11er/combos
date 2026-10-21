from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from opposite_moneyline_study import joint_upper, pair_width


def test_opposite_asks_and_fee_sides():
    r = pair_width(.62, .41, .07, .035)
    assert r['raw_width_cents'] == pytest.approx(3.)
    assert r['lower'] == pytest.approx(1-.41-.035*.41*.59)
    assert r['upper'] == pytest.approx(.62+.07*.62*.38)


def test_complement_preserves_width_and_reverses_endpoints():
    a = pair_width(.62, .41, .07, .035)
    b = pair_width(.41, .62, .035, .07)
    assert a['width'] == pytest.approx(b['width'])
    assert a['upper'] == pytest.approx(1-b['lower'])


def test_crossed_pair_not_silently_repaired_by_fees():
    with pytest.raises(ValueError, match='crossed'):
        pair_width(.4, .4, .07, .07)


def test_joint_width_propagation_not_flat_per_leg_sum():
    assert joint_upper([.5, .4], [.04, .02]) == pytest.approx(.52*.41)
    assert joint_upper([.5, .4], [0., 0.]) == pytest.approx(.2)
    assert joint_upper([.99, .99], [.1, .1]) == 1.


@pytest.mark.parametrize('value', [float('nan'), -1., 2.])
def test_invalid_points(value):
    with pytest.raises(ValueError):
        joint_upper([value, .5], [.01, .01])
