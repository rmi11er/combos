#!/usr/bin/env python3
"""Price every eligible retained CFB print; model coverage is explicit, never sampled.

Kalshi-only remains evaluable without external-market matches. Three-venue
models require their complete exact historical joins. Export both all available
model evaluations and their common cohort for paired comparisons.
"""
import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
from decimal import Decimal
from functools import lru_cache
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from combos.historical_fair import timestamp
from combos.joint_pricing import price_joint
from combos.matching import fixture_teams, norm
from combos.pricing import Interval, short_yes_economics
from combos.replay import complement


def gz(path):
    with gzip.open(path, 'rt') as f: return json.load(f)


@lru_cache(maxsize=100000)
def cached_joint(intervals, rho):
    return price_joint(intervals, rho)


@lru_cache(maxsize=10000)
def native_market(ticker):
    return gz(ROOT/'data/raw/legs'/f'{ticker}.json.gz')['payload']['market']


def canonical_buckets(legs, combo):
    contracts, fixtures = set(), set()
    for leg in legs:
        ticker = leg['market_ticker']; m = native_market(ticker)
        series, fixture = m['event_ticker'].split('-', 1)
        fixtures.add(fixture)
        teams = sorted(fixture_teams(m) or [])
        if series == 'KXNCAAFGAME':
            if len(teams) != 2: raise ValueError('canonical_team_identity_missing')
            key = f'{fixture}:full_game:moneyline:{teams[0]}'
        elif series == 'KXNCAAFSPREAD':
            selected = norm(m['yes_sub_title'].split(' wins by ')[0])
            if len(teams) != 2 or selected not in teams: raise ValueError('canonical_team_identity_missing')
            line = Decimal(str(m['floor_strike'])) * (1 if selected == teams[0] else -1)
            key = f'{fixture}:full_game:spread:{teams[0]}:{line.normalize():f}'
        elif series == 'KXNCAAFTOTAL':
            key = f'{fixture}:full_game:total:{Decimal(str(m["floor_strike"])).normalize():f}'
        else:
            # Period outright winners need not be complements when a tie can occur.
            # The native binary contract is canonical; fixture risk still aggregates.
            key = ticker
        contracts.add(key)
    return {'contract': sorted(contracts), 'fixture': sorted(fixtures), 'combo': [combo]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-run', type=Path, default=ROOT/'runs/cfb_full_week_20260907')
    parser.add_argument('--config', type=Path, default=ROOT/'config/cfb_fair_pilot.json')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(); args.out.mkdir(parents=True, exist_ok=True)
    settings = json.loads(args.config.read_text())
    spec = importlib.util.spec_from_file_location('cfb_pilot', ROOT/'scripts/cfb_fair_pilot.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.DATA = args.data_run
    pilot = module.Pilot(settings, args.data_run/'polymarket_mapping.json', allow_unsettled=True)
    from combos.kalshi_history import KalshiHistory
    from combos.pinnacle_history import PinnacleHistory
    kalshi = KalshiHistory(args.data_run)
    pinnacle = PinnacleHistory(args.data_run)
    tape_path = args.data_run/'cohort/combo_cohort.json.gz'; tape = gz(tape_path)
    cohort = json.loads((args.data_run/'cohort/summary.json').read_text())
    models = ('kalshi', 'pinnacle', 'blend', 'stronger_pinnacle')
    excluded = {m: Counter() for m in models}; rows = []; priced_ids = defaultdict(set)
    counts = Counter(); used_sources = set(); rejection_file = (args.out/'pricing_rejections.jsonl').open('w')
    context_file = gzip.open(args.out/'pricing_context.jsonl.gz', 'wt')
    started = time.time()
    try:
        for index, item in enumerate(tape['trades']):
            trade = item['trade']; identifier = trade['trade_id']; at = timestamp(trade['created_time'])
            market = tape['markets'][trade['ticker']]; legs = market['mve_selected_legs']
            reason = None
            if trade.get('taker_outcome_side', trade.get('taker_side')) != 'yes': reason = 'no_taker'
            q, p = float(trade['count_fp']), float(trade['yes_price_dollars'])
            if not 0 < p < 1 or q <= 0: reason = 'invalid_open_trade'
            event = market['event_ticker']
            if event.startswith('KXMVECROSSCATEGORY-SHARD1-'): rate = .035
            elif event.startswith('KXMVECROSSCATEGORY0-SHARD1-'): rate = 0.
            else: reason = 'unreviewed_fee_series'
            try: buckets = canonical_buckets(legs, trade['ticker'])
            except (ValueError, KeyError, FileNotFoundError) as exc: reason = str(exc)
            if reason:
                counts[reason] += 1
                rejection_file.write(json.dumps({'trade_id': identifier, 'stage': 'trade_eligibility', 'reason': reason})+'\n')
                continue
            fee = short_yes_economics(q, p, 0, rate)['maker_fee']
            settled = timestamp(market['settlement_ts']) if market.get('settlement_ts') else None
            settlement = float(market['settlement_value_dollars']) if settled is not None else None
            base = {'evaluation_id': identifier, 'at': at, 'quantity': q, 'yes_price': p, 'maker_fee': fee,
                    'sampling_weight': 1., 'settled_at': settled, 'yes_settlement': settlement, 'buckets': buckets,
                    'source_context': {'legs': legs, 'combo_ticker': trade['ticker'],
                                       'complete_trade_day': item.get('complete_trade_day'),
                                       'source_interval': item.get('source_interval'), 'maker_fee_rate': rate}}
            available = {}; contexts = {}; model_errors = {}
            try:
                k = [kalshi.at(l['market_ticker'], at) for l in legs]
                used_sources.update(v['source_provenance']['file'] for v in k)
                available['kalshi'] = ([complement(Interval(**v['interval']), l['side']) for v,l in zip(k, legs)], True, 1.)
                contexts['kalshi'] = k
            except (ValueError, KeyError, FileNotFoundError) as exc:
                excluded['kalshi'][str(exc)] += 1
                model_errors['kalshi'] = str(exc)
            try:
                pin = [pinnacle.at(l['market_ticker'], at) for l in legs]
                available['pinnacle'] = ([complement(Interval(**v['interval']), l['side']) for v,l in zip(pin, legs)], True, 1.)
                contexts['pinnacle'] = pin
            except (ValueError, KeyError, FileNotFoundError) as exc:
                excluded['pinnacle'][str(exc)] += 1
                model_errors['pinnacle'] = str(exc)
            try:
                missing = [l['market_ticker'] for l in legs if l['market_ticker'] not in pilot.maps]
                if missing: raise ValueError('incomplete_exact_three_venue_mapping')
                fairs = [pilot.fair(l['market_ticker'], at) for l in legs]
                contexts['three_venue'] = fairs
                for model in models[2:]:
                    key = 'stronger' if model == 'stronger_pinnacle' else 'blend'
                    intervals = [complement(Interval(**f['models'][model]), l['side']) for f,l in zip(fairs, legs)]
                    allowed = all(f[key]['guard']['quote_allowed'] for f in fairs) if model != 'pinnacle' else True
                    multiplier = min(f[key]['guard']['risk_multiplier'] for f in fairs) if model != 'pinnacle' else 1.
                    available[model] = (intervals, allowed, multiplier)
            except (ValueError, KeyError, FileNotFoundError) as exc:
                for model in models[2:]:
                    excluded[model][str(exc)] += 1; model_errors[model] = str(exc)
            for model, (intervals, allowed, multiplier) in available.items():
                try: joint = cached_joint(tuple(intervals), settings['correlation_rho'])
                except ValueError as exc:
                    excluded[model][str(exc)] += 1; model_errors[model] = str(exc); continue
                rows.append({**base, 'model': model, 'fair_point': joint['joint']['point'],
                             'stressed_upper': joint['stressed_upper'], 'quote_allowed': allowed, 'risk_multiplier': multiplier})
                priced_ids[identifier].add(model); counts[model] += 1
            if model_errors:
                rejection_file.write(json.dumps({'trade_id': identifier, 'available_models': sorted(available),
                                                'stage': 'pricing', 'model_reasons': model_errors,
                                                'missing_exact_legs': [l['market_ticker'] for l in legs if l['market_ticker'] not in pilot.maps]})+'\n')
            context_file.write(json.dumps({'trade_id': identifier, 'at': at, 'context': contexts}, separators=(',', ':'))+'\n')
            if index % 1000 == 0:
                pilot.cache.clear()
                print(json.dumps({'processed': index, 'total': len(tape['trades']), 'priced': dict(counts),
                                  'elapsed_seconds': round(time.time()-started)}), flush=True)
    finally:
        rejection_file.close(); context_file.close()
    references = [args.config, tape_path, args.data_run/'selection.json', args.data_run/'polymarket_mapping.json',
                  args.data_run/'cohort/manifest.json']
    references += [p for folder in ('history', 'kalshi_parts', 'polymarket') for p in sorted((args.data_run/folder).glob('*.gz'))]
    references += [Path(p) for p in sorted(used_sources)]
    references += [ROOT/'data/raw/legs'/f'{ticker}.json.gz' for ticker in
                   {leg['market_ticker'] for market in tape['markets'].values() for leg in market['mve_selected_legs']}]
    identity = {'configuration': settings, 'historical_only': True, 'input_files': {
        str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in references if p.exists()},
        'code_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in
                       [Path(__file__), ROOT/'scripts/cfb_fair_pilot.py', ROOT/'src/combos/kalshi_history.py',
                        ROOT/'src/combos/weighted_fair.py', ROOT/'src/combos/joint_pricing.py',
                        ROOT/'src/combos/pricing.py', ROOT/'src/combos/historical_fair.py',
                        ROOT/'src/combos/matching.py', ROOT/'src/combos/replay.py', ROOT/'src/combos/football_identity.py',
                        ROOT/'src/combos/pinnacle_history.py']}}
    cohort_id = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:12]
    payload = {'schema_version': 1, 'run_id': 'cfb-full-week:'+cohort_id,
               'display_name': 'CFB all retained week data', 'start_at': cohort['start_at'], 'end_at': cohort['end_at'],
               'candidate_prints': cohort['stages']['eligible_pregame_yes_taker']['prints'],
               'identity': identity, 'cohort_description': 'All eligible retained week prints; Saturday census, other days incomplete; no game sample',
               'opportunities': rows}
    (args.out/'opportunities.json').write_text(json.dumps(payload, separators=(',', ':'), allow_nan=False)+'\n')
    common = {key for key, values in priced_ids.items() if len(values) == len(models)}
    payload.update(run_id=payload['run_id']+':common', display_name='CFB all retained week data — common pricing cohort',
                   opportunities=[r for r in rows if r['evaluation_id'] in common])
    (args.out/'common_opportunities.json').write_text(json.dumps(payload, separators=(',', ':'), allow_nan=False)+'\n')
    report = {'source_cohort': cohort, 'eligible_public_prints': len(tape['trades']), 'priced_by_model': dict(counts),
              'common_priced_prints': len(common), 'pricing_exclusions': {k: dict(v) for k,v in excluded.items()},
              'exact_three_venue_legs': len(pilot.maps), 'mapping_exclusions': pilot.exclusions,
              'exact_pinnacle_legs': len(pinnacle.maps), 'pinnacle_mapping_exclusions': pinnacle.exclusions,
              'limitations': ['Kalshi uses all available native histories; external model comparisons require exact external joins.',
                             'Single-venue benchmarks use all their own available data; common input supplied for paired comparisons.',
                             'Retained sampled intervals are not a complete week portfolio path and are never multiplied by sampling weights.']}
    (args.out/'coverage.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('source_cohort', 'mapping_exclusions')}, indent=2))


if __name__ == '__main__': main()
