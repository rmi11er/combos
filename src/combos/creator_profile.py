"""Streaming, disk-deduplicated RFQ evidence; no inference of trading intent."""
from collections import Counter, defaultdict, deque
import hashlib
import json
from pathlib import Path
import sqlite3
from .journal import read_journal


def profile(journals, directory, window_seconds=60, minimum_requests=30,
            duplicate_fraction=.8, long_legs=20):
    out = Path(directory); out.mkdir(parents=True, exist_ok=False)
    db = sqlite3.connect(out/'evidence.sqlite')
    db.execute('CREATE TABLE requests (rfq_id TEXT PRIMARY KEY, creator TEXT, received_at REAL)')
    db.execute('CREATE TABLE flags (creator TEXT, available_at REAL, reason TEXT, window_requests INTEGER, duplicate_fraction REAL)')
    pending = deque(); rolling = defaultdict(Counter); totals = Counter()
    creators = defaultdict(Counter); last_burst = {}; last_at = float('-inf')
    first_at = None; last_received_at = None; inserted_count = 0
    manifest = {'complete': False, 'journals': [str(p) for p in journals],
                'policy': {'window_seconds': window_seconds, 'minimum_requests': minimum_requests,
                           'duplicate_fraction': duplicate_fraction, 'long_legs': long_legs}}
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2))
    try:
        for directory in journals:
            for row in read_journal(directory):
                at = float(row['received_at'])
                if at < last_at: raise ValueError('journals must be chronological; clock regression needs review')
                last_at = at
                first_at = at if first_at is None else first_at
                last_received_at = at
                if row['kind'] in ('disconnected', 'sequence_discontinuity', 'connect_attempt'):
                    kind = row['kind']
                    manifest[kind] = manifest.get(kind, 0)+1
                while pending and pending[0][0] <= at-window_seconds:
                    _, creator, signature = pending.popleft()
                    rolling[creator][signature] -= 1
                    if not rolling[creator][signature]: del rolling[creator][signature]
                    totals[creator] -= 1
                    if not totals[creator]: del totals[creator]; del rolling[creator]
                if row['kind'] != 'message' or row['payload'].get('type') != 'rfq_created': continue
                msg = row['payload']['msg']
                rfq, creator = msg.get('id'), msg.get('creator_id')
                if not rfq:
                    manifest['missing_rfq_id'] = manifest.get('missing_rfq_id', 0)+1
                    continue
                inserted = db.execute('INSERT OR IGNORE INTO requests VALUES (?,?,?)', (rfq, creator, at)).rowcount
                if not inserted:
                    manifest['duplicates_ignored'] = manifest.get('duplicates_ignored', 0)+1
                    continue
                inserted_count += 1
                if inserted_count % 10000 == 0: db.commit()
                if not creator:
                    manifest['missing_creator_id'] = manifest.get('missing_creator_id', 0)+1
                    continue
                counts = creators[creator]; counts['requests'] += 1
                legs = msg.get('mve_selected_legs', [])
                counts['long_leg_requests'] += int(len(legs) >= long_legs)
                counts['two_leg_requests'] += int(len(legs) == 2)
                # Event IDs can prove some shared events, but distinct market families
                # can share a fixture. This count is a lower-bound structural flag.
                events = [leg.get('event_ticker') for leg in legs if leg.get('event_ticker')]
                counts['repeated_event_requests'] += int(len(set(events)) < len(events))
                if not legs or any(not l.get('market_ticker') or l.get('side') not in ('yes', 'no') for l in legs):
                    counts['unusable_leg_sets'] += 1
                    continue
                signature = hashlib.sha256(json.dumps(sorted((l['market_ticker'], l['side']) for l in legs)).encode()).hexdigest()
                pending.append((at, creator, signature)); rolling[creator][signature] += 1; totals[creator] += 1
                share = rolling[creator][signature]/totals[creator]
                if totals[creator] >= minimum_requests and share >= duplicate_fraction and at-last_burst.get(creator, float('-inf')) >= window_seconds:
                    counts['separated_duplicate_bursts'] += 1; last_burst[creator] = at
                    db.execute('INSERT INTO flags VALUES (?,?,?,?,?)', (creator, at, 'duplicate_request_burst', totals[creator], share))
        with (out/'creators.jsonl').open('w') as f:
            for creator, counts in sorted(creators.items()):
                reasons = []
                if counts['long_leg_requests']: reasons.append('long_leg_context')
                if counts['repeated_event_requests']: reasons.append('shared_event_review')
                if counts['separated_duplicate_bursts']: reasons.append('duplicate_request_bursts')
                f.write(json.dumps({'creator_hash': hashlib.sha256(creator.encode()).hexdigest()[:16],
                    'counts': dict(counts), 'request_duplicate_bursts': counts['separated_duplicate_bursts'],
                    'reasons': reasons, 'status': 'review' if reasons else 'unflagged',
                    'blacklisted': False, 'markout_labels': 0})+'\n')
        db.commit()
        manifest.update(complete=True, creators=len(creators), unique_rfqs=db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],
                        first_received_at=first_at, last_received_at=last_received_at,
                        correlation_pickoffs='unlabeled: needs joint-model/mapping and causal markouts',
                        scope='observed requests only; gaps and cross-family fixture relationships not inferred')
        (out/'manifest.json').write_text(json.dumps(manifest, indent=2))
    finally: db.close()
    return manifest
