from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from replay_risk_ablation import opportunities, scenarios, BacktestConfig, concentration


def ledger():
    row = dict(evaluation_id='print', at=10, quantity=10, yes_price=.4,
               maker_fee=.1, settled_at=20, yes_settlement=0,
               buckets={'contract':['a','b'],'fixture':['f','g'],'combo':['c']},
               quote_allowed=True, risk_multiplier=1,
               source={'sampling_method':'census','nlegs':2},
               model='kalshi',fair_point=.3,stressed_upper=.35,
               accepted=False,reason='insufficient_edge')
    other={**deepcopy(row),'model':'polymarket','fair_point':.2}
    return {'constrained':False,'decisions':[row,other]}


def test_preserves_opportunities_without_reusing_admission_decisions():
    rows=opportunities(ledger())
    assert len(rows)==2 and [r['fair_point'] for r in rows]==[.3,.2]
    assert all('accepted' not in r and 'reason' not in r for r in rows)
    assert rows[0]['quantity']==10 and rows[0]['buckets']['fixture']==['f','g']


@pytest.mark.parametrize('defect,match', [('constrained','unlimited'),('price','paired'),('missing','common'),('sample','census')])
def test_rejects_selection_or_denominator_changes(defect,match):
    r=ledger()
    if defect=='constrained':r['constrained']=True
    if defect=='price':r['decisions'][1]['yes_price']=.5
    if defect=='missing':r['decisions'][1]['evaluation_id']='different'
    if defect=='sample':r['decisions'][1]['source']['sampling_method']='sample'
    with pytest.raises(ValueError,match=match):opportunities(r)


def test_fixed_grid_isolates_caps_and_preserves_pricing_and_capital():
    base=BacktestConfig(entry_basis='point');grid=list(scenarios(base))
    assert len(grid)==21 and len({n for n,c in grid})==21
    for name,c in grid:
        for field,value in asdict(base).items():
            if field not in ('per_contract_dollars','per_combo_dollars','per_fixture_dollars'):
                assert getattr(c,field)==value
        if name.endswith('baseline_others') and name.startswith('fixture_'):
            assert c.per_contract_dollars==100 and c.per_combo_dollars==100
        if name.endswith('baseline_others') and name.startswith('underlying_'):
            assert c.per_fixture_dollars==250 and c.per_combo_dollars==100


def test_concentration_removes_entire_shared_game_membership():
    rows=ledger()['decisions'][:1]
    rows[0]['accepted']=True
    result=concentration(rows)
    assert result['largest_winning_print']['net_pnl']==pytest.approx(3.9)
    assert result['fixture_omission_pnl']=={'f':0,'g':0}
    assert result['pnl_without_largest_print']==0
