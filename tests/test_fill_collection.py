from types import SimpleNamespace
import pytest
from combos.execution_journal import ExecutionJournal
from combos.fill_collection import FillCollector
from combos.kalshi_readonly import ReadOnlyClient


def row(identity='f', ts=150):
    return dict(fill_id=identity, order_id='o', trade_id=identity, ticker='m',
        exchange_index=0, subaccount_number=0, side='no', action='buy',
        is_taker=False, count_fp='1', yes_price_dollars='.3',
        no_price_dollars='.7', fee_cost='.001', ts=ts)


def setup(tmp_path, pages):
    journal = ExecutionJournal(tmp_path / 'journal.sqlite')
    iterator = iter(pages)
    calls = []
    def get(url, **kwargs):
        calls.append(kwargs['params'])
        payload = next(iterator)
        return SimpleNamespace(status_code=200, json=lambda: payload)
    client = ReadOnlyClient(SimpleNamespace(headers=lambda path: {}),
        session=SimpleNamespace(get=get), clock=lambda: 300)
    return journal, FillCollector(journal, client), calls


def test_overlap_and_deduplication(tmp_path):
    journal, collector, calls = setup(tmp_path, [
        {'fills': [row()], 'cursor': ''}, {'fills': [row(), row('f2', 210)], 'cursor': ''}])
    first = collector.poll(subaccount=0, initial_start=100, until=200, now=300, out=tmp_path/'a')
    second = collector.poll(subaccount=0, initial_start=100, until=250, now=300, out=tmp_path/'b')
    assert first['new_fills'] == second['new_fills'] == 1
    assert calls[1]['min_ts'] == 100
    assert second['checkpoint_advanced']
    assert not second['exchange_finality_established']
    journal.close()


def test_incomplete_page_keeps_checkpoint_and_ingestion_unchanged(tmp_path):
    journal, collector, _ = setup(tmp_path, [{'fills': [row()], 'cursor': 'more'}])
    receipt = collector.poll(subaccount=0, initial_start=100, until=200,
        now=300, out=tmp_path/'a', max_pages=1)
    assert not receipt['checkpoint_advanced']
    assert journal.db.execute('SELECT COUNT(*) FROM fill_poll_checkpoint').fetchone()[0] == 0
    assert journal.db.execute('SELECT COUNT(*) FROM account_fill_evidence').fetchone()[0] == 0
    journal.close()


def test_invalid_later_page_rolls_back_earlier_page(tmp_path):
    journal, collector, _ = setup(tmp_path, [
        {'fills': [row()], 'cursor': 'more'}, {'fills': [row('f2', 999)], 'cursor': ''}])
    receipt = collector.poll(subaccount=0, initial_start=100, until=200, now=300, out=tmp_path/'a')
    assert receipt['stop_reason'] == 'ingestion_rejected'
    assert not receipt['checkpoint_advanced']
    assert journal.db.execute('SELECT COUNT(*) FROM account_fill_evidence').fetchone()[0] == 0
    assert (tmp_path/'a'/'page_0002.json').exists()
    journal.close()
