"""Economic and coverage invariants on the final analysis outputs."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output'
s=json.loads((OUT/'summary.json').read_text());f=pd.read_csv(OUT/'cfb_trade_opportunities.csv');p=f[f.exclusion.isna()]
assert f.trade_id.is_unique
assert f['at'].between(1788584400,1788670800,inclusive='left').all()
assert p.fair_lower.le(p.fair_mid+1e-12).all() and p.fair_mid.le(p.fair_upper+1e-12).all()
assert p.edge_upper.le(p.edge_mid+1e-9).all()
assert p.fair_rho002.ge(p.fair_upper-1e-12).all()
assert p.fair_rho005.ge(p.fair_rho002-1e-12).all()
assert not p.same_game.any()
assert (p.taker_side=='yes').all()
assert p.maximum_leg_age_seconds.between(60,180).all()
assert s['requested_three_venue_estimate'] is None
assert s['assumptions']['no_combo_probability_band']
assert s['assumptions']['customer_ticket_cap_dollars'] is None
for v in ['mid','upper','rho002','rho005','upper_small_prints']:
    a=pd.read_csv(OUT/f'capital_path_{v}.csv')
    assert a.trade_id.is_unique
    assert a.expected_edge.ge(.003*a.quantity-1e-8).all()
    assert a.free_cash_after_allocation.ge(-1e-8).all()
    assert a.quantity.le(a.printed_quantity+1e-8).all()
    assert a.customer_premium.max()>10
    assert a.cumulative_edge.is_monotonic_increasing
    assert np.isclose(a.expected_edge.sum(),s['capital_upper_bound_scenarios'][v]['expected_edge'])
    assert np.isclose(a.terminal_net_pnl.sum(),s['capital_upper_bound_scenarios'][v]['terminal_net_pnl'])
    if v=='upper_small_prints':
        assert f.set_index('trade_id').loc[a.trade_id].premium.between(5,20).all()
hour=pd.read_csv(OUT/'hourly_volume.csv')
rfq=pd.read_csv(OUT/'cfb_rfq_quoteability.csv');q=rfq[rfq.reason=='quotable_individually']
assert q.edge_if_filled.ge(.003*q.hypothetical_contracts-1e-9).all()
assert q.maximum_loss.between(0,10000,inclusive='right').all()
if s['rfq_sample'].get('requests_with_creator_id',0)==0:
    assert s['creator_identity_status']=='unavailable_creator_identity'
    assert s['creator_count']==0 and not rfq.creator_identity_available.any()
assert np.isclose(hour.all_combo_premium.sum(),s['totals']['all_combo_taker_premium'])
assert int(hour.cfb_trades.sum())==len(f)
assert np.isclose(hour.cross_game_premium.sum()+hour.same_game_premium.sum(),s['totals']['cfb_two_leg_premium'])
print(json.dumps({'status':'passed','cfb_trades':len(f),'priced_trades':len(p),'catalog_complete':s['catalog_complete'],'checks':'identifiers, half-open window, probability/edge ordering, causal candle age, all capital ledgers, volume reconciliation, explicit missing blend'}))
