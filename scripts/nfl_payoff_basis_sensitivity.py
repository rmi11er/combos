"""Saved-snapshot sensitivity, not a live fair or estimated exception model."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from combos.payoff_basis import exchange_payoff_bounds
from combos.pinnacle_feed import fixture_index


def run(runtime_path, snapshot_path, reviews_path, out):
    paths = [runtime_path, snapshot_path, reviews_path, Path(__file__),
             Path(__file__).resolve().parents[1]/'src/combos/payoff_basis.py']
    hashes = {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    runtime = json.loads(runtime_path.read_text())
    reviews = {r['market_key']:r['review'] for r in json.loads(reviews_path.read_text())}
    with gzip.open(snapshot_path, 'rt') as handle:
        fixtures = fixture_index(json.load(handle)['payload'])
    rows, excluded = [], Counter()
    for mapping in runtime['mappings']:
        review = reviews[mapping['market_key']]
        if review['status'] not in ('completed_period_binary_verified', 'void_basis_required'):
            excluded[review['status']] += 1
            continue
        spec = mapping['pinnacle']
        fixture = fixtures[spec['fixture_id']]
        book = fixture['bookmakerOdds']['pinnacle+30']
        market = book['markets'][str(spec['market_id'])]
        if fixture.get('statusId') != 0 or book.get('bookmakerIsActive') is not True or book.get('suspended') is not False or market.get('marketActive') is not True:
            excluded['inactive'] += 1
            continue
        odds = []
        for side in ('yes', 'no'):
            selector = spec[side]
            value = market['outcomes'][selector['outcome_id']]['players']['0']
            if value['bookmakerOutcomeId'] != selector['bookmaker_outcome_id']:
                raise ValueError('changed exact outcome')
            if value.get('active') is not True:
                break
            price = float(value['price'])
            if not math.isfinite(price) or price <= 1:
                raise ValueError('invalid decimal odds')
            odds.append(price)
        if len(odds) != 2:
            excluded['inactive_outcome'] += 1
            continue
        q = (1/odds[0])/(1/odds[0]+1/odds[1])
        full_moneyline = mapping['market_type'] == 'moneyline' and mapping.get('period','full_game') == 'full_game'
        if review['status'] == 'void_basis_required' and not full_moneyline:
            raise ValueError('non-moneyline push requires different basis model')
        for tie_upper in ((0,.005,.01,.02) if full_moneyline else (0,)):
            for exception_upper in (0,.001,.005,.01):
                result = exchange_payoff_bounds((q,q), tie_probability=(0,tie_upper),
                    exception_probability=(0,exception_upper), exception_payoff=(0,1))
                rows.append({'market_key':mapping['market_key'], 'full_game_moneyline':full_moneyline,
                    'conditional_proportional_devig':q, 'tie_probability_upper':tie_upper,
                    'exception_probability_upper':exception_upper,
                    'lower':result['lower'], 'upper':result['upper'],
                    'upper_reserve_cents':100*(result['upper']-q),
                    'lower_difference_cents':100*(q-result['lower'])})
    summary_rows = []
    for is_ml in (False, True):
        for t in ((0,.005,.01,.02) if is_ml else (0,)):
            for e in (0,.001,.005,.01):
                group = [r for r in rows if (r['full_game_moneyline'], r['tie_probability_upper'], r['exception_probability_upper']) == (is_ml,t,e)]
                if not group:
                    continue
                upper = [r['upper_reserve_cents'] for r in group]
                magnitude = [max(r['upper_reserve_cents'],r['lower_difference_cents']) for r in group]
                summary_rows.append({'full_game_moneyline':is_ml,'tie_upper':t,'exception_upper':e,
                    'mappings':len(group),'median_upper_reserve_cents':statistics.median(upper),
                    'maximum_upper_reserve_cents':max(upper),'maximum_absolute_difference_cents':max(magnitude)})
    for p, digest in hashes.items():
        if hashlib.sha256(Path(p).read_bytes()).hexdigest() != digest:
            raise ValueError('input changed')
    out.mkdir(parents=True, exist_ok=False)
    summary = {'input_hashes':hashes,'excluded':dict(excluded), 'scenarios':summary_rows,
        'assumptions_empirically_validated':False,'pricing_authorized':False,
        'conditional_fair_method':'two_way_proportional_devig'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    (out/'rows.json').write_text(json.dumps(rows,indent=2))
    return summary


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('runtime','snapshot','reviews','out'):
        p.add_argument('--'+name, required=True, type=Path)
    a = p.parse_args()
    result = run(a.runtime,a.snapshot,a.reviews,a.out)
    print(json.dumps({'scenarios':len(result['scenarios']),'excluded':result['excluded']}))
