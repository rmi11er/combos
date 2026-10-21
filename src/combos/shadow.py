"""Passive Kalshi communications recording. There is no order/quote adapter."""
import asyncio
import base64
import json
import os
from pathlib import Path
import time
import uuid
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from websockets.asyncio.client import connect
from .journal import Journal

WS_PATH = '/trade-api/ws/v2'
WS_URL = 'wss://external-api-ws.kalshi.com'+WS_PATH


def auth_headers():
    key_id = os.environ['KALSHI_API_KEY_ID']
    key = serialization.load_pem_private_key(Path(os.environ['KALSHI_PRIVATE_KEY_PATH']).expanduser().read_bytes(), password=None)
    timestamp = str(time.time_ns()//1_000_000)
    signature = key.sign((timestamp+'GET'+WS_PATH).encode(),
                         padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH), hashes.SHA256())
    return {'KALSHI-ACCESS-KEY': key_id, 'KALSHI-ACCESS-TIMESTAMP': timestamp,
            'KALSHI-ACCESS-SIGNATURE': base64.b64encode(signature).decode()}


async def record(directory, seconds):
    if not 0 < seconds <= 31*86400: raise ValueError('duration must be positive and at most 31 days')
    auth_headers()  # Validate credentials before creating a run.
    journal = Journal(directory)
    deadline = time.monotonic()+seconds
    retry = 1.
    last_heartbeat = time.monotonic()
    try:
        async with asyncio.timeout(seconds):
            while time.monotonic() < deadline:
                session = str(uuid.uuid4())
                sequences = {}
                journal.append('connect_attempt', {}, session)
                try:
                    async with connect(WS_URL, additional_headers=auth_headers(), open_timeout=15,
                                       ping_interval=20, ping_timeout=20, close_timeout=2, max_size=8*1024*1024) as ws:
                        journal.append('connected', {}, session)
                        await ws.send(json.dumps({'id': 1, 'cmd': 'subscribe', 'params': {'channels': ['communications']}}))
                        retry = 1.
                        while True:
                            try:
                                raw = await asyncio.wait_for(ws.recv(), timeout=10)
                            except asyncio.TimeoutError:
                                raw = None
                            if raw is not None:
                                payload = json.loads(raw)
                                journal.append('message', payload, session)
                                sid, seq = payload.get('sid'), payload.get('seq')
                                if isinstance(seq, int) and sid is not None:
                                    if sid in sequences and seq != sequences[sid]+1:
                                        journal.append('sequence_discontinuity', {'sid': sid, 'previous': sequences[sid], 'current': seq}, session)
                                    sequences[sid] = seq
                                if payload.get('type') == 'error':
                                    raise RuntimeError('subscription error retained in journal')
                            if time.monotonic()-last_heartbeat >= 10:
                                journal.append('heartbeat', {'counts': dict(journal.counts)}, session)
                                journal.rotate()
                                print(json.dumps({'elapsed_seconds': round(time.time()-journal.started, 1), 'counts': dict(journal.counts)}), flush=True)
                                last_heartbeat = time.monotonic()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    # Exception text may contain headers/URLs. Keep only the class.
                    journal.append('disconnected', {'error_type': type(exc).__name__, 'retry_seconds': retry}, session)
                    journal.rotate()
                    await asyncio.sleep(min(retry, max(0., deadline-time.monotonic())))
                    retry = min(30., retry*2)
    except TimeoutError:
        journal.append('stop', {'reason': 'duration_reached'})
    except asyncio.CancelledError:
        journal.append('stop', {'reason': 'cancelled'})
        raise
    finally:
        journal.close()
    return {'directory': str(directory), 'counts': dict(journal.counts), 'closed_cleanly': True}
