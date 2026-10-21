import json
from pathlib import Path
import sqlite3
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from sweep_dynamic_edge import run


def test_sweep_only_reports_observed_pricing(tmp_path):
    db=sqlite3.connect(tmp_path/'decisions.sqlite');db.execute('CREATE TABLE candidate_decisions(source_seq INTEGER,result TEXT)')
    scenario={'assumed_usd_per_native_unit':1,'legs':[{'pricing_guard':{'maximum_interval_gap_cents':5,'padding_cents':.5},'venue_components':{'kalshi':{'two_sided_depth_payout_dollars':100},'polymarket':{'two_sided_depth_payout_dollars':100},'pinnacle':{'two_sided_depth_payout_dollars':100}}}]}
    db.execute('INSERT INTO candidate_decisions VALUES(?,?)',(1,json.dumps({'pricing':{'status':'scenario_priced','scenarios':[scenario]}}),));db.commit();db.close()
    out=tmp_path/'out.json';run(tmp_path/'decisions.sqlite',out);rows=json.loads(out.read_text())['policies'];assert rows[1]['records_above_base']>0;assert rows[1]['hypothetical_quote_or_fill_count']==0
