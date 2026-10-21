import importlib.util
from pathlib import Path
import numpy as np

spec=importlib.util.spec_from_file_location('research_inventory_relief',Path(__file__).resolve().parents[1]/'scripts/research_inventory_relief.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def test_exact_complement_reduces_risk():
    grid=m.scenario_grid(['A']);index={'A':0}
    r={'quantity':240,'yes_price':.5,'maker_fee':0,'selected_fixture_bits':[['A',1]]}
    loss=m.ticket_loss(r,grid,index)
    opposite=m.ticket_loss({**r,'selected_fixture_bits':[['A',0]]},grid,index)
    assert m.sensitivities(loss,['A']).tolist()==[240]
    assert np.allclose(loss+opposite,0)
    assert m.relief_gate(m.sensitivities(loss,['A']),m.sensitivities(loss+opposite,['A']),loss,loss+opposite,250,.9)


def test_opposite_leg_can_add_other_fixture_risk():
    before=np.array([240.,10.]);after=np.array([200.,260.])
    assert not m.relief_gate(before,after,np.array([100.]),np.array([80.]),250,.9)
    assert not m.relief_gate(before,np.array([200.,100.]),np.array([100.]),np.array([110.]),250,.9)


def test_not_constrained_no_discount():
    assert not m.relief_gate(np.array([100.]),np.array([50.]),np.array([100.]),np.array([50.]),250,.9)


def test_resolved_outcome_removes_only_known_fixture_sensitivity():
    grid=m.scenario_grid(['A','B']);loss=100*grid[:,0]+50*grid[:,1]
    assert m.sensitivities(loss,['A','B'],grid[:,0]).tolist()==[0,50]


def test_winner_revelation_uses_settlement_not_entry_and_ignores_no():
    rows=[{'yes_settlement':1,'settled_at':20,'selected_fixture_bits':[['A',1]]},
          {'yes_settlement':0,'settled_at':10,'selected_fixture_bits':[['B',0]]}]
    assert m.revealed_outcomes(rows)=={'A':(20,1)}


def test_chronological_full_fill_caps_and_settlement_cash():
    def row(eid,at,q,settled):
        return {'evaluation_id':eid,'at':at,'quantity':q,'yes_price':.5,'fair_point':.49,'maker_fee':0,
                'quote_allowed':True,'settled_at':settled,'yes_settlement':0,
                'selected_fixture_bits':[['A',1]],'buckets':{'contract':['A'],'combo':[eid]},'marks':{}}
    rows=[row('first',1,200,10),row('blocked',2,10,12),row('recycled',11,10,15)]
    summary,fills=m.replay(rows,'gross')
    assert [f['id'] for f in fills]==['first','recycled']
    assert summary['ending_cash']==10105
    assert summary['peak_gross_cash']==100
    # Changing a future outcome does not alter earlier allocation.
    altered=[{**r,'yes_settlement':1} for r in rows]
    _,other=m.replay(altered,'gross')
    assert [f['id'] for f in other]==['first','recycled']


def test_hurdle_quote_rounding_and_fee_are_recomputed():
    r={'fair_point':.2,'quantity':10,'yes_price':.3,'maker_fee':.1}
    quote=m.hurdle_quote(r,.001)
    assert quote['yes_price']>=.201
    assert quote['yes_price']-.2-quote['maker_fee']/10>=.001-1e-12
    lower=quote['yes_price']-.001
    fee=float(m.kalshi_fill_fee('10',m.Decimal(1)-m.Decimal(str(round(lower,3))),'.035')['net_fee'])
    assert lower-.2-fee/10<.001
