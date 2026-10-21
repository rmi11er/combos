import importlib.util
from pathlib import Path
import pytest
from test_settlement_accounting import case

spec=importlib.util.spec_from_file_location('settlement_review',Path(__file__).resolve().parents[1]/'scripts/reconcile_account_settlement.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def pages():
    s,f=case()
    settlement={'method':'GET','http_status':200,'path':'/trade-api/v2/portfolio/settlements',
        'params':{'subaccount':0},'payload':{'settlements':[s]}}
    fill={'method':'GET','http_status':200,'path':'/trade-api/v2/portfolio/fills',
        'params':{'subaccount':0,'ticker':'M'},'payload':{'fills':f,'cursor':''}}
    return settlement,fill


def test_archived_complete_review():
    s,f=pages()
    assert module.review(s,0,[f])['settlement_revenue_matches']


@pytest.mark.parametrize('change', ['truncated','bounded','subaccount','duplicate'])
def test_incomplete_or_filtered_history_rejected(change):
    s,f=pages();fs=[f]
    if change=='truncated':f['payload']['cursor']='next'
    if change=='bounded':f['params']['min_ts']=1
    if change=='subaccount':s['params'].pop('subaccount')
    if change=='duplicate':fs.append(f)
    with pytest.raises(ValueError):module.review(s,0,fs)
