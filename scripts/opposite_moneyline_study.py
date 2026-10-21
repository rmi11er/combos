#!/usr/bin/env python3
"""Read-only historical paired-moneyline uncertainty experiment, without depth."""
import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime
from functools import lru_cache
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from combos.backtest import BacktestConfig, run_backtest
from combos.kalshi_history import KalshiHistory
from combos.historical_fair import History
from combos.pricing import fee_per_share
from mlb_entry_sweep import metrics


def loadgz(path):
    with gzip.open(path, 'rt') as f:
        return json.load(f)


def pair_width(ask, opposite_ask, rate, opposite_rate):
    """Two acquisition asks bracket an ordinary exhaustive binary payoff."""
    for x in (ask, opposite_ask):
        if not math.isfinite(x) or not 0 <= x <= 1:
            raise ValueError('invalid_ask')
    raw = ask + opposite_ask - 1
    if raw < -1e-10:
        raise ValueError('crossed_raw_pair')
    lower = max(0., 1-opposite_ask-fee_per_share(opposite_ask, opposite_rate))
    upper = min(1., ask+fee_per_share(ask, rate))
    return {'raw_width_cents': max(0., 100*raw), 'width': max(0., upper-lower),
            'lower': lower, 'upper': upper}


def joint_upper(points, widths):
    if len(points) != len(widths) or not 2 <= len(points) <= 4:
        raise ValueError('invalid_legs')
    if any(not math.isfinite(p) or not 0 <= p <= 1 for p in points):
        raise ValueError('invalid_point')
    if any(not math.isfinite(w) or not 0 <= w <= 1 for w in widths):
        raise ValueError('invalid_width')
    return math.prod(min(1., p+w/2) for p, w in zip(points, widths))


class PairHistory:
    def __init__(self, run, sport):
        self.run, self.sport = run, sport
        self.exchange = run/'exchange' if sport == 'mlb' else run
        self.history = KalshiHistory(self.exchange, fallback_dirs=[] if sport == 'mlb' else None)
        self.used = set()
        if sport == 'mlb':
            p = run/'cohort/underlying_markets.json.gz'
            self.native = loadgz(p); self.used.add(p)
        else:
            paths = sorted((ROOT/'data/raw/legs').glob('KXNCAAFGAME-*.json.gz'))
            self.native = {p.name[:-8]: loadgz(p)['payload']['market'] for p in paths}
            self.used.update(paths)
        events = defaultdict(list)
        prefix = 'KXMLBGAME-' if sport == 'mlb' else 'KXNCAAFGAME-'
        for ticker, m in self.native.items():
            if ticker.startswith(prefix):
                events[m['event_ticker']].append(ticker)
        self.opponents = {}
        for event, tickers in events.items():
            if len(tickers) != 2:
                continue
            a, b = (self.native[t] for t in tickers)
            team_field = 'baseball_team' if sport == 'mlb' else 'football_team'
            if (not a.get('custom_strike', {}).get(team_field)
                    or not b.get('custom_strike', {}).get(team_field)
                    or a['custom_strike'][team_field] == b['custom_strike'][team_field]
                    or a.get('rules_secondary') != b.get('rules_secondary')
                    or any(m.get('strike_type') != 'structured' for m in (a, b))):
                continue
            self.opponents.update({tickers[0]: tickers[1], tickers[1]: tickers[0]})
        mp = self.exchange/('polymarket_mapping_reviewed.json' if sport == 'mlb' else 'polymarket_mapping.json')
        self.maps = json.loads(mp.read_text()); self.used.add(mp)

    @lru_cache(maxsize=512)
    def pm_history(self, ticker):
        m = self.maps[ticker]
        path = self.exchange/'polymarket'/(m['token']+'.json.gz')
        data = loadgz(path)
        if data.get('status') != 200:
            raise ValueError('pm_http_error')
        self.used.add(path)
        return History(data['payload']['history'], 't'), data['params']

    def pm_point(self, ticker, at):
        hist, params = self.pm_history(ticker)
        if not params['startTs'] <= at-60 <= params['endTs']:
            raise ValueError('uncovered_pm_history')
        t, row = hist.latest(at, 60)
        return t, float(row['p'])

    @lru_cache(maxsize=150000)
    def pair(self, ticker, at, rate):
        opponent = self.opponents.get(ticker)
        if not opponent:
            raise ValueError('opposite_native_payoff_unavailable')
        a, b = self.history.at(ticker, at), self.history.at(opponent, at)
        self.used.update(Path(x['source_provenance']['file']) for x in (a, b))
        result = pair_width(a['yes_ask'], b['yes_ask'], rate, rate)
        result.update(ticker=ticker, opponent=opponent, state_at=[a['source_at'], b['source_at']],
                      age_seconds=[at-a['source_at'], at-b['source_at']],
                      state_skew_seconds=abs(a['source_at']-b['source_at']),
                      rate=rate, fee_basis='same_native_series_retained_historical_rate_scenario',
                      source_files=[x['source_provenance']['file'] for x in (a, b)],
                      midpoint_inconsistency_cents=100*((a['yes_bid']+a['yes_ask']+b['yes_bid']+b['yes_ask'])/2-1))
        try:
            ma, mb = self.maps[ticker], self.maps[opponent]
            if ma['condition_id'] != mb['condition_id'] or ma['token'] == mb['token']:
                raise ValueError('pm_noncomplementary_tokens')
            ta, pa = self.pm_point(ticker, at); tb, pb = self.pm_point(opponent, at)
            if not all(math.isfinite(p) and 0 <= p <= 1 for p in (pa, pb)):
                raise ValueError('invalid_pm_point')
            result['pm'] = {'signed_inconsistency': pa+pb-1, 'absolute_inconsistency': abs(pa+pb-1),
                            'state_at': [ta, tb], 'state_skew_seconds': abs(ta-tb),
                            'age_seconds': [at-ta, at-tb], 'semantics': 'archived_points_not_executable_spread'}
        except (KeyError, FileNotFoundError, ValueError) as exc:
            result['pm_error'] = str(exc)
        return result


def model_points(ctx, model, sport):
    if sport == 'mlb':
        return [x[model]['interval']['point'] for x in ctx['context']]
    if model in ('kalshi', 'pinnacle'):
        return [x['interval']['point'] for x in ctx['context'][model]]
    return [x['models'][model]['point'] for x in ctx['context']['three_venue']]


def study(args):
    sport, run = args.sport, args.run
    replay = run/('replay_settlement_refreshed' if sport == 'cfb' else 'replay')/'opportunities.json'
    context_path = run/'replay/pricing_context.jsonl.gz'
    data = json.loads(replay.read_text())
    series = 'KXMLBGAME' if sport == 'mlb' else 'KXNCAAFGAME'
    # MLB's older ready replay includes sampled surrounding dates. September 5
    # is the complete retained census; CFB uses ALL retained week data.
    candidates = defaultdict(list); coverage = Counter()
    for r in data['opportunities']:
        coverage['input_model_rows'] += 1
        if sport == 'mlb' and (r['source']['sampling_method'] != 'census'
                or datetime.fromtimestamp(r['at'], ZoneInfo('America/Chicago')).date().isoformat() != '2026-09-05'):
            coverage['outside_complete_MLB_day'] += 1; continue
        candidates[r['evaluation_id']].append(r)
    pairs = PairHistory(run, sport)
    features, rows, exclusions = {}, [], Counter()
    with gzip.open(context_path, 'rt') as f:
        for line in f:
            ctx = json.loads(line); identifier = ctx.get('evaluation_id', ctx.get('trade_id'))
            originals = candidates.get(identifier)
            if not originals:
                continue
            legs = ctx.get('legs') or originals[0]['source_context']['legs']
            if not 2 <= len(legs) <= 4 or any(not l['market_ticker'].startswith(series+'-') for l in legs):
                exclusions['not_two_to_four_moneyline_only'] += 1; continue
            if len({l['market_ticker'].rsplit('-', 1)[0] for l in legs}) != len(legs):
                exclusions['same_game'] += 1; continue
            coverage['moneyline_eligible_prints'] += 1
            try:
                k = ctx['context']['kalshi'] if sport == 'cfb' else [x['kalshi'] for x in ctx['context']]
                ps = [pairs.pair(l['market_ticker'], ctx['at'], v['fee_basis']['taker_rate']) for l, v in zip(legs, k)]
                native_width = [v['interval']['upper']-v['interval']['lower'] for v in k]
            except (ValueError, KeyError, FileNotFoundError) as exc:
                exclusions[str(exc)] += 1; continue
            feature = {'evaluation_id': identifier, 'at': ctx['at'], 'legs': legs, 'pairs': ps,
                       'max_raw_pair_width_cents': max(p['raw_width_cents'] for p in ps),
                       'synchronized_recent': all(p['state_skew_seconds'] <= 120 and max(p['age_seconds']) <= 300 for p in ps),
                       'pm_complete': all('pm' in p for p in ps)}
            features[identifier] = feature
            for r in originals:
                try:
                    raw = model_points(ctx, r['model'], sport)
                    if len(raw) != len(legs):
                        raise ValueError('leg_context_length_mismatch')
                    points = [p if l['side'] == 'yes' else 1-p for p, l in zip(raw, legs)]
                    if not math.isclose(math.prod(points), r['fair_point'], rel_tol=1e-8, abs_tol=1e-10):
                        raise ValueError('baseline_point_does_not_reconcile')
                except (KeyError, ValueError) as exc:
                    exclusions[r['model']+':'+str(exc)] += 1; continue
                paired_upper = joint_upper(points, [p['width'] for p in ps])
                rows.append({**r, 'native_width_upper': joint_upper(points, native_width),
                             'paired_width_upper': paired_upper,
                             'stressed_with_pair_floor': max(r['stressed_upper'], paired_upper),
                             'pm_disagreement_upper': joint_upper(points, [min(1., p['width']+2*p['pm']['absolute_inconsistency']) for p in ps]) if feature['pm_complete'] else None})
    coverage['paired_prints'] = len(features)
    coverage['paired_model_rows'] = len(rows)
    out = args.out; out.mkdir(parents=True, exist_ok=True)
    with gzip.open(out/'features.jsonl.gz', 'wt') as f:
        for item in features.values():
            f.write(json.dumps(item, separators=(',', ':'))+'\n')
    manifests = {'sport': sport, 'coverage': dict(coverage), 'exclusions': dict(exclusions),
                 'source_window': [data['start_at'], data['end_at']],
                 'scope': 'All covered retained 2–4 distinct-game moneyline-only prints; MLB complete September 5 census; CFB all retained week, partial outside Saturday.',
                 'pair_scope': 'Native same-event distinct teams, identical secondary rules; ordinary completed game complement assumption. No outcome-based eligibility filter.',
                 'fees': 'Retained baseline maker cash fees unchanged; native same-series taker rates remain historical scenarios. No additional fee charged as a realized expense.',
                 'proxy': 'Symmetric uncertainty radius = half fee-expanded paired ask span around UNCHANGED source fair. This is a proxy, not an executable composite book or measured liquidity.',
                 'comparison_basis': 'Within-model matched cohorts; not a cross-model common intersection. Sell-all retains quote guards and funded risk. Width-only policies omit dependence; stressed_with_pair_floor retains the existing stressed upper as a minimum.',
                 'PM_proxy': 'Separate sensitivity adds absolute paired archived-point inconsistency to each leg radius; not identified bid/ask spread.',
                 'statistics': 'Annualized Sharpe and daily variance suppressed: one complete MLB day / incomplete CFB dates; raw engine statistics not used as inferential results.',
                 'orders_enabled': False, 'parameter_selection': 'Fixed half-width; no PnL fitting.',
                 'input_hashes': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(pairs.used | {replay, context_path, Path(__file__), ROOT/'src/combos/backtest.py', ROOT/'src/combos/kalshi_history.py', ROOT/'scripts/mlb_entry_sweep.py'})}}
    summaries = []
    variants = [('sell_all', None), ('point_0.3c', 'fair_point'), ('native_width', 'native_width_upper'),
                ('opposite_width', 'paired_width_upper'), ('existing_stressed', 'stressed_upper'),
                ('stressed_with_pair_floor', 'stressed_with_pair_floor')]
    with gzip.open(out/'decisions.jsonl.gz', 'wt') as df, gzip.open(out/'curves.jsonl.gz', 'wt') as cf:
        for cohort in ('paired', 'synchronized_recent', 'pm_complete'):
            cohort_rows = [r for r in rows if cohort == 'paired' or features[r['evaluation_id']][cohort]]
            if not cohort_rows:
                continue
            policies = variants if cohort != 'pm_complete' else [('point_0.3c', 'fair_point'), ('opposite_width', 'paired_width_upper'), ('opposite_plus_PM_gap', 'pm_disagreement_upper')]
            for variant, key in policies:
                transformed = [{**r, 'stressed_upper': max(r['fair_point'], r[key]) if key else r['fair_point']} for r in cohort_rows]
                cfg = BacktestConfig(entry_basis='stressed_upper', entry_filter='all_priced' if key is None else 'minimum_edge')
                for constrained in (True, False):
                    result = run_backtest(transformed, data['start_at'], data['end_at'], cfg, constrained)
                    tag = {'cohort': cohort, 'variant': variant, 'constrained': constrained}
                    for summary in result['summaries']:
                        model = summary['model']; decisions = [d for d in result['decisions'] if d['model'] == model]
                        selected = [d for d in decisions if d['accepted']]
                        for field in ('annualized_sharpe', 'daily_return_variance', 'daily_return_variance_bp2', 'daily_pnl_variance_dollars2'):
                            summary[field] = None
                        summary['sharpe_unavailable_reason'] = 'insufficient complete independent dates; deliberately suppressed'
                        summaries.append({**tag, 'model': model, 'summary': summary, 'selected': metrics(selected),
                                          'rejected': metrics([d for d in decisions if not d['accepted']])})
                    for d in result['decisions']:
                        df.write(json.dumps({**tag, **d}, separators=(',', ':'))+'\n')
                    for c in result['curves']:
                        cf.write(json.dumps({**tag, **c}, separators=(',', ':'))+'\n')
            print(json.dumps({'cohort': cohort, 'rows': len(cohort_rows), 'finished': True}), flush=True)
    # Width bins describe the FULL paired population and baseline selections.
    bins = []
    for model in sorted({r['model'] for r in rows}):
        for lo, hi in ((0, 2), (2, 5), (5, 10), (10, 100.00001)):
            subset = [r for r in rows if r['model'] == model and lo <= features[r['evaluation_id']]['max_raw_pair_width_cents'] < hi]
            baseline = [r for r in subset if r['quote_allowed'] and r['quantity']*(r['yes_price']-r['fair_point'])-r['maker_fee'] >= .003*r['quantity']]
            bins.append({'model': model, 'width_bin_cents': [lo, hi], 'all': metrics(subset), 'point_selected_unlimited': metrics(baseline)})
    (out/'summary.json').write_text(json.dumps(summaries, indent=2, allow_nan=False)+'\n')
    (out/'width_bins.json').write_text(json.dumps(bins, indent=2, allow_nan=False)+'\n')
    (out/'manifest.json').write_text(json.dumps(manifests, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'out': str(out), **coverage, 'exclusions': dict(exclusions)}), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sport', choices=('cfb', 'mlb'), required=True)
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    study(p.parse_args())
