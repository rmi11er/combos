import json,sqlite3,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from evaluate_dynamic_edge_markouts import run


def test_marks_are_joined_without_inventing_fills(tmp_path):
    d=sqlite3.connect(tmp_path/'d.sqlite');d.execute('create table candidate_decisions(source_seq integer,result text)')
    s={'assumed_usd_per_native_unit':1,'legs':[{'pricing_guard':{'maximum_interval_gap_cents':0,'padding_cents':.5},'venue_components':{'k':{'two_sided_depth_payout_dollars':10000}}}]}
    d.execute('insert into candidate_decisions values(?,?)',(1,json.dumps({'pricing':{'status':'scenario_priced','scenarios':[s]}})));d.commit();d.close()
    m=sqlite3.connect(tmp_path/'m.sqlite');m.execute('create table labels(value text)');m.execute('insert into labels values(?)',(json.dumps({'status':'observed','decision_seq':1,'horizon_seconds':10,'adverse_move_cents':.2,'entry_scenario':s}),));m.execute('insert into labels values(?)',(json.dumps({'status':'observed','decision_seq':99,'horizon_seconds':10,'adverse_move_cents':9,'entry_scenario':s}),));m.commit();m.close()
    out=tmp_path/'o.json';run(tmp_path/'d.sqlite',tmp_path/'m.sqlite',out);r=json.loads(out.read_text());assert r['observed_label_count']==1 and r['hypothetical_quote_or_fill_count']==0
