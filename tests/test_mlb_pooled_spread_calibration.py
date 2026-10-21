import importlib.util
from pathlib import Path
import sys
import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import mlb_pooled_spread_calibration as m
from spread_calibration_study import regression, summarize, components


def rows():
    rng=np.random.default_rng(12);output=[]
    for i in range(90):
        p=float(rng.uniform(.05,.7));fair=float(rng.uniform(.04,.65));q=float(rng.uniform(1,300))
        r={'quantity':q,'yes_price':p,'fair_point':fair,'maker_fee':.1,'yes_settlement':float(rng.random()<fair),'settled_at':1.,'nlegs':2+i%3,
           'raw':float(rng.uniform(.5,16)),'fee_expanded':float(rng.uniform(5,28)), 'buckets':{'fixture':[f'f{i%7}',f'g{i%5}']},'model':'kalshi','evaluation_id':str(i)}
        r['values']=components(r);output.append(r)
    return output


@pytest.mark.parametrize('measure',m.MEASURES)
@pytest.mark.parametrize('spec',m.SPECS)
def test_pooled_and_fixture_subtractions_match_row_refits(measure,spec):
    rs=rows();study=m.Study();study.add_day(rs[:21],measure);study.add_day(rs[21:],measure)
    actual=study.regression(spec);expected=regression(rs,measure,spec)
    assert actual['terms']==expected['terms']
    assert actual['leave_one_fixture_out_failures']==expected['leave_one_fixture_out_failures']
    for c in m.COMPONENTS:
        assert actual['components'][c]['coefficients']==pytest.approx(expected['components'][c]['coefficients'],abs=1e-8)
        assert actual['components'][c]['spread_slope_fixture_deletion_range']==pytest.approx(expected['components'][c]['spread_slope_fixture_deletion_range'],abs=1e-8)
        assert actual['components'][c]['weighted_r_squared']==pytest.approx(expected['components'][c]['weighted_r_squared'],abs=1e-8)
    summary=study.overall.report();expected_summary=summarize(rs)
    assert summary['components_cents']==pytest.approx(expected_summary['components_cents'])
    for index,b in enumerate(study.bins):
        assert b.report()['components_cents']==pytest.approx(summarize([r for r in rs if m.bucket(r[measure])==index])['components_cents'])


def test_unknowns_weighted_sums_not_daily_mean():
    a,b=rows()[:2];a['quantity']=1.;b['quantity']=100.;b['values']={'compensation':10.,'residual':None,'realized':None}
    s=m.Study();s.add_day([a],'raw');s.add_day([b],'raw');r=s.overall.report()
    assert r['known_quantity']==1 and r['unknown_quantity']==100
    assert r['components_cents']==a['values']
    assert r['all_priced_compensation_cents']==pytest.approx((a['values']['compensation']+1000)/101)


def test_rank_failure_explicit():
    rs=rows()
    for r in rs:r['raw']=2
    s=m.Study();s.add_day(rs,'raw');assert s.regression('spread_only')['status'].startswith('rank_deficient')


def test_fixed_models_and_validation_fixture_purge():
    rs=rows()[:3]
    doubled=[{**r,'model':model} for r in rs for model in ['kalshi','polymarket']]
    kept,purged,coverage=m.retained_rows(doubled,['kalshi','polymarket'],'validation',{'f0'})
    assert purged==1 and len(kept)==4 and coverage['common_after_purge']==2
    kept,purged,coverage=m.retained_rows(doubled,['kalshi','polymarket','missing'],'development',set())
    assert not kept and coverage['missing_models']==['missing']


def test_completion_and_feature_hash_certificates(tmp_path):
    import json
    date='2026-07-01';root=tmp_path/'batch';replay=root/date/'replay/opportunities.json';replay.parent.mkdir(parents=True);replay.write_text('{}')
    feature_root=tmp_path/'features';fm=feature_root/date/'feature_manifest.json';fm.parent.mkdir(parents=True);fp=fm.parent/'features.jsonl.gz';fp.write_bytes(b'fake fixture')
    feature={'complete':True,'replay':str(replay),'features_sha256':m.digest(fp),'source_sha256':{str(replay):m.digest(replay)}};fm.write_text(json.dumps(feature))
    state={'days':{date:{'status':'running'}},'stages':{date+'/replay':{'status':'complete','output_sha256':{str(replay):m.digest(replay)}}}}
    state_path=root/'batch_status.json';state_path.write_text(json.dumps(state));plan={'dates':{date:'development'}}
    assert not m.certified_inputs([root],feature_root,plan)[1]
    state['days'][date]['status']='complete';state_path.write_text(json.dumps(state));assert date in m.certified_inputs([root],feature_root,plan)[1]
    fp.write_bytes(b'changed')
    with pytest.raises(ValueError,match='feature_certificate'):m.certified_inputs([root],feature_root,plan)
    feature['features_sha256']=m.digest(fp);fm.write_text(json.dumps(feature));replay.write_text('{"changed":true}')
    with pytest.raises(ValueError,match='replay_certificate'):m.certified_inputs([root],feature_root,plan)
