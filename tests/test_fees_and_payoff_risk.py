from copy import deepcopy
from decimal import Decimal
import sys
from pathlib import Path
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from combos.fees import kalshi_fill_fee,polymarket_fill_fee,taker_fee_context
from combos.payoff_risk import canonical_leg_risk,nfl_risk_identity
from combos.observations import Observation
from combos.event_store import EventStore
from combos.shadow_engine import ShadowEngine
from combos.creator_service import CreatorService
from test_runtime import config,observation,add,rfq,drain,decisions


def mapping(team,typ='moneyline',line=None):
    fixture='NFL:2026-09-13:CIN-DET'
    key=fixture+':'+typ+':'+team+(':'+str(line) if line is not None else '')
    return {'market_key':key,'fixture_key':fixture,'sport':'NFL','market_type':typ}


def test_team_complements_and_buy_sell_signs():
    lions=mapping('DET');bengals=mapping('CIN')
    for action in ('buy','sell'):
        a=canonical_leg_risk(lions,'yes',action,10)
        b=canonical_leg_risk(bengals,'no',action,10)
        assert a==b
    buy=canonical_leg_risk(lions,'yes','buy',10)
    sell=canonical_leg_risk(lions,'yes','sell',10)
    assert buy['key']==sell['key']
    assert buy['conditional_payoff_change_dollars']==-sell['conditional_payoff_change_dollars']
    assert canonical_leg_risk(lions,'no','sell',10)['conditional_payoff_change_dollars']==buy['conditional_payoff_change_dollars']


def test_spread_complements_share_only_the_exact_half_line():
    a=canonical_leg_risk(mapping('DET','spreads','3.50'),'yes')
    b=canonical_leg_risk(mapping('CIN','spreads','-3.5'),'no')
    assert a==b
    assert canonical_leg_risk(mapping('CIN','spreads','-4.5'),'no')['key']!=a['key']
    with pytest.raises(ValueError,match='half_point'):nfl_risk_identity(mapping('DET','spreads',3))
    with pytest.raises(ValueError,match='mismatch'):
        canonical_leg_risk({**mapping('DET'),'risk_identity':{'key':'other','yes_sign':1}},'yes')


def test_equivalent_moneyline_aliases_cannot_bypass_contract_cap(tmp_path):
    c=config();base=c['mappings'][0]
    left={**deepcopy(base),**mapping('DET'),'kalshi_ticker':'KXNFLGAME-det'}
    alias={**deepcopy(base),**mapping('CIN'),'kalshi_ticker':'KXNFLGAME-cin'}
    c['mappings']=[left,alias,c['mappings'][1]]
    store=EventStore(tmp_path/'risk.sqlite');creators=CreatorService(store);engine=ShadowEngine(store,c,replay=True)
    for m in c['mappings']:
        for venue in ('kalshi','polymarket','pinnacle'):
            add(store,'observation',observation(m['market_key'],venue),m['market_key']+venue,100)
    first=rfq(quantity=100);first['mve_selected_legs'][0]={'market_ticker':'KXNFLGAME-det','side':'yes'}
    second=rfq('r2',quantity=100);second['mve_selected_legs'][0]={'market_ticker':'KXNFLGAME-cin','side':'no'}
    add(store,'rfq',first,'r1',100);add(store,'rfq',second,'r2',100.1);drain(creators,engine)
    a,b=decisions(store)
    assert a['status']=='shadow_quote' and b['reason']=='contract_risk_limit'
    assert a['canonical_leg_risk'][0]==b['canonical_leg_risk'][0]
    assert b['risk']['checks'][0]['used_dollars']>0
    store.close()


def test_current_fee_rates_and_kalshi_published_fcm_example():
    assert polymarket_fill_fee(100,'.5','.05')['net_fee']==Decimal('1.25')
    assert kalshi_fill_fee(100,'.5','.07')['net_fee']==Decimal('1.75')
    f=kalshi_fill_fee(1,'.055','.07',balance_precision='.01')
    assert f['trade_fee']==Decimal('.003639')
    assert f['rounding_fee']==Decimal('.001361')
    assert f['net_fee']==Decimal('.005') and f['balance_change']==Decimal('-.06')
    direct=kalshi_fill_fee(1,'.055','.07')
    assert direct['net_fee']==Decimal('.0037')


def test_accumulator_sell_alignment_and_rebate_cap():
    carry=Decimal(0);fees=[]
    for _ in range(3):
        fill=kalshi_fill_fee(1,'.055','.07',balance_precision='.01',accumulator=carry)
        carry=fill['accumulator'];fees.append(fill['net_fee'])
        assert fill['net_fee']>=0 and fill['balance_change']%Decimal('.01')==0
    sell=kalshi_fill_fee('.03','.3301','.07','sell',balance_precision='.0001',accumulator='.01')
    assert sell['balance_change']%Decimal('.0001')==0 and sell['net_fee']>=0
    assert sell['accumulator']>=0
    # A zero-fee fill cannot refund an accumulated amount larger than this fill's fees.
    zero=kalshi_fill_fee(1,'.5',0,accumulator='.01')
    assert zero['rebate']==0 and zero['accumulator']==Decimal('.01')


def test_finite_size_fee_bounds_use_cash_and_preserve_no_complement():
    context=taker_fee_context('kalshi','.055','.065',1,1,'.07')
    assert context['sides']['ask']['conservative_fee_per_share']>=.07*.065*.935
    row=observation('a','kalshi',point=.5)
    row.update(yes_bid='.055',yes_ask='.065',yes_bid_size=1,yes_ask_size=1,taker_rate=.07,
               fee_model='venue_cash_v2',balance_precision='.0001')
    o=Observation.from_record(row)
    assert o.fee_context['sides']['bid']['action']=='sell'
    assert o.selected_interval('no').lower==pytest.approx(1-o.interval.upper)
    row.pop('balance_precision')
    with pytest.raises(ValueError,match='precision'):Observation.from_record(row)


def test_polymarket_rounding_bound_and_tiny_fee():
    assert polymarket_fill_fee('.01','.001','.05')['net_fee']==0
    f=taker_fee_context('polymarket','.001','.002','.01','.01','.05')
    assert f['sides']['bid']['conservative_fee_per_share']>=float(Decimal('.05')*Decimal('.001')*Decimal('.999'))
