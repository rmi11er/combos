"""Review one archived settlement against complete, ticker-filtered fill pages."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from combos.kalshi_readonly import private_json
from combos.settlement_accounting import reconcile_buy_only_settlement


def review(settlement_page, row_index, fill_pages):
    if (settlement_page.get('method') != 'GET' or settlement_page.get('http_status') != 200 or
            settlement_page.get('path') != '/trade-api/v2/portfolio/settlements'):
        raise ValueError('successful settlement read required')
    subaccount = settlement_page.get('params', {}).get('subaccount')
    if type(subaccount) is not int:
        raise ValueError('settlement page must explicitly filter a subaccount')
    if type(row_index) is not int or row_index < 0:
        raise ValueError('nonnegative row index required')
    settlement = settlement_page['payload']['settlements'][row_index]
    fills = []
    cursor = ''
    seen = set()
    for page in fill_pages:
        params = page.get('params', {})
        if (page.get('method') != 'GET' or page.get('http_status') != 200 or
                page.get('path') != '/trade-api/v2/portfolio/fills' or
                params.get('ticker') != settlement['ticker'] or
                params.get('subaccount') != subaccount or params.get('cursor', '') != cursor or
                any(k not in ('ticker', 'subaccount', 'cursor', 'limit') for k in params)):
            raise ValueError('complete exact-market fill pagination required')
        if cursor in seen:
            raise ValueError('duplicate or cyclic fill pages')
        seen.add(cursor)
        fills.extend(page['payload']['fills'])
        cursor = page['payload'].get('cursor')
        if not isinstance(cursor, str):
            raise ValueError('fill cursor missing')
    if not fill_pages or cursor:
        raise ValueError('incomplete fill pagination')
    return reconcile_buy_only_settlement(settlement, fills, subaccount)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settlement-page', type=Path, required=True)
    parser.add_argument('--row-index', type=int, default=0)
    parser.add_argument('--fill-page', type=Path, action='append', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--journal', type=Path, help='Persist reconciliation evidence without changing cash or holds')
    args = parser.parse_args()
    result = review(json.loads(args.settlement_page.read_text()), args.row_index,
        [json.loads(p.read_text()) for p in args.fill_page])
    result['source_references'] = [str(args.settlement_page), *map(str, args.fill_page)]
    if args.journal:
        from combos.execution_journal import ExecutionJournal
        from combos.settlement_evidence import SettlementEvidence
        page = json.loads(args.settlement_page.read_text())
        fills = [fill for path in args.fill_page
                 for fill in json.loads(path.read_text())['payload']['fills']]
        journal = ExecutionJournal(args.journal)
        try:
            record = SettlementEvidence(journal).record(
                page['payload']['settlements'][args.row_index], fills,
                page['params']['subaccount'], result['source_references'])
            result['evidence_id'] = record['evidence_id']
        finally:
            journal.close()
    private_json(args.out, result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('ticker','source_references')}))
