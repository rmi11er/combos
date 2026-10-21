import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('review',Path(__file__).resolve().parents[1]/'scripts/review_creator_markouts.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def test_transitive_fixture_overlap_is_one_component():
    assert module.components([('a','b'),('b','c'),('d','e')])==2


def test_repeated_requests_do_not_multiply_fixture_representatives():
    base=dict(creator_id='creator',horizon_seconds=10,fixtures=['a','b'])
    rows=[dict(base,rfq_id='first',entry_at=1,adverse_move_cents=-1)]
    rows += [dict(base,rfq_id=str(i),entry_at=i+2,adverse_move_cents=1) for i in range(100)]
    result=module.grouped(rows)[0]
    assert result['raw_observed_labels']==101 and result['fixture_sets']==1
    assert result['first_per_fixture_set_mean_adverse_cents']==-1
    assert result['raw_mean_adverse_cents']>0 and result['action']=='review_only'
