import pytest
from combos.research_markout import ResearchMarkouts


class Pricing:
    point=.25
    def revalue(self,msg,at,seq):
        return {'status':'scenario_priced','scenarios':[{'assumed_usd_per_native_unit':1,'independent_combo_point':self.point}]}


def entry():
    return {'source_seq':1,'rfq_id':'r','at':100,'nlegs':2,
        'scenario':{'independent_combo_point':.25},
        'research_policy':{'quote':{'yes_ask':'.26','single_fill_fee':'0','quantity_bound':'10'}}}


def test_future_event_cannot_leak_into_horizon_and_censoring():
    pricing=Pricing();s=ResearchMarkouts(pricing,(10,30))
    s.schedule({'id':'r','creator_id':'c'},entry())
    assert list(s.advance(109,2))==[]
    result=list(s.advance(111,2))[0]
    pricing.point=.9  # Event at111 is applied only after marking horizon110.
    assert result['adverse_move_cents']==0 and result['available_source_seq']==2
    assert result['valuation_at']==110
    pending=list(s.finish());assert len(pending)==1 and pending[0]['status']=='right_censored'


def test_exact_horizon_events_can_be_applied_before_inclusive_flush():
    p=Pricing();s=ResearchMarkouts(p,(10,));s.schedule({'id':'r'},entry())
    assert list(s.advance(110,2))==[]
    p.point=.3
    r=list(s.advance(110,3,inclusive=True))[0]
    assert r['adverse_move_cents']==pytest.approx(5)
    assert r['quote_minus_future_fair_cents']==pytest.approx(-4)


def test_missing_future_prices_are_not_zero_markouts():
    class Missing:
        def revalue(self,*args):return {'status':'excluded','reason':'stale'}
    s=ResearchMarkouts(Missing(),(10,));s.schedule({'id':'r'},entry())
    r=list(s.advance(111,2))[0]
    assert r['status']=='unavailable' and r['reason']=='stale'
    assert 'adverse_move_cents' not in r


def test_duplicate_entry_rejected():
    s=ResearchMarkouts(Pricing());s.schedule({'id':'r'},entry())
    with pytest.raises(ValueError):s.schedule({'id':'r'},entry())
