import importlib.util
import pytest
from pathlib import Path

spec=importlib.util.spec_from_file_location('review',Path(__file__).parents[1]/'scripts/shadow_trade_review.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def test_trade_volume_not_reused_and_lifetime_side_price_enforced():
    base=dict(status='shadow_quote',market_ticker='T',quantity=10,
        decision_completed_at=100,valid_until=103,yes_ask=.4,
        economics={'maker_fee':0,'expected_edge':.1},pricing={'joint':{'point':.3}})
    quotes=[dict(base,quote_key='a'),dict(base,quote_key='b')]
    trade=dict(trade_id='t',created_time='1970-01-01T00:01:41Z',
        yes_price_dollars='.42',count_fp='15',taker_side='yes')
    tape={'T':{'trades':[trade,trade]}}
    fills=m.match(quotes,tape,0)
    assert [f['quantity'] for f in fills]==[10,5]
    assert sum(f['point_edge_dollars'] for f in fills)==pytest.approx(1.5)
    assert not m.match(quotes,tape,2)
    for replacement in ({'taker_side':'no'},{'yes_price_dollars':'.39'},
                        {'created_time':'1970-01-01T00:01:43Z'}):
        assert not m.match(quotes,{'T':{'trades':[dict(trade,**replacement)]}},0)
