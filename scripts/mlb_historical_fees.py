"""Explicit dated historical fee assumptions for research, never live defaults."""
import json
import math
import re
from pathlib import Path


def load_fee_scenario(path):
    data = json.loads(Path(path).read_text())
    if data.get('schema_version') != 1 or not data.get('reference'):
        raise ValueError('fee_scenario_schema_and_reference_required')
    for name in ('start_at', 'end_at', 'kalshi_combo_maker_rate', 'kalshi_leg_taker_rate'):
        value = data.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError('invalid_fee_scenario_' + name)
    if data['start_at'] >= data['end_at']:
        raise ValueError('invalid_fee_scenario_interval')
    if any(not 0 <= data[key] < 1 for key in ('kalshi_combo_maker_rate', 'kalshi_leg_taker_rate')):
        raise ValueError('invalid_fee_scenario_rate')
    if type(data.get('historical_effective_date_verified')) is not bool:
        raise ValueError('explicit_fee_verification_status_required')
    policy = data.get('polymarket_rate_policy')
    if policy not in ('native_market_schedule_unverified', 'fixed_scenario'):
        raise ValueError('explicit_polymarket_fee_policy_required')
    if policy == 'fixed_scenario':
        rate = data.get('polymarket_taker_rate')
        if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not math.isfinite(rate) or not 0 <= rate < 1:
            raise ValueError('invalid_polymarket_scenario_rate')
    if data['historical_effective_date_verified'] and policy == 'native_market_schedule_unverified':
        raise ValueError('unverified_native_PM_schedule_cannot_be_verified')
    seen = {}
    for item in data.get('kalshi_rate_overrides', []):
        if item.get('kind') not in ('combo_maker', 'leg_taker') or not item.get('series') or not item.get('reference'):
            raise ValueError('invalid_dated_kalshi_rate_override')
        for key in ('start_at', 'end_at', 'rate'):
            value = item.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError('invalid_dated_kalshi_rate_override')
        if not item['start_at'] < item['end_at'] or not 0 <= item['rate'] < 1 or type(item.get('verified')) is not bool:
            raise ValueError('invalid_dated_kalshi_rate_override')
        key = item['kind'], item['series']
        for previous in seen.get(key, []):
            if max(previous['start_at'], item['start_at']) < min(previous['end_at'], item['end_at']):
                raise ValueError('overlapping_dated_kalshi_rate_overrides')
        seen.setdefault(key, []).append(item)
    return data


def require_coverage(scenario, start_at, end_at=None):
    if not scenario['start_at'] <= start_at < scenario['end_at']:
        raise ValueError('historical_fee_scenario_does_not_cover_timestamp')
    if end_at is not None and not start_at < end_at <= scenario['end_at']:
        raise ValueError('historical_fee_scenario_does_not_cover_interval')


def fee_basis(scenario):
    status = 'verified' if scenario['historical_effective_date_verified'] else 'UNVERIFIED RESEARCH SCENARIO'
    return status + ': ' + scenario['reference']


def kalshi_rate(scenario, ticker, at, kind):
    require_coverage(scenario, at)
    parts = ticker.split('-')
    # Native combo shard suffixes belong to the series, unlike event tokens.
    series = '-'.join(parts[:2]) if len(parts) > 1 and re.fullmatch(r'SHARD\d+', parts[1]) else parts[0]
    for item in scenario.get('kalshi_rate_overrides', []):
        if item['kind'] == kind and item['series'] == series and item['start_at'] <= at < item['end_at']:
            return item['rate'], {'reference': item['reference'], 'verified': item['verified'],
                                  'start_at': item['start_at'], 'end_at': item['end_at'], 'series': series}
    field = {'combo_maker': 'kalshi_combo_maker_rate', 'leg_taker': 'kalshi_leg_taker_rate'}[kind]
    return scenario[field], {'reference': scenario['reference'],
                             'verified': scenario['historical_effective_date_verified'],
                             'start_at': scenario['start_at'], 'end_at': scenario['end_at'], 'series': series}
