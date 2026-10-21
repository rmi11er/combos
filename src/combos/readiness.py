"""Reviewable launch blockers; configuration coverage is not live feed health."""
from collections import Counter
import math
import os
from .rfq_scope import validate_scope, check_mappings


def readiness(config, weights, polling, at):
    blockers=[]; counts=Counter(); all_counts=Counter(); mapping_checks=[]; eligible=[]
    try:validate_scope(config)
    except ValueError as exc:blockers.append(str(exc))
    if not weights.delayed_pinnacle:blockers.append('delayed_pinnacle_guards_disabled')
    for key in ('capital_dollars','per_contract_dollars','per_combo_dollars','per_fixture_dollars'):
        value=config.get(key)
        if not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:
            blockers.append(key+'_unconfigured')
    for mapping in config['mappings']:
        reasons=[]
        fallback=config.get('source_fallback',{}).get('enabled',False)
        try:check_mappings([{'market_ticker':mapping['kalshi_ticker']}],[mapping],config)
        except (ValueError,KeyError) as exc:reasons.append(str(exc))
        if at>=mapping['start_at']-max(config.get('pregame_cutoff_seconds',60),weights.pregame_cutoff_seconds):reasons.append('pregame_cutoff')
        rules_vetted = mapping.get('pinnacle', {}).get('settlement_policy') in ('full_game_moneyline_rules_v1', 'nonplayer_rules_v1')
        if mapping.get('pricing_block_reason') and not rules_vetted and not (fallback and mapping['pricing_block_reason'] in ('pinnacle_payoff_mapping_unreviewed','void_basis_required')):reasons.append(mapping['pricing_block_reason'])
        spec=mapping.get('pinnacle',{})
        if not spec.get('selector_reference') and not fallback:reasons.append('pinnacle_selector_unreviewed')
        if not spec.get('payoff_reference') and not rules_vetted and not fallback:reasons.append('pinnacle_payoff_mapping_unreviewed')
        if not fallback and (spec.get('limit_currency')!='USD' or spec.get('limit_unit')!='stake' or not spec.get('limit_reference')):
            reasons.append('pinnacle_limit_units_unreviewed')
        if any(not mapping.get('fees',{}).get(v,{}).get('reference') or
               mapping['fees'][v].get('valid_until',0)<=at for v in (('kalshi',) if fallback else ('kalshi','polymarket'))):
            reasons.append('leg_fee_metadata_unverified_or_expired')
        reasons=list(dict.fromkeys(reasons))
        mapping_checks.append({'market_key':mapping['market_key'],'reasons':reasons})
        all_counts.update(reasons)
        if reasons:counts[reasons[0]]+=1
        else:eligible.append(mapping)
    if len({m['fixture_key'] for m in eligible})<config.get('minimum_legs',2):
        blockers.append('insufficient_reviewed_pregame_fixtures')
    valid_terms=[v for v in config.get('combo_terms',{}).values()
                 if v.get('fee_reference') and v.get('price_ranges') and v.get('valid_until',0)>at]
    if not valid_terms:blockers.append('combo_fee_metadata_unverified_or_expired')
    fallback=config.get('source_fallback',{}).get('enabled',False)
    if not fallback and not os.environ.get('ODDSPAPI_API_KEY'):blockers.append('oddspapi_key_unavailable_to_process')
    if not fallback and not polling.get('tournament_ids'):blockers.append('oddspapi_tournament_ids_unconfigured')
    if not fallback and polling.get('known_used') is None:blockers.append('oddspapi_account_usage_unreconciled')
    start,end=polling.get('billing_cycle_start'),polling.get('billing_cycle_end')
    if not fallback and (start is None or end is None or not start<=at<end):blockers.append('oddspapi_billing_cycle_unconfigured_or_expired')
    return {'checked_at':at,'mode':config['mode'],'configured_leg_range':[config.get('minimum_legs',2),config.get('maximum_legs',4)],
        'scope':'NFL; full-game/first-half/first-quarter non-player families; distinct fixtures; pregame',
        'mapping_families':dict(Counter(m.get('period','full_game')+':'+m['market_type'] for m in config['mappings'])),
        'capital_dollars':config['capital_dollars'],'mappings':len(config['mappings']),
        'mapping_exclusions':dict(counts),'all_mapping_exclusions':dict(all_counts),
        'mapping_checks':mapping_checks,'configuration_eligible_mappings':len(eligible),
        'configuration_eligible_fixtures':len({m['fixture_key'] for m in eligible}),
        'shadow_configuration_blockers':blockers,'shadow_configuration_ready':not blockers,
        'live_ready':False,'live_implementation_blockers':[
            'exchange_quote_submit_accept_confirm_cancel_adapter_not_implemented',
            'exchange_derived_target_cost_quantity_not_reconciled',
            'account_balance_positions_open_quotes_orders_fills_reconciliation_not_implemented',
            'live_fee_rounding_and_account_precision_not_verified',
            'restart_unknown_submission_and_cancel_race_recovery_not_exercised'],
        'operational_evidence_required':[
            'actual_three_venue_coverage_and_native_timestamp_limit_unit_payoff_verification',
            'sustained_shadow_run_with_complete_decisions_and_latency_measurement',
            'supervised_accept_confirm_execution_test_with_fill_and_capital_reconciliation',
            'always_on_host_and_measured_disk_capacity_with_off_host_archive'],
        'note':'Static preflight only. A ready configuration does not prove current feed health or customer acceptance.'}
