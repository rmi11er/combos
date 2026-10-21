"""Rotating append-only research journal. Closed chunks are independently readable."""
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import time


class Journal:
    def __init__(self, directory, chunk_rows=10000):
        self.path = Path(directory)
        self.path.mkdir(parents=True, exist_ok=False)
        if chunk_rows < 1: raise ValueError('chunk_rows must be positive')
        self.chunk_rows = chunk_rows
        self.handle = None
        self.rows = 0
        self.chunks = []
        self.counts = Counter()
        self.started = time.time()
        self.closed = False
        self._manifest(False)

    def _manifest(self, complete):
        value = {'schema_version': 1, 'started_at': self.started, 'updated_at': time.time(),
                 'closed_cleanly': complete, 'counts': dict(self.counts), 'chunks': self.chunks,
                 'scope': 'passive communications only; connection gaps are unrecoverable here'}
        tmp = self.path/'manifest.tmp'
        tmp.write_text(json.dumps(value, indent=2))
        tmp.replace(self.path/'manifest.json')

    def append(self, kind, payload, session_id=None, received_at=None):
        if self.closed: raise ValueError('journal closed')
        if self.handle is None:
            self.open_path = self.path/f'chunk_{len(self.chunks):06d}.jsonl.gz.open'
            self.handle = gzip.open(self.open_path, 'wt', compresslevel=1)
            self.rows = 0
        self.handle.write(json.dumps({'kind': kind, 'received_at': received_at if received_at is not None else time.time(),
                                     'session_id': session_id, 'payload': payload}, separators=(',', ':'), allow_nan=False)+'\n')
        self.rows += 1
        self.counts[kind] += 1
        if kind == 'message':
            event = payload.get('type', 'unknown')
            self.counts[event] += 1
            if event == 'rfq_created':
                self.counts['rfq_created_with_creator' if payload.get('msg', {}).get('creator_id') else 'rfq_created_without_creator'] += 1
        if self.rows >= self.chunk_rows: self.rotate()

    def rotate(self):
        if self.handle is None: return
        self.handle.close(); self.handle = None
        final = self.open_path.with_suffix('')
        self.open_path.replace(final)
        with final.open('rb') as f: digest = hashlib.file_digest(f, 'sha256').hexdigest()
        self.chunks.append({'file': final.name, 'rows': self.rows, 'bytes': final.stat().st_size, 'sha256': digest})
        self._manifest(False)

    def close(self):
        if not self.closed:
            self.rotate(); self._manifest(True); self.closed = True


def read_journal(directory):
    directory = Path(directory)
    manifest = json.loads((directory/'manifest.json').read_text())
    if not manifest['closed_cleanly'] or list(directory.glob('*.open')):
        raise ValueError('journal was not closed cleanly; inspect/recover before replay')
    for chunk in manifest['chunks']:
        path = directory/chunk['file']
        with path.open('rb') as f:
            if hashlib.file_digest(f, 'sha256').hexdigest() != chunk['sha256']:
                raise ValueError('journal checksum mismatch')
        count = 0
        with gzip.open(path, 'rt') as f:
            for line in f:
                count += 1
                yield json.loads(line)
        if count != chunk['rows']: raise ValueError('journal row count mismatch')
