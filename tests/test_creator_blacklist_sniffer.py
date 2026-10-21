import json
import sqlite3
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from creator_blacklist_sniffer import run


def evidence(tmp_path, rows):
    p=tmp_path/'evidence.sqlite';db=sqlite3.connect(p)
    db.executescript('CREATE TABLE evidence(source_id TEXT,decision_seq INTEGER,horizon INTEGER,payload TEXT,fixtures TEXT); CREATE TABLE availability(source_id TEXT,decision_seq INTEGER,horizon INTEGER,available_by REAL);')
    for i,row in enumerate(rows):
        db.execute('INSERT INTO evidence VALUES(?,?,?,?,?)',('s',i,row['horizon_seconds'],json.dumps(row),json.dumps(row.get('fixtures',[]))))
        db.execute('INSERT INTO availability VALUES(?,?,?,?)',('s',i,row['horizon_seconds'],row['entry_at']+.1))
    db.commit();db.close();return p


def row(creator,at,i,horizon=30,move=.5,nlegs=2):
    return {'status':'observed','creator_id':creator,'rfq_id':f'r{i}','entry_at':at,
        'horizon_seconds':horizon,'adverse_move_cents':move,
        'entry_scenario':{'legs':[{'market_key':str(n)} for n in range(nlegs)]}}


def test_separate_sniffer_scores_burst_pickoff_and_wide_legs(tmp_path):
    rows=[row('toxic',100+i*.5,i,nlegs=5) for i in range(25)] + [row('normal',100+i*10,100+i,move=.01) for i in range(3)]
    e=evidence(tmp_path,rows);out=tmp_path/'blacklist.sqlite';r=run(e,out,200)
    assert r['automatic_sanctions']==0 and r['review_recommendations']==1
    db=sqlite3.connect(out);x=db.execute('SELECT recommendation,reasons FROM creator_reviews WHERE creator_id=?',('toxic',)).fetchone();assert x[0]=='review';assert 'excessive_leg_count' in x[1];db.close()


def test_run_is_idempotent_and_keeps_source_hash(tmp_path):
    e=evidence(tmp_path,[row('c',100,1,move=.01)]);out=tmp_path/'blacklist.sqlite'
    a=run(e,out,200);b=run(e,out,200);assert a==b
    db=sqlite3.connect(out);assert db.execute('SELECT COUNT(*) FROM runs').fetchone()[0]==1;db.close()
