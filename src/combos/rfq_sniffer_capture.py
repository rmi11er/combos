"""Passive RFQ/public-trade journal for offline behavioral screening."""
import asyncio
import hashlib
import json
from pathlib import Path
import time
import uuid

from websockets.asyncio.client import connect

from .journal import Journal
from .runtime_clock import Deadline
from .shadow import WS_URL, auth_headers


async def capture(directory, seconds):
    if not 0 < seconds <= 86400:
        raise ValueError('capture duration must be between zero and one day')
    auth_headers()
    journal = Journal(directory)
    sources = [Path(__file__),Path(__file__).with_name('journal.py'),Path(__file__).with_name('runtime_clock.py')]
    (Path(directory)/'capture_metadata.json').write_text(json.dumps({
        'channels':['communications','trade'],'requested_seconds':seconds,
        'purpose':'passive_behavioral_blacklist_research','orders_enabled':False,
        'source_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}},indent=2)+'\n')
    deadline = Deadline(seconds)
    retry = 1
    try:
        while not deadline.expired():
            session = uuid.uuid4().hex
            journal.append('connect_attempt', {}, session)
            sequences = {}
            try:
                async with connect(WS_URL, additional_headers=auth_headers(),
                                   open_timeout=15, close_timeout=2, max_size=16*1024*1024,
                                   ping_interval=20, ping_timeout=20) as ws:
                    journal.append('connected', {}, session)
                    await ws.send(json.dumps({'id': 1, 'cmd': 'subscribe',
                        'params': {'channels': ['communications', 'trade']}}))
                    last_flush = time.monotonic()
                    while not deadline.expired():
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=.5)
                        except asyncio.TimeoutError:
                            raw = None
                        if raw:
                            at = time.time()
                            payload = json.loads(raw)
                            journal.append('message', payload, session, at)
                            sid, seq = payload.get('sid'), payload.get('seq')
                            if sid is not None and isinstance(seq, int):
                                if sid in sequences and seq != sequences[sid]+1:
                                    journal.append('sequence_discontinuity',
                                        {'sid': sid, 'previous': sequences[sid], 'current': seq}, session)
                                sequences[sid] = seq
                            if payload.get('type') == 'error':
                                raise ValueError('subscription_error')
                        if time.monotonic()-last_flush >= 10:
                            journal.append('heartbeat', {}, session)
                            journal.rotate()
                            print(json.dumps({'elapsed_seconds': round(deadline.elapsed()['wall_seconds'], 1),
                                              'counts': dict(journal.counts)}), flush=True)
                            last_flush = time.monotonic()
                            retry = 1
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                journal.append('disconnected', {'error_type': type(exc).__name__}, session)
                journal.rotate()
                await asyncio.sleep(min(retry, 1 if deadline.expired() else 30))
                retry = min(30, retry*2)
    finally:
        journal.append('stop', deadline.elapsed())
        journal.close()
    if not journal.counts.get('rfq_created'):
        raise RuntimeError('No RFQs captured; inspect the retained journal connection/subscription diagnostics.')
    return {'directory': str(directory), 'counts': dict(journal.counts), **deadline.elapsed()}
