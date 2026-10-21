"""Mechanical config migration: enable reviewed moneyline selectors, no orders."""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from authorize_nfl_event_mappings import accepted_review, LIMIT_REFERENCE
from combos.event_types import validate_event_type

ROOT = Path(__file__).resolve().parents[1]


def enable(config, candidates, reviews, digest):
    existing = {m['market_key']:m for m in config['mappings']}
    enabled=[]; unavailable=[]
    for source in candidates:
        if source['market_type'] != 'moneyline': continue
        result = reviews.get(source['market_key'])
        if not source.get('pinnacle') or not accepted_review(source, result):
            unavailable.append(source['kalshi_ticker']); continue
        m=deepcopy(existing.get(source['market_key'], source))
        if m.get('pricing_block_reason') not in (None, 'pinnacle_payoff_mapping_unreviewed', 'void_basis_required'):
            unavailable.append(m['kalshi_ticker']); continue
        spec=m.get('pinnacle')
        if not spec or not spec.get('selector_reference'):
            unavailable.append(m['kalshi_ticker']); continue
        profile=validate_event_type(m)
        status='moneyline_tie_normalized_user_accepted' if result['status']=='void_basis_required' else result['status']
        m['event_type']=profile['event_type']
        m['event_resolution']=dict(reference=profile['reference'],normal_game_basis=status,
            review_artifact_sha256=digest,score_pairs_checked=result['score_pairs_checked'],
            void_score_pairs=result.get('void_score_pairs',0),
            exception_policy='status_and_exchange_terms_guard; no silent payoff substitution')
        spec.update(payoff_reference=f"{profile['reference']}:score-grid:{digest}",
            settlement_policy='nonplayer_rules_v1',limit_currency='USD',limit_unit='stake',
            limit_reference=LIMIT_REFERENCE,
            selector_status='exact_catalog_candidate; moneyline_payoff_authorized')
        m['payoff_review']={**m.get('payoff_review',{}),'status':status,'review_artifact_sha256':digest}
        basis=m['payoff_review'].get('basis')
        if basis is not None: basis['pinnacle']=status
        m.pop('pricing_block_reason',None)
        existing[m['market_key']]=m; enabled.append(m['kalshi_ticker'])
    config=deepcopy(config);config['mappings']=list(existing.values())
    # This is mapping eligibility in both pricing modes, not order activation.
    config['moneyline_authorization']={'review_artifact_sha256':digest,'enabled':len(enabled),
        'basis':'user_accepts_full_game_tie_void_normalization; exact_period_spreads_unchanged',
        'unavailable_selectors':unavailable}
    if any(m.get('period','full_game')!='full_game' for m in config['mappings']):
        config.get('candidate_scope',{})['full_game_only']=False
    return config, dict(enabled=len(enabled),unavailable=unavailable,
        enabled_periods=dict(Counter(existing[k]['period'] for k in existing if existing[k]['kalshi_ticker'] in enabled)))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',action='append',required=True,type=Path);a=p.parse_args()
    source=ROOT/'runs/morning_research_20260908/pinnacle_delivery_mapping_review/runtime_reviewed_candidates.json'
    review=ROOT/'runs/nfl_all_payoff_enumeration_20260909/rows.json'
    candidates=json.loads(source.read_text())['mappings']
    reviews={r['market_key']:r['review'] for r in json.loads(review.read_text())}
    digest=hashlib.sha256(review.read_bytes()).hexdigest()
    for path in a.config:
        original=json.loads(path.read_text())
        config,report=enable(original,candidates,reviews,digest)
        # Bulk mechanical migration. Preserve all execution switches and limits.
        path.write_text(json.dumps(config,indent=2)+'\n')
        print(json.dumps(dict(config=str(path),**report)))
