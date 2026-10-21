import json, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from combos.event_store import EventStore


def test_fill_edge_report_joins_markout_and_settlement(tmp_path):
    db=tmp_path/'events.sqlite'; store=EventStore(db)
    pricing={'legs':[{'venue_point_range_cents':1.,'guard':{'maximum_interval_gap_cents':.5},
                      'venues':{'kalshi':{'weight':.5,'fee_expanded_spread_cents':2.},
                                'polymarket':{'weight':.3,'fee_expanded_spread_cents':1.},
                                'pinnacle':{'weight':.2,'fee_expanded_spread_cents':1.}}}]}
    with store.transaction():
        store.append('simulation_fill_confirmed','shadow',{
            'reservation_id':'shadow:r1','source_seq':20,'decision_source_seq':10,
            'confirmed_at':101.,'creator_id':'c1','quantity':10.,'fill_price':.30,
            'initial_fair_point':.27,'confirmation_fair_point':.27,'fair_move_cents':0.,
            'quote_gross_edge_cents':3.,'fill_gross_edge_cents':3.,'fill_net_edge_cents':2.5,
            'fill_net_edge_dollars':.25,'too_tight_at_confirmation':False,
            'confirmation_pricing':pricing},'fill-confirmed',101.)
        store.append('markout','shadow',{'decision_seq':10,'horizon_seconds':5.,'status':'observed',
            'markout_net_edge_per_share':.02,'markout_net_edge_dollars':.20},'markout',106.)
        store.append('risk_transition','shadow',{'reservation_id':'shadow:r1','new_status':'simulated_settled',
            'pnl_dollars':1.5},'settled',200.)
    store.close()
    out=tmp_path/'report'
    subprocess.run([sys.executable,str(ROOT/'scripts/shadow_fill_edge_report.py'),
                    '--events',str(db),'--out',str(out)],check=True)
    report=json.loads((out/'summary.json').read_text())
    assert report['fills']==1 and report['settled_fills']==1
    assert any(x['group']=='settlement_cohort' and x['key']=='maker_win' for x in report['groups'])
    cohort=next(x for x in report['groups'] if x['group']=='settlement_cohort')
    assert cohort['markouts']['5.0']['markout_net_edge_dollars']==.2
    csv_text=(out/'fills.csv').read_text()
    assert 'markout_5.0_net_edge_dollars' in csv_text
