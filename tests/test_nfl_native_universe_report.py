from decimal import Decimal
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from nfl_native_universe_report import economics, labels


def native(value='0.1400'):
    return {'trade': {'count_fp': '100.00', 'yes_price_dollars': '0.3000'},
            'settlement_value_dollars': value, 'result': 'scalar',
            'pregame_scheduled_proxy': False,
            'classification': {'pure_nfl': True, 'nlegs': 3, 'series': ['KXNFLGAME'],
                'earliest_scheduled_start': None, 'target_fixtures_only': False,
                'fullgame_core': True, 'distinct_fixtures': True}}


def test_fractional_native_settlement_preserved_exactly():
    result = economics(native(), '0')
    assert result['known_net_pnl'] == Decimal('16.000000')
    assert result['known_prints'] == 1 and result['unknown_prints'] == 0
    assert economics(native(), '.035')['known_net_pnl'] == Decimal('15.2650')


def test_unknown_schedule_never_becomes_in_play():
    row = native()
    assert labels(row)['phase'] == 'Unknown schedule'
    row['classification']['earliest_scheduled_start'] = 1768100000
    assert labels(row)['phase'] == 'After schedule cutoff'


def test_unknown_native_outcome_bounded_without_result_imputation():
    row = native(None)
    row['result'] = 'yes'
    result = economics(row, '0')
    assert result['known_prints'] == 0 and result['unknown_prints'] == 1
    assert result['unknown_lower'] == Decimal('-70')
    assert result['unknown_upper'] == Decimal('30')
