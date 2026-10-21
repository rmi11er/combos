"""Bounded overlapping fill polls with atomic ingestion/checkpoint publication.

The checkpoint records a successfully queried upper bound, not exchange finality.
Late reports older than the overlap still require periodic deeper reconciliation.
"""
import time
from .execution_fills import FillEvidence
from .execution_journal import encoded
from .kalshi_readonly import PREFIX, private_json


class FillCollector:
    def __init__(self, journal, client):
        self.journal, self.client = journal, client
        self.evidence = FillEvidence(journal)
        journal.db.execute('''CREATE TABLE IF NOT EXISTS fill_poll_checkpoint (
            subaccount INTEGER PRIMARY KEY, initial_start INTEGER NOT NULL,
            queried_through INTEGER NOT NULL, detail TEXT NOT NULL)''')

    def poll(self, *, subaccount, initial_start, until, out, overlap_seconds=120,
             max_pages=5, now=None):
        now = time.time() if now is None else now
        for value in (subaccount, initial_start, until, overlap_seconds, max_pages):
            if type(value) is not int:
                raise ValueError('integer poll bounds required')
        if not (0 <= subaccount <= 63 and 0 <= initial_start < until <= now
                and 1 <= overlap_seconds <= 86400 and 1 <= max_pages <= 100):
            raise ValueError('invalid poll bounds')
        prior = self.journal.db.execute('SELECT * FROM fill_poll_checkpoint WHERE subaccount=?', (subaccount,)).fetchone()
        if prior and (prior['initial_start'] != initial_start or until < prior['queried_through']):
            raise ValueError('changed starting horizon or backwards poll')
        start = max(initial_start, prior['queried_through'] - overlap_seconds) if prior else initial_start
        out.mkdir(mode=0o700, parents=True, exist_ok=False)
        paths = []

        def archive(page):
            path = out / f'page_{len(paths)+1:04d}.json'
            private_json(path, page)
            paths.append(path)

        result = self.client.paginate(PREFIX + 'portfolio/fills', ('fills',),
            params={'subaccount': subaccount, 'min_ts': start, 'max_ts': until, 'limit': 100},
            max_pages=max_pages, archive=archive)
        receipt = {'subaccount': subaccount, 'min_ts': start, 'max_ts': until,
            'pages': len(paths), 'pagination_complete': result['pagination_complete'],
            'stop_reason': result['stop_reason'], 'checkpoint_advanced': False,
            'new_fills': 0, 'exchange_finality_established': False,
            'capital_release_authorized': False}
        if result['pagination_complete']:
            try:
                with self.journal.transaction():
                    # A concurrent collector cannot advance from a stale checkpoint.
                    current = self.journal.db.execute('SELECT * FROM fill_poll_checkpoint WHERE subaccount=?', (subaccount,)).fetchone()
                    if (tuple(current) if current else None) != (tuple(prior) if prior else None):
                        raise ValueError('checkpoint changed during poll')
                    inserted = 0
                    for page, path in zip(result['pages'], paths):
                        for row in page['payload']['fills']:
                            if type(row.get('ts')) is not int or not start <= row['ts'] <= until:
                                raise ValueError('fill outside requested time bounds')
                        inserted += self.evidence.ingest(page, str(path))['new_fills']
                    self.journal.db.execute('INSERT OR REPLACE INTO fill_poll_checkpoint VALUES(?,?,?,?)',
                        (subaccount, initial_start, until, encoded({'min_ts': start, 'out': str(out)})))
                receipt.update(checkpoint_advanced=prior is None or until > prior['queried_through'],
                               checkpoint_published=True, new_fills=inserted)
            except (KeyError, TypeError, ValueError) as exc:
                receipt['ingestion_error'] = type(exc).__name__
                receipt['stop_reason'] = 'ingestion_rejected'
        private_json(out / 'receipt.json', receipt)
        return receipt
