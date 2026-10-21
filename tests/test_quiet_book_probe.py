import asyncio
from decimal import Decimal
from types import SimpleNamespace
import pytest
import combos.quiet_book_probe as module


@pytest.mark.parametrize('mode,config',[('live',{}),('shadow',{'maximum_requests':0}),
    ('shadow',{'maximum_books_per_request':101}),('shadow',{'interval_seconds':1})])
def test_shadow_and_request_bounds(mode,config):
    with pytest.raises(ValueError):module.QuietBookProbe(config,mode)


@pytest.mark.parametrize('reconnect',[False,True])
def test_real_async_result_verifies_or_rejects_generation(monkeypatch,reconnect):
    monkeypatch.setattr(module.time,'time',lambda:100.5)
    def fetch(tokens):
        return {'request_started_at':100,'received_at':100.5,'http_status':200,
            'response_headers':{'Date':'Thu, 01 Jan 1970 00:01:40 GMT'},
            'payload':[{'asset_id':'t','timestamp':'1000','bids':[{'price':'.4','size':'10'}],
                        'asks':[{'price':'.6','size':'20'}]}]}
    monkeypatch.setattr(module,'fetch',fetch)
    async def exercise():
        p=module.QuietBookProbe({'maximum_requests':1},'shadow');p.reset('first')
        row={'market_key':'m','active':True,'observed_at':1}
        p.observe('t',row)
        books=SimpleNamespace(books={'t':{'bid':{Decimal('.4'):Decimal(10)},'ask':{Decimal('.6'):Decimal(20)}}})
        events=[]
        def emit(kind,payload,at=None):events.append((kind,payload));return 'reference'
        p.tick(books,emit)
        await p.task
        if reconnect:p.reset('second')
        p.tick(books,emit)
        assert p.requests==1
        assert any(kind=='book_verification' for kind,_ in events)==(not reconnect)
        assert row['observed_at']==1
        await p.close()
    asyncio.run(exercise())


def test_confirmed_mismatch_requires_reset_then_stops_at_budget():
    p=module.QuietBookProbe({'maximum_resyncs':1},'shadow')
    events=[]
    def emit(kind,payload,at=None):events.append((kind,payload));return 'reference'
    p.reset('first');p.mismatch_tokens.add('t')
    with pytest.raises(module.BookResyncRequired):p.tick(None,emit)
    assert p.requests==0 and p.resyncs==1
    p.reset('second');assert not p.mismatch_tokens
    p.mismatch_tokens.add('t')
    with pytest.raises(module.SnapshotRecoveryExhausted):p.tick(None,emit)
    assert p.resyncs==1
