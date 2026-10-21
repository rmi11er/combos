"""Bounded private GET collection; does not initialize or release trading risk."""
import argparse
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from combos.kalshi_readonly import ReadOnlyClient, ReadSigner, PREFIX, private_json
from combos.account_cash import assess_account_cash


def collect(client, out, max_pages=5, strategy_budget=None):
    out = Path(out)
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    request_count = 0

    def archive(page):
        nonlocal request_count
        request_count += 1
        private_json(out / f'request_{request_count:04d}.json', page)

    summary = {'atomic_snapshot': False, 'ledger_initialization_authorized': False,
               'collections': {}}
    for label, suffix, params, fields in (
        ('positions', 'portfolio/positions', {'subaccount': 0, 'count_filter': 'position', 'limit': 100}, ('market_positions',)),
        ('resting_orders', 'portfolio/orders', {'subaccount': 0, 'status': 'resting', 'limit': 100}, ('orders',)),
        ('self_quotes', 'communications/quotes', {'user_filter': 'self', 'limit': 100}, ('quotes',)),
    ):
        result = client.paginate(PREFIX + suffix, fields, params=params,
                                 max_pages=max_pages, archive=archive)
        summary['collections'][label] = {
            'rows': sum(len(v) for v in result['rows'].values()),
            'pages': len(result['pages']), 'pagination_complete': result['pagination_complete'],
            'stop_reason': result['stop_reason']}
        if result['stop_reason'] == 'request_failed':
            summary['stopped_after_request_failure'] = True
            break
    else:
        balance = client.get(PREFIX + 'portfolio/balance', {'subaccount': 0})
        archive(balance)
        summary['balance_http_status'] = balance.get('http_status')
        if strategy_budget is not None:
            try:
                assessment = assess_account_cash(balance, strategy_budget, time.time())
                private_json(out / 'cash_assessment.json', assessment)
                summary['cash_assessment'] = assessment
            except (ValueError, KeyError, TypeError) as exc:
                summary['cash_assessment_error'] = str(exc)
    summary['request_count'] = request_count
    private_json(out / 'summary.json', summary)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    parser.add_argument('--max-pages', type=int, choices=range(1, 101), default=5)
    parser.add_argument('--strategy-budget', type=str, help='Assess available cash against this budget; never initializes a ledger')
    args = parser.parse_args()
    import json
    print(json.dumps(collect(ReadOnlyClient(ReadSigner.from_environment()), args.out, args.max_pages, args.strategy_budget)))
