import importlib.util
from pathlib import Path
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('mlb_day_acquire',ROOT/'scripts/mlb_public_day_acquire.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def test_route_straddling_cutoff_is_complete_nonoverlapping():
 assert m.routes(100,300,200)==[(100,200,'/historical/trades'),(200,300,'/markets/trades')]
 assert m.routes(100,200,200)==[(100,200,'/historical/trades')]
 assert m.routes(200,300,200)==[(200,300,'/markets/trades')]

class Fake:
 def __init__(self,payloads):self.payloads=iter(payloads);self.calls=0
 def get(self,path,params):
  self.calls+=1;p=next(self.payloads)
  if isinstance(p,Exception):raise p
  return {'request':{'endpoint':path,'params':params},'http_status':200,'payload':p}

def test_budget_exhaustion_is_not_census_and_resume_finishes(tmp_path):
 a=Fake([{'trades':[{'ticker':'KXMVE-X'}],'cursor':'next'},m.BudgetExhausted()])
 result=m.collect_partition(a,tmp_path,100,200,'/markets/trades')
 assert not result['complete'] and len(result['pages'])==1
 b=Fake([{'trades':[],'cursor':''}])
 result=m.collect_partition(b,tmp_path,100,200,'/markets/trades')
 assert result['complete'] and len(result['pages'])==2 and b.calls==1
 c=Fake([])
 assert m.collect_partition(c,tmp_path,100,200,'/markets/trades')['complete']
 assert c.calls==0

def test_repeated_cursor_fails_instead_of_false_completion(tmp_path):
 a=Fake([{'trades':[],'cursor':'repeat'},{'trades':[],'cursor':'repeat'}])
 with pytest.raises(ValueError,match='Repeated pagination'):
  m.collect_partition(a,tmp_path,100,200,'/markets/trades')
