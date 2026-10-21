import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))

from combos.journal import Journal
from combos.rfq_sniffer import Policy, Sniffer, scan_journals, similar, structure


def legs(n=12, edit=None, concentrated=True):
    result = [{'market_ticker':f'KXMLBHIT-26SEP071710WSHSD-P{i}-1',
               'event_ticker':'KXMLBHIT-26SEP071710WSHSD' if concentrated else f'KXMLBGAME-26SEP07G{i}',
               'side':'yes'} for i in range(n)]
    if edit is not None:
        result[-1]['market_ticker'] = f'KXMLBHIT-26SEP071710WSHSD-ALT{edit}-1'
    return result


def request(identifier, selected=None, creator='a', ticker='combo'):
    return {'id':identifier,'creator_id':creator,'market_ticker':ticker,
            'mve_selected_legs':selected if selected is not None else legs()}


def test_near_duplicates_are_side_sensitive_and_not_chained(tmp_path):
    p = Policy(huge_repeated_requests=50)
    a,_ = structure(legs())
    b,_ = structure(legs(edit=1))
    assert similar(a,b,p)
    changed = legs()
    for row in changed[:3]: row['side']='no'
    c,_ = structure(changed)
    assert not similar(a,c,p)
    s = Sniffer(tmp_path/'s.db',p)
    for i in range(30): s.request(request(str(i),legs(edit=i%3)),i/2,'raw')
    burst = s.db.execute('SELECT reasons FROM bursts').fetchone()
    assert 'minor_edit_parlay_spam' in json.loads(burst[0])
    assert s.db.execute('SELECT COUNT(*) FROM blacklist').fetchone()[0]==0
    s.close()


def test_blacklist_persists_and_duplicate_replay_does_not_escalate(tmp_path):
    path = tmp_path/'s.db'
    s = Sniffer(path)
    for start in (0,61):
        for i in range(10): s.request(request(f'{start}:{i}',legs(edit=i%2)),start+i/10,'raw')
    s.db.commit();s.close()
    s = Sniffer(path)
    for i in range(10): s.request(request(f'122:{i}',legs(edit=i%2)),122+i/10,'raw')
    s.db.commit()
    assert s.db.execute('SELECT COUNT(*) FROM bursts').fetchone()[0]==3
    assert s.db.execute('SELECT COUNT(*) FROM blacklist').fetchone()[0]==1
    for i in range(10): s.request(request(f'122:{i}',legs(edit=i%2)),200+i/10,'raw')
    assert s.db.execute('SELECT COUNT(*) FROM bursts').fetchone()[0]==3
    result=s.export(tmp_path/'review',now=130)
    assert result['active_blacklist_ids']==1
    assert json.loads((tmp_path/'review/blacklist.json').read_text())['creator_ids']==['a']
    assert s.export(tmp_path/'review',now=130+7*86400)['active_blacklist_ids']==0
    s.close()


def test_huge_alone_missing_identity_and_diverse_low_rate_are_not_blocks(tmp_path):
    s = Sniffer(tmp_path/'s.db')
    for i in range(40):
        s.request(request(str(i),legs(edit=i),creator=None),i,'raw')
    s.request(request('huge',legs(100)),41,'raw')
    for i in range(20):
        s.request(request(f'rare{i}',legs(2,edit=i,concentrated=False),creator='b'),42+i,'raw')
    assert s.db.execute('SELECT COUNT(*) FROM bursts').fetchone()[0]==0
    assert s.db.execute('SELECT COUNT(*) FROM blacklist').fetchone()[0]==0
    s.close()


def test_general_rate_spam_needs_no_parlay_similarity(tmp_path):
    s = Sniffer(tmp_path/'s.db')
    for i in range(120):
        s.request(request(str(i),legs(2,edit=i,concentrated=False)),i/10,'raw')
    row=s.db.execute('SELECT reasons FROM bursts').fetchone()
    assert json.loads(row[0])==['high_request_rate_watch']
    assert s.db.execute('SELECT block_eligible FROM bursts').fetchone()[0]==0
    assert s.db.execute('SELECT COUNT(*) FROM blacklist').fetchone()[0]==0
    s.close()


def test_event_structure_is_only_a_proxy():
    data=legs(12)
    for i, row in enumerate(data):
        row['event_ticker']=('KXMLBHIT' if i<6 else 'KXMLBRBI')+'-26SEP071710WSHSD'
    _,f=structure(data)
    assert f['huge_concentrated']
    assert f['maximum_legs_inferred_fixture']==12
    assert 'not_estimated' in f['correlation_basis']
    assert not structure(legs(12,concentrated=False))[1]['huge_concentrated']


def test_no_trade_requires_covered_horizon_and_ignores_old_delayed_print(tmp_path):
    s=Sniffer(tmp_path/'s.db',Policy(trade_horizon_seconds=10))
    for rid,at in [('yes',1),('none',2),('old',3),('tail',98),('gap',40)]:
        s.request(request(rid,ticker=rid),at,'raw')
    s.db.executemany('INSERT INTO coverage VALUES(?,?,?)',[('c1',0,30),('c2',60,100)])
    s.db.executemany('INSERT INTO trades VALUES(?,?,?,?)',[('t1','yes',5,5),('t2','old',6,0)])
    s.label_trade_context()
    values=dict(s.db.execute('SELECT id,trade_context FROM requests').fetchall())
    assert values['yes']=='later_public_trade_same_market'
    assert values['none']==values['old']=='no_public_trade_observed_in_covered_window'
    assert values['tail']==values['gap']=='censored_or_trade_coverage_unknown'
    s.close()


def test_scan_journal_idempotency_and_subscription_coverage(tmp_path):
    journal=Journal(tmp_path/'journal')
    journal.append('connect_attempt',{},received_at=100)
    for i,channel in enumerate(['communications','trade']):
        journal.append('message',{'type':'subscribed','msg':{'channel':channel}},received_at=101+i)
    journal.append('message',{'type':'rfq_created','msg':request('one')},received_at=103)
    for at in range(104,181): journal.append('heartbeat',{},received_at=at)
    journal.append('stop',{},received_at=181)
    journal.close()
    db,out=tmp_path/'s.db',tmp_path/'review'
    first=scan_journals([tmp_path/'journal'],db,out)
    second=scan_journals([tmp_path/'journal'],db,out)
    assert first['unique_requests']==second['unique_requests']==1
    assert first['trade_context']=={'no_public_trade_observed_in_covered_window':1}


def test_config_change_rejected_and_bursts_expire(tmp_path):
    import pytest
    path=tmp_path/'s.db'
    s=Sniffer(path,Policy(burst_evidence_seconds=70))
    for start in (0,100,200):
        for i in range(10): s.request(request(f'{start}:{i}'),start+i/10,'raw')
    s.db.commit()
    assert s.db.execute('SELECT COUNT(*) FROM blacklist').fetchone()[0]==0
    s.close()
    with pytest.raises(ValueError,match='policy changed'):
        Sniffer(path,Policy())
    s=Sniffer(path)
    s.close()


def test_capture_gap_censors_absence_without_discarding_request(tmp_path):
    journal=Journal(tmp_path/'journal')
    journal.append('connect_attempt',{},received_at=100)
    for i,channel in enumerate(['communications','trade']):
        journal.append('message',{'type':'subscribed','msg':{'channel':channel}},received_at=101+i)
    journal.append('message',{'type':'rfq_created','msg':request('one')},received_at=103)
    for at in range(104,120): journal.append('heartbeat',{},received_at=at)
    journal.append('sequence_discontinuity',{},received_at=120)
    for at in range(121,181): journal.append('heartbeat',{},received_at=at)
    journal.append('stop',{},received_at=181)
    journal.close()
    result=scan_journals([tmp_path/'journal'],tmp_path/'s.db',tmp_path/'review')
    assert result['unique_requests']==1
    assert result['trade_context']=={'censored_or_trade_coverage_unknown':1}
    assert result['diagnostics']['sequence_discontinuity']==1


def test_restart_retains_partial_window(tmp_path):
    path=tmp_path/'s.db'
    s=Sniffer(path)
    for i in range(5): s.request(request(str(i)),i,'raw')
    s.db.commit();s.close()
    s=Sniffer(path)
    for i in range(5,10): s.request(request(str(i)),i,'raw')
    assert s.db.execute('SELECT COUNT(*) FROM bursts').fetchone()[0]==1
    s.close()


def test_watch_rate_never_blacklists_but_extreme_rate_can(tmp_path):
    s=Sniffer(tmp_path/'s.db')
    for start in (0,61,122):
        for i in range(120):
            s.request(request(f'watch:{start}:{i}',legs(2,edit=f'{start}:{i}',concentrated=False)),start+i/10,'raw')
    assert s.db.execute('SELECT COUNT(*) FROM blacklist').fetchone()[0]==0
    for start in (200,261,322):
        for i in range(600):
            s.request(request(f'fast:{start}:{i}',legs(2,edit=f'{start}:{i}',concentrated=False),creator='fast'),start+i/20,'raw')
    assert s.db.execute('SELECT creator FROM blacklist').fetchone()[0]=='fast'
    assert s.db.execute("SELECT COUNT(*) FROM bursts WHERE creator='fast' AND block_eligible=1").fetchone()[0]==3
    s.close()


def test_rotating_templates_do_not_need_eighty_percent_share(tmp_path):
    s=Sniffer(tmp_path/'s.db',Policy(huge_repeated_requests=50))
    for i in range(60):
        selected=legs(6)
        if i%2:
            for leg in selected: leg['market_ticker']+='-OTHER'
        s.request(request(str(i),selected),i/2,'raw')
    row=s.db.execute('SELECT evidence FROM bursts WHERE block_eligible=1').fetchone()
    evidence=json.loads(row[0])
    assert evidence['identical']==30
    assert evidence['identical']/evidence['requests']<.8
    s.close()


def test_large_template_edits_scale_but_remain_capped():
    p=Policy()
    original,_=structure(legs(100))
    def edited(n,k):
        result=legs(n)
        for row in result[:k]: row['market_ticker']+='-EDIT'
        return structure(result)[0]
    assert similar(original,edited(100,5),p)
    assert not similar(original,edited(100,6),p)
    fifty,_=structure(legs(50))
    assert similar(fifty,edited(50,3),p)
    twelve,_=structure(legs(12))
    assert not similar(twelve,edited(12,3),p)


def test_two_trade_horizons_and_absence_never_blocks(tmp_path):
    s=Sniffer(tmp_path/'s.db')
    s.request(request('r',ticker='m'),10,'raw')
    s.db.execute('INSERT INTO coverage VALUES(?,?,?)',('c',0,400))
    s.db.execute('INSERT INTO trades VALUES(?,?,?,?)',('t','m',130,130))
    s.label_trade_context()
    row=s.db.execute('SELECT trade_context,extended_trade_context FROM requests').fetchone()
    assert row['trade_context']=='no_public_trade_observed_in_covered_window'
    assert row['extended_trade_context']=='later_public_trade_same_market'
    assert s.db.execute('SELECT COUNT(*) FROM blacklist').fetchone()[0]==0
    s.close()


def test_recurrence_requires_qualified_separate_period_and_time(tmp_path):
    s=Sniffer(tmp_path/'s.db')
    for period,starts in [('A',(0,61,122)),('B',(190,251,312))]:
        for start in starts:
            for i in range(10):
                s.request(request(f'{period}:{start}:{i}'),start+i/10,'raw',period)
    row=s.db.execute('SELECT * FROM blacklist').fetchone()
    assert row['confidence']=='provisional'
    assert row['expires_at']-row['last_at']==86400
    for start in (2000,2061,2122):
        for i in range(10): s.request(request(f'B:{start}:{i}'),start+i/10,'raw','B')
    row=s.db.execute('SELECT * FROM blacklist').fetchone()
    assert row['confidence']=='recurrent'
    assert row['expires_at']-row['last_at']==7*86400
    assert set(json.loads(row['qualifying_periods']))=={'A','B'}
    s.close()


def test_one_long_capture_stays_provisional(tmp_path):
    s=Sniffer(tmp_path/'s.db')
    for start in (0,61,122,2000,2061,2122):
        for i in range(10): s.request(request(f'{start}:{i}'),start+i/10,'raw','same')
    assert s.db.execute('SELECT confidence FROM blacklist').fetchone()[0]=='provisional'
    s.close()
