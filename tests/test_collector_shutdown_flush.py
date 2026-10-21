import asyncio
import pytest
from combos.live_collectors import flushing_connection


class Connection:
    def __init__(self,events):self.events=events
    async def __aenter__(self):self.events.append('connected');return self
    async def __aexit__(self,*args):
        self.events.append('close_started')
        await asyncio.sleep(0)
        self.events.append('close_finished')


def test_normal_exit_flushes_before_close():
    events=[]
    async def run():
        async with flushing_connection(Connection(events),lambda:events.append('flushed')):
            events.append('received')
    asyncio.run(run())
    assert events==['connected','received','flushed','close_started','close_finished']


def test_cancelled_collection_flushes_before_close_and_preserves_cancellation():
    events=[]
    async def run():
        ready=asyncio.Event()
        async def collect():
            async with flushing_connection(Connection(events),lambda:events.append('flushed')):
                events.append('received');ready.set();await asyncio.Future()
        task=asyncio.create_task(collect());await ready.wait();task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
    asyncio.run(run())
    assert events==['connected','received','flushed','close_started','close_finished']


def test_flush_failure_still_closes_connection():
    events=[]
    def flush():raise RuntimeError('disk failure')
    async def run():
        with pytest.raises(RuntimeError,match='disk failure'):
            async with flushing_connection(Connection(events),flush):pass
    asyncio.run(run())
    assert events==['connected','close_started','close_finished']
