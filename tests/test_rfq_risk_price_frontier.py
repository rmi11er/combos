import sys
from pathlib import Path
from decimal import Decimal as D
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from rfq_risk_price_frontier import frontier,price_terms


@pytest.mark.parametrize('contracts,target', [('100',None),(None,'10')])
@pytest.mark.parametrize('rate', [D('0'),D('.035')])
def test_binary_risk_search_matches_exhaustive_price_and_edge_scan(contracts,target,rate):
    prices=[D(i)/100 for i in range(40,100)]
    for room in (0,1000,10000,100000,500000):
        expected=None
        for p in prices:
            q,fee,cost=price_terms(p,contracts,target,rate)
            if cost<=room and q*(p-D('.4'))-fee>=q*D('.003'):
                expected=p;break
        actual=frontier(prices,D('.4'),room,contracts,target,rate,D('.4'),D('.003'))
        assert (D(actual['ask']) if actual else None)==expected
        if actual and contracts is not None:assert D(actual['quantity_bound'])==D(contracts)
