from copy import deepcopy
import json
from combos.research_quote_consumer import ResearchQuoteConsumer
from combos.scenario_worker import ScenarioWorker
from combos.event_store import EventStore

RUNTIME={'mode':'shadow','mappings':[{'market_key':k,'fixture_key':k,'market_type':'synthetic'} for k in ('a','b')],
 'combo_terms':{'M':{'fee_reference':'test','verified_at':0,'valid_until':1000,'maker_fee_rate':0,'price_ranges':[{'start':0,'end':1,'step':'.01'}]}}}
POLICY={'reserve_fraction':0,'edge_per_combo':.003,'native_stake_usd_scale':1,'capacity_mode':'all_admitted_fill_no_release','capital_dollars':10000,'caps':{'contract':10,'combo':10,'fixture':10}}
class Pricing:
    def consume(self,e,evaluation_at=None,price_rfqs=True):
        if e['kind']!='rfq' or not price_rfqs:return None
        return {'source_seq':e['seq'],'rfq_id':e['payload']['id'],'status':'scenario_priced','scenarios':[{'assumed_usd_per_native_unit':1,'independent_combo_point':.25,'independent_marginal_upper':.3,'legs':[{'market_key':k,'side':'yes','pricing_guard':{'quote_allowed':True,'risk_multiplier':1}} for k in ('a','b')]}]}
def event(seq=1):return {'seq':seq,'kind':'rfq','received_at':100,'source':'test','payload':{'id':str(seq),'creator_id':'creator','market_ticker':'M1','contracts_fp':'10'}}


def test_causal_creator_block_and_expiry():
    c=ResearchQuoteConsumer(Pricing(),RUNTIME,POLICY)
    assert c.consume(event(),101)['research_policy']['status']=='reserved_scenario'
    c.consume({'seq':2,'kind':'creator_policy','received_at':102,'payload':{'creator_id':'creator','state':{'status':'cooldown','expires_at':105}}})
    assert c.consume(event(3),103)['research_policy']['reason']=='creator_cooldown'
    assert c.consume(event(4),106)['research_policy']['creator_status']=='watch'


def test_restart_rebuilds_held_risk(tmp_path):
    s=EventStore(tmp_path/'input');e=event();s.append('rfq','test',e['payload'],'one',100)
    def consumer():return ResearchQuoteConsumer(Pricing(),RUNTIME,POLICY)
    w=ScenarioWorker(s,str(tmp_path/'out'),consumer(),{});w.step(clock=lambda:101)
    first=json.loads(w.db.execute('select result from candidate_decisions').fetchone()[0]);assert first['quote_sizing_and_risk_applied']
    w.close();c=consumer();w=ScenarioWorker(s,str(tmp_path/'out'),c,{})
    assert len(c.risk.active)==1
    s.append('rfq','test',event(2)['payload'],'two',101);w.step(clock=lambda:102)
    second=json.loads(w.db.execute('select result from candidate_decisions order by source_seq desc limit 1').fetchone()[0]);assert second['pricing']['research_policy']['status']=='risk_rejected'
    assert w.db.execute('select count(*) from candidate_decisions').fetchone()[0]==2
    w.close();s.close()


def test_strictest_leg_guard_reduces_admission():
    c=ResearchQuoteConsumer(Pricing(),RUNTIME,POLICY)
    e=event();pricing=Pricing().consume(e)
    pricing['scenarios'][0]['legs'][1]['pricing_guard']['risk_multiplier']=.5
    r=c.evaluate(e,pricing,101)
    assert r['status']=='risk_rejected' and r['pricing_risk_multiplier']==.5
    assert set(r['admission']['binding_limits'])=={'contract','combo','fixture'}
    assert not c.risk.active


def test_missing_and_halted_guards_cannot_admit():
    for guard,reason in [(None,'pricing_guard_missing'),({'quote_allowed':False,'risk_multiplier':1},'pricing_guard_halt')]:
        c=ResearchQuoteConsumer(Pricing(),RUNTIME,POLICY);e=event();p=Pricing().consume(e)
        p['scenarios'][0]['legs'][0]['pricing_guard']=guard
        r=c.evaluate(e,p,101)
        assert r['reason']==reason and not c.risk.active


def test_explicit_legacy_ablation_reports_guard_disabled():
    c=ResearchQuoteConsumer(Pricing(),RUNTIME,{**POLICY,'apply_pricing_risk_multiplier':False})
    e=event();p=Pricing().consume(e)
    for l in p['scenarios'][0]['legs']:l.pop('pricing_guard')
    r=c.evaluate(e,p,101)
    assert r['status']=='reserved_scenario' and r['pricing_risk_multiplier_applied'] is False


def test_defensive_guard_after_restart_counts_previous_hold(tmp_path):
    class DefensivePricing(Pricing):
        def consume(self,e,evaluation_at=None,price_rfqs=True):
            r=super().consume(e,evaluation_at,price_rfqs)
            if r and e['seq']>1:
                r['scenarios'][0]['legs'][0]['pricing_guard']['risk_multiplier']=.5
            return r
    s=EventStore(tmp_path/'input')
    e=event();e['payload']['contracts_fp']='4';s.append('rfq','test',e['payload'],'one',100)
    def consumer():return ResearchQuoteConsumer(DefensivePricing(),RUNTIME,POLICY)
    w=ScenarioWorker(s,str(tmp_path/'out'),consumer(),{});w.step(clock=lambda:101);w.close()
    c=consumer();w=ScenarioWorker(s,str(tmp_path/'out'),c,{})
    assert len(c.risk.active)==1
    e=event(2);e['payload']['contracts_fp']='4';s.append('rfq','test',e['payload'],'two',101)
    w.step(clock=lambda:102)
    r=json.loads(w.db.execute('select result from candidate_decisions order by source_seq desc limit 1').fetchone()[0])['pricing']['research_policy']
    assert r['pricing_risk_multiplier']==.5 and r['status']=='risk_rejected'
    assert len(c.risk.active)==1
    w.close();s.close()
