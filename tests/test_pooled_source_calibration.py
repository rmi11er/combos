import gzip,json,sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from pooled_source_calibration import analyze


def test_matched_score_and_fixture_omission(tmp_path):
    p=tmp_path/'rows.gz'
    with gzip.open(p,'wt') as f:
        for i,outcome in enumerate((0,1)):
            for model in ('kalshi','polymarket','exchange_blend_equal','exchange_blend_pm75'):
                f.write(json.dumps(dict(evaluation_id=str(i),model=model,at=i,quantity=10,yes_price=.5,maker_fee=.1,yes_settlement=outcome,fair_point=.2 if model=='polymarket' else .5,buckets={'fixture':[str(i)]}))+'\n')
    r=analyze([p]);assert r['common_prints']==2
    assert r['models']['kalshi']['quantity_weighted_brier']==.25
    assert r['models']['polymarket']['quantity_weighted_brier']==pytest.approx(.34)
    assert [x['pm_minus_k_brier'] for x in r['fixture_omissions']]==pytest.approx([.39,-.21])
    assert r['models']['polymarket']['net_dollars']==pytest.approx(-.2)
    with pytest.raises(ValueError,match='duplicate print'):analyze([p,p])
