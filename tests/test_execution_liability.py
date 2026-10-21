from decimal import Decimal
from dataclasses import replace
import pytest
from combos.execution_liability import FeeEvidence, QuoteLiability, no_quote_cash_bound
from combos.execution_journal import ExecutionJournal
from combos.execution_risk import ExecutionRiskHolds
from combos.fees import kalshi_fill_fee


EVIDENCE=FeeEvidence('.035','.0001','synthetic:maker-rate','synthetic:direct-account',0,1000)


@pytest.mark.parametrize('precision',['.0001','.01'])
@pytest.mark.parametrize('rate',['0','.035','.07'])
def test_fragmented_actual_cash_is_below_bound(precision,rate):
    e=replace(EVIDENCE,balance_precision=precision,maximum_rate=rate)
    for limit in ('.0001','.1234','.5','.9999'):
        bound=Decimal(no_quote_cash_bound('.20',limit,e,100)['cash_bound'])
        for sizes in ([Decimal('.01')]*20,[Decimal('.07'),Decimal('.13')],[Decimal('.20')]):
            carry=Decimal(0);spent=Decimal(0)
            for q in sizes:
                # Improved price or limit price: total debit is monotone in p.
                price=max(Decimal('.0001'),Decimal(limit)-Decimal('.0001'))
                fee=kalshi_fill_fee(q,price,rate,'buy',precision,carry)
                carry=fee['accumulator'];spent-=fee['balance_change']
            assert spent<=bound


def test_liability_is_reserved_atomically_and_larger_size_fails(tmp_path):
    j=ExecutionJournal(tmp_path/'execution.sqlite')
    c={k:100 for k in ('capital_dollars','maximum_committed_dollars','per_contract_dollars','per_combo_dollars','per_fixture_dollars')}
    holds=ExecutionRiskHolds(j,c);service=QuoteLiability(holds)
    body={'rfq_id':'r1','yes_bid':'0','no_bid':'.7','post_only':True,'rest_remainder':False}
    buckets={'contract':['a'],'combo':['c'],'fixture':['f']}
    with pytest.raises(ValueError,match='post-only'):
        service.reserve('bad','risk:bad',{**body,'post_only':False},'10',EVIDENCE,100,buckets)
    assert holds.available_units()==1000000
    result=service.reserve('create:r1','risk:r1',body,'10',EVIDENCE,100,buckets)
    assert Decimal(result['liability']['cash_bound'])==Decimal('7.1735')
    quote={'rfq_id':'r1','yes_bid_dollars':'0','no_bid_dollars':'.7','post_only':True,
           'yes_contracts_fp':'10','no_contracts_fp':'10'}
    assert service.assess_returned_size('create:r1',quote,EVIDENCE,101)['within_reserved_cash']
    quote['no_contracts_fp']='10.01'
    assert not service.assess_returned_size('create:r1',quote,EVIDENCE,101)['within_reserved_cash']
    assert holds.available_units()==1000000-71735
    with pytest.raises(ValueError,match='validity'):
        service.assess_returned_size('create:r1',quote,EVIDENCE,1001)
    j.close()


def test_missing_precision_evidence_and_invalid_quantity_rejected():
    with pytest.raises(ValueError,match='evidence required'):
        no_quote_cash_bound('10','.7',replace(EVIDENCE,precision_reference=''),100)
    with pytest.raises(ValueError,match='fixed-point'):
        no_quote_cash_bound('10.001','.7',EVIDENCE,100)
