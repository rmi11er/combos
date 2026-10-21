import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('research_volume_markouts',Path(__file__).resolve().parents[1]/'scripts/research_volume_markouts.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def test_prior_volume_excludes_simultaneous_and_future():
    assert m.prior_volume([1,2,2,3],[10,20,30,40],[2,3],[0,2]).tolist()==[10,50]
    with pytest.raises(ValueError):m.prior_volume([2,1],[1,1],[3],[0])


def test_chicago_day_not_utc():
    assert m.date_at(1767650400)=='2026-01-05'
