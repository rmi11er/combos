"""MLB model research preserves side, exposure, causality and accounting."""
from copy import deepcopy
import gzip
import importlib.util
import json
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))
import mlb_model_replay as replay
import mlb_model_report as report
from combos.backtest import BacktestConfig,run_backtest
from combos.pricing import Interval


def gz(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(path,'wt') as f:json.dump(data,f)


def row(identifier='a',at=100.,legs=2,quantity=10.,price=.3,fee=.1,settlement=1.):
    return {'model':'kalshi','evaluation_id':identifier,'at':at,'quantity':quantity,'yes_price':price,
            'maker_fee':fee,'yes_settlement':settlement,'settled_at':300. if settlement is not None else None,
            'fair_point':.2,'stressed_upper':.25,'quote_allowed':True,'risk_multiplier':1.,
            'buckets':{'contract':['shared-a','b'],'fixture':['fixture-a','fixture-b'],'combo':[identifier]},
            'source':{'nlegs':legs,'series':['KXMLBGAME'],'start_at':1000.}}


def test_selected_no_reverses_interval_endpoints_and_probability():
    fair=Interval(.17,.23,.31)
    assert replay.selected(fair,'yes') is fair
    no=replay.selected(fair,'no')
    assert (no.lower,no.point,no.upper)==pytest.approx((.69,.77,.83))
    restored=replay.selected(no,'no')
    assert (restored.lower,restored.point,restored.upper)==pytest.approx((.17,.23,.31))
    with pytest.raises(ValueError,match='invalid_selected_side'):replay.selected(fair,'buy')


def test_opponent_yes_no_share_gross_moneyline_risk_without_hedge_credit():
    away='KXMLBGAME-26SEP051305NYYBAL-NYY';home='KXMLBGAME-26SEP051305NYYBAL-BAL'
    native={away:{},home:{}}
    keys=[replay.risk_buckets([{'market_ticker':ticker,'side':side}],native)
          for ticker,side in ((away,'yes'),(home,'no'),(away,'no'),(home,'yes'))]
    assert all(k['contract']==keys[0]['contract'] and k['fixture']==keys[0]['fixture'] for k in keys)
    later='KXMLBGAME-26SEP051905NYYBAL-NYY'
    other=replay.risk_buckets([{'market_ticker':later,'side':'yes'}],{later:{}})
    assert other['contract']!=keys[0]['contract']  # Doubleheader/scheduled game identity remains distinct.


def test_known_pnl_unknown_bounds_fees_and_edge_keep_distinct_meanings():
    known=row();unknown=row('b',at=110,quantity=20,price=.2,fee=.2,settlement=None);unknown['fair_point']=.1
    m=report.metrics([known,unknown])
    assert m['known_outcomes']==1 and m['unknown_outcomes']==1
    assert m['known_net_pnl']==pytest.approx(-7.1)
    assert m['loose_final_pnl_bounds']==pytest.approx([-23.3,-3.3])
    assert m['fees']==pytest.approx(.3)
    assert m['yes_premium']==pytest.approx(7.) and m['payout_notional']==30
    assert m['point_edge']==pytest.approx(2.7)
    times,equity=report.curve([known,unknown],90,200)
    assert [t.timestamp() for t in times]==[90,100,200]
    assert equity[-1]==pytest.approx(9992.9)  # Settlement is booked at trade time only for this display.
    assert report.curve([known,unknown],90,200,'edge')[1][-1]==pytest.approx(2.7)
    assert report.curve([known,unknown],90,200,'payout')[1][-1]==30


def test_leg_facets_are_contributions_from_one_shared_risk_portfolio():
    first=row('two-leg',quantity=100,fee=.1,legs=2)
    second=row('three-leg',at=101,quantity=100,fee=.1,legs=3)
    second['buckets']['contract'].append('c');second['buckets']['fixture'].append('fixture-c')
    result=run_backtest([first,second],90,200,BacktestConfig(entry_basis='point'),True)
    accepted={d['evaluation_id'] for d in result['decisions'] if d['accepted']}
    assert accepted=={'two-leg'}
    assert next(d for d in result['decisions'] if d['evaluation_id']=='three-leg')['reason']=='contract_risk_limit'
    selected=[r for r in (first,second) if r['evaluation_id'] in accepted]
    facets=[[r for r in selected if report.cuts(r)['legs']==str(n)] for n in (2,3,4)]
    assert sum(report.metrics(rs)['known_net_pnl'] for rs in facets)==pytest.approx(report.metrics(selected)['known_net_pnl'])
    assert sum(report.curve(rs,90,200)[1][-1]-10000 for rs in facets)==pytest.approx(report.curve(selected,90,200)[1][-1]-10000)
    # Reinitializing a separate portfolio for the three-leg group would accept it;
    # the report must instead attribute the existing shared decisions above.
    assert run_backtest([second],90,200,BacktestConfig(entry_basis='point'),True)['decisions'][0]['accepted']


def exchange_fixture(tmp_path):
    ticker='KXMLBGAME-26SEP051305NYYBAL-NYY';exchange=tmp_path/'exchange';exchange.mkdir()
    (exchange/'polymarket_mapping_reviewed.json').write_text(json.dumps({ticker:{'status':'matched','token':'123','fee_rate':.03}}))
    gz(exchange/'kalshi_parts'/(ticker+'.part000.json.gz'),{'status':200,'params':{'start_ts':100,'end_ts':300,'period_interval':1},
       'payload':{'ticker':ticker,'candlesticks':[
           {'end_period_ts':120,'yes_bid':{'close_dollars':.39},'yes_ask':{'close_dollars':.41}},
           {'end_period_ts':180,'yes_bid':{'close_dollars':.79},'yes_ask':{'close_dollars':.81}}]}})
    gz(exchange/'polymarket/123.json.gz',{'status':200,'params':{'startTs':100,'endTs':300},
       'payload':{'history':[{'t':120,'p':.45},{'t':180,'p':.85}]}})
    return ticker,exchange


def test_historical_exchange_points_wait_for_publication_and_require_coverage(tmp_path):
    ticker,exchange=exchange_fixture(tmp_path);provider=replay.SourceFairs(exchange)
    before,_,_=provider.fair(ticker,179.999)
    assert 'kalshi' not in before and 'polymarket' not in before
    available,context,errors=provider.fair(ticker,180.)
    assert available['kalshi'][0].point==pytest.approx(.4)
    assert available['polymarket'][0].point==pytest.approx(.45)
    assert context['kalshi']['available_at']<=180 and context['polymarket']['available_at']<=180
    assert all(model not in available for model in ('pinnacle','blend','stronger_pinnacle'))
    assert errors['blend']=='Pinnacle_MLB_history_unavailable'
    at_next,_,_=provider.fair(ticker,240.)
    assert at_next['kalshi'][0].point==pytest.approx(.8)
    assert at_next['polymarket'][0].point==pytest.approx(.85)
    after,_,errors=provider.fair(ticker,361.)
    assert not after and errors['kalshi']=='uncovered_kalshi_timestamp' and errors['polymarket']=='uncovered_PM_timestamp'


def pinnacle_bundle(path,ticker,coverage):
    spec={'kalshi_ticker':ticker,'mapping_scope':'ordinary_completed_game_only','mapping_reference':'synthetic:reviewed-paired-outcomes',
          'yes_history':[{'createdAt':120,'price':2.,'limit':100.},{'createdAt':160,'price':3.,'limit':100.}],
          'no_history':[{'createdAt':120,'price':2.,'limit':100.},{'createdAt':160,'price':1.5,'limit':100.}]}
    if coverage is not None:spec['coverage']=coverage
    path.write_text(json.dumps({'schema_version':1,'sport':'mlb','mappings':[spec]}));return path


@pytest.mark.parametrize('coverage',[None,{'start_at':100,'end_at':300,'complete':False,'source_reference':'request'},
                                     {'start_at':100,'end_at':300,'complete':True}])
def test_pinnacle_bundle_requires_explicit_complete_request_coverage(tmp_path,coverage):
    ticker,exchange=exchange_fixture(tmp_path)
    bundle=pinnacle_bundle(tmp_path/'pin.json',ticker,coverage)
    with pytest.raises(ValueError,match='verified_Pinnacle_history_request_coverage_required'):
        replay.SourceFairs(exchange,bundle)


def test_pinnacle_asof_delay_and_coverage_do_not_carry_prices_across_unobserved_time(tmp_path):
    ticker,exchange=exchange_fixture(tmp_path)
    bundle=pinnacle_bundle(tmp_path/'pin.json',ticker,{'start_at':100,'end_at':170,'complete':True,'source_reference':'synthetic:complete-request'})
    provider=replay.SourceFairs(exchange,bundle)
    before,_,_=provider.fair(ticker,149.999)
    assert 'pinnacle' not in before
    old,context,_=provider.fair(ticker,189.999)
    assert old['pinnacle'][0].point==pytest.approx(.5)
    assert context['pinnacle']['side_times']==[120,120]
    assert 'blend' in old and 'stronger_pinnacle' in old
    new,context,_=provider.fair(ticker,190.)
    assert new['pinnacle'][0].point==pytest.approx(1/3)
    assert context['pinnacle']['side_times']==[160,160]
    uncovered,_,errors=provider.fair(ticker,200.001)
    assert all(model not in uncovered for model in ('pinnacle','blend','stronger_pinnacle'))
    assert errors['pinnacle']=='uncovered_Pinnacle_timestamp'


def test_common_cohort_report_reruns_capacity_instead_of_subsetting_old_fills(tmp_path,monkeypatch):
    start=report.stamp('2026-09-05T05:00:00Z');end=report.stamp('2026-09-06T05:00:00Z')
    extra=row('off-intersection',at=start+100,quantity=100)
    common=row('shared-print',at=start+101,quantity=100)
    pm=deepcopy(common);pm['model']='polymarket'
    for r in (extra,common,pm):
        r['settled_at']=end+100;r['source'].update(sampling_method='census',start_at=end)
    inputs=tmp_path/'input.json';inputs.write_text(json.dumps({'run_id':'synthetic:common-capacity','opportunities':[extra,common,pm]}))
    # Verify report/accounting execution; chart rendering has its own artifact review.
    monkeypatch.setattr(report.plt.Figure,'savefig',lambda *a,**k:None)
    monkeypatch.setattr(report.plt.Figure,'tight_layout',lambda *a,**k:None)
    output=tmp_path/'report'
    monkeypatch.setattr(sys,'argv',['mlb_model_report.py','--input',str(inputs),'--out',str(output),'--common-only'])
    report.main()
    with gzip.open(output/'constrained_fills.jsonl.gz','rt') as f:fills=[json.loads(line) for line in f]
    assert {(r['model'],r['fill_id']) for r in fills}=={('kalshi','shared-print'),('polymarket','shared-print')}
    manifest=json.loads((output/'manifest.json').read_text())
    assert manifest['cohort_basis']=='common_available_model_intersection_portfolios_rerun'
    assert manifest['daily_sharpe'] is None and manifest['daily_return_variance'] is None
    assert manifest['three_source_status']=='missing_Pinnacle_history_not_a_zero_fill_result'


def test_replay_excludes_exact_sixty_second_pregame_boundary(tmp_path,monkeypatch):
    base=report.stamp('2026-09-05T05:00:00Z');cohort=tmp_path/'cohort';cohort.mkdir();exchange=tmp_path/'exchange';exchange.mkdir()
    tickers=['KXMLBGAME-26SEP051305NYYBAL-NYY','KXMLBGAME-26SEP051840SDCIN-SD']
    legs=[{'market_ticker':t,'side':'yes'} for t in tickers]
    gz(cohort/'underlying_markets.json.gz',{t:{'strike_type':'structured'} for t in tickers})
    gz(cohort/'combo_markets.json.gz',{'COMBO':{'mve_selected_legs':legs}})
    (exchange/'polymarket_mapping_reviewed.json').write_text('{}')
    c={'nlegs':2,'distinct_fixtures':True,'earliest_scheduled_start':base+160,'series':['KXMLBGAME'],'start_basis':'synthetic:scheduled'}
    with gzip.open(cohort/'candidate_trades.jsonl.gz','wt') as f:
        for identifier,at in [('before',base+99.999),('boundary',base+100)]:
            t={'trade_id':identifier,'ticker':'COMBO','created_time':report.datetime.fromtimestamp(at,report.timezone.utc).isoformat(),
               'taker_side':'yes','count_fp':'10','yes_price_dollars':'.3'}
            f.write(json.dumps({'trade':t,'classification':c,'settlement_at':base+300,'settlement_value':0.,'maker_fee_dollars':.1,
                                'sampling_method':'census','source_window':[base,base+86400],'fee_basis':'synthetic:fixed'})+'\n')
    class FakeFairs:
        def __init__(self,*args):pass
        def fair(self,*args):return {'kalshi':(Interval(.2,.2,.2),True,1.)},{},{}
    monkeypatch.setattr(replay,'SourceFairs',FakeFairs)
    out=tmp_path/'out';monkeypatch.setattr(sys,'argv',['mlb_model_replay.py','--cohort',str(cohort),'--exchange',str(exchange),'--out',str(out)])
    replay.main()
    result=json.loads((out/'opportunities.json').read_text())
    assert [r['evaluation_id'] for r in result['opportunities']]==['before']
    hashed=result['identity']['input_sha256']
    assert str(cohort/'combo_markets.json.gz') in hashed
    assert any(p.endswith('/src/combos/historical_fair.py') for p in hashed)
