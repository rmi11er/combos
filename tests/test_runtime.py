from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from combos.event_store import EventStore
from combos.creator_service import CreatorService,creator_state
from combos.risk import RiskLedger
from combos.shadow_engine import ShadowEngine,quote_price
from combos.live_books import Books


def config():
    c=json.loads((ROOT/'config/runtime.json').read_text())
    c.update(per_contract_dollars=100,per_combo_dollars=100,per_fixture_dollars=100,correlation_rho=0)
    c['mappings']=[{'market_key':key+':A-B:moneyline:A','fixture_key':key+':A-B','sport':'NFL','mapping_reference':'synthetic:reviewed',
        'market_type':'moneyline','kalshi_ticker':'KXNFLGAME-'+key,'polymarket_yes_token':'pm-'+key,'start_at':10000,
        'fees':{'kalshi':{'rate':0,'reference':'synthetic:zero'},'polymarket':{'rate':0,'reference':'synthetic:zero'}}}
        for key in ('a','b')]
    c['combo_terms']={'COMBO':{'maker_fee_rate':0,'fee_reference':'synthetic:zero',
        'price_ranges':[{'start':0,'end':1,'step':.01}]}}
    return c


def rfq(identifier='r1',creator='c1',quantity=10):
    return {'id':identifier,'creator_id':creator,'market_ticker':'COMBO-one','contracts_fp':str(quantity),
            'mve_selected_legs':[{'market_ticker':'KXNFLGAME-a','side':'yes'},{'market_ticker':'KXNFLGAME-b','side':'yes'}]}


def observation(key,venue,at=100,point=.5):
    return {'market_key':key+':A-B:moneyline:A' if key in ('a','b','c','d') else key,'venue':venue,'observed_at':at,'available_at':at,'active':True,
        'source_reference':'synthetic:book','mapping_reference':'synthetic:reviewed','fee_reference':'synthetic:zero',
        'yes_bid':point-.02,'yes_ask':point+.02,'yes_bid_size':100,'yes_ask_size':100,
        'size_unit':'payout_dollars','taker_rate':0,'decimal_odds_yes':1/point,'decimal_odds_no':1/(1-point),
        'max_stake_yes':50,'max_stake_no':50,'limit_currency':'USD','limit_unit':'stake'}


def seed(store,at=100,point=.5):
    with store.transaction():
        for key in ('a','b'):
            for venue in ('kalshi','polymarket','pinnacle'):
                store.append('observation','synthetic',observation(key,venue,at,point),f'{key}:{venue}:{at}',at)


def add(store,kind,payload,key,at):
    with store.transaction():return store.append(kind,'synthetic',payload,key,at)


def drain(creators,engine):
    for _ in range(100):
        a=creators.step();b=engine.step()
        if not a and not b:return
    raise AssertionError('consumers did not drain')


def decisions(store):
    pointers=[json.loads(row[0]) for row in store.db.execute('SELECT result FROM decisions ORDER BY source_seq')]
    return [store.read(p['decision_event_seq']-1,1)[0]['payload'] for p in pointers]


def test_atomic_event_rollback_and_dedup(tmp_path):
    store=EventStore(tmp_path/'bus.sqlite')
    store.register('test',{'v':1})
    with pytest.raises(RuntimeError):
        with store.transaction():
            store.append('test','synthetic',{'x':1},'one',100)
            store.checkpoint('test',1)
            raise RuntimeError('crash')
    assert store.read()==[] and store.cursor('test')==0
    first=add(store,'test',{'x':1},'one',100)
    assert add(store,'test',{'x':1},'one',100)==first
    with pytest.raises(ValueError,match='conflicting'):add(store,'test',{'x':2},'one',100)
    store.close()


def test_collection_mapping_cannot_price_until_payoff_review_and_fees_valid(tmp_path):
    store=EventStore(tmp_path/'review.sqlite');c=config()
    c['mappings'][0]['pricing_block_reason']='pinnacle_payoff_mapping_unreviewed'
    engine=ShadowEngine(store,c,replay=True)
    with pytest.raises(ValueError,match='pinnacle_payoff_mapping_unreviewed'):
        engine.fair(rfq()['mve_selected_legs'],100)
    c['mappings'][1]['fixture_key']='a:A-B'
    with pytest.raises(ValueError,match='same_fixture'):
        engine.fair(rfq()['mve_selected_legs'],100)
    c['mappings'][1]['fixture_key']='b:A-B'
    del c['mappings'][0]['pricing_block_reason']
    c['mappings'][0]['fees']['kalshi']['valid_until']=100
    with pytest.raises(ValueError,match='leg_fee_metadata_expired'):
        engine.fair(rfq()['mve_selected_legs'],100)
    store.close()


def test_expired_combo_fees_do_not_create_reservations(tmp_path):
    store=EventStore(tmp_path/'fees.sqlite');c=config();c['combo_terms']['COMBO']['valid_until']=100
    creators=CreatorService(store);engine=ShadowEngine(store,c,replay=True);seed(store)
    add(store,'rfq',rfq(),'r1',100);drain(creators,engine)
    assert decisions(store)[0]['reason']=='combo_fee_metadata_expired'
    assert engine.risk.available()==100000000
    store.close()


def test_settled_leg_is_not_priced_from_an_old_exchange_book(tmp_path):
    store=EventStore(tmp_path/'settled.sqlite');c=config()
    creators=CreatorService(store);engine=ShadowEngine(store,c,replay=True);seed(store)
    request=rfq();request['mve_selected_legs'][0]['yes_settlement_value_dollars']='0.5000'
    add(store,'rfq',request,'r1',100);drain(creators,engine)
    assert decisions(store)[0]['reason']=='settled_leg_requires_scalar_pricing'
    assert engine.risk.available()==100000000
    store.close()


def test_expired_leg_fees_keep_raw_book_but_disable_observation():
    c=config();c['mappings'][0]['fees']['kalshi']['valid_until']=100
    books=Books('kalshi',c['mappings'])
    output=books.consume({'type':'orderbook_snapshot','msg':{'market_ticker':'KXNFLGAME-a',
        'yes_dollars_fp':[['.4','100']],'no_dollars_fp':[['.5','100']]}},100,'raw:snapshot')
    assert not output[0][1]['active']
    assert output[0][1]['invalid_reason']=='fee_metadata_expired'
    assert books.books['KXNFLGAME-a']['bid']


def test_late_unsubscribed_delta_does_not_reset_other_books_or_reuse_old_ladder():
    books=Books('kalshi',config()['mappings']);books.set_targets({'KXNFLGAME-a','KXNFLGAME-b'})
    def snapshot(ticker,seq):
        return {'type':'orderbook_snapshot','sid':1,'seq':seq,'msg':{'market_ticker':ticker,
            'yes_dollars_fp':[['.4','100']],'no_dollars_fp':[['.5','100']]}}
    def delta(seq):
        return {'type':'orderbook_delta','sid':1,'seq':seq,'msg':{'market_ticker':'KXNFLGAME-a',
            'price_dollars':'.4','delta_fp':'1','side':'yes'}}
    books.consume(snapshot('KXNFLGAME-a',1),100,'raw:1')
    books.consume(snapshot('KXNFLGAME-b',2),100,'raw:2')
    books.set_targets({'KXNFLGAME-b'})
    assert books.consume(delta(3),101,'raw:3')[0][1]['reason']=='unsubscribed_book'
    assert 'KXNFLGAME-b' in books.books and 'KXNFLGAME-a' not in books.books
    books.set_targets({'KXNFLGAME-a','KXNFLGAME-b'})
    assert books.consume(delta(4),102,'raw:4')[0][1]['reason']=='awaiting_fresh_snapshot'
    books.consume(snapshot('KXNFLGAME-a',5),102,'raw:5')
    assert books.consume(delta(6),103,'raw:6')[0][1]['active']
    with pytest.raises(ValueError,match='sequence_gap'):
        books.consume(delta(8),104,'raw:8')


def test_runtime_manifest_rejects_changed_code_and_configuration(tmp_path,monkeypatch):
    import hashlib,importlib.util
    from combos.weighted_fair import WeightPolicy
    spec=importlib.util.spec_from_file_location('runtime_manifest_cli',ROOT/'scripts/runtime.py')
    cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)
    monkeypatch.setattr(cli,'ROOT',tmp_path)
    source=tmp_path/'pinned.py';source.write_text('original')
    store=EventStore(tmp_path/'manifest.sqlite');c=config();weights=WeightPolicy()
    store.put('runtime','manifest',{'config':c,'weights':weights.__dict__,
        'code_sha256':{'pinned.py':hashlib.sha256(source.read_bytes()).hexdigest()}})
    cli.validate_manifest(store,c,weights)
    changed=deepcopy(c);changed['capital_dollars']=999
    with pytest.raises(ValueError,match='config differs'):cli.validate_manifest(store,changed,weights)
    source.write_text('changed')
    with pytest.raises(ValueError,match='source differs'):cli.validate_manifest(store,c,weights)
    store.close()


def test_creator_cooldown_is_causal_persistent_and_expires(tmp_path):
    path=tmp_path/'bus.sqlite';store=EventStore(path)
    service=CreatorService(store,{'window_seconds':1,'minimum_requests':2,'bursts_before_cooldown':2,'cooldown_seconds':10})
    seqs=[]
    for index,at in enumerate((100,100.1,102,102.1,102.2)):
        seqs.append(add(store,'rfq',rfq(str(index)),'r'+str(index),at))
    while service.step():pass
    assert creator_state(store,'c1',seqs[3],102.1)['status']=='watch'
    assert creator_state(store,'c1',seqs[4],102.2)['status']=='cooldown'
    assert creator_state(store,'c1',seqs[4],113)['expired']
    cursor=store.cursor('creators');store.close();store=EventStore(path)
    service=CreatorService(store,{'window_seconds':1,'minimum_requests':2,'bursts_before_cooldown':2,'cooldown_seconds':10})
    assert service.step()==0 and store.cursor('creators')==cursor
    assert store.db.execute('SELECT COUNT(*) FROM creator_requests').fetchone()[0]==5
    store.close()


def test_quote_full_size_risk_and_restart(tmp_path):
    path=tmp_path/'bus.sqlite';store=EventStore(path);c=config();c['per_contract_dollars']=8
    creators=CreatorService(store);engine=ShadowEngine(store,c,replay=True);seed(store)
    add(store,'rfq',rfq(),'r1',100)
    add(store,'rfq',rfq('r2'),'r2',101)
    drain(creators,engine)
    results=decisions(store)
    assert results[0]['status']=='shadow_quote'
    assert results[0]['yes_ask']==pytest.approx(.27)
    assert results[0]['quantity']==10
    assert results[1]['reason']=='contract_risk_limit'
    assert engine.risk.available()==100000000-73000
    # A rejected RFQ must not create fill-eligible markout obligations.
    assert store.db.execute('SELECT COUNT(*) FROM markouts').fetchone()[0] == len(c['markout_horizons_seconds'])
    store.close();store=EventStore(path);creators=CreatorService(store);engine=ShadowEngine(store,c,replay=True)
    drain(creators,engine)
    assert store.db.execute('SELECT COUNT(*) FROM decisions').fetchone()[0]==2
    add(store,'heartbeat',{},'tick',104);drain(creators,engine)
    assert engine.risk.available()==100000000
    assert store.db.execute('SELECT status FROM reservations').fetchone()[0]=='expired'
    store.close()


def test_missing_feed_suspension_and_target_cost_upper_bound(tmp_path):
    store=EventStore(tmp_path/'bus.sqlite');creators=CreatorService(store);engine=ShadowEngine(store,config(),replay=True)
    add(store,'rfq',rfq(),'r1',99);seed(store)
    r=rfq('target');del r['contracts_fp'];r['target_cost_dollars']='10.00'
    add(store,'rfq',r,'r2',100)
    add(store,'venue_reset',{'venue':'pinnacle'},'reset',101)
    add(store,'rfq',rfq('r3'),'r3',102)
    drain(creators,engine)
    results=decisions(store)
    assert 'observation_missing' in results[0]['reason']
    assert results[1]['quantity']==38 and 'upper_bound' in results[1]['size_model']
    assert results[2]['reason']=='pinnacle: inactive'
    store.close()


def test_markouts_are_later_labels_not_fills(tmp_path):
    store=EventStore(tmp_path/'bus.sqlite');creators=CreatorService(store);engine=ShadowEngine(store,config(),replay=True)
    seed(store);add(store,'rfq',rfq(),'r1',100);drain(creators,engine)
    # Publish all six refreshed books atomically; emit a heartbeat to evaluate.
    seed(store,105,.6);add(store,'heartbeat',{},'tick',105);drain(creators,engine)
    labels=[e['payload'] for e in store.read(0,1000) if e['kind']=='markout']
    assert labels[0]['observed_at']>=105
    assert labels[0]['kind']=='hypothetical_quote_markout'
    assert labels[0]['adverse_move_cents']>0
    assert store.db.execute("SELECT COUNT(*) FROM reservations WHERE status='simulated_filled'").fetchone()[0]==0
    assert creator_state(store,'c1',1000,105)['status']=='clear'
    store.close()


def test_risk_atomic_concurrent_reservations_and_settlement(tmp_path):
    path=tmp_path/'bus.sqlite';c=config();c['capital_dollars']=100
    store=EventStore(path);RiskLedger(store,c);store.close()
    def attempt(identifier):
        store=EventStore(path);risk=RiskLedger(store,c)
        try:
            with store.transaction():
                return risk.reserve(identifier,'c',60,{'contract':['a'],'combo':[identifier],'fixture':['game']},200,{'quantity':100})['allowed']
        finally:store.close()
    with ThreadPoolExecutor(max_workers=2) as pool:assert sum(pool.map(attempt,['a','b']))==1
    store=EventStore(path);risk=RiskLedger(store,c)
    identifier=store.db.execute('SELECT id FROM reservations').fetchone()[0]
    with store.transaction():risk.transition(identifier,'simulated_filled',101,1)
    with store.transaction():risk.expire(201,2)
    assert risk.available()==400000
    with store.transaction():risk.transition(identifier,'simulated_settled',202,3,100)
    assert risk.available()==1400000
    with pytest.raises(ValueError):
        with store.transaction():risk.transition(identifier,'reserved',203,4)
    store.close()


def test_kalshi_snapshot_delta_complement_and_gap():
    books=Books('kalshi',config()['mappings'])
    snapshot={'type':'orderbook_snapshot','sid':1,'seq':1,'msg':{'market_ticker':'KXNFLGAME-a',
        'yes_dollars_fp':[['0.48','10']],'no_dollars_fp':[['0.48','15']]}}
    _,row=books.consume(snapshot,100,'raw:1')[0]
    assert row['yes_ask']==.52 and row['yes_ask_size']==15
    delta={'type':'orderbook_delta','sid':1,'seq':2,'msg':{'market_ticker':'KXNFLGAME-a',
        'side':'no','price_dollars':'0.48','delta_fp':'-15','ts_ms':100000}}
    _,row=books.consume(delta,100,'raw:2')[0]
    assert row['active'] is False
    delta['seq']=4
    with pytest.raises(ValueError,match='sequence_gap'):books.consume(delta,100,'raw:4')


def test_live_empty_snapshot_omits_ladders():
    books=Books('kalshi',[])
    snapshot={'type':'orderbook_snapshot','sid':4,'seq':1,'msg':{'market_ticker':'KXMVE-example'}}
    kind,row=books.consume(snapshot,100,'raw:1')[0]
    assert kind=='combo_book' and row['valid'] is False


def test_source_clock_skew_is_preserved_and_large_offset_disables_price():
    books=Books('kalshi',config()['mappings'])
    msg={'type':'orderbook_snapshot','sid':1,'seq':1,'msg':{'market_ticker':'KXNFLGAME-a',
        'yes_dollars_fp':[['.48','10']],'no_dollars_fp':[['.48','15']],'ts_ms':100040}}
    row=books.consume(msg,100,'raw:1')[0][1]
    assert row['active'] and row['observed_at']<=row['available_at']
    assert row['source_observed_at']==100.04
    msg['seq']=2;msg['msg']['ts_ms']=100500
    row=books.consume(msg,100,'raw:2')[0][1]
    assert not row['active'] and row['invalid_reason']=='source_clock_offset_exceeds_tolerance'


def test_polymarket_absolute_sizes_and_unknown_delta():
    books=Books('polymarket',config()['mappings'])
    snapshot={'event_type':'book','asset_id':'pm-a','timestamp':'100000',
        'bids':[{'price':'.48','size':'10'}],'asks':[{'price':'.52','size':'15'}]}
    books.consume(snapshot,100,'raw:1')
    change={'event_type':'price_change','timestamp':'101000','price_changes':[{'asset_id':'pm-a','price':'.48','size':'3','side':'BUY'}]}
    assert books.consume(change,101,'raw:2')[0][1]['yes_bid_size']==3
    change['price_changes'][0]['asset_id']='pm-b'
    with pytest.raises(ValueError,match='without_snapshot'):books.consume(change,101,'raw:3')


def test_grid_and_unconfigured_risk(tmp_path):
    assert quote_price(.253,.003,0,[{'start':0,'end':1,'step':.01}])==.26
    with pytest.raises(ValueError,match='precision'):
        quote_price(.253,.003,0,[{'start':0,'end':1,'step':.00001}])
    store=EventStore(tmp_path/'bus.sqlite');c=config();c['per_contract_dollars']=None;risk=RiskLedger(store,c)
    with store.transaction():
        result=risk.reserve('a','c',1,{'contract':['a'],'combo':['x'],'fixture':['g']},200,{'quantity':1})
    assert result['reason']=='risk_limits_unconfigured' and risk.available()==100000000
    store.close()


def test_archive_restore_reproduces_quote_and_detects_corruption(tmp_path):
    import importlib.util
    spec=importlib.util.spec_from_file_location('runtime_cli',ROOT/'scripts/runtime.py')
    cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)
    store=EventStore(tmp_path/'original.sqlite');creators=CreatorService(store);engine=ShadowEngine(store,config(),replay=True)
    seed(store);add(store,'rfq',rfq(),'r1',100);drain(creators,engine)
    original=decisions(store)[0]
    manifest=cli.archive(store,tmp_path/'archive',chunk_rows=4)
    assert manifest['complete'] and len(manifest['chunks'])>1
    restored=EventStore(tmp_path/'restored.sqlite')
    cli.restore_inputs(restored,tmp_path/'archive')
    drain(CreatorService(restored),ShadowEngine(restored,config(),replay=True))
    result=decisions(restored)[0]
    for key in ('status','yes_ask','quantity','economics','pricing','risk'):
        assert result[key]==original[key]
    cli.export_review(restored,tmp_path/'review')
    assert (tmp_path/'review/decisions.jsonl').stat().st_size>0
    chunk=tmp_path/'archive'/manifest['chunks'][0]['file']
    with chunk.open('ab') as f:f.write(b'corrupt')
    corrupt=EventStore(tmp_path/'corrupt.sqlite')
    with pytest.raises(ValueError,match='checksum'):cli.restore_inputs(corrupt,tmp_path/'archive')
    assert corrupt.read()==[]
    store.close();restored.close();corrupt.close()


def test_blacklist_expiry_logged_without_new_requests(tmp_path):
    store=EventStore(tmp_path/'bus.sqlite');service=CreatorService(store)
    add(store,'creator_override',{'creator_id':'c','status':'cooldown','reason':'synthetic-test',
        'evidence':['synthetic:review'],'expires_at':110},'override',100)
    add(store,'heartbeat',{},'tick',111)
    while service.step():pass
    changes=[e['payload'] for e in store.read(0,100) if e['kind']=='creator_policy']
    assert changes[0]['state']['status']=='cooldown'
    assert changes[1]['state']['status']=='watch' and changes[1]['state']['reason']=='cooldown_expired'
    store.close()


def test_creator_watermark_blocks_unreviewed_rfqs_and_future_policy(tmp_path):
    store=EventStore(tmp_path/'bus.sqlite');creators=CreatorService(store);engine=ShadowEngine(store,config(),replay=True)
    seed(store);add(store,'rfq',rfq(),'r1',100)
    engine.step()
    assert decisions(store)==[]
    add(store,'creator_override',{'creator_id':'c1','status':'blocked','reason':'synthetic-test','evidence':['synthetic']},'override',101)
    add(store,'rfq',rfq('r2'),'r2',102)
    drain(creators,engine)
    first,second=decisions(store)
    assert first['status']=='shadow_quote' and second['reason']=='creator_blocked'
    assert second['status']=='shadow_quote_blocked'
    assert second['shadow_counterfactual'] and second['creator_policy_eligible'] is False
    assert store.db.execute('SELECT COUNT(*) FROM markouts').fetchone()[0] == 2*len(engine.config['markout_horizons_seconds'])
    # The creator override cancels the earlier real reservation; the blocked
    # RFQ is counterfactual and never consumes risk.
    assert engine.risk.available()==100000000
    store.close()
