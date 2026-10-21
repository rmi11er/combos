import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))

from combos.demand_experiment import assign, score, score_markouts


def records():
    a=assign('rfq-1','frozen-seed')
    a.update(experiment_stage='prospective_frozen',decision_at=100,
             assignment_frozen_at=101,response_end_at=120,price_band='10-25c',
             candidates={a['arm']:{'yes_ask':'.21','quantity':10}})
    r=dict(assignment_id=a['assignment_id'],arm=a['arm'],source_type='observed_live',
           customer_exposure_confirmed=True,quote_id='quote-1',evidence_reference='journal:1',
           yes_ask='.21',quantity=10,sent_at=102,ack_at=103,response_end_at=120,
           observed_through_at=120,continuous_observation=True,full_window_exposure=True)
    return a,r


def test_assignment_stable_and_missing_unknown():
    a,r=records()
    assert assign('rfq-1','frozen-seed')['arm']==a['arm']
    result=score([a],[])
    assert result['groups'][0]['acceptance_rate_resolved'] is None
    assert result['groups'][0]['not_exposed']==1


@pytest.mark.parametrize('field,value',[
    ('source_type','simulation'),('customer_exposure_confirmed',False),
    ('yes_ask','.22'),('quantity',11),('response_end_at',121),('sent_at',100)])
def test_reject_invalid_exposure(field,value):
    a,r=records();r[field]=value
    with pytest.raises(ValueError):score([a],[r])


def test_retrospective_cannot_become_exposure():
    a,r=records();a['experiment_stage']='retrospective_dry_run'
    with pytest.raises(ValueError,match='prospective'):score([a],[r])


def test_censor_and_acceptance():
    a,r=records()
    assert score([a],[r])['labels'][0]['status']=='not_accepted'
    r['full_window_exposure']=False
    assert score([a],[r])['labels'][0]['status']=='censored'
    r.update(accepted_at=110,acceptance_evidence_reference='journal:accept')
    assert score([a],[r])['labels'][0]['status']=='accepted'
    with pytest.raises(ValueError):score([a],[r,r])


def test_markout_fee_sign_coverage_and_lookahead():
    a,r=records();r.update(accepted_at=110,acceptance_evidence_reference='journal:accept')
    response=score([a],[r])
    f=dict(assignment_id=a['assignment_id'],source_type='observed_live',
           evidence_reference='journal:fill',fill_id='fill-1',quote_id='quote-1',
           quantity=5,yes_price=.21,maker_fee_dollars=.01,filled_at=111,
           marks=[dict(horizon_seconds=10,fair=.20,observed_at=121,available_at=121,
                       evidence_reference='fair:121')])
    result=score_markouts([a],response,[f])
    assert result['groups'][0]['net_markout_cents_per_contract']==pytest.approx(.8)
    assert result['groups'][1]['quantity_coverage']==0
    assert result['groups'][1]['net_markout_dollars'] is None
    with pytest.raises(ValueError):score_markouts([a],response,[f,f])
    f['marks'][0]['available_at']=122
    with pytest.raises(ValueError,match='lookahead'):score_markouts([a],response,[f])
