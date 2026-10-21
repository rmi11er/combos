from copy import deepcopy
import pytest
from build_quote_features import features, MODELS


def test_no_side_complement_causal_availability_and_interval_width():
    c = {m: {'interval': {'lower': .3, 'point': .4, 'upper': .6}, 'available_at': 9} for m in MODELS}
    row = {'at': 10, 'legs': [{'side': 'yes'}, {'side': 'no'}], 'context': [deepcopy(c), deepcopy(c)]}
    for value in features(row).values():
        assert value['point'] == pytest.approx(.24)
        assert value['independent_upper'] == pytest.approx(.42)
        assert value['summed_marginal_interval_cents'] == pytest.approx(60)
    row['context'][1]['polymarket']['available_at'] = 11
    with pytest.raises(ValueError, match='future_source'):
        features(row)
