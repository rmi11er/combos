from src.combos.matching import match_market,event_index
import json

def test_spread_outcome_and_period_identity():
    event={'slug':'cfb-ohio-nebr-2026-09-05','startTime':'2026-09-05T16:00:00Z','markets':[
      {'sportsMarketType':'moneyline','outcomes':'["Ohio","Nebraska"]'},
      {'sportsMarketType':'spreads','outcomes':'["Nebraska","Ohio"]','line':-24.5,'conditionId':'c','slug':'s','clobTokenIds':'["nebr","ohio"]'}]}
    k={'ticker':'KXNCAAFSPREAD-26SEP05OHIONEB-NEB25','rules_primary':'If Nebraska wins by more than 24.5 points in the Ohio vs Nebraska college football game originally scheduled for Sep 5, 2026, then the market resolves to Yes.','yes_sub_title':'Nebraska wins by over 24.5 points','floor_strike':24.5}
    idx=event_index([event]);m=match_market(k,idx)
    assert m['status']=='matched' and m['token']=='nebr'
    k['ticker']='KXNCAAF1HSPREAD-26SEP05OHIONEB-NEB25'
    assert match_market(k,idx)['status']=='payoff_unmatched'
