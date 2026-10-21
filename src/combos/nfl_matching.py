"""Deterministic NFL full-game joins; no fuzzy or nearest-line fallback.

These mappings establish exchange collection identities and normal-game payoffs.
They do not assert that sportsbook pushes or exceptional settlements are equal.
"""
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal
import hashlib
import json
import re
from zoneinfo import ZoneInfo
from .payoff_risk import nfl_risk_identity

SERIES = {'KXNFLGAME': 'moneyline', 'KXNFLSPREAD': 'spreads', 'KXNFLTOTAL': 'totals'}
PM_CODES = {'JAX': 'JAC', 'LA': 'LAR'}
MONTHS = {m: i for i, m in enumerate(('JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'), 1)}
FEE_SCHEDULE = 'https://kalshi.com/docs/kalshi-fee-schedule.pdf'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def array(value):
    return json.loads(value) if isinstance(value, str) else value


def pm_code(value):
    value = value.upper()
    return PM_CODES.get(value, value)


def event_identity(event, codes):
    """Ticker date is Eastern scheduled date; never use expiry as kickoff."""
    match = re.fullmatch(r'KXNFL(?:GAME|SPREAD|TOTAL)-(\d{2})([A-Z]{3})(\d{2})([A-Z]+)', event)
    if not match:
        raise ValueError('unsupported_kalshi_event')
    yy, mm, dd, pair = match.groups()
    day = datetime(2000 + int(yy), MONTHS[mm], int(dd)).date().isoformat()
    splits = [(a, pair[len(a):]) for a in codes if pair.startswith(a) and pair[len(a):] in codes and a != pair[len(a):]]
    if len(splits) != 1:
        raise ValueError('ambiguous_fixture_teams')
    return day, tuple(sorted(splits[0]))


def half_line(value):
    line = Decimal(str(value))
    if not line.is_finite() or abs(line) % 1 != Decimal('.5'):
        raise ValueError('integer_or_invalid_line_requires_push_model')
    return line


def polymarket_fee(market):
    if market.get('feesEnabled') is False:
        return 0.0
    schedule = market.get('feeSchedule') or {}
    if schedule.get('exponent') != 1 or schedule.get('takerOnly') is not True:
        raise ValueError('unsupported_polymarket_fee_schedule')
    rate = Decimal(str(schedule.get('rate')))
    if not rate.is_finite() or not 0 <= rate < 1:
        raise ValueError('invalid_polymarket_fee_rate')
    return float(rate)


def kalshi_rates(series):
    multip = Decimal(str(series['fee_multiplier']))
    if not multip.is_finite() or not 0 <= multip <= 10:
        raise ValueError('invalid_kalshi_fee_multiplier')
    kind = series['fee_type']
    maker = {'quadratic': Decimal('0'), 'quadratic_with_maker_fees': Decimal('.0175'),
             'quadratic_with_combo_maker_fees': Decimal('.035')}.get(kind)
    if maker is None:
        raise ValueError('unsupported_kalshi_fee_type')
    return {'maker': float(maker * multip), 'taker': float(Decimal('.07') * multip)}


def validate_pm_payoff(market, outcomes, aliases, line):
    """Cross-check machine-readable lines against the actual settlement text."""
    description = market['description']
    if re.search(r'first half|second half|\bquarter\b|regulation only', description, re.I):
        raise ValueError('period_rules_conflict_with_full_game')
    typ = market['sportsMarketType']
    if typ == 'moneyline':
        if 'tie' not in description.lower() or '50-50' not in description:
            raise ValueError('moneyline_tie_terms_unrecognized')
        for label in outcomes:
            if f'If {label} wins, the market will resolve to "{label}".' not in description:
                raise ValueError('moneyline_outcome_rules_unrecognized')
    elif typ == 'totals':
        match = re.search(r'resolve to "Over".*?combine to score (\d+) or more points', description, re.S)
        under = re.search(r'combined total is less than (\d+).*?resolve to "Under"', description, re.S)
        if not match or not under or Decimal(match[1]) != line + Decimal('.5') or match[1] != under[1]:
            raise ValueError('total_line_and_rules_disagree')
    else:
        match = re.search(r'resolve to "([^"]+)" if the (.+?) win the game by (\d+) or more points', description)
        labels = [o.casefold() for o in outcomes]
        if not match or match[1].casefold() not in labels or match[2].casefold() not in aliases:
            raise ValueError('spread_rules_unrecognized')
        i = labels.index(match[1].casefold())
        handicap = line if i == 0 else -line
        if handicap >= 0 or Decimal(match[3]) != -handicap + Decimal('.5') or aliases.get(labels[i]) != aliases[match[2].casefold()]:
            raise ValueError('spread_line_and_rules_disagree')
        if f'Otherwise, this market will resolve to "{outcomes[1-i]}".' not in description:
            raise ValueError('spread_complement_rules_unrecognized')


def build_mappings(kalshi_markets, pm_events, series, season, week):
    codes = set()
    team_ids = {}
    for market in kalshi_markets:
        if market['ticker'].split('-')[0] == 'KXNFLGAME':
            code = market['ticker'].rsplit('-', 1)[-1]
            codes.add(code)
            team_id = market['custom_strike']['football_team']
            if team_id in team_ids and team_ids[team_id] != code:
                raise ValueError('conflicting_kalshi_team_identity')
            team_ids[team_id] = code

    fixtures = {}
    rejected_pm = []
    for event in pm_events:
        if event.get('seriesSlug') != f'nfl-{season}' or event.get('eventWeek') != week:
            raise ValueError('unexpected_polymarket_season_or_week')
        teams = event.get('teams') or []
        if len(teams) != 2 or any(t.get('league') != 'nfl' for t in teams):
            raise ValueError('invalid_polymarket_fixture_teams')
        pair = tuple(sorted(pm_code(t['abbreviation']) for t in teams))
        if len(set(pair)) != 2 or not set(pair) <= codes:
            raise ValueError('unknown_polymarket_team')
        identity = (event['eventDate'], pair)
        if identity in fixtures:
            raise ValueError('duplicate_polymarket_fixture')
        start = datetime.fromisoformat(event['startTime'].replace('Z', '+00:00'))
        if start.tzinfo is None:
            raise ValueError('kickoff_timezone_missing')
        if start.astimezone(ZoneInfo('America/New_York')).date().isoformat() != event['eventDate']:
            raise ValueError('kickoff_and_eastern_event_date_disagree')
        aliases = {}
        for team in teams:
            for label in (team['alias'], team['name'], team['abbreviation']):
                key = label.casefold()
                code = pm_code(team['abbreviation'])
                if key in aliases and aliases[key] != code:
                    raise ValueError('ambiguous_team_alias')
                aliases[key] = code
        candidates = defaultdict(list)
        for market in event.get('markets', []):
            typ = market.get('sportsMarketType')
            if typ not in SERIES.values():
                continue
            try:
                if not market.get('active') or market.get('closed') or not market.get('acceptingOrders'):
                    raise ValueError('polymarket_not_accepting_orders')
                outcomes, tokens = array(market['outcomes']), array(market['clobTokenIds'])
                if len(outcomes) != 2 or len(tokens) != 2 or len(set(tokens)) != 2 or not all(str(t).isdigit() for t in tokens):
                    raise ValueError('invalid_binary_outcomes')
                rate = polymarket_fee(market)
                line = half_line(market['line']) if typ != 'moneyline' else None
                description = market.get('description', '')
                if not description or not market.get('conditionId'):
                    raise ValueError('payoff_definition_missing')
                validate_pm_payoff(market, outcomes, aliases, line)
                pending = []
                for i, label in enumerate(outcomes):
                    if typ == 'totals':
                        if label.casefold() not in ('over', 'under'):
                            raise ValueError('invalid_total_outcome')
                        key = (typ, label.casefold(), line)
                    else:
                        if label.casefold() not in aliases:
                            raise ValueError('unknown_outcome_team')
                        code = aliases[label.casefold()]
                        # The signed handicap belongs to outcome zero, not home/away.
                        key = (typ, code, None if typ == 'moneyline' else -(line if i == 0 else -line))
                    pending.append((key, (market, i, str(tokens[i]), rate)))
                for key, candidate in pending:
                    candidates[key].append(candidate)
            except (KeyError, TypeError, ValueError) as exc:
                rejected_pm.append({'market_id': market.get('id'), 'reason': str(exc)})
        fixtures[identity] = (event, start.timestamp(), candidates)

    mappings, unmatched = [], []
    eligible_counts = Counter()
    for market in sorted(kalshi_markets, key=lambda m: m['ticker']):
        ticker = market['ticker']; series_id = ticker.split('-')[0]
        if series_id not in SERIES:
            continue
        typ = SERIES[series_id]
        try:
            identity = event_identity(market['event_ticker'], codes)
            if identity not in fixtures:
                raise ValueError('outside_requested_week_or_fixture_unmatched')
            eligible_counts[typ] += 1
            if market.get('status') != 'active':
                raise ValueError('kalshi_not_active')
            event, start, candidates = fixtures[identity]
            line = half_line(market['floor_strike']) if typ != 'moneyline' else None
            team = 'over' if typ == 'totals' else team_ids[market['custom_strike']['football_team']]
            if typ != 'totals' and team not in identity[1]:
                raise ValueError('team_not_in_fixture')
            if typ != 'moneyline' and 'more than ' + str(market['floor_strike']) not in market['rules_primary']:
                raise ValueError('kalshi_strict_threshold_unrecognized')
            if typ == 'moneyline' and '$0.50' not in market['rules_secondary']:
                raise ValueError('kalshi_moneyline_tie_terms_unrecognized')
            matches = candidates.get((typ, team, line), [])
            if len(matches) != 1:
                raise ValueError('exact_payoff_not_listed' if not matches else 'ambiguous_exact_payoff')
            pm, outcome_index, token, pm_rate = matches[0]
            basis = {'normal_game': 'full_game_including_overtime', 'tie': 'each_team_0.5' if typ == 'moneyline' else 'binary_half_point_line',
                     'exception_basis': 'Kalshi_48h_and_fair_price_rules_differ_from_Polymarket_postponement_and_cancellation',
                     'pinnacle': 'pending_provider_payoff_and_push_review',
                     'combo_settlement': 'product_of_underlying_settlement_values'}
            proof = {'kalshi_ticker': ticker, 'kalshi_rules': [market['rules_primary'], market['rules_secondary']],
                     'polymarket_id': pm['id'], 'condition_id': pm['conditionId'], 'description': pm['description'],
                     'outcomes': array(pm['outcomes']), 'selected_index': outcome_index, 'token': token,
                     'start_at': start, 'basis': basis}
            fixture_key = 'NFL:' + identity[0] + ':' + '-'.join(identity[1])
            payoff_key = typ + ':' + team + (':' + str(line) if line is not None else '')
            mappings.append({'market_key': fixture_key + ':' + payoff_key, 'fixture_key': fixture_key,
                'sport': 'NFL', 'start_at': start, 'market_type': typ, 'kalshi_ticker': ticker,
                'polymarket_yes_token': token, 'polymarket_market_id': str(pm['id']),
                'polymarket_condition_id': pm['conditionId'], 'polymarket_event_slug': event['slug'],
                'mapping_reference': 'nfl-payoff-v1:sha256:' + digest(proof), 'payoff_review': proof,
                'pricing_block_reason': 'pinnacle_payoff_mapping_unreviewed',
                'fees': {'kalshi': {'rate': kalshi_rates(series[series_id])['taker'],
                    'fee_model':'venue_cash_v2','balance_precision':'.0001',
                    'precision_basis':'direct_member_reference; verify account before execution',
                    'reference': FEE_SCHEDULE + '#series=' + series_id + '&sha256=' + digest(series[series_id])},
                    'polymarket': {'rate': pm_rate,
                    'fee_model':'venue_cash_v2',
                    'reference': 'https://gamma-api.polymarket.com/markets/' + str(pm['id']) + '#feeSchedule-sha256=' + digest(pm.get('feeSchedule'))}}})
        except (KeyError, TypeError, ValueError) as exc:
            unmatched.append({'kalshi_ticker': ticker, 'market_type': typ, 'reason': str(exc)})
    if len({m['market_key'] for m in mappings}) != len(mappings):
        raise ValueError('duplicate_canonical_payoff')
    for mapping in mappings:
        mapping['risk_identity']=nfl_risk_identity(mapping)
    return mappings, {'season': season, 'week': week, 'fixtures': len(fixtures), 'kalshi_in_week': dict(eligible_counts),
        'matched': dict(Counter(m['market_type'] for m in mappings)), 'unmatched': unmatched,
        'rejected_polymarket': rejected_pm, 'pricing_ready': False,
        'remaining': ['Pinnacle payoff mapping and live observations', 'exceptional settlement basis policy', 'user risk caps']}
