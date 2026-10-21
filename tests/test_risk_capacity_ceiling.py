import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from risk_capacity_ceiling import ceiling


def test_six_moneyline_games_cannot_commit_more_than_300():
    rows=[{'model':'kalshi','buckets':{'contract':[str(i),str(j)],'fixture':[str(i),str(j)]},'risk_multiplier':1}
          for i in range(6) for j in range(i+1,6)]
    r=ceiling(rows)
    assert r['risk_only_committed_cash_ceiling_dollars']==300
    assert r['families']['fixture']['loose_committed_cash_ceiling_dollars']==750


def test_duplicate_aliases_do_not_double_count_and_empty_has_zero_bound():
    r=ceiling([{'model':'kalshi','buckets':{'contract':['a','a'],'fixture':['f','f']}}])
    assert r['risk_only_committed_cash_ceiling_dollars']==100
    assert ceiling([])['risk_only_committed_cash_ceiling_dollars']==0


def test_declines_raised_per_trade_caps():
    with pytest.raises(ValueError,match='non_increasing'):
        ceiling([{'model':'kalshi','risk_multiplier':2}])
