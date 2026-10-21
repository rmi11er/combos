"""OddsPapi v4 full snapshots, exact reviewed selectors, conservative source age.

Unreviewed payload semantics remain a pricing exclusion. This is a REST adapter,
not a Pinnacle WebSocket or a substitution of receipt time for source change time.
"""
from datetime import datetime
import math
from .observations import Observation


def timestamp(value):
    if not isinstance(value, str):raise ValueError('native_timestamp_missing')
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:raise ValueError('native_timestamp_timezone_missing')
    return dt.timestamp()


def fixture_index(payload):
    # Public v4 docs show a single fixture. Accept a fixture or an explicit list;
    # unknown wrappers fail rather than guessing where a partial snapshot lives.
    rows = [payload] if isinstance(payload, dict) and 'fixtureId' in payload else payload
    if not isinstance(rows, list):raise ValueError('unreviewed_batch_payload_shape')
    result = {}
    for row in rows:
        key = str(row['fixtureId'])
        if key in result:raise ValueError('duplicate_fixture_in_snapshot')
        result[key] = row
    return result


def same_native_market_identity(previous, current, fixture, book, spec):
    """Allow observed Pinnacle line/alternate-line revisions to advance.

    v4 snapshots retain catalog market/outcome IDs and the native side/line
    strings while components 4 and (for altLine) 5 change. This is not a
    general prefix match: unknown shapes, changed periods,
    fixtures, sports, leagues and outcome lines still fail closed.
    """
    if previous == current:
        return True
    if not isinstance(previous, str) or not isinstance(current, str):
        return False
    old, new = previous.split('/'), current.split('/')
    if not old or old[0] not in ('line', 'altLine'):
        return False
    expected_length = 7 if old[0] == 'line' else 8
    if len(old) != expected_length or len(new) != expected_length:
        return False
    revision_indices = {4} if old[0] == 'line' else {4, 5}
    if any(old[i] != new[i] for i in range(expected_length) if i not in revision_indices):
        return False
    if any(not old[i].isdigit() or not new[i].isdigit() for i in revision_indices):
        return False
    if fixture.get('sportId') != 14 or fixture.get('tournamentId') != 31:
        return False
    if old[1:3] != ['15', '889']:
        return False
    if str((fixture.get('externalProviders') or {}).get('pinnacleId')) != old[3]:
        return False
    if str(book.get('bookmakerFixtureId')) != old[3]:
        return False
    catalog = spec.get('catalog') or {}
    if str(catalog.get('marketId')) != str(spec['market_id']):
        return False
    outcomes = catalog.get('outcomes') or []
    if len(outcomes) != 2 or {str(o.get('outcomeId')) for o in outcomes} != {
        str(spec['yes']['outcome_id']), str(spec['no']['outcome_id'])
    }:
        return False
    market = book.get('markets', {}).get(str(spec['market_id']), {})
    if set(market.get('outcomes', {})) != {str(o['outcomeId']) for o in outcomes}:
        return False
    for side in ('yes', 'no'):
        selection = spec[side]
        players = market['outcomes'][str(selection['outcome_id'])].get('players', {})
        if set(players) != {'0'} or players['0'].get('bookmakerOutcomeId') != selection['bookmaker_outcome_id']:
            return False
    return True


def normalize(mapping, fixtures, received_at, source_reference, delay_seconds=30., bookmaker='pinnacle', snapshot=None, freshness_policy=None):
    row = {'market_key':mapping['market_key'], 'venue':'pinnacle', 'observed_at':received_at,
           'available_at':received_at, 'active':False, 'source_reference':source_reference,
           'mapping_reference':mapping['mapping_reference'], 'provider_bookmaker':bookmaker}
    phase = None
    try:
        if bookmaker not in ('pinnacle','pinnacle+30'):raise ValueError('unsupported_pinnacle_feed')
        spec = mapping.get('pinnacle')
        if not spec or not spec.get('selector_reference'):
            raise ValueError('pinnacle_selector_unreviewed')
        fixture = fixtures.get(str(spec['fixture_id']))
        if fixture is None:raise ValueError('fixture_missing_in_snapshot')
        phase = {0:'pregame',1:'in_play',2:'finished',3:'cancelled'}.get(fixture.get('statusId'), 'unknown')
        if phase != 'pregame':raise ValueError('pinnacle_fixture_not_pregame')
        if mapping.get('market_type') not in ('moneyline','spreads','totals','team_totals') or mapping.get('period','full_game') not in ('full_game','first_half','first_quarter') or mapping.get('player_prop',False) is not False:
            raise ValueError('outside_supported_non_player_scope')
        catalog=spec.get('catalog')
        if catalog is not None:
            expected={'full_game':'result','first_half':'p1+p2','first_quarter':'p1'}[mapping.get('period','full_game')]
            kind=mapping['market_type']
            allowed_types={'teamtotals-team1','teamtotals-team2'} if kind=='team_totals' else {kind}
            if kind=='moneyline' and expected!='result':allowed_types={'spreads'}
            if catalog.get('playerProp') is not False or catalog.get('sportId')!=14 or catalog.get('period')!=expected or catalog.get('marketType') not in allowed_types:
                raise ValueError('pinnacle_catalog_scope_mismatch')
        # Full-game moneyline settlement has been reviewed against the
        # published Pinnacle and exchange rules.  Other families continue to
        # require an explicit payoff reference and remain fail-closed.
        rules_vetted = spec.get('settlement_policy') in ('full_game_moneyline_rules_v1', 'nonplayer_rules_v1')
        if not spec.get('payoff_reference') or (mapping.get('pricing_block_reason') and not rules_vetted):
            raise ValueError('pinnacle_payoff_mapping_unreviewed')
        if spec.get('limit_currency') != 'USD' or spec.get('limit_unit') != 'stake' or not spec.get('limit_reference'):
            raise ValueError('pinnacle_limit_units_unreviewed')
        book = fixture['bookmakerOdds'][bookmaker]
        if book.get('bookmakerIsActive') is not True or book.get('suspended') is not False:
            raise ValueError('pinnacle_book_inactive')
        market = book['markets'][str(spec['market_id'])]
        if not same_native_market_identity(spec['bookmaker_market_id'], market.get('bookmakerMarketId'), fixture, book, spec):
            raise ValueError('pinnacle_market_line_changed')
        if market.get('marketActive') is not True:raise ValueError('pinnacle_market_inactive')
        values, times = {}, []
        for side in ('yes','no'):
            selector = spec[side]
            value = market['outcomes'][str(selector['outcome_id'])]['players']['0']
            if value.get('active') is not True or value.get('playerName') is not None:
                raise ValueError('pinnacle_outcome_inactive_or_prop')
            if value.get('bookmakerOutcomeId') != selector['bookmaker_outcome_id']:
                raise ValueError('pinnacle_outcome_line_changed')
            values[side] = value
            # Price-change timestamps are intentionally not refreshed on a poll.
            changed = timestamp(value.get('bookmakerChangedAt') or value.get('changedAt'))
            if not math.isfinite(changed) or changed > received_at:
                raise ValueError('pinnacle_source_clock_ahead')
            times.append(changed)
        if spec['yes']['outcome_id'] == spec['no']['outcome_id']:
            raise ValueError('pinnacle_opposing_outcomes_identical')
        row.update(observed_at=min(*times, received_at-delay_seconds),
                   decimal_odds_yes=values['yes']['price'], decimal_odds_no=values['no']['price'],
                   max_stake_yes=values['yes']['limit'], max_stake_no=values['no']['limit'],
                   limit_currency='USD',limit_unit='stake',active=True,
                   native_changed_at=times, freshness_basis='older_of_both_price_changes_and_nominal_delay')
        row['native_market_identity_context'] = {
            'reviewed_bookmaker_market_id': spec['bookmaker_market_id'],
            'snapshot_bookmaker_market_id': market['bookmakerMarketId'],
            'revision_changed': spec['bookmaker_market_id'] != market['bookmakerMarketId'],
            'validation': 'exact_catalog_outcomes_and_native_side_line; line_revision_components_only',
        }
        row['freshness_context']={'bookmaker_changed_at':{side:values[side].get('bookmakerChangedAt') for side in values},
            'vendor_changed_at':{side:values[side].get('changedAt') for side in values},
            'response_received_at':received_at,'request_started_at':(snapshot or {}).get('request_started_at'),
            'response_headers':(snapshot or {}).get('response_headers',{}),'nominal_delay_seconds':delay_seconds,
            'upstream_freshness_validated':False,
            'weight_age_basis':'conservative_last_change_proxy_pending_verified_snapshot_policy'}
        if freshness_policy is not None:
            from .snapshot_age import delivery_observation_time
            observed, context = delivery_observation_time(snapshot, received_at, delay_seconds, freshness_policy)
            row.update(observed_at=observed, freshness_basis=context['weight_age_basis'])
            row['freshness_context'].update(context)
        Observation.from_record(row)
    except (KeyError, TypeError, ValueError) as exc:
        row.update(active=False,invalid_reason=str(exc))
    return row, phase
