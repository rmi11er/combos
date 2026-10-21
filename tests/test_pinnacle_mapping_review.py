import importlib.util
from pathlib import Path

spec=importlib.util.spec_from_file_location('mapping_review',Path(__file__).resolve().parents[1]/'scripts/review_pinnacle_mapping.py')
review=importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


def sample(kind='spreads',key='SEA:1.5'):
    mapping={'market_key':'NFL:game:'+kind+':'+key,'fixture_key':'NFL:game','market_type':kind,
             'mapping_reference':'synthetic:rules','pinnacle':{'catalog':{'marketType':kind},
              'yes':{'bookmaker_outcome_id':'-1.5/home'},'no':{'bookmaker_outcome_id':'-1.5/away'}}}
    fixture={'participant1Abbr':'SEA','participant2Abbr':'NE'}
    return mapping,fixture


def test_full_score_grid_checks_home_handicap_sign_and_complement():
    mapping,fixture=sample()
    result=review.review_mapping(mapping,fixture)
    assert result['status']=='normal_game_binary_verified'
    mapping['pinnacle']['yes']['bookmaker_outcome_id']='-1.5/away'
    assert review.review_mapping(mapping,fixture)['status']=='normal_game_mismatch'


def test_tied_moneyline_remains_basis_mismatch_not_binary_equivalence():
    mapping,fixture=sample('moneyline','SEA')
    mapping['pinnacle']['yes']['bookmaker_outcome_id']='home'
    mapping['pinnacle']['no']['bookmaker_outcome_id']='away'
    result=review.review_mapping(mapping,fixture)
    assert result['status']=='normal_game_verified_tie_basis_required'
    assert result['tie_void_pairs']==101


def test_total_integer_boundary_and_period_exclusion():
    mapping,fixture=sample('totals','over:45.5')
    mapping['pinnacle']['yes']['bookmaker_outcome_id']='45.5/over'
    mapping['pinnacle']['no']['bookmaker_outcome_id']='45.5/under'
    assert review.review_mapping(mapping,fixture)['status']=='normal_game_binary_verified'
    mapping['pinnacle']['yes']['bookmaker_outcome_id']='46.5/over'
    assert review.review_mapping(mapping,fixture)['status']=='normal_game_mismatch'
    mapping['period']='first_half'
    assert review.review_mapping(mapping,fixture)['status']=='deferred_period_or_team_total'
