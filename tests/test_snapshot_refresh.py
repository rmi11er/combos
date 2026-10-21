import pytest
from combos.snapshot_refresh import SnapshotRefresh


def test_quiet_only_batch_spacing_and_no_receipt_renewal():
    s=SnapshotRefresh({'maximum_books_per_request':1},'shadow')
    s.observed('a',0);s.observed('b',0);s.observed('c',14)
    assert s.choose({'a','b','c'},14)==[]
    assert s.choose({'a','b','c'},15)==['a']
    assert s.updated['a']==0
    assert s.choose({'a','b','c'},16)==[]
    assert s.choose({'a','b','c'},20)==['b']


def test_budget_survives_reset_and_requires_new_snapshot():
    s=SnapshotRefresh({'maximum_requests':1},'shadow');s.observed('a',0)
    assert s.choose({'a'},15)==['a']
    s.reset();assert s.updated=={}
    s.observed('a',20);assert s.choose({'a'},40)==[]


@pytest.mark.parametrize('mode,config',[('live',{}),('shadow',{'maximum_requests':0}),('shadow',{'quiet_seconds':1})])
def test_invalid_config(mode,config):
    with pytest.raises(ValueError):SnapshotRefresh(config,mode)


def test_demand_refresh_precedes_expiry_without_renewing_book():
    s=SnapshotRefresh({'demand_priority':True,'maximum_books_per_request':1},'shadow')
    s.observed('demanded',0);s.observed('quiet',0)
    assert s.choose({'demanded','quiet'},7,{'demanded'})==[]
    assert s.choose({'demanded','quiet'},8,{'demanded'})==['demanded']
    assert s.updated['demanded']==0
    s.observed('demanded',8.1)
    assert s.choose({'demanded','quiet'},15,{'demanded'})==['quiet']


def test_undemanded_or_unsubscribed_book_not_refreshed_early():
    s=SnapshotRefresh({'demand_priority':True},'shadow');s.observed('a',0);s.observed('b',0)
    assert s.choose({'a'},8,{'b'})==[]
    assert s.choose({'a'},15,set())==['a']
