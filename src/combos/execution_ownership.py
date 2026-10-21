"""Maker quote/order/fill evidence matching; no cash release or order submission."""
from .quote_reconciliation import match_quote,decimal,timestamp
from .execution_fills import normalize_fill


def match_maker_order(expected,quote,order,received_at,now,exchange_index):
    assessment=match_quote(expected,quote,received_at,now)
    if quote.get('status')!='executed' or quote.get('accepted_side')!='no':raise ValueError('executed NO quote required')
    maker=quote.get('creator_order_id');requester=quote.get('rfq_creator_order_id')
    if not isinstance(maker,str) or not maker or maker==requester:raise ValueError('distinct maker order identity required')
    if type(exchange_index) is not int or exchange_index<0:raise ValueError('invalid exchange identity')
    for key,value in {'order_id':maker,'ticker':expected.market_ticker,'user_id':expected.creator_user_id,
                      'subaccount_number':expected.creator_subaccount,'exchange_index':exchange_index,'side':'no','action':'buy'}.items():
        if order.get(key)!=value or type(order.get(key)) is not type(value):raise ValueError('maker_order_mismatch:'+key)
    if order.get('outcome_side','no')!='no':raise ValueError('conflicting outcome side')
    yes,no=decimal(order['yes_price_dollars']),decimal(order['no_price_dollars'])
    if yes+no!=1 or no!=decimal(expected.no_bid):raise ValueError('maker order limit differs')
    initial,filled,remaining=(decimal(order[k]) for k in ('initial_count_fp','fill_count_fp','remaining_count_fp'))
    if any(q<0 or q%decimal('.01') for q in (initial,filled,remaining)) or initial<=0 or filled+remaining>initial:
        raise ValueError('invalid maker order quantities')
    if initial>decimal(assessment['quantities']['no_contracts_fp']):raise ValueError('order exceeds quoted size')
    executed=timestamp(quote['executed_ts']);created=timestamp(order['created_time']);updated=timestamp(order['last_update_time'])
    if not assessment['created_at']<=executed<=received_at or not executed<=created<=updated<=received_at:
        raise ValueError('maker order timing mismatch')
    return {'quote_id':quote['id'],'rfq_id':quote['rfq_id'],'order_id':maker,'requester_order_id':requester,
            'ticker':expected.market_ticker,'user_id':expected.creator_user_id,'subaccount_number':expected.creator_subaccount,
            'exchange_index':exchange_index,'side':'no','action':'buy','limit_price':str(no),'maximum_quantity':str(initial),
            'capital_release_authorized':False,'basis':'quote_creator_order_id_and_private_order_identity'}


def match_maker_fill(binding,raw_fill):
    fill=normalize_fill(raw_fill)
    for key in ('order_id','ticker','subaccount_number','exchange_index','side','action'):
        if fill[key]!=binding[key] or type(fill[key]) is not type(binding[key]):raise ValueError('maker_fill_mismatch:'+key)
    if fill['is_taker']:raise ValueError('post_only_maker_fill_was_taker')
    if decimal(fill['no_price'])>decimal(binding['limit_price']):raise ValueError('fill price exceeds limit')
    if decimal(fill['quantity'])>decimal(binding['maximum_quantity']):raise ValueError('fill exceeds order quantity')
    return {'matched':True,'quote_id':binding['quote_id'],'rfq_id':binding['rfq_id'],'fill':fill,
            'capital_release_authorized':False,'remaining_check':'deduplicated cumulative fills and terminal order/account reconciliation'}
