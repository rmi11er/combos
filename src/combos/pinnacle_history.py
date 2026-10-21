"""Independent Pinnacle historical fair; exchange prices/depth are not inputs."""
from dataclasses import asdict
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
import json
import math
from pathlib import Path

from .football_identity import provider_team_key, provider_team_identity
from .historical_fair import History, timestamp
from .matching import norm
from .pricing import pinnacle_fair

ROOT = Path(__file__).resolve().parents[2]
SERIES = {'KXNCAAFGAME': 'moneyline', 'KXNCAAFSPREAD': 'spreads', 'KXNCAAFTOTAL': 'totals'}


def _read_gzip(path):
    with gzip.open(path, 'rt') as stream:
        return json.load(stream)


class PinnacleHistory:
    """Exact full-game ML/half-point payoff joins, including unsettled fixtures.

    The weekly mapping file supplies fixture teams/time only, regardless of its
    PM payoff-match status. Native Kalshi metadata supplies the selected payoff.
    Archive availability is assumed to be createdAt + 30 seconds; unchanged
    active state is carried forward without claiming verified live freshness.
    """
    def __init__(self, data_run, *, mapping_path=None, market_dir=None, catalog_path=None,
                 extra_archive_delay=30., pregame_cutoff_seconds=60.):
        self.data_run = Path(data_run)
        self.market_dir = Path(market_dir) if market_dir else ROOT / 'data/raw/legs'
        mapping_path = Path(mapping_path) if mapping_path else self.data_run / 'polymarket_mapping.json'
        catalog_path = Path(catalog_path) if catalog_path else ROOT / 'runs/oddspapi_freshness_20260907/football_market_catalog.json'
        self.delay, self.cutoff = float(extra_archive_delay), float(pregame_cutoff_seconds)
        if not math.isfinite(self.delay) or self.delay < 30:
            raise ValueError('historical Pinnacle delay must be at least thirty seconds')
        if not math.isfinite(self.cutoff) or self.cutoff < 60:
            raise ValueError('pregame cutoff must be at least sixty seconds')
        self.maps, self.exclusions, self._pairs_cache = {}, [], {}
        self.market_exclusions = []
        self._catalog = {str(row['marketId']): row for row in json.loads(catalog_path.read_text())}
        self._catalog_reference = str(catalog_path)
        self._catalog_hash = hashlib.sha256(catalog_path.read_bytes()).hexdigest()
        self._mapping_reference = str(mapping_path)
        self._mapping_hash = hashlib.sha256(mapping_path.read_bytes()).hexdigest()
        fixtures = json.loads((self.data_run / 'fixtures.json').read_text())['payload']
        by_fixture = {}
        for fixture in fixtures:
            key = (tuple(sorted(provider_team_key(fixture, i) for i in (1, 2))), timestamp(fixture['startTime']))
            by_fixture.setdefault(key, []).append(fixture)
        mappings = json.loads(mapping_path.read_text())
        for ticker, row in mappings.items():
            try:
                kind = SERIES[ticker.split('-')[0]]
                # No row['status'], token, fee, depth, candle or PM-price requirements.
                identity = (tuple(sorted(row['teams'])), timestamp(row['start_time']))
                candidates = by_fixture.get(identity, [])
                if len(candidates) != 1:
                    raise ValueError('no_exact_fixture_identity' if not candidates else 'ambiguous_fixture_identity')
                fixture = candidates[0]
                market_path = self.market_dir / f'{ticker}.json.gz'
                market = _read_gzip(market_path)['payload']['market']
                if market.get('ticker', ticker) != ticker:
                    raise ValueError('Kalshi metadata ticker mismatch')
                team = 'over' if kind == 'totals' else norm(market['yes_sub_title'].split(' wins by ')[0])
                line = None if kind == 'moneyline' else Decimal(str(market['floor_strike']))
                if line is not None and (not line.is_finite() or abs(line) % 1 != Decimal('.5')):
                    raise ValueError('exact_half_point_payoff_required')
                pairs = self._pairs(fixture)
                payoff = (kind, team, line)
                if payoff not in pairs:
                    raise ValueError('no_exact_pinnacle_payoff')
                entry = pairs[payoff]
                if isinstance(entry, str):
                    raise ValueError(entry)
                yes, no, mid, yes_oid, no_oid, source, source_hash = entry
                self.maps[ticker] = {'fixture': fixture, 'kind': kind, 'team': team, 'line': line,
                    'start_at': timestamp(fixture['startTime']), 'pin_yes': yes, 'pin_no': no,
                    'native_market_id': mid, 'native_yes_outcome_id': yes_oid,
                    'native_no_outcome_id': no_oid, 'source_path': source, 'source_sha256': source_hash,
                    'kalshi_metadata_path': str(market_path),
                    'kalshi_metadata_sha256': hashlib.sha256(market_path.read_bytes()).hexdigest(),
                    'provider_team_identities': [provider_team_identity(fixture, i) for i in (1, 2)]}
            except (KeyError, ValueError, TypeError, OSError, InvalidOperation) as exc:
                reason = str(exc) if isinstance(exc, ValueError) else (
                    'required_metadata_missing' if isinstance(exc, (KeyError, OSError)) else 'invalid_payoff_metadata')
                self.exclusions.append({'ticker': ticker, 'reason': reason})

    def _pairs(self, fixture):
        fid = fixture['fixtureId']
        if fid in self._pairs_cache:
            pairs = self._pairs_cache[fid]
            if isinstance(pairs, str):
                raise ValueError(pairs)
            return pairs
        path = self.data_run / 'history' / f'{fid}.json.gz'
        if not path.exists():
            self._pairs_cache[fid] = 'missing_pinnacle_fixture_history'
            raise ValueError('missing_pinnacle_fixture_history')
        payload = _read_gzip(path)['payload']
        if payload.get('fixtureId') != fid:
            raise ValueError('Pinnacle history fixture mismatch')
        book = payload.get('bookmakers', {}).get('pinnacle+30', {}).get('markets', {})
        pairs = {}; home, away = (provider_team_key(fixture, i) for i in (1, 2))
        source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        for mid, market in book.items():
            description = self._catalog.get(str(mid), {})
            kind = description.get('marketType')
            if (description.get('playerProp') is not False or description.get('period') != 'result'
                    or kind not in ('moneyline', 'spreads', 'totals')):
                continue
            line = None if kind == 'moneyline' else Decimal(str(description['handicap']))
            if line is not None and (not line.is_finite() or abs(line) % 1 != Decimal('.5')):
                continue
            names = {row['outcomeName']: str(row['outcomeId']) for row in description['outcomes']}
            labels = ('Over', 'Under') if kind == 'totals' else ('1', '2')
            if set(names) != set(labels) or len(description['outcomes']) != 2:
                continue
            history_error = None
            try:
                histories = [History(market['outcomes'][names[label]]['players']['0'], 'createdAt') for label in labels]
            except KeyError:
                self.market_exclusions.append({'fixture_id': fid, 'native_market_id': str(mid),
                                               'reason': 'missing_opposing_native_history'})
                continue
            except ValueError as exc:
                history_error = str(exc)
                self.market_exclusions.append({'fixture_id': fid, 'native_market_id': str(mid),
                                               'reason': history_error})
            for i, label in enumerate(labels):
                if kind == 'totals' and i == 1:
                    continue
                team = 'over' if kind == 'totals' else home if i == 0 else away
                # Native handicap is the home team's spread: home -h / away +h
                # becomes the exact Kalshi winning-margin threshold.
                threshold = None if kind == 'moneyline' else line if kind == 'totals' or i == 1 else -line
                payoff = (kind, team, threshold)
                if payoff in pairs:
                    pairs[payoff] = 'ambiguous_native_payoff'
                    self.market_exclusions.append({'fixture_id': fid, 'native_market_id': str(mid),
                                                   'reason': 'ambiguous_native_payoff'})
                    continue
                if history_error is not None:
                    pairs[payoff] = history_error
                else:
                    pairs[payoff] = (histories[i], histories[1-i], str(mid), names[label], names[labels[1-i]],
                                     str(path), source_hash)
        self._pairs_cache[fid] = pairs
        return pairs

    def at(self, ticker, at):
        decision_at = float(at)
        if not math.isfinite(decision_at):
            raise ValueError('finite decision timestamp required')
        if ticker not in self.maps:
            raise ValueError('unmapped_pinnacle_payoff')
        mapped = self.maps[ticker]
        if decision_at >= mapped['start_at'] - self.cutoff:
            raise ValueError('pregame_cutoff')
        yes_at, yes = mapped['pin_yes'].latest(decision_at, self.delay)
        no_at, no = mapped['pin_no'].latest(decision_at, self.delay)
        if yes.get('active') is not True or no.get('active') is not True:
            raise ValueError('Pinnacle latest activity must be explicitly true')
        available = max(yes_at, no_at) + self.delay
        if available > decision_at:
            raise ValueError('historical lookahead')
        interval = pinnacle_fair(float(yes['price']), float(no['price']))
        return {'interval': asdict(interval), 'source_at': min(yes_at, no_at),
                'source_provenance': {'venue': 'pinnacle+30', 'historical_only': True,
                    'source_at_basis': 'oldest selected opposing-side creation time',
                    'source_path': mapped['source_path'], 'source_sha256': mapped['source_sha256'],
                    'native_market_id': mapped['native_market_id'],
                    'native_yes_outcome_id': mapped['native_yes_outcome_id'],
                    'native_no_outcome_id': mapped['native_no_outcome_id'],
                    'fixture_id': mapped['fixture']['fixtureId'], 'kickoff_at': mapped['start_at'],
                    'yes_state_at': yes_at, 'no_state_at': no_at, 'available_at_assumption': available,
                    'extra_archive_delay_seconds': self.delay, 'upstream_freshness_validated': False,
                    'historical_active_state_carry_forward_assumed': True,
                    'payoff_basis': 'normal_completed_game_only; exceptional terms unverified',
                    'kalshi_metadata_path': mapped['kalshi_metadata_path'],
                    'kalshi_metadata_sha256': mapped['kalshi_metadata_sha256'],
                    'fixture_mapping_reference': self._mapping_reference,
                    'fixture_mapping_sha256': self._mapping_hash,
                    'catalog_reference': self._catalog_reference, 'catalog_sha256': self._catalog_hash,
                    'provider_team_identities': mapped['provider_team_identities']}}
