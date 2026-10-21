from copy import deepcopy
from decimal import Decimal
import pytest
from combos.execution_fills import FillEvidence, normalize_fill
from combos.execution_journal import ExecutionJournal


def fill(**changes):
    return dict(fill_id='f1', order_id='o1', trade_id='t1', ticker='combo',
        subaccount_number=0, exchange_index=0, side='no', action='buy',
        is_taker=False, count_fp='1.60', yes_price_dollars='.08',
        no_price_dollars='.92', fee_cost='.002100', **changes)


def envelope(rows):
    return dict(method='GET', path='/trade-api/v2/portfolio/fills', http_status=200,
        request_started_at=100, received_at=101, params={'subaccount': 0},
        payload={'fills': rows, 'cursor': ''})


def test_restart_and_overlapping_pages_do_not_double_count(tmp_path):
    path = tmp_path / 'journal.sqlite'
    journal = ExecutionJournal(path)
    evidence = FillEvidence(journal)
    assert evidence.ingest(envelope([fill()]), 'page1')['new_fills'] == 1
    journal.close()
    journal = ExecutionJournal(path)
    evidence = FillEvidence(journal)
    assert evidence.ingest(envelope([fill(), fill()]), 'page2')['new_fills'] == 0
    totals = evidence.order_totals('o1', 0, 0)
    assert totals['fill_count'] == 1
    assert Decimal(totals['quantity']) == Decimal('1.6')
    assert Decimal(totals['fee']) == Decimal('.0021')
    assert Decimal(totals['trade_cash_flow_before_balance_adjustments']) == Decimal('-1.4741')
    assert not totals['order_complete'] and not totals['capital_release_authorized']
    journal.close()


def test_conflict_rolls_back_entire_page(tmp_path):
    journal = ExecutionJournal(tmp_path / 'journal.sqlite')
    evidence = FillEvidence(journal)
    evidence.ingest(envelope([fill()]), 'original')
    new = fill(); new['fill_id'] = 'f2'
    changed = fill(); changed['fee_cost'] = '.1'
    with pytest.raises(ValueError, match='conflicting'):
        evidence.ingest(envelope([new, changed]), 'conflict')
    assert evidence.order_totals('o1', 0, 0)['fill_count'] == 1
    assert journal.db.execute('SELECT COUNT(*) FROM account_fill_observations').fetchone()[0] == 1
    journal.close()


@pytest.mark.parametrize('side,action,price', [('yes','buy','.08'), ('no','buy','.92'),
                                            ('yes','sell','.08'), ('no','sell','.92')])
def test_direction_and_reported_fee(side, action, price):
    row = fill(); row.update(side=side, action=action)
    normalized = normalize_fill(row)
    principal = Decimal('1.6') * Decimal(price)
    expected = (-principal if action == 'buy' else principal) - Decimal('.0021')
    assert Decimal(normalized['trade_cash_flow_before_balance_adjustments']) == expected


@pytest.mark.parametrize('field,value', [('count_fp','NaN'), ('count_fp','.001'),
    ('no_price_dollars','.91'), ('fee_cost','-.01'), ('outcome_side','yes'),
    ('subaccount_number',True), ('is_taker',1)])
def test_malformed_economics_rejected(field, value):
    row = fill(); row[field] = value
    with pytest.raises(ValueError):
        normalize_fill(row)
