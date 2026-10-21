import json
from copy import deepcopy
import pytest
from test_runtime import config, rfq, seed, add, drain, decisions, observation
from combos.event_store import EventStore
from combos.creator_service import CreatorService
from combos.shadow_engine import ShadowEngine
from combos.risk import RiskLedger
from combos.inventory_fitting import variance_delta, evaluate


def policy():
    c=config()
    c.update(minimum_net_edge_per_share=.003,per_contract_dollars=1000,per_combo_dollars=1000,
             per_fixture_dollars=80,maximum_ticket_gross_liability_dollars=250)
    c['moneyline_offset']={'enabled':True,'eligible_scope':'exact_full_game_moneyline_distinct_fixture_team_match',
                          'net_contract_and_fixture_risk_buckets':True,'cash_collateral_credit':False}
    c['inventory_fitting']={'enabled':True,'minimum_net_edge_per_share':.001,'fixture_pressure_trigger':.9,
                          'paper_trade_matching':True}
    c['combo_terms']['COMBO']['price_ranges']=[{'start':0,'end':1,'step':.0001}]
    return c


def setup(tmp_path):
    s=EventStore(tmp_path/'events.sqlite');c=policy();e=ShadowEngine(s,c,replay=True);cr=CreatorService(s)
    seed(s);drain(cr,e)
    return s,c,e,cr


def tape(trade_id='t1',qty=10,price=.99,ts=100.1,side='yes'):
    return {'trade_id':trade_id,'market_ticker':'COMBO-one','count_fp':str(qty),
            'yes_price_dollars':str(price),'ts_ms':ts*1000,'taker_side':side}


def test_variance_opposing_is_not_automatically_a_hedge():
    a=[('a','a',1,True),('b','b',1,True)]
    b=[('a','a',-1,True),('c','c',1,True)]
    probs=dict(a=.5,b=.5,c=.5)
    assert variance_delta(b,100,[(a,100)],probs)>0
    assert variance_delta(b,50,[(a,100)],probs)<0


@pytest.mark.parametrize('signed_first',[True,False])
def test_mixed_pools_share_one_cap(tmp_path,signed_first):
    s=EventStore(tmp_path/'risk.sqlite');c=policy();c.update(per_fixture_dollars=100)
    ledger=RiskLedger(s,c)
    buckets={'fixture':['a'],'contract':['a'],'combo':['a']}
    with s.transaction():
        for i,signed in enumerate([signed_first,not signed_first]):
            result=ledger.reserve(str(i),'creator',80,buckets,200,{},signed_buckets={'fixture':[{'key':'a','side':1}]} if signed else {})
            assert result['allowed']==(i==0)
        assert result['reason']=='fixture_risk_limit'


def test_filled_credit_partial_cash_and_expiry(tmp_path):
    s,c,e,cr=setup(tmp_path)
    add(s,'rfq',rfq(quantity=100),'r1',100);drain(cr,e)
    q=decisions(s)[0];assert q['status']=='shadow_quote'
    before=e.risk.available()
    assert e.risk.bucket_state('fixture:a:A-B')['credits'][-1]==0
    add(s,'paper_trade',tape(qty=40),'t1',100.1);drain(cr,e)
    states=s.db.execute('SELECT * FROM reservations ORDER BY id').fetchall()
    assert sorted(r['status'] for r in states)==['reserved','simulated_filled']
    assert sum(json.loads(r['context'])['quantity'] for r in states)==100
    assert e.risk.bucket_state('fixture:a:A-B')['credits'][-1]>0
    assert e.risk.available()==before  # risk-credit is never cash-credit
    add(s,'heartbeat',{},'expire',104);drain(cr,e)
    assert s.db.execute("SELECT COUNT(*) FROM reservations WHERE status='simulated_filled'").fetchone()[0]==1
    assert e.risk.bucket_state('fixture:a:A-B',True)['risk_dollars']>0
    s.close()
    s=EventStore(tmp_path/'events.sqlite');e=ShadowEngine(s,c,replay=True)
    assert e.risk.bucket_state('fixture:a:A-B')['credits'][-1]>0


def test_trade_volume_dedup_and_fifo(tmp_path):
    s,c,e,cr=setup(tmp_path)
    for i in range(2):add(s,'rfq',rfq('r'+str(i),quantity=10),'r'+str(i),100)
    drain(cr,e)
    add(s,'paper_trade',tape(qty=15),'t1',100.1);drain(cr,e)
    qty=lambda:sum(json.loads(r[0])['quantity'] for r in s.db.execute("SELECT context FROM reservations WHERE status='simulated_filled'"))
    assert qty()==15
    add(s,'paper_trade',tape(qty=15),'duplicate',100.2);drain(cr,e)
    assert qty()==15
    s.close();s=EventStore(tmp_path/'events.sqlite');e=ShadowEngine(s,c,replay=True);cr=CreatorService(s)
    add(s,'paper_trade',tape(qty=15),'duplicate_restart',100.3);drain(cr,e)
    assert qty()==15


@pytest.mark.parametrize('changes',[{'ts_ms':99900},{'taker_side':'no'},{'yes_price_dollars':'.01'},
                                  {'is_block_trade':True},{'count_fp':'nan'},{'ts_ms':104000}])
def test_ineligible_print_does_not_fill(tmp_path,changes):
    s,c,e,cr=setup(tmp_path);add(s,'rfq',rfq(),'r1',100);drain(cr,e)
    p=tape();p.update(changes);add(s,'paper_trade',p,'bad',100.1);drain(cr,e)
    assert s.db.execute("SELECT COUNT(*) FROM reservations WHERE status='simulated_filled'").fetchone()[0]==0


def test_full_requested_size_not_ticket_clipped(tmp_path):
    s,c,e,cr=setup(tmp_path)
    add(s,'rfq',rfq(quantity=1000),'big',100);drain(cr,e)
    assert decisions(s)[0]['reason']=='full_request_exceeds_ticket_liability_cap'


def test_selective_floor_and_fill_time_revalidation(tmp_path):
    s,c,e,cr=setup(tmp_path)
    add(s,'rfq',rfq(quantity=100),'r1',100);drain(cr,e)
    q=decisions(s)[0]
    assert q['required_net_edge_per_share']==.003
    assert q['inventory_fitting']['reason']=='no_pressured_filled_fixture'
    add(s,'paper_trade',tape(qty=100),'t1',100.1);drain(cr,e)
    request=rfq('hedge',quantity=30)
    request['mve_selected_legs'][0]['side']='no'
    request['mve_selected_legs'][1]['side']='no'
    add(s,'rfq',request,'hedge',100.2);drain(cr,e)
    q=decisions(s)[-1]
    assert q['status']=='shadow_quote',q
    assert q['inventory_fitting']['eligible'],q['inventory_fitting']
    assert q['required_net_edge_per_share']==.001
    add(s,'paper_trade',tape('t2',qty=10,ts=100.3),'t2',100.3);drain(cr,e)
    fills=[x['payload'] for x in s.read(limit=1000) if x['kind']=='simulation_fill_confirmed']
    assert fills[-1]['required_net_edge_per_share']==.001
    assert fills[-1]['inventory_fitting']['variance_delta_dollars_squared']<0
    assert fills[-1]['actual_exchange_fill'] is False


def test_pending_hedge_never_earns_credit(tmp_path):
    s,c,e,cr=setup(tmp_path)
    add(s,'rfq',rfq(quantity=100),'r1',100);drain(cr,e)
    request=rfq('opposite',quantity=30);request['mve_selected_legs'][0]['side']='no'
    add(s,'rfq',request,'opposite',100.1);drain(cr,e)
    assert decisions(s)[-1]['required_net_edge_per_share']==.003
    assert e.risk.bucket_state('fixture:a:A-B')['credits']=={-1:0,1:0}


def test_partial_fee_rounding_cannot_overdraw_hold(tmp_path):
    s=EventStore(tmp_path/'risk.sqlite');c=policy();ledger=RiskLedger(s,c)
    from combos.pricing import short_yes_economics
    cost=short_yes_economics(1,.5,0,.035)['maximum_loss']
    with s.transaction():
        assert ledger.reserve('r','c',cost,{'fixture':['a'],'contract':['a'],'combo':['a']},200,
                              {'quantity':1,'yes_ask':.5,'maker_fee_rate':.035})['allowed']
        with pytest.raises(ValueError,match='partial_fill_fee_rounding'):
            ledger.fill('r',.06,.5,100,1)
        assert json.loads(s.db.execute('SELECT context FROM reservations').fetchone()[0])['quantity']==1


def test_unpriceable_held_inventory_prevents_discount(tmp_path,monkeypatch):
    s,c,e,cr=setup(tmp_path)
    add(s,'rfq',rfq(quantity=100),'r1',100);drain(cr,e)
    add(s,'paper_trade',tape(qty=100),'t1',100.1);drain(cr,e)
    request=rfq('opposite',quantity=30)
    for leg in request['mve_selected_legs']:leg['side']='no'
    pricing=e.fair(request['mve_selected_legs'],100.2)
    assert evaluate(e,pricing,30,.26,0,100.2)['eligible']
    def stale(*args):raise ValueError('stale_held_feed')
    monkeypatch.setattr(e,'fair',stale)
    result=evaluate(e,pricing,30,.26,0,100.2)
    assert not result['eligible'] and result['reason']=='stale_held_feed'


def test_partial_fill_rollback_is_atomic(tmp_path,monkeypatch):
    s,c,e,cr=setup(tmp_path)
    add(s,'rfq',rfq(quantity=100),'r1',100);drain(cr,e)
    before=e.risk.available()
    add(s,'paper_trade',tape(qty=40),'t1',100.1);cr.step()
    append=s.append
    def crash(kind,*args,**kwargs):
        if kind=='simulation_fill_confirmed':raise RuntimeError('interrupted')
        return append(kind,*args,**kwargs)
    monkeypatch.setattr(s,'append',crash)
    with pytest.raises(RuntimeError,match='interrupted'):e.step()
    assert e.risk.available()==before
    assert s.db.execute('SELECT COUNT(*) FROM reservations').fetchone()[0]==1
    assert s.db.execute('SELECT COUNT(*) FROM shadow_paper_trades').fetchone()[0]==0
    monkeypatch.setattr(s,'append',append);drain(cr,e)
    assert s.db.execute("SELECT COUNT(*) FROM reservations WHERE status='simulated_filled'").fetchone()[0]==1


def test_partial_markout_uses_fill_size_not_full_quote():
    from scripts.shadow_fill_edge_report import fill_markouts
    marks={'5':{'status':'observed','reference':{'value':.2},'markout_net_edge_dollars':30}}
    result=fill_markouts({'quantity':10,'fill_price':.3,'maker_fee_rate':0},marks)
    assert result['5']['markout_net_edge_dollars']==pytest.approx(1)
    assert marks['5']['markout_net_edge_dollars']==30


@pytest.mark.parametrize('floor',[0,float('nan'),.003,.005])
def test_invalid_floor_cannot_initialize(tmp_path,floor):
    c=policy();c['inventory_fitting']['minimum_net_edge_per_share']=floor
    with pytest.raises(ValueError,match='invalid_inventory_edge_floor'):
        ShadowEngine(EventStore(tmp_path/'invalid.sqlite'),c,replay=True)


def test_collector_retains_only_recent_rfq_trade_candidates(tmp_path,monkeypatch):
    import asyncio
    from combos import live_collectors
    c=policy();sent=[]
    packets=[{'type':'trade','msg':tape('before')},
             {'type':'rfq_created','msg':rfq()},
             {'type':'trade','msg':tape('after')},
             {'type':'trade','msg':dict(tape('unrelated'),market_ticker='OTHER')}]
    class Socket:
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def send(self,payload):sent.append(json.loads(payload))
        async def recv(self):
            if packets:return json.dumps(packets.pop(0))
            await asyncio.Event().wait()
    monkeypatch.setattr(live_collectors,'connect',lambda *args,**kwargs:Socket())
    monkeypatch.setattr(live_collectors,'auth_headers',lambda:{})
    asyncio.run(live_collectors.collect(tmp_path/'collector.sqlite',c,'kalshi',.05))
    s=EventStore(tmp_path/'collector.sqlite')
    rows=[e['payload'] for e in s.read(limit=1000) if e['kind']=='paper_trade']
    assert [r['trade_id'] for r in rows]==['after']
    assert all(p['cmd']=='subscribe' for p in sent)


def test_comparison_launcher_records_policy_without_starting_services(tmp_path,monkeypatch):
    from scripts import run_shadow
    import sys
    from types import SimpleNamespace
    c=policy();path=tmp_path/'config.json';path.write_text(json.dumps(c))
    commands=[]
    def run(command,**kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0,stdout='')
    monkeypatch.setattr(run_shadow,'load_env',lambda path:None)
    monkeypatch.setattr(run_shadow,'run',run)
    monkeypatch.setattr(sys,'argv',['run_shadow.py','--config',str(path),'--run-dir',str(tmp_path/'run'),
                                  '--skip-preflight','--hedge-floor-cents','0.05'])
    assert run_shadow.main()==0
    resolved=json.loads((tmp_path/'run/shadow_policy.json').read_text())
    assert resolved['inventory_fitting']['minimum_net_edge_per_share']==.0005
    assert resolved['minimum_net_edge_per_share']==.003
    assert all(str(tmp_path/'run/shadow_policy.json') in command for command in commands)


def test_default_deployment_initializes_with_guards_intact(tmp_path):
    from pathlib import Path
    from combos.weighted_fair import WeightPolicy
    root=Path(__file__).resolve().parents[1]
    c=json.loads((root/'config/runtime_nfl_authorized_shadow_20260910.json').read_text())
    w=WeightPolicy(**json.loads((root/'config/weighting.json').read_text()))
    s=EventStore(tmp_path/'deployment.sqlite');e=ShadowEngine(s,c,w)
    assert e.config['inventory_fitting']['minimum_net_edge_per_share']==.001
    assert e.config['minimum_net_edge_per_share']==.003
    assert c['correlation_tail']['enabled'] and c['correlation_rho']==.05
    assert c['quote_reference']['marginal_fraction']==0
    assert w.consensus_lean_enabled
    assert e.pricer.leg_model.policy.liquidity_weighted_pair_fallback
    assert c['orders_enabled'] is False and c['live_enabled'] is False
    assert e.risk.available()==10000*10000
    s.close()
