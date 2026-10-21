from combos.refresh_demand import RefreshDemand,choose
from combos.event_store import EventStore


def test_published_demand_expiry_and_unknown_tokens(tmp_path):
    s=EventStore(tmp_path/'events.sqlite');d=RefreshDemand({'a':'A'})
    assert d.poll(s.db,100)=={}
    s.append('rfq_refresh_demand','kalshi',{'market_tickers':['a','unknown']},'a',101)
    assert d.poll(s.db,102)=={'A':101}
    assert d.poll(s.db,161)=={}
    s.close()


def test_priority_exploration_and_refresh_cadence():
    tokens=[str(i) for i in range(100)]
    selected=choose(tokens,{}, {'99':100},100,10,exploration=2)
    assert selected[0]=='99' and len(selected)==len(set(selected))==10
    selected=choose(tokens,{'99':99},{'99':100},100,10,exploration=2)
    assert '99' not in selected


def test_bounded_poll_does_not_skip_events(tmp_path):
    s=EventStore(tmp_path/'events.sqlite');d=RefreshDemand({'a':'A','b':'B'})
    for t in ('a','b'):s.append('rfq_refresh_demand','kalshi',{'market_tickers':[t]},t,100)
    assert d.poll(s.db,101,limit=1)=={'A':100}
    assert d.poll(s.db,101,limit=1)=={'A':100,'B':100}
    s.close()
