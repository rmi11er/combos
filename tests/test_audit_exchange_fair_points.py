import copy
from decimal import Decimal as D
import gzip
import json
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from audit_exchange_fair_points import audit,MODELS


def context(k,p):
    result={'kalshi':{'available_at':60,'source_at':0,'yes_bid':k,'yes_ask':k,
                     'fee_basis':{'taker_rate':0},'interval':dict(lower=k,point=k,upper=k)},
            'polymarket':{'available_at':60,'state_at':0,'fee_rate':0,'interval':dict(lower=p,point=p,upper=p)}}
    for m,w in MODELS.items():
        if m not in result:
            value=float(D(str(k))*(1-w)+D(str(p))*w)
            result[m]={'interval':dict(lower=value,point=value,upper=value)}
    return result


@pytest.mark.parametrize('failure',[None,'orientation','future','interval','time'])
def test_reconstruction_detects_pricing_and_timing_errors(tmp_path,failure):
    row={'evaluation_id':'x','at':61,'legs':[{'side':'yes'},{'side':'no'}],
         'context':[context(.6,.5),context(.3,.5)]}
    decisions=[]
    for model,w in MODELS.items():
        value=(D('.6')*(1-w)+D('.5')*w)*(1-(D('.3')*(1-w)+D('.5')*w))
        decisions.append({'evaluation_id':'x','at':61,'model':model,'fair_point':float(value)})
    if failure=='orientation':row['legs'][1]['side']='yes'
    if failure=='future':row['context'][0]['kalshi']['available_at']=62
    if failure=='interval':row['context'][0]['polymarket']['interval']['upper']=.8
    if failure=='time':decisions[0]['at']=62
    paths=[tmp_path/'context.gz',tmp_path/'decisions.gz']
    for path,rows in zip(paths,([row],decisions)):
        with gzip.open(path,'wt') as stream:
            for r in rows:stream.write(json.dumps(r)+'\n')
    if failure:
        with pytest.raises(ValueError):audit(*paths)
    else:assert audit(*paths)['passed']
