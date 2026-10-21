import pytest
from combos.execution_ownership import match_maker_order,match_maker_fill
from combos.quote_reconciliation import ExpectedQuote


def evidence():
    e=ExpectedQuote('r','M','maker',0,'0','.7','10',100,quote_id='q',fixed_contracts='10')
    q={'id':'q','rfq_id':'r','market_ticker':'M','creator_user_id':'maker','creator_subaccount':0,'rest_remainder':False,'post_only':True,
       'yes_bid_dollars':'0','no_bid_dollars':'.7','yes_contracts_fp':'10','no_contracts_fp':'10','contracts_fp':'10',
       'created_ts':'1970-01-01T00:01:41Z','updated_ts':'1970-01-01T00:01:44Z','executed_ts':'1970-01-01T00:01:43Z',
       'status':'executed','accepted_side':'no','creator_order_id':'maker-order','rfq_creator_order_id':'requester-order'}
    o={'order_id':'maker-order','user_id':'maker','ticker':'M','subaccount_number':0,'exchange_index':0,'side':'no','action':'buy',
       'yes_price_dollars':'.3','no_price_dollars':'.7','initial_count_fp':'10','fill_count_fp':'2','remaining_count_fp':'8',
       'created_time':'1970-01-01T00:01:43Z','last_update_time':'1970-01-01T00:01:44Z'}
    return e,q,o


def fill():return {'fill_id':'f','trade_id':'t','order_id':'maker-order','ticker':'M','subaccount_number':0,'exchange_index':0,'side':'no','action':'buy','is_taker':False,'count_fp':'2','yes_price_dollars':'.31','no_price_dollars':'.69','fee_cost':'.001'}


def test_maker_order_and_improved_fill_match_without_releasing_capital():
    e,q,o=evidence();binding=match_maker_order(e,q,o,104,105,0);r=match_maker_fill(binding,fill())
    assert r['matched'] and not r['capital_release_authorized']


@pytest.mark.parametrize('field,value',[('order_id','requester-order'),('user_id','other'),('subaccount_number',1),('side','yes'),('initial_count_fp','11')])
def test_wrong_order_evidence_rejected(field,value):
    e,q,o=evidence();o[field]=value
    with pytest.raises(ValueError):match_maker_order(e,q,o,104,105,0)


@pytest.mark.parametrize('field,value',[('order_id','requester-order'),('is_taker',True),('count_fp','11'),('exchange_index',1)])
def test_wrong_fill_evidence_rejected(field,value):
    e,q,o=evidence();b=match_maker_order(e,q,o,104,105,0);f=fill();f[field]=value
    with pytest.raises(ValueError):match_maker_fill(b,f)
