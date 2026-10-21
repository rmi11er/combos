"""Compare full-depth and top-only verification on captured requests, without RFQ repricing."""
import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import sys
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from combos.live_books import Books
from combos.book_verification import verify_snapshot
from top_book_verification_research import verify_top_snapshot


def serial(book):
    return {side: [(str(p), str(q)) for p, q in levels.items()] for side, levels in book.items()}


def run(capture, out):
    runtime = json.loads((capture/'runtime.json').read_text())
    books = Books('polymarket', runtime['mappings'])
    key_tokens = {m['market_key']: m['polymarket_yes_token'] for m in runtime['mappings'] if m.get('polymarket_yes_token')}
    observations = {}
    awaiting = set()
    request = None
    rows = []
    db = sqlite3.connect((capture/'events.sqlite').resolve().as_uri()+'?mode=ro&immutable=1', uri=True)
    kinds = ('venue_reset', 'polymarket', 'observation', 'book_rebuild', 'book_verification_selection', 'book_verification_raw')
    for seq, kind, source, at, ref, raw in db.execute('SELECT seq,kind,source,received_at,event_key,payload FROM events ORDER BY seq'):
        if kind not in kinds:
            continue
        r = json.loads(zlib.decompress(raw))
        if kind == 'venue_reset' and source == 'polymarket':
            books = Books('polymarket', runtime['mappings'])
            observations.clear()
            awaiting.clear()
        elif kind == 'book_rebuild':
            awaiting.update(r['tokens'])
            for token in r['tokens']:
                books.books.pop(token, None)
        elif kind == 'polymarket':
            if r.get('event_type') == 'book':
                awaiting.discard(r['asset_id'])
            elif r.get('event_type') == 'price_change' and awaiting:
                r = dict(r, price_changes=[c for c in r['price_changes'] if c['asset_id'] not in awaiting])
            books.consume(r, at, ref)
        elif kind == 'observation' and r.get('venue') == 'polymarket':
            token = key_tokens[r['market_key']]
            observations[token] = r
        elif kind == 'book_verification_selection':
            request = {t: {'book': serial(books.books[t]), 'observation': deepcopy(observations[t])} for t in r['tokens']}
        elif kind == 'book_verification_raw':
            if r.get('http_status') != 200 or not isinstance(r.get('payload'), list):
                continue
            assert request is not None
            assert sorted(request) == sorted(s['asset_id'] for s in r['payload'])
            for snapshot in r['payload']:
                token = snapshot['asset_id']
                prior = request[token]
                current = observations.get(token, {})
                args = dict(token=token, snapshot=snapshot, before=prior['book'], after=serial(books.books.get(token, {})),
                    generation_before=prior['observation'].get('connection_generation'), generation_after=current.get('connection_generation'),
                    revision_before=prior['observation'].get('book_revision'), revision_after=current.get('book_revision'),
                    request_started_at=r['request_started_at'], received_at=r['received_at'],
                    response_headers=r['response_headers'], source_reference=ref)
                row = {'raw_seq': seq, 'token': token, 'source_reference': ref}
                for name, verify in (('full', verify_snapshot), ('top', verify_top_snapshot)):
                    try:
                        row[name] = {'status': 'verified', 'evidence': verify(**args)}
                    except (ValueError, KeyError, TypeError) as exc:
                        row[name] = {'status': 'rejected', 'reason': str(exc)}
                rows.append(row)
    db.close()
    counts = Counter((r['full']['status'], r['top']['status']) for r in rows)
    summary = {'comparisons': len(rows), 'status_pairs': {str(k): v for k, v in counts.items()},
        'full_reasons': dict(Counter(r['full'].get('reason', 'verified') for r in rows)),
        'top_reasons': dict(Counter(r['top'].get('reason', 'verified') for r in rows)),
        'limitations': ['Captured request schedule and recovery actions held fixed.',
            'Top certificates are not inserted into pricing; RFQ coverage and performance are not yet evaluated.',
            'Both verifiers share chronology and canonicalization code; not an independent arithmetic audit.']}
    out.mkdir(parents=True, exist_ok=False)
    (out/'rows.json').write_text(json.dumps(rows, indent=2))
    (out/'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capture', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    run(a.capture, a.out)
