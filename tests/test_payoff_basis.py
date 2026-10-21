import pytest
from combos.payoff_basis import exchange_payoff_bounds


def bounds(q=(.8,.8), tie=(0,0), exception=(0,0), payoff=(0,1)):
    return exchange_payoff_bounds(q, tie_probability=tie,
        exception_probability=exception, exception_payoff=payoff)


def test_no_exceptions_preserves_fair_and_ties_shrink_toward_half():
    assert bounds()['lower'] == .8
    r = bounds(tie=(.01,.01))
    assert r['lower'] == pytest.approx(.797)
    assert r['upper'] == pytest.approx(.797)


def test_unknown_exception_cash_payoff_bounds():
    r = bounds(exception=(0,.01))
    assert r['lower'] == pytest.approx(.792)
    assert r['upper'] == pytest.approx(.802)
    assert not r['assumptions_empirically_validated']


def test_selected_no_side_complements_bounds():
    yes = bounds(q=(.6,.8), tie=(0,.02), exception=(0,.01), payoff=(.2,.7))
    no = bounds(q=(.2,.4), tie=(0,.02), exception=(0,.01), payoff=(.3,.8))
    assert no['lower'] == pytest.approx(1-yes['upper'])
    assert no['upper'] == pytest.approx(1-yes['lower'])


@pytest.mark.parametrize('bad', [(-.1,.2), (.9,.2), (0,float('nan')), (0,True)])
def test_invalid_assumptions_rejected(bad):
    with pytest.raises(ValueError):
        bounds(tie=bad)
