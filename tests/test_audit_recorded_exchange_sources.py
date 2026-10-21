import gzip
import hashlib
import json
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from audit_recorded_exchange_sources import audit


def write(path,value,lines=False):
    path.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(path,'wt') as f:f.write(json.dumps(value)+ ('\n' if lines else ''))


@pytest.mark.parametrize('fault',[None,'rounding','kalshi_price','stale_pm','pm_price'])
def test_raw_source_mutations(tmp_path,fault):
    k=tmp_path/'k.gz'
    write(k,{'status':200,'payload':{'ticker':'K','candlesticks':[{'end_period_ts':0,
        'yes_bid':{'close_dollars':'.4'},'yes_ask':{'close_dollars':'.6'}}]}})
    write(tmp_path/'polymarket/token.json.gz',{'status':200,'params':{'startTs':0,'endTs':10},
          'payload':{'history':[{'t':0,'p':.4},{'t':1,'p':.5}]}})
    row={'at':61,'legs':[{'market_ticker':'K'}],'context':[{
        'kalshi':{'source_at':0,'yes_bid':.4,'yes_ask':.6,'source_provenance':{
            'file':str(k),'sha256':hashlib.sha256(k.read_bytes()).hexdigest(),'candle_price_schema':'explicit_close_dollars_only'}},
        'polymarket':{'mapping':{'token':'token'},'state_at':1,'interval':{'point':.5}}}]}
    if fault=='kalshi_price':row['context'][0]['kalshi']['yes_bid']=.3
    if fault=='stale_pm':row['context'][0]['polymarket']['state_at']=0
    if fault=='pm_price':row['context'][0]['polymarket']['interval']['point']=.6
    if fault=='rounding':row['context'][0]['polymarket']['interval']['point']=.5000000000000001
    context=tmp_path/'context.gz';write(context,row,True)
    if fault not in (None,'rounding'):
        with pytest.raises(AssertionError):audit(context,tmp_path)
    else:assert audit(context,tmp_path)['passed']
