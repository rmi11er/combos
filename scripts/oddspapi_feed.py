#!/usr/bin/env python3
"""Inspect the account or run one quota-controlled Pinnacle REST recorder."""
import argparse
from collections import Counter
import fcntl
import hashlib
import json
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from combos.event_store import EventStore
from combos.oddspapi import OddsPapi
from combos.pinnacle_feed import fixture_index, normalize
from combos.pinnacle_matching import bind_selectors
from combos.request_budget import RequestBudget
from combos.runtime_clock import Deadline


def inspect(cache):
    envelope = OddsPapi(cache).get('account', refresh=True)
    payload = envelope['payload']
    # Never print the account envelope, identifiers or credential-bearing fields.
    return {'retrieved_at':envelope['retrieved_at'], 'subscriptions':[
        {k:s.get(k) for k in ('is_active','valid_from','valid_until','bookmakers',
                              'sport_ids','request_limit','request_count','websocket_access')}
        for s in payload.get('subscriptions',[]) if s.get('is_active') is True]}


def capture(args):
    deadline = Deadline(args.seconds)
    runtime = json.loads(Path(args.runtime).read_text())
    polling = json.loads(Path(args.polling).read_text())
    if not polling['tournament_ids']:raise ValueError('reviewed_tournament_ids_required')
    if polling['bookmakers'] not in (['pinnacle'],['pinnacle+30']):raise ValueError('single_pinnacle_feed_required')
    bookmaker=polling['bookmakers'][0]
    if polling.get('billing_cycle_start') is None or polling.get('billing_cycle_end') is None:
        raise ValueError('explicit_billing_boundaries_required')
    if polling.get('known_used') is None:raise ValueError('account_usage_reconciliation_required')
    if min(polling['active_poll_seconds'],polling['idle_poll_seconds']) < 30:
        raise ValueError('minimum_poll_interval_30_seconds')
    if polling['nominal_delay_seconds'] < 30:raise ValueError('delay_must_be_at_least_30_seconds')
    budget_path = Path(polling['budget_path']).resolve()
    budget_path.parent.mkdir(parents=True, exist_ok=True)
    # One owner per subscription across ALL run databases; quota claims also atomic.
    with open(str(budget_path)+'.collector.lock','a') as handle:
        try:fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('subscription_collector_already_running') from None
        budget = RequestBudget(budget_path, polling['billing_cycle_start'],polling['billing_cycle_end'],
            polling['subscription_request_limit'],polling['reserve_fraction'],polling['known_used'])
        store = EventStore(args.db); initialized = False
        try:
            manifest = store.get('runtime','manifest')
            if not manifest or manifest['config'] != runtime:raise ValueError('runtime_manifest_config_mismatch')
            for name, digest in manifest['code_sha256'].items():
                if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:
                    raise ValueError('runtime_manifest_source_mismatch')
            run = uuid.uuid4().hex; count = 0
            def emit(kind, payload, at):
                nonlocal count
                count += 1
                key = f'pinnacle:{run}:{count}'
                store.append(kind,'pinnacle',payload,key,at)
                return key
            client = OddsPapi(args.cache,request_budget=budget)
            catalog_envelope = client.get('markets', {'language':'en'}, max_cache_age_seconds=86400)
            catalog = [m for m in catalog_envelope['payload'] if m.get('sportId') == polling['sport_id']]
            with store.transaction():
                emit('venue_reset',{'venue':'pinnacle','reason':'collector_started'},time.time())
                emit('feed_configuration',{'polling':polling,
                    'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},time.time())
            initialized = True
            next_poll = 0.
            while not deadline.expired():
                if time.monotonic() >= next_poll:
                    active = any(time.time() < m['start_at']-runtime.get('pregame_cutoff_seconds',60)
                                 for m in runtime['mappings'])
                    interval = polling['active_poll_seconds'] if active else polling['idle_poll_seconds']
                    try:
                        envelope = client.get('odds-by-tournaments',
                            {'tournamentIds':','.join(map(str,polling['tournament_ids'])),
                             'bookmakers':bookmaker,'verbosity':3,'oddsFormat':'decimal'},
                            max_cache_age_seconds=interval-.001)
                        at = envelope['retrieved_at']
                        fixtures = fixture_index(envelope['payload'])
                        current_mappings = json.loads(json.dumps(runtime['mappings']))
                        selector_result = bind_selectors(current_mappings, list(fixtures.values()), catalog,
                                                         bookmaker=bookmaker)
                        prior = {m['market_key']: m for m in runtime['mappings']}
                        # Selector IDs may revise while the canonical payoff and
                        # reviewed assumptions remain unchanged. Carry only those
                        # reviewed fields across the exact rebind.
                        for mapping in current_mappings:
                            old = prior.get(mapping['market_key'], {})
                            old_spec = old.get('pinnacle') or {}
                            new_spec = mapping.get('pinnacle') or {}
                            for field in ('payoff_reference', 'limit_currency', 'limit_unit', 'limit_reference'):
                                if field in old_spec and new_spec:
                                    new_spec[field] = old_spec[field]
                            if new_spec:
                                mapping['pinnacle'] = new_spec
                        with store.transaction():
                            reference = emit('external_raw',envelope,at)
                            emit('pinnacle_selector_audit', {
                                'matched': selector_result['candidate_mappings'],
                                'unmatched': selector_result['unmatched_mappings'],
                                'rejected_native_reasons': dict(Counter(r['reason'] for r in selector_result['rejected_native_markets'])),
                            }, at)
                            counts = Counter()
                            for mapping in current_mappings:
                                row,phase = normalize(mapping,fixtures,at,reference,polling['nominal_delay_seconds'],bookmaker,envelope,
                                                      runtime.get('pinnacle_freshness_policy'))
                                emit('observation',row,at)
                                counts['active' if row['active'] else row['invalid_reason']] += 1
                                if phase is not None:
                                    emit('fixture_status',{'fixture_key':mapping['fixture_key'],
                                        'phase':phase,'source_reference':reference},at)
                            emit('feed_status',{'venue':'pinnacle','status':'snapshot_received',
                                'fixtures':len(fixtures),'normalization':dict(counts),'requests_used':budget.used()},at)
                    except (RuntimeError,ValueError,KeyError,TypeError):
                        # Raw cache survives parse failure. Never log exception text
                        # from an external transport or credential-bearing request.
                        with store.transaction():
                            emit('venue_reset',{'venue':'pinnacle','reason':'poll_or_normalization_failed'},time.time())
                        raise
                    next_poll = time.monotonic()+interval
                with store.transaction():emit('heartbeat',{'venue':'pinnacle'},time.time())
                time.sleep(min(1., max(0., next_poll-time.monotonic())))
            with store.transaction():emit('capture_timing',{'venue':'pinnacle',**deadline.elapsed()},time.time())
        finally:
            if initialized:
                with store.transaction():
                    store.append('venue_reset','pinnacle',{'venue':'pinnacle','reason':'collector_stopped'},
                                 'pinnacle:stop:'+uuid.uuid4().hex,time.time())
            store.close();budget.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cache',default=str(ROOT/'data/raw/oddspapi_live'))
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('inspect')
    c=sub.add_parser('capture');c.add_argument('--db',required=True)
    c.add_argument('--runtime',default=str(ROOT/'config/runtime_nfl_week1.json'))
    c.add_argument('--polling',default=str(ROOT/'config/oddspapi_polling.json'))
    c.add_argument('--seconds',required=True,type=float)
    args=p.parse_args()
    if args.command=='inspect':print(json.dumps(inspect(args.cache),indent=2))
    else:capture(args)


if __name__=='__main__':main()
