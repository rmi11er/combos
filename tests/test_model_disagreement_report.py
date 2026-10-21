from copy import deepcopy
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from model_disagreement_report import pair_rows, metrics, summarize


def rows():
    k = dict(model='kalshi', evaluation_id='a', at=100, quantity=10, yes_price=.3,
             maker_fee=.1, yes_settlement=0, fair_point=.4, accepted=False,
             reason='insufficient_edge', buckets={'combo': ['c'], 'fixture': ['f', 'g']},
             source={'nlegs': 2, 'series': ['KXMLBGAME']})
    p = {**deepcopy(k), 'model': 'polymarket', 'fair_point': .2, 'accepted': True, 'reason': 'accepted'}
    return [k, p]


def test_disagreement_direction_and_paired_scores():
    pairs, _ = pair_rows(rows())
    m = metrics(pairs)
    assert m['pm_minus_kalshi_brier_quantity_weighted'] == pytest.approx(-.12)
    assert m['known_net_seller_pnl'] == pytest.approx(2.9)
    assert m['pnl_per_known_cumulative_no_cash'] == pytest.approx(2.9/7.1)
    result = summarize(pairs)
    assert any(g['value'] == 'pm_lower:polymarket_only' for g in result['groups'])
    assert all(r['prints'] == 0 for r in result['leave_one_fixture_out'])


def test_unknowns_not_losses_or_scores():
    rs = rows()
    for r in rs:
        r['yes_settlement'] = None
    m = metrics(pair_rows(rs)[0])
    assert m['known_net_seller_pnl'] == 0
    assert m['pm_minus_kalshi_brier_quantity_weighted'] is None
    assert m['loose_final_pnl_bounds'] == pytest.approx([-7.1, 2.9])


def test_reject_mismatches_duplicate_and_inventory_selection():
    rs = rows()
    with pytest.raises(ValueError, match='duplicate'):
        pair_rows(rs + [rs[0]])
    rs[1]['quantity'] = 20
    with pytest.raises(ValueError, match='inconsistent_paired_quantity'):
        pair_rows(rs)
    rs = rows()
    rs[1]['reason'] = 'contract_risk_limit'
    with pytest.raises(ValueError, match='unconstrained_price_only'):
        pair_rows(rs)
