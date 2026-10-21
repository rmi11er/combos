from copy import deepcopy
import gzip
import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from combos.pinnacle_feed import fixture_index, normalize
from combos.oddspapi import OddsPapi
from combos.observations import Observation


def sample():
    mapping={'market_key':'NFL:totals:45.5','market_type':'totals','mapping_reference':'synthetic:reviewed',
        'pinnacle':{'fixture_id':'f','selector_reference':'synthetic:exact-line',
          'payoff_reference':'synthetic:no-push','limit_reference':'synthetic:USD-stake',
          'limit_currency':'USD','limit_unit':'stake','market_id':'m','bookmaker_market_id':'game/total/45.5',
          'yes':{'outcome_id':'over','bookmaker_outcome_id':'45.5/over'},
          'no':{'outcome_id':'under','bookmaker_outcome_id':'45.5/under'}}}
    outcomes={s:{'players':{'0':{'active':True,'playerName':None,'bookmakerOutcomeId':'45.5/'+s,
        'price':2.,'limit':50,'bookmakerChangedAt':'1970-01-01T00:01:10Z'}}} for s in ('over','under')}
    fixture={'fixtureId':'f','statusId':0,'bookmakerOdds':{'pinnacle':{'bookmakerIsActive':True,
        'suspended':False,'markets':{'m':{'bookmakerMarketId':'game/total/45.5','marketActive':True,'outcomes':outcomes}}}}}
    return mapping,fixture


def test_exact_pair_and_source_age_never_rejuvenated_by_new_receipt():
    mapping,fixture=sample();index=fixture_index([fixture])
    row,phase=normalize(mapping,index,100,'raw:1')
    assert row['active'] and phase=='pregame'
    assert row['observed_at']==70 and row['available_at']==100
    assert Observation.from_record(row).bid_capacity==100
    assert Observation.from_record(row).freshness_context['response_received_at']==100
    assert not row['freshness_context']['upstream_freshness_validated']
    later,_=normalize(mapping,index,130,'raw:2')
    assert later['observed_at']==70 and later['available_at']==130
    missing,_=normalize(mapping,{},131,'raw:3')
    assert not missing['active'] and missing['invalid_reason']=='fixture_missing_in_snapshot'


@pytest.mark.parametrize('change', ['line','inactive','currency','prop','unreviewed','future','started'])
def test_bad_inputs_never_enter_fair(change):
    m,f=sample();market=f['bookmakerOdds']['pinnacle']['markets']['m']
    if change=='line':market['bookmakerMarketId']='game/total/46.5'
    if change=='inactive':market['marketActive']=False
    if change=='currency':m['pinnacle']['limit_currency']='EUR'
    if change=='prop':market['outcomes']['over']['players']['0']['playerName']='player'
    if change=='unreviewed':m['pricing_block_reason']='pending'
    if change=='future':market['outcomes']['over']['players']['0']['bookmakerChangedAt']='1970-01-01T00:02:00Z'
    if change=='started':f['statusId']=1
    row,phase=normalize(m,fixture_index(f),100,'raw')
    assert not row['active'] and row['invalid_reason']
    if change=='started':assert phase=='in_play'


def test_unknown_payload_or_duplicate_fixture_cannot_silently_drop_data():
    _,f=sample()
    with pytest.raises(ValueError,match='shape'):fixture_index({'data':[f]})
    with pytest.raises(ValueError,match='duplicate'):fixture_index([f,f])


def test_account_key_is_redacted_before_return_and_cache(tmp_path):
    class Response:
        status_code=200;headers={}
        def json(self):return {'api_key':'DO_NOT_ARCHIVE','subscriptions':[]}
    class Session:
        def get(self,*a,**kw):return Response()
    client=OddsPapi(tmp_path,api_key='synthetic',session=Session())
    envelope=client.get('account')
    assert envelope['payload']['api_key']=='[REDACTED]'
    for path in tmp_path.rglob('*.gz'):
        with gzip.open(path,'rt') as f:assert 'DO_NOT_ARCHIVE' not in f.read()


def test_delayed_bookmaker_is_requested_and_normalized_by_its_actual_slug():
    import importlib.util
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    spec=importlib.util.spec_from_file_location('smoke_probe',root/'scripts/oddspapi_smoke.py')
    cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)
    account={'subscriptions':[
        {'is_active':False,'sport_ids':[14],'bookmakers':{'pinnacle':{}}},
        {'is_active':True,'sport_ids':[14],'bookmakers':{'pinnacle+30':{}}}]}
    assert cli.subscribed_pinnacle(account,14)=='pinnacle+30'
    with pytest.raises(ValueError,match='entitled'):cli.subscribed_pinnacle(account,10)
    m,f=sample()
    f['bookmakerOdds']['pinnacle+30']=f['bookmakerOdds'].pop('pinnacle')
    row,_=normalize(m,fixture_index(f),100,'raw',bookmaker='pinnacle+30')
    assert row['active'] and row['venue']=='pinnacle' and row['provider_bookmaker']=='pinnacle+30'
    missing,_=normalize(m,fixture_index(f),100,'raw',bookmaker='pinnacle')
    assert not missing['active']


def test_period_team_total_adapter_and_catalog_scope():
    m,f=sample();m.update(market_type='team_totals',period='first_half',player_prop=False)
    m['pinnacle']['catalog']={'playerProp':False,'sportId':14,'period':'p1+p2','marketType':'teamtotals-team1'}
    market=f['bookmakerOdds']['pinnacle']['markets']['m']
    for side in ('yes','no'):
        selector=m['pinnacle'][side]
        selector['bookmaker_outcome_id']='home/'+selector['bookmaker_outcome_id']
        market['outcomes'][selector['outcome_id']]['players']['0']['bookmakerOutcomeId']=selector['bookmaker_outcome_id']
    row,_=normalize(m,fixture_index(f),100,'raw');assert row['active']
    m['pinnacle']['catalog']['period']='result'
    row,_=normalize(m,fixture_index(f),100,'raw')
    assert not row['active'] and row['invalid_reason']=='pinnacle_catalog_scope_mismatch'


@pytest.mark.parametrize('status,phase',[(1,'in_play'),(2,'finished'),(3,'cancelled'),(99,'unknown')])
def test_native_fixture_status_never_reopens_pregame(status,phase):
    m,f=sample();f['statusId']=status
    row,actual=normalize(m,fixture_index(f),100,'raw')
    assert actual==phase and not row['active']
    assert row['invalid_reason']=='pinnacle_fixture_not_pregame'


def revision_sample(alternate=False):
    mapping, fixture = sample()
    spec = mapping['pinnacle']
    old = 'altLine/15/889/123/100/789/0/totals' if alternate else 'line/15/889/123/100/0/totals'
    spec['bookmaker_market_id'] = old
    spec['catalog'] = {'marketId':'m','playerProp':False,'sportId':14,
                       'period':'result','marketType':'totals',
                       'outcomes':[{'outcomeId':'over'},{'outcomeId':'under'}]}
    fixture.update(sportId=14,tournamentId=31,externalProviders={'pinnacleId':123})
    book = fixture['bookmakerOdds']['pinnacle']
    book['bookmakerFixtureId'] = '123'
    book['markets']['m']['bookmakerMarketId'] = old.replace('/100/', '/101/')
    if alternate:
        book['markets']['m']['bookmakerMarketId'] = book['markets']['m']['bookmakerMarketId'].replace('/789/', '/790/')
    return mapping, fixture


@pytest.mark.parametrize('alternate',[False,True])
def test_native_market_revision_can_advance_with_exact_identity_and_lines(alternate):
    mapping, fixture = revision_sample(alternate)
    row, _ = normalize(mapping,fixture_index(fixture),100,'raw:revision')
    assert row['active']
    assert row['native_market_identity_context']['revision_changed']


@pytest.mark.parametrize('change',['fixture','league','sport','period','line','catalog','native_fixture','market_kind','unknown_shape'])
def test_revision_tolerance_never_accepts_semantic_changes(change):
    mapping, fixture = revision_sample(True)
    market = fixture['bookmakerOdds']['pinnacle']['markets']['m']
    if change=='fixture':market['bookmakerMarketId']=market['bookmakerMarketId'].replace('/123/','/124/')
    if change=='league':fixture['tournamentId']=999
    if change=='sport':fixture['sportId']=13
    if change=='period':market['bookmakerMarketId']=market['bookmakerMarketId'].replace('/0/totals','/1/totals')
    if change=='line':market['outcomes']['over']['players']['0']['bookmakerOutcomeId']='46.5/over'
    if change=='catalog':mapping['pinnacle']['catalog']['outcomes'][1]['outcomeId']='different'
    if change=='native_fixture':fixture['externalProviders']['pinnacleId']=124
    if change=='market_kind':market['bookmakerMarketId']=market['bookmakerMarketId'].replace('/totals','/spreads')
    if change=='unknown_shape':market['bookmakerMarketId']='unknown/123/101'
    row,_=normalize(mapping,fixture_index(fixture),100,'raw:bad-revision')
    assert not row['active']


def test_revision_handling_does_not_lift_payoff_review_block():
    mapping, fixture = revision_sample()
    mapping['pricing_block_reason']='pinnacle_payoff_mapping_unreviewed'
    row,_=normalize(mapping,fixture_index(fixture),100,'raw')
    assert not row['active'] and row['invalid_reason']=='pinnacle_payoff_mapping_unreviewed'
