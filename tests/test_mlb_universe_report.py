import importlib.util
from pathlib import Path
import pandas as pd
import pytest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('mlb_universe_report',ROOT/'scripts/mlb_universe_report.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def test_unknown_outcome_bounds_include_fees_and_known_pnl_does_not_invent_result():
 u=m.economics(100,.2,.56,None)
 assert u['known_pnl']==0
 assert u['unknown_lower']==pytest.approx(-80.56)
 assert u['unknown_upper']==pytest.approx(19.44)
 assert m.economics(100,.2,.56,1)['known_pnl']==u['unknown_lower']
 assert m.economics(100,.2,.56,0)['known_pnl']==u['unknown_upper']

def test_shared_fixture_concentration_is_deduplicated_per_print_and_overlap_explicit():
 d=pd.DataFrame([{'trade_id':'a','ticker':'combo1','known_pnl':10.,'yes_premium':10.,'quantity':100.,'nlegs':2,'fixtures':['A'],'known':True}, {'trade_id':'b','ticker':'combo2','known_pnl':-3.,'yes_premium':10.,'quantity':100.,'nlegs':2,'fixtures':['A','B'],'known':True}])
 r=m.concentration(d)
 rows={x['fixture']:x for x in r['fixture']['largest_profits']}
 assert rows['A']['prints']==2 and rows['A']['known_pnl']==7
 assert rows['B']['known_pnl']==-3
 assert rows['A']['pnl_after_excluding_fixture']==0
 assert 'not additive' in r['fixture_warning']
