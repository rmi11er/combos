from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('mlb_exchange',ROOT/'scripts/mlb_exchange_acquire.py')
mlb=importlib.util.module_from_spec(spec);spec.loader.exec_module(mlb)


def sample():
    outcomes=['Detroit Tigers','Cleveland Guardians']
    money={'sportsMarketType':'moneyline','outcomes':outcomes,'clobTokenIds':['101','102'],
        'conditionId':'condition-1','slug':'mlb-det-cle-old-date','feesEnabled':True,
        'feeSchedule':{'rate':.03,'exponent':1,'takerOnly':True},
        'description':' '.join(f'This market will resolve to "{o}" if the {o} win the game.' for o in outcomes)}
    event={'startTime':'2026-09-04T18:10:00Z','slug':'mlb-det-cle-old-date','markets':[money]}
    native={'ticker':'KXMLBGAME-26SEP041410DETCLEG1-CLE',
        'rules_primary':'If Cleveland wins the Detroit vs Cleveland professional baseball game 1 originally scheduled for Sep 4, 2026 at 2:10 PM EDT, then the market resolves to Yes.'}
    return native,event


def test_exact_start_joins_postponed_slug_and_selects_actual_team_token():
    native,event=sample();result=mlb.pm_match(native,[event])
    assert result['status']=='matched' and result['token']=='102'
    assert result['fee_rate']==.03
    event['markets'][0]['feeSchedule']['rate']=.05
    assert mlb.pm_match(native,[event])['fee_rate']==.05


@pytest.mark.parametrize('at',['2026-09-04T18:11:00Z','2026-09-04T18:10:00','2026-09-05T18:10:00Z'])
def test_wrong_or_timezone_naive_start_cannot_match(at):
    native,event=sample();event['startTime']=at
    assert mlb.pm_match(native,[event])['status']=='unmatched'


def test_doubleheader_distinct_times_and_conflicting_explicit_game_number():
    native,first=sample();second=deepcopy(first)
    second['startTime']='2026-09-04T23:15:00Z';second['markets'][0]['clobTokenIds']=['201','202']
    assert mlb.pm_match(native,[second,first])['token']=='102'
    second_native=deepcopy(native);second_native['ticker']='KXMLBGAME-26SEP041915DETCLEG2-CLE'
    second_native['rules_primary']=second_native['rules_primary'].replace('game 1','game 2')
    assert mlb.pm_match(second_native,[first,second])['token']=='202'
    first['title']='Detroit Tigers vs Cleveland Guardians — Game 2'
    assert mlb.pm_match(native,[first])['status']=='unmatched'


def test_duplicate_same_time_fixture_with_distinct_tokens_is_ambiguous():
    native,event=sample();other=deepcopy(event);other['markets'][0]['clobTokenIds']=['201','202']
    assert mlb.pm_match(native,[event,other])['status']=='ambiguous'


def test_partial_game_and_duplicate_tokens_are_excluded():
    native,event=sample();event['markets'][0]['question']='Detroit vs Cleveland first five innings'
    assert mlb.pm_match(native,[event])['status']=='unmatched'
    event['markets'][0].pop('question');event['markets'][0]['clobTokenIds']=['101','101']
    assert mlb.pm_match(native,[event])['status']=='unmatched'


@pytest.mark.parametrize('fee',[{'rate':.03,'exponent':1,'takerOnly':False},
    {'rate':float('nan'),'exponent':1,'takerOnly':True},
    {'rate':-.01,'exponent':1,'takerOnly':True},
    {'rate':True,'exponent':1,'takerOnly':True},
    {'rate':.03,'exponent':2,'takerOnly':True}])
def test_unknown_or_invalid_fee_formula_never_defaults(fee):
    native,event=sample();event['markets'][0]['feeSchedule']=fee
    assert mlb.pm_match(native,[event])['status']=='unmatched'


def test_complement_spread_sign_and_prose_threshold():
    native,event=sample();native.update(ticker='KXMLBSPREAD-26SEP041410DETCLEG1-CLE2',floor_strike=1.5,
        rules_primary='If Cleveland wins by more than 1.5 runs in the Detroit vs Cleveland game 1, then the market resolves to Yes.')
    spread=deepcopy(event['markets'][0]);spread.update(sportsMarketType='spreads',line=1.5,
        clobTokenIds=['301','302'],description='This market will resolve to "Cleveland Guardians" if the Cleveland Guardians win the game by 2 or more runs. Otherwise, this market will resolve to "Detroit Tigers".')
    event['markets'].append(spread)
    result=mlb.pm_match(native,[event]);assert result['status']=='matched' and result['token']=='302'
    spread['line']=-1.5
    assert mlb.pm_match(native,[event])['status']=='unmatched'
    spread['line']=1.5;spread['description']=spread['description'].replace('2 or more','3 or more')
    assert mlb.pm_match(native,[event])['status']=='unmatched'


def test_total_line_prose_and_native_strike_must_all_agree():
    native,event=sample();native.update(ticker='KXMLBTOTAL-26SEP041410DETCLEG1-8',floor_strike=7.5,
        rules_primary='If Detroit and Cleveland collectively score more 7.5 runs in game 1, then the market resolves to Yes.')
    total=deepcopy(event['markets'][0]);total.update(sportsMarketType='totals',line=7.5,
        outcomes=['Over','Under'],clobTokenIds=['401','402'],description='This market will resolve to "Over" if the teams combine to score 8 or more runs. If the combined total is less than 8, this market will resolve to "Under".')
    event['markets'].append(total)
    assert mlb.pm_match(native,[event])['token']=='401'
    native['rules_primary']=native['rules_primary'].replace('7.5','8.5')
    assert mlb.pm_match(native,[event])['status']=='unmatched'
