"""Read a retained capture without opening the runtime's mutating EventStore."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3
import zlib


def audit(path):
    db = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
    db.execute('PRAGMA query_only=ON')
    db.execute('BEGIN')
    high = db.execute('SELECT MAX(seq) FROM events').fetchone()[0] or 0
    types, fields, legs, seconds, creators = (Counter() for _ in range(5))
    seen, deleted, sets = set(), set(), set()
    first, last, repeated, missing, total_bytes = None, None, 0, 0, 0
    digest = hashlib.sha256()
    for seq, at, payload in db.execute(
        "SELECT seq,received_at,payload FROM events WHERE kind='kalshi' AND seq<=? ORDER BY seq", (high,)
    ):
        digest.update(str(seq).encode() + b':' + payload)
        total_bytes += len(payload)
        value = json.loads(zlib.decompress(payload))
        typ, msg = value.get('type'), value.get('msg', {})
        types[typ] += 1
        if typ == 'rfq_deleted':
            deleted.add(msg.get('id'))
        if typ != 'rfq_created':
            continue
        fields.update(msg.keys())
        rid = msg.get('id')
        if rid in seen:
            repeated += 1
            continue
        seen.add(rid)
        first = at if first is None else min(first, at)
        last = at if last is None else max(last, at)
        seconds[int(at)] += 1
        creator = msg.get('creator_id')
        missing += not bool(creator)
        if creator:
            creators[creator] += 1
        selected = msg.get('mve_selected_legs') or []
        legs[len(selected)] += 1
        signature = tuple(sorted((l.get('market_ticker', ''), l.get('side', '')) for l in selected))
        if creator and signature:
            sets.add((creator, signature))
    db.close()
    elapsed = last - first if first is not None else 0
    return {
        'database': str(path), 'snapshot_max_seq': high,
        'kalshi_event_digest': digest.hexdigest(),
        'method': 'Complete kalshi-kind scan through snapshot_max_seq; read-only SQLite transaction.',
        'kalshi_message_types': dict(types), 'rfq_created_field_counts': dict(fields),
        'unique_rfq_ids': len(seen), 'repeated_create_ids': repeated,
        'missing_creator_ids': missing, 'unique_creators': len(creators),
        'leg_count_distribution': dict(sorted(legs.items())),
        'first_rfq_received_at': first, 'last_rfq_received_at': last,
        'rfq_receipt_span_seconds': elapsed,
        'rfqs_per_receipt_second': len(seen)/elapsed if elapsed else None,
        'max_rfqs_in_utc_aligned_second': max(seconds.values(), default=0),
        'top_creator_request_counts_without_identifiers': [n for _, n in creators.most_common(10)],
        'unique_creator_leg_sets': len(sets),
        'created_ids_with_delete_in_same_capture': len(seen & deleted),
        'deleted_ids_without_create_in_same_capture': len(deleted - seen),
        'compressed_kalshi_payload_bytes': total_bytes,
        'limitations': ['Bounded capture, not representative daily traffic.',
                        'Deletion is not proof of execution or malicious cancellation.',
                        'No requester direction or private quote outcome inferred.'],
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('database', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.database)
    with args.out.open('x') as handle:
        json.dump(result, handle, indent=2)
        handle.write('\n')
    print(json.dumps(result, indent=2))
