import importlib.util
from pathlib import Path
import time
spec=importlib.util.spec_from_file_location('account_reads',Path(__file__).resolve().parents[1]/'scripts/collect_account_reads.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class Client:
    def paginate(self,path,fields,params,max_pages,archive):
        return {'rows':{f:[] for f in fields},'pages':[],'pagination_complete':True,'stop_reason':'cursor_exhausted'}
    def get(self,path,params):
        now=time.time()
        return {'method':'GET','path':path,'params':params,'http_status':200,
            'request_started_at':now,'received_at':now,'payload':{'balance_dollars':'-1048.3917'}}


def test_optional_assessment_cannot_replace_account_cash_with_research_budget(tmp_path):
    result=module.collect(Client(),tmp_path/'reads',strategy_budget='10000')
    assert result['cash_assessment']['maximum_initial_strategy_cash_dollars']=='0'
    assert not result['ledger_initialization_authorized']
    assert not result['cash_assessment']['ledger_initialization_authorized']
    assert (tmp_path/'reads/cash_assessment.json').exists()


def test_bad_budget_is_reported_without_losing_archived_account_reads(tmp_path):
    result=module.collect(Client(),tmp_path/'reads',strategy_budget='nan')
    assert 'cash_assessment_error' in result
    assert (tmp_path/'reads/request_0001.json').exists()
    assert not result['ledger_initialization_authorized']
