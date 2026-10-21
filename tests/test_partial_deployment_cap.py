from dataclasses import dataclass, asdict
import gzip
import json
from copy import deepcopy
from combos.backtest import BacktestConfig
from test_research_partial_sizing import row
from research_partial_sizing import size_rows, fee
from mlb_streaming_longitudinal import evaluate_one
from combos.deployment_risk import DeploymentCappedRiskLedger
from deployment_exposure_audit import audit_decisions
import pytest


@dataclass(frozen=True)
class Config(BacktestConfig):
    maximum_committed_dollars: float = 10


def test_partial_size_limits_reinvestment_and_releases_after_settlement(tmp_path):
    c = Config(entry_basis='point', capital_dollars=10,
               per_contract_dollars=100, per_combo_dollars=100, per_fixture_dollars=100)
    inputs = [row('profit', 1, settled=2), row('large', 3, settled=6),
              row('blocked', 4, settled=6), row('released', 7, settled=10)]
    output, admitted = size_rows(inputs, c)
    assert [r['quantity'] for r in output if r['quote_allowed']] == [19, 19, 19]
    assert admitted == {('k', 'profit'), ('k', 'large'), ('k', 'released')}
    assert output[2]['source']['sizing_research']['maximum_whole_quantity'] == 0
    for r in output:
        sizing = r['source']['sizing_research']
        assert sizing['committed_before_units'] <= 100000
        if r['quote_allowed']:
            assert r['maker_fee'] == fee(r['quantity'], r['yes_price'], .035)
    legacy = BacktestConfig(entry_basis='point', capital_dollars=10,
               per_contract_dollars=100, per_combo_dollars=100, per_fixture_dollars=100)
    uncapped, _ = size_rows(inputs, legacy)
    assert uncapped[1]['quantity'] > output[1]['quantity']
    alternative = deepcopy(inputs)
    alternative[1]['yes_settlement'] = 1
    changed, _ = size_rows(alternative, c)
    assert [(r['quantity'], r['quote_allowed']) for r in output[:3]] == [(r['quantity'], r['quote_allowed']) for r in changed[:3]]
    plan = {'timezone': 'UTC', 'dates': {'1970-01-01': 'development'},
            'evaluation': {'minimum_complete_resolved_slates_for_descriptive_sharpe': 1}}
    coverage = {'observed_dates': ['1970-01-01'], 'missing_dates': []}
    result, _ = evaluate_one(iter(output), 'k', 'partial', 'partial', c, True,
        coverage, plan, tmp_path/'replay', ledger_factory=DeploymentCappedRiskLedger)
    assert result['portfolio']['fills'] == 3
    with gzip.open(tmp_path/'replay.decisions.jsonl.gz', 'rt') as handle:
        audited = audit_decisions((json.loads(line) for line in handle), asdict(c))
    assert audited['passed'] and audited['fills'] == 3 and audited['peak_integer_cash'] <= 10


@pytest.mark.parametrize('value', [0, -1, float('nan'), float('inf'), .00001])
def test_bad_ceiling(value):
    with pytest.raises(ValueError):
        size_rows([], Config(entry_basis='point', maximum_committed_dollars=value))
