#!/usr/bin/env python3
"""Stream a bounded runtime log into a health, coverage and creator review.

Read-only SQLite access; no orders, consumer changes or uncompressed event copy.
Volume is separated into requested contracts, target ticket cost and public prints.
"""
from array import array
from collections import Counter, defaultdict
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import time
import zlib
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from combos.rfq_scope import collection_candidate


def review(path, mappings, out):
    out.mkdir(parents=True, exist_ok=False)
    db = sqlite3.connect('file:' + str(path.resolve()) + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    end = db.execute('SELECT COALESCE(MAX(seq),0) FROM events').fetchone()[0]
    kinds = Counter(); raw_types = Counter(); decisions = Counter(); leg_counts = Counter()
    by_legs = defaultdict(Counter)
    scope = Counter(); books = Counter(); mapped_seen = defaultdict(set)
    trade_ids = set(); trades = Counter(); sizes = Counter(); resets = []; errors = []
    policy_counts = Counter(); lags = array('d'); minutes = defaultdict(Counter)
    maps = {m['kalshi_ticker']: m for m in mappings}
    first = last = None; cursor = 0; last_progress = time.monotonic()
    missing_decisions = []; observations = Counter()
    last_message = {}; message_gaps = []; capture_timing = []
    with (out / 'creator_evidence.jsonl').open('w') as evidence:
        while cursor < end:
            rows = db.execute('SELECT * FROM events WHERE seq>? AND seq<=? ORDER BY seq LIMIT 2000', (cursor, end)).fetchall()
            if not rows:
                raise ValueError('missing event tail')
            for row in rows:
                cursor = row['seq']; kind = row['kind']; at = row['received_at']; kinds[kind] += 1
                first = at if first is None else min(first, at); last = at if last is None else max(last, at)
                p = json.loads(zlib.decompress(row['payload']))
                minute = int(at // 60) * 60
                if kind in ('kalshi', 'polymarket'):
                    raw_types[kind + ':' + str(p.get('type') or p.get('event_type'))] += 1
                    if kind in last_message and at-last_message[kind] > 5:
                        message_gaps.append({'venue':kind,'after_at':last_message[kind],
                            'resumed_at':at,'seconds':at-last_message[kind],'resumed_seq':cursor})
                    last_message[kind] = at
                rfq = p if kind == 'rfq' else p.get('msg') if kind == 'kalshi' and p.get('type') == 'rfq_created' else None
                if rfq is not None:
                    scope['rfq_received'] += 1; minutes[minute]['rfqs'] += 1
                    legs = rfq.get('mve_selected_legs') or []; leg_counts[len(legs)] += 1
                    scope['creator_missing'] += not bool(rfq.get('creator_id'))
                    if not db.execute('SELECT 1 FROM decisions WHERE source_seq=?', (cursor,)).fetchone():
                        missing_decisions.append(cursor)
                    if rfq.get('contracts_fp'):
                        sizes['requested_contracts'] += float(rfq['contracts_fp'])
                    if rfq.get('target_cost_dollars'):
                        sizes['requested_target_cost_dollars'] += float(rfq['target_cost_dollars'])
                    if collection_candidate(legs,{'sport':'NFL','minimum_legs':2,'maximum_legs':4}):
                        scope['two_through_four_nonplayer_nfl'] += 1
                        found = [maps.get(l['market_ticker']) for l in legs]
                        if all(found):
                            scope['all_legs_mapped'] += 1
                            if len({m['fixture_key'] for m in found}) == len(legs):
                                scope['mapped_cross_game'] += 1; minutes[minute]['mapped_cross_game_rfqs'] += 1
                if kind == 'kalshi' and p.get('type') == 'trade':
                    msg = p['msg']; tid = msg.get('trade_id')
                    if not tid:
                        trades['missing_trade_id'] += 1
                    elif tid in trade_ids:
                        trades['duplicate_trade_frames'] += 1
                    else:
                        trade_ids.add(tid); trades['unique_public_prints'] += 1
                        if msg['market_ticker'].startswith('KXMVE'):
                            qty = float(msg['count_fp']); price = float(msg['yes_price_dollars'])
                            trades['combo_public_prints'] += 1
                            trades['combo_contracts_traded'] += qty
                            trades['combo_yes_consideration_dollars'] += qty * price
                            minutes[minute]['public_combo_contracts'] += qty
                elif kind == 'decision':
                    decisions[p.get('reason') or p['status']] += 1
                    lags.append(p.get('completed_processing_lag_seconds',p['processing_lag_seconds']))
                    n=len(p.get('request',{}).get('mve_selected_legs') or [])
                    by_legs[n]['decisions'] += 1
                    by_legs[n]['reason:'+str(p.get('reason') or p['status'])] += 1
                    if p['status']=='shadow_quote':
                        values={'shadow_quotes':1,'proposed_yes_premium_dollars':p['economics']['customer_premium'],
                            'proposed_payout_notional_dollars':p['quantity'],
                            'proposed_stressed_net_edge_dollars':p['economics']['expected_edge'],
                            'proposed_maximum_loss_dollars':p['economics']['maximum_loss']}
                        for key,value in values.items():
                            by_legs[n][key]+=value;minutes[minute][key]+=value
                        by_legs[n]['dependence_reserve_cents_sum']+=p.get('pricing',{}).get('dependence',{}).get('reserve_cents',0)

                elif kind == 'observation':
                    venue = p['venue']; observations[venue] += 1
                    books[venue + (':active' if p.get('active') else ':inactive')] += 1
                    mapped_seen[venue].add(p['market_key'])
                elif kind == 'venue_reset':
                    resets.append(dict(seq=cursor, at=at, **p))
                elif kind == 'consumer_error':
                    errors.append(dict(seq=cursor, **p))
                elif kind == 'capture_timing':
                    capture_timing.append(p)
                elif kind == 'creator_policy':
                    policy_counts[p['state']['status']] += 1
                    record = dict(seq=cursor, at=at, **p)
                    if p['state']['reason'] in ('duplicate_request_burst', 'repeated_duplicate_bursts'):
                        trigger = db.execute('SELECT kind,payload FROM events WHERE seq=?', (p['state']['evidence_source_seq'],)).fetchone()
                        raw_trigger = json.loads(zlib.decompress(trigger['payload']))
                        request = raw_trigger if trigger['kind'] == 'rfq' else raw_trigger['msg']
                        record['trigger_request'] = request
                        signature = p['evidence']['signature']; creator = p['creator_id']
                        policy = json.loads(db.execute("SELECT config FROM consumers WHERE name='creators'").fetchone()[0])
                        window = policy['window_seconds']
                        total = db.execute('SELECT COUNT(*) FROM creator_requests WHERE creator=? AND at>? AND at<=?', (creator, at-window, at)).fetchone()[0]
                        repeated = db.execute('SELECT COUNT(*) FROM creator_requests WHERE creator=? AND signature=? AND at>? AND at<=?', (creator, signature, at-window, at)).fetchone()[0]
                        record['reconstructed_window'] = {'total': total, 'same_leg_set': repeated,
                            'duplicate_fraction': repeated / total if total else None, 'window_seconds': window,
                            'meets_burst_rule': total >= policy['minimum_requests'] and repeated >= policy['duplicate_fraction'] * total}
                    evidence.write(json.dumps(record, sort_keys=True) + '\n')
            if time.monotonic() - last_progress > 20:
                print(json.dumps({'reviewed_through_seq': cursor, 'end_seq': end}), flush=True)
                last_progress = time.monotonic()
    duration = (last - first) if first is not None else 0
    cursors = [dict(r) for r in db.execute('SELECT name,seq,updated_at FROM consumers')]
    creator_rows = db.execute('SELECT COUNT(*), COUNT(DISTINCT creator) FROM creator_requests').fetchone()
    active = dict(db.execute('SELECT status, COUNT(*) FROM creator_active GROUP BY status').fetchall())
    storage = sum(p.stat().st_size for p in (path, Path(str(path)+'-wal')) if p.exists())
    lag_values = sorted(lags)
    def quantile(q):
        if not lag_values: return None
        index = (len(lag_values)-1)*q; low = int(index); high = min(low+1,len(lag_values)-1)
        return lag_values[low] + (lag_values[high]-lag_values[low])*(index-low)
    result = {'db': str(path), 'through_seq': end, 'first_at': first, 'last_at': last, 'duration_seconds': duration,
        'events_by_kind': dict(kinds), 'raw_message_types': dict(raw_types), 'scope': dict(scope),
        'mapping_coverage_note': 'Eligibility joined to the supplied mapping snapshot; not evidence of three-venue prices or fills.',
        'decisions_by_reason': dict(decisions), 'missing_decisions': missing_decisions,
        'decision_coverage_complete': not missing_decisions and sum(decisions.values()) == scope['rfq_received'],
        'leg_counts': dict(leg_counts), 'decisions_by_leg_count':dict(by_legs),
        'proposal_totals_note':'Sums over hypothetical quotes, including repeated customers/overlapping exposure. Not fills, deployable capital or captured edge.', 'requested_sizes_not_trades': dict(sizes), 'public_trades': dict(trades),
        'creator_distinct_rfq_ids': creator_rows[0], 'unique_creators': creator_rows[1],
        'creator_policy_transitions': dict(policy_counts), 'creator_final_explicit_states': active,
        'observations': dict(observations), 'book_validity': dict(books),
        'unique_observed_mappings': {v: len(keys) for v,keys in mapped_seen.items()},
        'feed_resets': resets, 'consumer_errors': errors, 'consumers': cursors,
        'recorded_message_gaps_over_5_seconds':message_gaps, 'capture_timing':capture_timing,
        'all_consumers_drained': all(c['seq'] == end for c in cursors),
        'lag_measure':'through_decision_computation_when_recorded; legacy_rows_use_initial_processing_lag',
        'lag_seconds': {'median': quantile(.5), 'p99': quantile(.99), 'maximum': max(lags,default=None)},
        'storage_bytes': storage, 'storage_gb_per_day_at_this_rate': storage/duration*86400/1e9 if duration else None,
        'disk_free_bytes': shutil.disk_usage(path.parent).free,
        'minutes': [{'utc_minute': datetime.fromtimestamp(t,timezone.utc).isoformat(), **counts} for t,counts in sorted(minutes.items())]}
    (out/'summary.json').write_text(json.dumps(result, indent=2) + '\n')
    (out/'manifest.json').write_text(json.dumps({'through_seq':end, 'created_at':time.time(),
        'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.glob('*.json*'))}},indent=2)+'\n')
    db.close()
    print(json.dumps({k: result[k] for k in ('through_seq','duration_seconds','scope','decision_coverage_complete','unique_creators',
        'creator_policy_transitions','unique_observed_mappings','lag_seconds','storage_bytes','all_consumers_drained')}, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--mapping-config', type=Path, default=Path('config/runtime_nfl_week1.json'))
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    review(args.db, json.loads(args.mapping_config.read_text())['mappings'], args.out)
