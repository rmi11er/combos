#!/usr/bin/env python3
"""Offline selector, normal-game payoff and timestamp review. Never enables quotes."""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from combos.feed_freshness import FreshnessAudit
from combos.pinnacle_feed import fixture_index, same_native_market_identity
from combos.pinnacle_matching import bind_selectors

RULES_URL = 'https://www.pinnacle.com/en/future/betting-rules'


def native_payoff(spec, home_score, away_score, side):
    parts = spec[side]['bookmaker_outcome_id'].split('/')
    kind = spec['catalog']['marketType']
    if kind == 'moneyline':
        margin = home_score - away_score
        if not margin:
            return None  # stake refund, not a 0.5 binary-contract payout
        return int(margin > 0) if parts[0] == 'home' else int(margin < 0)
    if kind == 'spreads':
        home_cover = Decimal(home_score - away_score) + Decimal(parts[0]) > 0
        return int(home_cover if parts[-1] == 'home' else not home_cover)
    if kind == 'totals':
        over = Decimal(home_score + away_score) > Decimal(parts[0])
        return int(over if parts[-1] == 'over' else not over)
    raise ValueError('outside_full_game_review')


def review_mapping(mapping, fixture):
    kind = mapping['market_type']
    if mapping.get('period', 'full_game') != 'full_game' or kind not in ('moneyline', 'spreads', 'totals'):
        return {'status':'deferred_period_or_team_total'}
    spec = mapping.get('pinnacle')
    if not spec or fixture is None:
        return {'status':'exact_selector_unavailable'}
    suffix = mapping['market_key'][len(mapping['fixture_key'])+1:].split(':')
    home,away = ({'JAX':'JAC','LA':'LAR'}.get(fixture['participant'+str(i)+'Abbr'],fixture['participant'+str(i)+'Abbr']) for i in (1,2))
    if kind in ('moneyline','spreads') and suffix[1] not in (home,away):
        return {'status':'normal_game_mismatch','reason':'selected_team_not_in_fixture'}
    mismatches = []
    ties = 0
    checked = 0
    # Independent settlement enumeration checks the mapped side/line against
    # every integer score pair 0..100; it is not a probability or tie estimate.
    for hs in range(101):
        for aws in range(101):
            if kind == 'moneyline':
                target = .5 if hs == aws else int((hs > aws) if suffix[1] == home else (aws > hs))
            elif kind == 'spreads':
                margin = hs-aws if suffix[1] == home else aws-hs
                target = int(Decimal(margin) > Decimal(suffix[-1]))
            else:
                target = int(Decimal(hs+aws) > Decimal(suffix[-1]))
            actual = native_payoff(spec, hs, aws, 'yes')
            opposite = native_payoff(spec, hs, aws, 'no')
            checked += 1
            if actual is None:
                ties += 1
            elif actual != target or opposite != 1-target:
                if len(mismatches) < 3:
                    mismatches.append({'home_score':hs,'away_score':aws,'target':target,'native':actual})
    return {'status':'normal_game_mismatch' if mismatches else
            'normal_game_verified_tie_basis_required' if ties else 'normal_game_binary_verified',
            'score_pairs_checked':checked, 'tie_void_pairs':ties, 'mismatches':mismatches,
            'source_rules':RULES_URL,
            'exchange_rule_reference':mapping['mapping_reference'],
            'meaning':'identity/payoff verification conditional on normal completed game; not unconditional pricing approval',
            'exceptional_basis':['Pinnacle 12h start deadline versus exchange postponement terms',
                'Pinnacle 55-minute suspension and venue-change rules differ',
                'cancellation/void versus exchange cash settlement'],
            'remaining_requirements':['exception-state adjustment or explicit model basis reserve',
                'Pinnacle limit currency confirmation', 'validated source information-time policy']}


def run(runtime_path, raw_dir, catalog_path, output):
    output.mkdir(parents=True, exist_ok=True)
    runtime=json.loads(runtime_path.read_text())
    envelopes=[]; hashes={}
    for path in raw_dir.rglob('*.json.gz'):
        with gzip.open(path,'rt') as handle: envelope=json.load(handle)
        if envelope.get('request',{}).get('endpoint') != 'odds-by-tournaments': continue
        envelopes.append(envelope)
        hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    envelopes.sort(key=lambda x:x['retrieved_at'])
    if not envelopes: raise ValueError('no archived tournament snapshots')
    fixtures=fixture_index(envelopes[-1]['payload'])
    old_counts=Counter(); old_rows=[]
    for mapping in runtime['mappings']:
        spec=mapping.get('pinnacle'); status='selector_absent'
        if spec:
            fixture=fixtures.get(spec['fixture_id'])
            book=(fixture or {}).get('bookmakerOdds',{}).get('pinnacle+30',{})
            market=book.get('markets',{}).get(spec['market_id'])
            if not market: status='market_absent'
            elif market['bookmakerMarketId']==spec['bookmaker_market_id']: status='native_id_unchanged'
            elif same_native_market_identity(spec['bookmaker_market_id'],market['bookmakerMarketId'],fixture,book,spec): status='revision_only_verified'
            else: status='identity_change_requires_review'
        old_counts[status]+=1
        old_rows.append({'market_key':mapping['market_key'],'status':status})
    candidate=deepcopy(runtime)
    rebound=bind_selectors(candidate['mappings'],list(fixtures.values()),json.loads(catalog_path.read_text()))
    counts=Counter(); rows=[]
    for mapping in candidate['mappings']:
        spec=mapping.get('pinnacle')
        result=review_mapping(mapping,fixtures.get(spec['fixture_id']) if spec else None)
        counts[result['status']]+=1
        row={'market_key':mapping['market_key'],'review':result}
        rows.append(row)
        mapping['pinnacle_review'] = result
        # These are useful reviewed selector candidates; exceptional-state cash
        # payoffs, USD limits and source-time policy have not been certified.
        mapping['pricing_block_reason']='pinnacle_payoff_mapping_unreviewed'
    candidate['comment']='Offline reviewed selector candidates; normal-game checks only. All pricing blocks retained.'
    audit=FreshnessAudit()
    for envelope in envelopes: audit.add(envelope)
    summary={'input_runtime':str(runtime_path),'input_runtime_sha256':hashlib.sha256(runtime_path.read_bytes()).hexdigest(),
        'snapshot_hashes':hashes,'catalog_sha256':hashlib.sha256(catalog_path.read_bytes()).hexdigest(),
        'old_selectors':dict(old_counts),'refreshed_selectors':rebound,
        'payoff_review_counts':dict(counts),'pricing_ready_mappings':0,
        'freshness':audit.report(),'delay_toxicity_conclusion':'not tested; no inference from quiet prices',
        'snapshot_received_at':envelopes[-1]['retrieved_at']}
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    (output/'mapping_reviews.json').write_text(json.dumps(rows,indent=2)+'\n')
    (output/'original_selector_status.json').write_text(json.dumps(old_rows,indent=2)+'\n')
    (output/'runtime_reviewed_candidates.json').write_text(json.dumps(candidate,indent=2)+'\n')
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime',type=Path,required=True)
    parser.add_argument('--raw-dir',type=Path,required=True)
    parser.add_argument('--catalog',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=run(args.runtime,args.raw_dir,args.catalog,args.output)
    print(json.dumps({k:result[k] for k in ('old_selectors','payoff_review_counts','pricing_ready_mappings')},indent=2))
