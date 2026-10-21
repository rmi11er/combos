from copy import deepcopy
import pytest
from combos.payoff_enumeration import review, native


def mapping(kind, suffix, native_kind, yes, no, period='first_half'):
    return {'fixture_key':'NFL:date:A-B', 'market_key':f'NFL:date:A-B:{period}:{kind}:{suffix}',
        'market_type':kind, 'period':period, 'pinnacle':{
            'catalog':{'marketType':native_kind, 'period':'p1+p2', 'sportId':14, 'playerProp':False},
            'yes':{'bookmaker_outcome_id':yes}, 'no':{'bookmaker_outcome_id':no}}}


@pytest.mark.parametrize('m', [
    mapping('moneyline','A','spreads','-0.5/home','-0.5/away'),
    mapping('moneyline','B','spreads','0.5/away','0.5/home'),
    mapping('spreads','B:1.5','spreads','1.5/away','1.5/home'),
    mapping('totals','over:7.5','totals','7.5/over','7.5/under'),
    mapping('team_totals','A:over:7.5','teamtotals-team1','home/7.5/over','home/7.5/under'),
    mapping('team_totals','B:over:7.5','teamtotals-team2','away/7.5/over','away/7.5/under')])
def test_completed_period_payoffs(m):
    result = review(m, {'participant1Abbr':'A','participant2Abbr':'B'}, maximum_score=15)
    assert result['status'] == 'completed_period_binary_verified'
    assert result['score_pairs_checked'] == 256
    bad = deepcopy(m); bad['pinnacle']['yes'], bad['pinnacle']['no'] = bad['pinnacle']['no'], bad['pinnacle']['yes']
    assert review(bad, {'participant1Abbr':'A','participant2Abbr':'B'}, maximum_score=15)['status'] == 'payoff_mismatch'


def test_integer_push_not_treated_as_binary_loss():
    m = mapping('totals','over:7','totals','7/over','7/under')
    assert native(m['pinnacle'], 3, 4, 'yes') is None
    assert review(m, {'participant1Abbr':'A','participant2Abbr':'B'}, maximum_score=10)['status'] == 'void_basis_required'


def test_period_scope_rejected():
    m = mapping('totals','over:7.5','totals','7.5/over','7.5/under')
    m['pinnacle']['catalog']['period'] = 'result'
    with pytest.raises(ValueError, match='scope'):
        review(m, {'participant1Abbr':'A','participant2Abbr':'B'})
