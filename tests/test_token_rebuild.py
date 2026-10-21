from types import SimpleNamespace
import pytest
from combos.quiet_book_probe import QuietBookProbe


def test_isolated_rebuild_waits_for_snapshot_and_is_bounded():
    p=QuietBookProbe({'token_quarantine':True,'token_rebuild':True},'shadow');p.reset('g')
    p.quarantined.add('bad');b=SimpleNamespace(books={'bad':{'old':1},'good':{'ok':2}})
    assert p.rebuild_targets(b)==['bad']
    assert b.books=={'good':{'ok':2}} and p.rebuild_targets(b)==[]
    raw={'event_type':'price_change','price_changes':[{'asset_id':'bad'},{'asset_id':'good'}]}
    assert p.filter_rebuild_frame(raw)['price_changes']==[{'asset_id':'good'}]
    assert len(raw['price_changes'])==2
    p.filter_rebuild_frame({'event_type':'book','asset_id':'bad'})
    assert not p.awaiting_rebuild and 'bad' in p.quarantined
    assert p.filter_rebuild_frame(raw)==raw


def test_no_rebuild_during_verification_and_configuration():
    p=QuietBookProbe({'token_quarantine':True,'token_rebuild':True},'shadow');p.quarantined.add('bad');p.task=object()
    assert p.rebuild_targets(None)==[]
    with pytest.raises(ValueError):QuietBookProbe({'token_rebuild':True},'shadow')
