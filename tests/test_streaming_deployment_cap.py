from dataclasses import dataclass, asdict
from copy import deepcopy
import pytest

from combos.backtest import BacktestConfig
from combos.deployment_risk import DeploymentCappedRiskLedger
from test_mlb_longitudinal_sweep import plan, opportunity
from test_mlb_streaming_longitudinal import gzrows
from mlb_streaming_longitudinal import evaluate_one
from mlb_longitudinal_sweep import bounds
from deployment_exposure_audit import audit_decisions


@dataclass(frozen=True)
class CappedConfig(BacktestConfig):
    maximum_committed_dollars: float = 100


def test_replay_ceiling_after_settled_profit_and_future_outcome_invariance(tmp_path):
    p = plan()
    coverage = {'observed_dates': list(p['dates']), 'missing_dates': []}
    settled = bounds('2026-07-02', p['timezone'])[0]
    first = opportunity('2026-07-01', 'first', settlement=settled, result=0)
    later = opportunity('2026-07-03', 'later')
    later.update(quantity=150, maker_fee=0)
    config = CappedConfig(entry_basis='point', capital_dollars=100,
                          per_contract_dollars=1000, per_combo_dollars=1000,
                          per_fixture_dollars=1000)
    capped, _ = evaluate_one(iter([first, later]), 'kalshi', 'cap', 'cap',
        config, True, coverage, p, tmp_path/'cap', ledger_factory=DeploymentCappedRiskLedger)
    normal, _ = evaluate_one(iter([first, later]), 'kalshi', 'normal', 'normal',
        config, True, coverage, p, tmp_path/'normal')
    assert capped['portfolio']['fills'] == 1
    assert normal['portfolio']['fills'] == 2
    assert capped['portfolio']['peak_committed_cash'] <= 100
    assert normal['portfolio']['peak_committed_cash'] == 105
    decision = gzrows(tmp_path/'cap.decisions.jsonl.gz')[-1]
    assert decision['reason'] == 'deployment_cash_limit'
    assert decision['risk']['binding_funding_limits'] == ['deployment_ceiling']
    decisions = gzrows(tmp_path/'cap.decisions.jsonl.gz')
    audit = audit_decisions(iter(decisions), asdict(config))
    assert audit['fills'] == 1 and audit['binding_limits_nonexclusive'] == {'deployment_ceiling': 1}
    tampered = deepcopy(decisions)
    tampered[-1]['accepted'] = True
    with pytest.raises(AssertionError, match='admission_mismatch'):
        audit_decisions(iter(tampered), asdict(config))

    # Changing a later unresolved trade's eventual outcome cannot change entry.
    late_settlement = bounds('2026-07-04', p['timezone'])[0]
    for outcome in (0, 1):
        changed = dict(later, settled_at=late_settlement, yes_settlement=outcome)
        result, _ = evaluate_one(iter([first, changed]), 'kalshi', 'cap', 'cap',
            config, True, coverage, p, tmp_path/f'future{outcome}', ledger_factory=DeploymentCappedRiskLedger)
        assert result['portfolio']['fills'] == 1
