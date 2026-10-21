import json
import sys
from copy import deepcopy
import pytest
from test_inventory_fitting import policy
from scripts import refresh_nfl_fee_metadata as refresh


@pytest.mark.parametrize('wrong_identity',[False,True])
def test_refresh_preserves_scope_and_handles_exchange_only_mappings(tmp_path,monkeypatch,wrong_identity):
    c=policy()
    for i,m in enumerate(c['mappings']):
        m['kalshi_ticker']='KXNFLGAME-'+str(i)
    c['mappings'][0].update(polymarket_market_id='1',polymarket_condition_id='condition')
    base='https://external-api.kalshi.com/trade-api/v2'
    c['combo_terms']['COMBO']['grid_reference']=base+'/markets/COMBO-sample'
    c['combo_terms']['COMBO-']=c['combo_terms'].pop('COMBO')
    source=tmp_path/'policy.json';source.write_text(json.dumps(c))
    original=source.read_bytes()
    def get(url,timeout):
        if 'gamma-api' in url:
            payload=[{'markets':[{'id':'1','conditionId':'wrong' if wrong_identity else 'condition','feesEnabled':False}]}]
        elif '/fee_changes?' in url:payload={'series_fee_change_arr':[]}
        elif '/markets/' in url:payload={'market':{'ticker':'COMBO-sample','price_ranges':[{'start':0,'end':1,'step':.001}]}}
        else:payload={'series':{'fee_multiplier':1,'fee_type':'quadratic'}}
        class Response:
            def raise_for_status(self):pass
            def json(self):return payload
        return Response()
    monkeypatch.setattr(refresh.requests,'get',get)
    monkeypatch.setattr(sys,'argv',['refresh','--config',str(source),'--raw-dir',str(tmp_path/'raw'),
        '--polymarket-events-url','https://gamma-api.polymarket.com/events?series_id=synthetic',
        '--refresh-combo-terms'])
    if wrong_identity:
        with pytest.raises(ValueError,match='payoff identity changed'):refresh.main()
        assert source.read_bytes()==original
    else:
        refresh.main();updated=json.loads(source.read_text())
        assert updated['inventory_fitting']==c['inventory_fitting']
        assert [m['market_key'] for m in updated['mappings']]==[m['market_key'] for m in c['mappings']]
        assert all(m['fees']['kalshi']['valid_until']>m['fees']['kalshi']['verified_at'] for m in updated['mappings'])
        assert updated['combo_terms']['COMBO-']['maker_fee_rate']==0
        assert updated['combo_terms']['COMBO-']['valid_until']>0
