from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from combos.creator_service import CreatorService
from combos.event_store import EventStore
from combos.shadow_engine import ShadowEngine
from combos.shadow_policy_study import ShadowPolicyStudy
from test_runtime import add, config, decisions, drain, observation, rfq, seed


def study_config():
    value = json.loads((ROOT / 'config/shadow_policy_study.json').read_text())
    value.update(policy_available_at=0., fee_terms_available_at=0., balance_precision='.0001')
    return value


def run_case(path, runtime, request=None, initial=None):
    store = EventStore(path)
    engine = ShadowEngine(store, runtime, replay=True)
    if initial is None:
        seed(store)
    else:
        for index, row in enumerate(initial):
            add(store, 'observation', row, 'book:' + str(index), 100)
    add(store, 'rfq', request or rfq(), 'rfq', 100)
    drain(CreatorService(store), engine)
    decision = decisions(store)[0]
    reservations = [dict(row) for row in store.db.execute('SELECT * FROM reservations')]
    store.close()
    return decision, reservations


def test_auto_wiring_keeps_baseline_quote_and_reservations_identical(tmp_path):
    original, old_reservations = run_case(tmp_path / 'original.sqlite', config())
    runtime = config()
    runtime['shadow_policy_study'] = study_config()
    actual, reservations = run_case(tmp_path / 'study.sqlite', runtime)
    for key in ('status', 'yes_ask', 'no_bid', 'quantity', 'quote', 'economics', 'risk'):
        assert actual[key] == original[key]
    assert reservations == old_reservations
    assert actual['config_version'] != original['config_version']
    study = actual['shadow_policy_study']
    assert study['status'] == 'evaluated'
    assert len(study['variants']) == 4
    for variant in study['variants']:
        assert variant['deployable'] is False
        assert variant['evaluation']['selected'] is None
        assert variant['evaluation']['orders_enabled'] is False
        assert all(c['acceptance'] is None for c in variant['evaluation']['candidates'])


def test_point_candidates_logged_when_baseline_stressed_floor_is_infeasible(tmp_path):
    runtime = config()
    runtime.update(correlation_rho=1., minimum_net_edge_per_share=.5, shadow_policy_study=study_config())
    actual, reservations = run_case(tmp_path / 'no-floor.sqlite', runtime)
    assert actual['status'] == 'skipped'
    assert actual['reason'] == 'no_price_with_required_edge'
    assert reservations == []
    variants = {v['name']: v['evaluation'] for v in actual['shadow_policy_study']['variants']}
    assert variants['existing_stressed']['floor'] is None
    assert variants['blend_point']['floor']['yes_ask'] == .75
    assert variants['polymarket_point']['floor']['yes_ask'] == .75


def test_selected_no_leg_reverses_disagreement_and_preserves_true_depth(tmp_path):
    runtime = config()
    runtime['shadow_policy_study'] = study_config()
    request = rfq()
    request['mve_selected_legs'][0]['side'] = 'no'
    initial = [observation(key, venue, point=.6 if key == 'a' and venue == 'polymarket' else .5)
               for key in ('a', 'b') for venue in ('kalshi', 'polymarket', 'pinnacle')]
    actual, _ = run_case(tmp_path / 'complement.sqlite', runtime, request, initial)
    disagreement = actual['shadow_policy_study']['source_disagreement']
    assert disagreement['legs'][0]['polymarket_minus_kalshi_selected_cents'] == pytest.approx(-10.)
    assert disagreement['source_combo_point_probabilities']['kalshi'] == .25
    assert disagreement['source_combo_point_probabilities']['polymarket'] == pytest.approx(.2)
    assert disagreement['polymarket_minus_kalshi_combo_cents'] == pytest.approx(-5.)
    pm = disagreement['legs'][0]['venues']['polymarket']
    assert pm['two_sided_depth_payout_dollars'] == 100
    assert pm['source_reference'] == 'synthetic:book'
    assert pm['age_seconds'] == 0


@pytest.mark.parametrize('failure', ['mapping', 'historical_depth', 'creator', 'size'])
def test_ineligible_or_unmodeled_requests_never_gain_candidates(tmp_path, failure):
    runtime = config()
    runtime['shadow_policy_study'] = study_config()
    request = rfq()
    initial = None
    if failure == 'mapping':
        runtime['mappings'][0]['pricing_block_reason'] = 'payoff_unreviewed'
    elif failure == 'historical_depth':
        initial = [observation(key, venue) for key in ('a', 'b') for venue in ('kalshi', 'polymarket', 'pinnacle')]
        initial[1]['depth_imputed'] = True
    elif failure == 'creator':
        request.pop('creator_id')
    else:
        request.pop('contracts_fp')
        request['target_cost_dollars'] = '10'
    actual, _ = run_case(tmp_path / (failure + '.sqlite'), runtime, request, initial)
    study = actual['shadow_policy_study']
    assert study['status'] in ('blocked', 'unavailable')
    assert study['variants'] == []
    assert study['selected'] is None
    assert study['orders_enabled'] is False


def test_candidate_can_be_researched_after_risk_rejection_without_risk_mutation(tmp_path):
    runtime = config()
    runtime.update(per_contract_dollars=1, shadow_policy_study=study_config())
    actual, reservations = run_case(tmp_path / 'risk.sqlite', runtime)
    assert actual['reason'] == 'contract_risk_limit'
    assert actual['shadow_policy_study']['status'] == 'evaluated'
    assert actual['shadow_policy_study']['risk_context']['baseline_risk']['allowed'] is False
    assert reservations == []


def test_audit_error_or_future_policy_never_changes_baseline(tmp_path):
    runtime = config()
    runtime['shadow_policy_study'] = study_config()
    runtime['shadow_policy_study']['policy_available_at'] = 101
    actual, reservations = run_case(tmp_path / 'future.sqlite', runtime)
    assert actual['status'] == 'shadow_quote'
    assert len(reservations) == 1
    assert actual['shadow_policy_study']['status'] == 'unavailable'
    assert 'future_information' in actual['shadow_policy_study']['reason']


def test_sport_profile_versions_and_config_hashes_are_independent():
    study = study_config()
    nfl_runtime = config()
    mlb_runtime = {**nfl_runtime, 'sport': 'MLB'}
    nfl = ShadowPolicyStudy(study, nfl_runtime, None).manifest()
    mlb = ShadowPolicyStudy(study, mlb_runtime, None).manifest()
    assert nfl['sport_model_version'] != mlb['sport_model_version']
    changed = deepcopy(study)
    changed['sports']['MLB']['commercial_markups_per_contract'].append(.03)
    assert ShadowPolicyStudy(changed, mlb_runtime, None).manifest()['config_sha256'] != mlb['config_sha256']
    assert changed['sports']['NFL'] == study['sports']['NFL']


def test_configuration_cannot_enable_orders_or_mix_stressed_source_reserves():
    study = study_config()
    study['orders_enabled'] = True
    with pytest.raises(ValueError, match='orders_must_be_disabled'):
        ShadowPolicyStudy(study, config(), None)
    study = study_config()
    study['sports']['NFL']['variants'][0]['fair_source'] = 'polymarket'
    with pytest.raises(ValueError, match='stressed_reserves_require_existing_blend'):
        ShadowPolicyStudy(study, config(), None)


def test_report_distinguishes_candidates_from_fills_and_uninstrumented_decisions(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location('shadow_policy_report', ROOT / 'scripts/shadow_policy_report.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    runtime = config()
    runtime['shadow_policy_study'] = study_config()
    actual, _ = run_case(tmp_path / 'report.sqlite', runtime)
    old = deepcopy(actual)
    old.pop('shadow_policy_study')
    report = module.summarize([{'kind': 'decision', 'payload': value} for value in (actual, old)])
    assert report['decision_count'] == 2
    assert report['study_statuses'] == {'evaluated': 1, 'not_instrumented': 1}
    assert report['realized_candidate_pnl'] is None
    assert report['acceptance_labels_available'] is False
    assert all(row['selected_candidates'] == 0 for row in report['variants'].values())
    assert all(row['candidate_prices_logged'] > 0 for row in report['variants'].values())


def test_archive_report_rejects_corrupt_chunks(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location('shadow_policy_report', ROOT / 'scripts/shadow_policy_report.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    (tmp_path / 'events.jsonl.gz').write_bytes(b'corrupt')
    manifest = {'complete': True, 'chunks': [{'file': 'events.jsonl.gz', 'sha256': 'incorrect', 'rows': 1}]}
    with pytest.raises(ValueError, match='hash_mismatch'):
        list(module.archived_events(tmp_path, manifest))
