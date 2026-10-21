import importlib.util
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]


def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def test_hedge_deltas_are_product_derivatives():
    m=load('research_hedge_followup')
    assert m.deltas([.2,.3,.4]).tolist()==pytest.approx([.12,.08,.06])
    assert m.deltas([0,.3,.4]).tolist()==pytest.approx([.12,0,0])


def test_forecast_score_actual_denominator_and_zero_observed():
    m=load('research_final_analysis')
    rows=[{'lead_hours':1,'date':'a','actual_remaining':100,'forecast_remaining':75,'constant_pace_remaining':0,'observed_contracts':0},
          {'lead_hours':1,'date':'b','actual_remaining':100,'forecast_remaining':125,'constant_pace_remaining':0,'observed_contracts':20}]
    result=m.forecast_scores(rows)[0]
    assert result['clock_wape']==.25
    assert result['constant_wape']==1
    assert result['clock_bias_fraction']==0
    assert result['zero_observed_groups']==1
