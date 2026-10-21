import json,sys,time,os,signal
from pathlib import Path
from types import SimpleNamespace
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import sustained_shadow_supervisor as supervisor
from combos.event_store import EventStore


def command(tmp_path,code,name='child'):
    return (name,[sys.executable,'-c',code],None,tmp_path/(name+'.log'))


def test_child_failure_timeout_early_exit_and_reaping(tmp_path):
    failure=supervisor.supervise([command(tmp_path,'raise SystemExit(7)')],2,poll=.01,stop_grace=.05)
    assert failure['failure']=='child_failed' and failure['all_direct_children_reaped']
    timeout=supervisor.supervise([command(tmp_path,'import time;time.sleep(60)')],.05,poll=.01,stop_grace=.05)
    assert timeout['failure']=='supervisor_timeout' and timeout['all_direct_children_reaped']
    early=supervisor.supervise([command(tmp_path,'pass')],2,poll=.01,stop_grace=.05,minimum_seconds=1)
    assert early['failure']=='child_exited_before_requested_duration'


def test_config_mutation_stops_children(tmp_path):
    cfg=tmp_path/'config';cfg.write_text('original');hashes={str(cfg):supervisor.digest(cfg)}
    code=f"import time;from pathlib import Path;time.sleep(.04);Path({str(cfg)!r}).write_text('changed');time.sleep(60)"
    result=supervisor.supervise([command(tmp_path,code)],3,lambda:supervisor.assert_frozen(hashes),poll=.01,stop_grace=.05)
    assert result['failure']=='supervisor_exception:ValueError' and result['all_direct_children_reaped']


def test_live_rejected_before_any_runtime_initialization():
    with pytest.raises(ValueError,match='live_rejected'):supervisor.validate_runtime({'mode':'live'}, {})


def test_reviewed_mapping_allowed_without_removing_existing_guards():
    config=json.loads((supervisor.ROOT/'config/runtime_nfl_week1_nonplayer.json').read_text())
    weights=json.loads((supervisor.ROOT/'config/weighting.json').read_text())
    # Synthetic in-memory test only: validator must not require every mapping blocked.
    config['mappings'][0].pop('pricing_block_reason',None)
    supervisor.validate_runtime(config,weights)
    config['pregame_only']=False
    with pytest.raises(ValueError):supervisor.validate_runtime(config,weights)


def make_events(tmp_path,quote=False,missing_disposition=False):
    store=EventStore(tmp_path/'events.sqlite')
    for venue in ('kalshi','polymarket','pinnacle'):
        store.append('observation',venue,{'venue':venue,'active':True,'yes_bid_size':10,'yes_ask_size':10},venue,1)
    store.append('rfq','test',{'id':'r','creator_id':'c','selected_legs':[]},'rfq',1)
    if not missing_disposition:
        store.append('decision','shadow',{'source_seq':4,'mode':'shadow','fills_assumed':False,'risk':{'allowed':True},'pricing':{'quote_allowed':True,'legs':[{'phase':'pregame','guard':{'quote_allowed':True},'venues':{v:{'two_sided_depth_payout_dollars':10} for v in ('kalshi','polymarket','pinnacle')}}]*2},'status':'shadow_quote' if quote else 'skipped','reason':None if quote else 'blocked','completed_processing_lag_seconds':.1},'decision',1)
    end=store.db.execute('SELECT MAX(seq) FROM events').fetchone()[0]
    for role in ('creators','shadow'):
        store.register(role,{})
        with store.transaction():store.checkpoint(role,end)
    store.close()


@pytest.mark.parametrize('quote,missing,healthy',[(False,False,False),(True,False,True),(True,True,False)])
def test_real_eventstore_evidence_dispositions(tmp_path,quote,missing,healthy):
    make_events(tmp_path,quote,missing)
    result=supervisor.evidence(tmp_path,{'failure':None},{'archive':{'failure':None}},{'maximum_processing_lag_seconds':2})
    assert result['healthy_pricing_observed'] is healthy
    assert result['capture_evidence_observed'] is True
    assert result['orders_enabled'] is False and result['live_ready'] is False
    assert result['rfqs']==1
    if missing:assert not result['capture_complete'] and not result['all_rfq_dispositions_recorded']


def test_prepare_cached_account_reconciles_shared_budget_without_network(tmp_path,monkeypatch):
    config=json.loads((supervisor.ROOT/'config/runtime_nfl_week1_nonplayer.json').read_text())
    weights=json.loads((supervisor.ROOT/'config/weighting.json').read_text())
    polling=json.loads((supervisor.ROOT/'config/oddspapi_polling.json').read_text())
    now=time.time();polling['budget_path']=str(tmp_path/'shared.sqlite')
    account={'retrieved_at':now,'subscriptions':[{'is_active':True,'bookmakers':{'pinnacle+30':{}},'sport_ids':[14],'request_count':9,'request_limit':100000,'valid_from':'2026-09-01T00:00:00Z','valid_until':'2027-09-01T00:00:00Z'}]}
    for name,data in [('config',config),('weights',weights),('polling',polling),('account',account)]:
        (tmp_path/name).write_text(json.dumps(data))
    (tmp_path/'key').write_text('test-secret-not-a-real-key')
    args=SimpleNamespace(out=tmp_path/'capture',runtime=tmp_path/'config',weights=tmp_path/'weights',polling=tmp_path/'polling',account_summary=tmp_path/'account',key_file=tmp_path/'key',purpose='capture')
    supervisor.prepare(args)
    prepared=json.loads((args.out/'prepared.json').read_text())
    supervisor.assert_frozen(prepared['hashes'])
    assert prepared['shared_budget_used']==9
    assert 'test-secret' not in (args.out/'prepared.json').read_text()
    assert (args.out/'snapshot/scripts/oddspapi_feed.py').exists()
    assert (args.out/'snapshot/src/combos/live_collectors.py').exists()


def test_source_closure_covers_local_runtime_and_feed_dependencies():
    paths=supervisor.code_files()
    assert supervisor.ROOT/'scripts/runtime.py' in paths
    assert supervisor.ROOT/'scripts/oddspapi_feed.py' in paths
    assert set((supervisor.ROOT/'src/combos').glob('*.py'))<=set(paths)


def checkpoint_tail(store):
    end=store.db.execute('SELECT MAX(seq) FROM events').fetchone()[0]
    with store.transaction():
        for role in ('creators','shadow'):store.checkpoint(role,end)


def test_equal_counts_duplicate_disposition_does_not_hide_missing_rfq(tmp_path):
    make_events(tmp_path)
    store=EventStore(tmp_path/'events.sqlite')
    store.append('rfq','test',{'id':'r2'},'rfq2',2)
    store.append('decision','shadow',{'source_seq':4,'mode':'shadow','status':'skipped'},'duplicate',2)
    checkpoint_tail(store);store.close()
    result=supervisor.evidence(tmp_path,{'failure':None},{},{'maximum_processing_lag_seconds':2})
    assert result['rfqs']==result['decision_count']==2
    assert result['disposition_reconciliation']=={'missing':1,'duplicate':1,'orphan':0,'malformed':0}
    assert not result['capture_complete']


@pytest.mark.parametrize('lag',[None,float('nan'),float('inf'),-1,3])
def test_missing_nonfinite_or_out_of_budget_quote_lag_rejected(lag):
    payload={'mode':'shadow','fills_assumed':False,'risk':{'allowed':True},'pricing':{'quote_allowed':True,'legs':[{'phase':'pregame','guard':{'quote_allowed':True},'venues':{v:{'two_sided_depth_payout_dollars':10} for v in ('kalshi','polymarket','pinnacle')}}]*2}}
    if lag is not None:payload['completed_processing_lag_seconds']=lag
    assert 'invalid_completed_lag' in supervisor.quote_context_errors(payload,2)


def test_global_depth_cannot_replace_quote_context():
    errors=supervisor.quote_context_errors({'status':'shadow_quote','completed_processing_lag_seconds':.1},2)
    assert 'invalid_shadow_mode' in errors and 'invalid_pricing_guard' in errors


def test_descendant_is_stopped_even_when_leader_exits(tmp_path):
    import subprocess
    pid_file=tmp_path/'grandchild.pid'
    grandchild="import signal,time;signal.signal(signal.SIGINT,signal.SIG_IGN);signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(60)"
    parent=f"import subprocess,sys;from pathlib import Path;p=subprocess.Popen([sys.executable,'-c',{grandchild!r}]);Path({str(pid_file)!r}).write_text(str(p.pid))"
    result=supervisor.supervise([command(tmp_path,parent)],2,poll=.01,stop_grace=.05)
    assert result['all_direct_children_reaped']
    pid=int(pid_file.read_text())
    for _ in range(100):
        state=subprocess.run(['ps','-o','stat=','-p',str(pid)],capture_output=True,text=True).stdout.strip()
        if not state or state.startswith('Z'):break
        time.sleep(.01)
    assert not state or state.startswith('Z')


def test_frozen_runtime_init_drain_archive_export_offline(tmp_path):
    import shutil,subprocess
    snapshot=tmp_path/'snapshot'
    for path in supervisor.code_files():
        target=snapshot/path.relative_to(supervisor.ROOT)
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
    for name in ('runtime_nfl_week1_nonplayer.json','weighting.json'):
        shutil.copyfile(supervisor.ROOT/'config'/name,snapshot/name)
    db=tmp_path/'events.sqlite'
    prefix=[sys.executable,str(snapshot/'scripts/runtime.py'),'--db',str(db),'--config',str(snapshot/'runtime_nfl_week1_nonplayer.json'),'--weights',str(snapshot/'weighting.json')]
    def invoke(args):
        result=subprocess.run(prefix+args,capture_output=True,text=True,timeout=15)
        assert result.returncode==0,result.stderr
    invoke(['init'])
    store=EventStore(db);store.append('rfq','test',{'id':'offline','creator_id':'tester','selected_legs':[]},'offline-rfq',time.time());store.close()
    for _ in range(3):
        for role in ('creators','shadow'):invoke(['worker',role,'--seconds','2','--drain'])
    invoke(['archive','--out',str(tmp_path/'archive')]);invoke(['export-review','--out',str(tmp_path/'review')])
    result=supervisor.evidence(tmp_path,{'failure':None},{'archive':{'failure':None},'export':{'failure':None}},{'maximum_processing_lag_seconds':2})
    assert result['capture_complete'] and result['all_rfq_dispositions_recorded']
    assert result['decision_count']==1 and not result['healthy_pricing_observed']
    assert (tmp_path/'archive/manifest.json').is_file()
