"""Settlement, exact matching and scope regressions for expanded NFL families."""
import copy, json, gzip
from collections import Counter
from pathlib import Path
import pytest
from combos.payoff_risk import nfl_risk_identity, canonical_leg_risk
from combos.rfq_scope import check_legs,check_mappings,check_start
from combos.pinnacle_matching import bind_selectors
from combos.nfl_nonplayer_matching import _pm_entries


def mapping(period='first_half',kind='moneyline',suffix='A'):
    fixture='NFL:2026-09-09:A-B'
    return {'fixture_key':fixture,'market_key':fixture+(':'+period if period!='full_game' else '')+':'+kind+':'+suffix,
            'sport':'NFL','period':period,'market_type':kind,'tie_settlement':'team_loses','start_at':1000,
            'kalshi_ticker':{'moneyline':'KXNFL1H','team_totals':'KXNFL1HTEAMTOTAL','spreads':'KXNFL1HSPREAD'}[kind]+'-test'}


def test_outright_period_win_equals_minus_half_but_not_no_opponent_win():
    a=mapping();b=mapping(suffix='B');spread=mapping(kind='spreads',suffix='A:0.5')
    assert nfl_risk_identity(a)==nfl_risk_identity(spread)
    assert canonical_leg_risk(a,'yes')['key']!=canonical_leg_risk(b,'no')['key']
    assert canonical_leg_risk(a,'yes','buy')['conditional_payoff_change_dollars']==canonical_leg_risk(a,'no','sell')['conditional_payoff_change_dollars']
    assert nfl_risk_identity(mapping('full_game'))['key']==nfl_risk_identity(mapping('full_game',suffix='B'))['key']


def test_period_risk_and_team_total_side_aliases():
    over=mapping(kind='team_totals',suffix='A:over:10.5');under=mapping(kind='team_totals',suffix='A:under:10.5')
    assert canonical_leg_risk(over,'yes')['key']==canonical_leg_risk(under,'no')['key']
    assert canonical_leg_risk(over,'yes')['selected_sign']==canonical_leg_risk(under,'no')['selected_sign']
    assert nfl_risk_identity(over)['key']!=nfl_risk_identity(mapping('full_game','team_totals','A:over:10.5'))['key']
    over['period']='first_quarter'
    with pytest.raises(ValueError,match='period_key'):nfl_risk_identity(over)


def test_period_scope_still_requires_game_pregame_and_exact_family():
    c={'sport':'NFL'};legs=[{'market_ticker':'KXNFL1H-test','side':'yes'},{'market_ticker':'KXNFL1Q-test','side':'no'}]
    check_legs(legs,c)
    m=mapping();check_mappings(legs[:1],[m],c)
    with pytest.raises(ValueError,match='pregame_cutoff'):check_start(m,{},940,c)
    with pytest.raises(ValueError,match='pregame_only'):check_start(m,{'started':True},900,c)
    m['period']='full_game'
    with pytest.raises(ValueError,match='period_mismatch'):check_mappings(legs[:1],[m],c)
    legs[1]['market_ticker']='KXNFL2H-test'
    with pytest.raises(ValueError,match='outside_supported'):check_legs(legs,c)


def test_two_way_period_moneyline_is_not_an_outright_match():
    pm={'sportsMarketType':'first_half_moneyline','active':True,'closed':False,'acceptingOrders':True,
        'outcomes':['A','B'],'clobTokenIds':['1','2'],'feesEnabled':False,
        'description':'Winning in the first half; tie resolves 50-50.'}
    assert _pm_entries(pm,{'a':'A','b':'B'})==[]


def fixture_and_catalog():
    catalog=[{'marketId':1,'sportId':14,'playerProp':False,'period':'p1+p2','marketType':'spreads','handicap':-.5,
              'outcomes':[{'outcomeId':2},{'outcomeId':3}]}]
    market={'bookmakerMarketId':'native','outcomes':{str(i):{'players':{'0':{'playerName':None,'bookmakerOutcomeId':f'-0.5/{side}'}}}
                for i,side in ((2,'home'),(3,'away'))}}
    f={'fixtureId':'f','sportId':14,'tournamentId':31,'participant1Abbr':'A','participant2Abbr':'B',
       'startTime':'2026-09-10T00:20:00Z','bookmakerOdds':{'pinnacle+30':{'markets':{'1':market}}}}
    return f,catalog


def test_pinnacle_selector_maps_period_win_to_exact_spread_and_rejects_drift():
    from datetime import datetime
    f,c=fixture_and_catalog();m=mapping();m['start_at']=datetime.fromisoformat(f['startTime']).timestamp()
    report=bind_selectors([m],[f],c)
    assert report['candidate_mappings']==1 and m['pinnacle']['yes']['outcome_id']=='2'
    assert 'payoff_reference' not in m['pinnacle'] # matching is not settlement approval
    for field,value in [('period','result'),('handicap',-1.5),('playerProp',True)]:
        wrong=copy.deepcopy(c);wrong[0][field]=value
        assert bind_selectors([m],[f],wrong)['candidate_mappings']==0
    f['bookmakerOdds']['pinnacle+30']['markets']['1']['outcomes']['3']['players']['0']['bookmakerOutcomeId']='-1.5/away'
    assert bind_selectors([m],[f],c)['candidate_mappings']==0
