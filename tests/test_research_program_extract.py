import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('research_program_extract',Path(__file__).resolve().parents[1]/'scripts/research_program_extract.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def test_selected_orientation():
    assert m.product_selected([{'side':'yes'},{'side':'no'}],[.8,.3])==pytest.approx(.56)
    with pytest.raises(ValueError): m.product_selected([{'side':'maybe'}],[.5])
    with pytest.raises(ValueError): m.product_selected([{'side':'yes'}],[float('nan')])


def test_horizon_crossing_does_not_read_future():
    assert m.mark_at(None,[],100,100)=={'status':'crosses_first_kickoff'}


def test_source_availability_guard():
    class History:
        def at(self,ticker,at):
            return {'available_at':at+1}
    with pytest.raises(AssertionError):
        m.mark_at(History(),[{'market_ticker':'A','side':'yes'}],100,200)
