import sys
from pathlib import Path
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from review_football_week_20260914 import classify
from analyze_football_week_20260914 import Candles,simulate


def test_monday_exclusion_precedes_sport_and_leg_count():
    assert classify([['KXNFLGAME-26SEP14D ENKC-KC'.replace('D EN','DEN'),'yes',''],
                     ['KXNCAAFGAME-26SEP12CALSYR-SYR','yes','']])[0]=='excluded_monday'


def test_slate_and_same_fixture_classification():
    assert classify([['KXNFLGAME-26SEP13ARILAC-LAC','yes',''],
                     ['KXNFLSPREAD-26SEP13ARILAC-ARI4','yes','']])==('NFL',2,False)
    assert classify([['KXNCAAFGAME-26SEP19AAA-B','yes','']])[0]=='excluded_other_slate_CFB'
    assert classify([['KXNCAAFGAME-26SEP12AAA-A','yes',''],
                     ['KXNCAAFGAME-26SEP12BBB-B','no','']])==('CFB',2,True)


def test_candle_publication_delay_and_max_age():
    c=Candles.__new__(Candles);c.rows={('day','ticker'):([60,120],[(60,.4,.42,10),(120,.6,.62,15)])}
    with pytest.raises(ValueError,match='missing_prior'):c.at('day','ticker',119)
    assert c.at('day','ticker',179)['point']==pytest.approx(.41)
    assert c.at('day','ticker',180)['point']==pytest.approx(.61)
    with pytest.raises(ValueError,match='older'):c.at('day','ticker',301)


def test_paper_benchmark_uses_our_ask_not_public_improvement():
    row={'id':'trade','ticker':'COMBO','q':10,'price':.3,'fair':.2,'rate':0,
        'at':100,'settled_at':200,'settlement':0,'quote_proxy_eligible':True,
        'max_width_cents':2,'tail_pass':True,'production_blocked':False,
        'fixtures':['a','b'],'risk_legs':[('a','ka',1,False),('b','kb',1,False)],
        'moneyline_eligible':False,'price_ranges':[{'start':0,'end':1,'step':.0001}]}
    result,fills,curve=simulate([row],None,'test')
    assert result['prints']==1
    fill=fills[0]
    assert fill['price']<.21 and fill['public_price']==.3
    assert fill['pnl']==pytest.approx(10*fill['price']-fill['fee'])
    assert fill['cost']<=250 and fill['model_ev']>=.03-1e-10
    assert curve[-1]['settled_equity']==pytest.approx(10000+fill['pnl'])
    row['q']=1000
    assert simulate([row],None,'test')[0]['rejects']['full_print_exceeds_ticket_cap']==1
