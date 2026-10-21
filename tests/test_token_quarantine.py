import asyncio
from decimal import Decimal as D
from types import SimpleNamespace
import combos.quiet_book_probe as module


def test_quarantine_suppresses_updates_and_preserves_other_books():
    p=module.QuietBookProbe({'token_quarantine':True},'shadow');p.reset('one')
    p.observe('bad',{'market_key':'bad','active':True,'observed_at':1})
    p.mismatch_tokens.add('bad');p.requests=p.budget;events=[]
    p.tick(None,lambda kind,row,at=None:events.append((kind,row)))
    assert p.quarantined=={'bad'} and p.resyncs==0
    assert p.observe('bad',{'market_key':'bad','active':True,'observed_at':2})['active'] is False
    assert 'active' not in p.observe('good',{'market_key':'good','active':True,'observed_at':2})
    assert [r for k,r in events if k=='observation'][0]['active'] is False
    p.reset('two');assert 'bad' in p.quarantined


def test_matching_recheck_restores_before_certificate(monkeypatch):
    monkeypatch.setattr(module.time,'time',lambda:100.5)
    def fetch(tokens):
        return {'request_started_at':100,'received_at':100.5,'http_status':200,
            'response_headers':{'Date':'Thu, 01 Jan 1970 00:01:40 GMT'},
            'payload':[{'asset_id':'t','timestamp':'1000','bids':[{'price':'.4','size':'10'}],'asks':[{'price':'.6','size':'20'}]}]}
    monkeypatch.setattr(module,'fetch',fetch)
    async def exercise():
        p=module.QuietBookProbe({'token_quarantine':True,'maximum_requests':1},'shadow');p.reset('one')
        p.observe('t',{'market_key':'m','active':True,'observed_at':1});p.quarantined.add('t')
        b=SimpleNamespace(books={'t':{'bid':{D('.4'):D(10)},'ask':{D('.6'):D(20)}}});events=[]
        def emit(kind,row,at=None):events.append((kind,row));return 'ref'
        p.tick(b,emit);await p.task;p.tick(b,emit)
        assert not p.quarantined and p.recovery_attempts['t']==1
        kinds=[k for k,r in events];assert kinds.index('observation')<kinds.index('book_verification')
        assert next(r for k,r in events if k=='observation')['active']
        await p.close()
    asyncio.run(exercise())


def test_exhausted_market_stays_quarantined_without_global_failure():
    p=module.QuietBookProbe({'token_quarantine':True},'shadow');p.reset('one')
    p.observe('t',{'market_key':'m','active':True,'observed_at':1});p.quarantined.add('t');p.recovery_attempts['t']=3
    p.tick(SimpleNamespace(books={'t':{}}),lambda *a:None)
    assert p.task is None and p.quarantined=={'t'}
