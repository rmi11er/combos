import copy
from datetime import datetime, timedelta
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import pytest

SPEC = importlib.util.spec_from_file_location('dated_universe', Path(__file__).parents[1]/'scripts/mlb_dated_universe_report.py')
m = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(m)


def row(identifier='a', settlement=0., q=10, price=.2, fee=.1):
    return {'trade':{'trade_id':identifier,'ticker':'combo','created_time':'2026-07-01T12:00:00Z','taker_side':'yes','count_fp':str(q),'yes_price_dollars':str(price)},
            'classification':{'pure_mlb':True,'nlegs':6,'distinct_fixtures':False,'fullgame_core':False,'known_player_prop':True,'fixture_tokens':['x','x','y']},
            'sampling_method':'census','pregame_scheduled_proxy':False,'settlement_value':settlement,'maker_fee_dollars':fee,
            'fee_rate_provenance':{'verified':False,'reference':'explicit scenario'}}


def cohort(tmp, rows, date='2026-07-01'):
    p=tmp/date;p.mkdir(); start=datetime.fromisoformat(date).replace(tzinfo=m.ZONE);end=start+timedelta(days=1)
    manifest=p/'manifest.json';manifest.write_text('{}')
    summary={'date':date,'start_at':start.timestamp(),'end_at':end.timestamp(),'complete_census':True,'pure_mlb_prints':len(rows),
             'sources':[{'start_at':start.timestamp(),'end_at':end.timestamp(),'method':'census','sample_weight_in_replay':1,'path':str(manifest),'sha256':m.digest(manifest)}]}
    (p/'summary.json').write_text(json.dumps(summary))
    with gzip.open(p/'universe_trades.jsonl.gz','wt') as f:
        for r in rows:f.write(json.dumps(r)+'\n')
    return p


def test_unknown_bounds_fee_and_full_scope(tmp_path):
    a=row(); b=row('b',None); c=row('c',1);c['trade']['taker_side']='no'
    report,_,_=m.analyze([cohort(tmp_path,[a,b,c])]);t=report['totals']
    assert t['prints']==2 and t['unknown_prints']==1
    assert t['known_net_pnl']==pytest.approx(1.9)
    assert t['final_pnl_lower']==pytest.approx(-6.2)
    assert t['final_pnl_upper']==pytest.approx(3.8)
    assert report['cuts']['legs']['5+']['prints']==2
    assert report['cuts']['family']['Includes known player prop']['prints']==2
    assert report['cuts']['phase']['After scheduled start']['prints']==2
    assert len(report['fixtures'])==2
    assert all(x['prints']==2 and x['final_pnl_lower_after_exclusion']==0 for x in report['fixtures'])
    assert report['opposite_or_unknown_taker_direction_excluded']==1
    assert report['statistics']['observed_date_pnl_variance_dollars2'] is None


def test_identical_duplicates_removed_conflicts_fail(tmp_path):
    a=row();p=cohort(tmp_path,[a,a]);r,_,_=m.analyze([p]);assert r['totals']['prints']==1 and r['duplicate_identical_rows_removed']==1
    b=copy.deepcopy(a);b['maker_fee_dollars']=.2
    with gzip.open(p/'universe_trades.jsonl.gz','wt') as f:f.write(json.dumps(a)+'\n'+json.dumps(b)+'\n')
    with pytest.raises(ValueError,match='conflicting_duplicate'):m.analyze([p])


def test_noncontiguous_calendar_and_hash_fail(tmp_path):
    p=cohort(tmp_path,[row()]);s=json.loads((p/'summary.json').read_text());s['sources'][0]['start_at']+=1;(p/'summary.json').write_text(json.dumps(s))
    with pytest.raises(ValueError,match='noncontiguous'):m.analyze([p])
    s['sources'][0]['start_at']-=1;(p/'summary.json').write_text(json.dumps(s));(p/'manifest.json').write_text('changed')
    with pytest.raises(ValueError,match='hash_mismatch'):m.analyze([p])


def test_calendar_gaps_not_zero_returns(tmp_path):
    a=cohort(tmp_path,[row()]);b=row('b',1);b['trade']['created_time']='2026-07-03T12:00:00Z';c=cohort(tmp_path,[b],'2026-07-03')
    r,curves,_=m.analyze([a,c]);assert r['observed_dates']==['2026-07-01','2026-07-03']
    assert r['statistics']['observed_date_pnl_variance_dollars2']==pytest.approx(50)
    assert r['statistics']['annualized_sharpe'] is None
    assert len(curves)==2


def test_corrupt_economics_and_universe_count_fail(tmp_path):
    a=row();a['seller_pnl_dollars']=100;p=cohort(tmp_path,[a])
    with pytest.raises(ValueError,match='pnl_mismatch'):m.analyze([p])
    a.pop('seller_pnl_dollars');a['trade']['yes_price_dollars']='nan'
    with pytest.raises(ValueError,match='invalid_trade'):m.economics(a)
    s=json.loads((p/'summary.json').read_text());s['pure_mlb_prints']=2;(p/'summary.json').write_text(json.dumps(s))
    with gzip.open(p/'universe_trades.jsonl.gz','wt') as f:f.write(json.dumps(row())+'\n')
    with pytest.raises(ValueError,match='row_count'):m.analyze([p])
