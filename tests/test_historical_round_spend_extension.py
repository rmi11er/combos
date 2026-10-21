from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from historical_round_spend_extension import selected_mask,cash_replay
from round_spend_proxy_backtest import allowed,POLICIES,metrics
from combos.backtest import BacktestConfig


def test_vector_selection_matches_original_policy():
    rng=np.random.default_rng(7)
    rows=[dict(quantity=10,yes_price=float(p),fair_point=.5,maker_fee=.001,quote_allowed=i%7!=0)
          for i,p in enumerate(rng.uniform(.49,.51,300))]
    labels=rng.random(300)<.5
    d=pd.DataFrame(rows);d['edge']=d.quantity*(d.yes_price-d.fair_point)-d.maker_fee
    for policy in POLICIES:
        assert selected_mask(d,policy,labels).tolist()==[allowed(r,policy,bool(l)) for r,l in zip(rows,labels)]


def test_prefilter_preserves_financial_fills_and_cash_recycling():
    def row(i,at,settled,eligible=True):
        return dict(model='kalshi',evaluation_id=i,at=at,quantity=100,yes_price=.2,
            maker_fee=1,fair_point=.1,stressed_upper=.15,quote_allowed=eligible,risk_multiplier=1,
            settled_at=settled,yes_settlement=0,
            buckets={'contract':['a'],'fixture':['game'],'combo':[i]})
    rows=[row('first',10,30),row('excluded',31,40,False),row('second',35,45)]
    cfg=BacktestConfig(entry_basis='point',entry_filter='all_priced',capital_dollars=100)
    full=cash_replay(rows,0,50,cfg)
    filtered=cash_replay([r for r in rows if r['quote_allowed']],0,50,cfg)
    assert full['fills']==filtered['fills']
    assert metrics(full)==metrics(filtered)
