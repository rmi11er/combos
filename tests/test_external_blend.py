import json
import pytest
from src.combos.external_blend import HistoricalBlend

def test_external_blend_is_causal_and_keeps_missing_distinct(tmp_path):
    file=tmp_path/'books.jsonl'
    common={'kalshi_market_ticker':'K','mapping_verified':True,'source_reference':'fixture:test','available_at':100,'liquidity_available_at':100,'liquidity_payout_dollars':1000}
    rows=[dict(common,venue=v,yes_bid=.45,yes_ask=.55,historical_taker_rate=.07) for v in ['kalshi','polymarket']]
    rows.append(dict(common,venue='pinnacle',decimal_odds_yes=1.91,decimal_odds_no=1.91))
    file.write_text('\n'.join(json.dumps(r) for r in rows))
    model=HistoricalBlend(file)
    assert model.leg('K','yes',101).point==pytest.approx(.5)
    with pytest.raises(ValueError):model.leg('K','yes',99)
    with pytest.raises(ValueError):model.leg('K','yes',300)
    with pytest.raises(ValueError):model.leg('MISSING','yes',101)
