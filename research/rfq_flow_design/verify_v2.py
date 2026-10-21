"""Read-only consistency checks for the completed v2 sniffer database/export."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import sqlite3


def verify(database, export):
    db=sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True)
    db.row_factory=sqlite3.Row
    db.execute('PRAGMA query_only=ON')
    db.execute('BEGIN')
    policy=json.loads(db.execute("SELECT value FROM metadata WHERE key='policy'").fetchone()[0])
    summary=json.loads((Path(export)/'summary.json').read_text())
    blacklist=json.loads((Path(export)/'blacklist.json').read_text())
    assert policy==summary['policy']
    previous={};count=0;eligible=0
    for row in db.execute('SELECT * FROM bursts ORDER BY at,id'):
        creator,at,level=row['creator'],row['at'],row['block_eligible']
        evidence=json.loads(row['evidence']);reasons=json.loads(row['reasons'])
        assert at-previous.get((creator,level),-1e30)>=policy['window_seconds']
        previous[(creator,level)]=at
        window=db.execute('SELECT id,features,legs FROM requests WHERE creator=? AND at>? AND at<=?',
                          (creator,at-policy['window_seconds'],at)).fetchall()
        ids={r['id'] for r in window}
        assert len(window)==evidence['requests']
        assert set(evidence['sample_rfq_ids'])<=ids
        assert evidence['trigger_rfq_id'] in ids
        assert 0<=evidence['large_concentrated_similar']<=evidence['similar']<=len(window)
        # Exact matches are counted across the whole creator window. Similar
        # matches belong to one retained anchor; anchor eviction can split them.
        trigger=next(r for r in window if r['id']==evidence['trigger_rfq_id'])
        exact=sum(r['legs']==trigger['legs'] and json.loads(r['features'])['valid_legs'] for r in window)
        assert evidence['identical']==exact
        assert bool(level)==evidence['block_eligible']
        for reason in reasons:
            if reason=='high_request_rate_watch':
                assert not level and len(window)>=policy['watch_rate_requests']
            elif reason=='high_request_rate':
                assert level and len(window)>=policy['rate_requests']
            elif reason=='identical_parlay_spam':
                assert level and evidence['identical']>=policy['repeated_requests']
            elif reason=='minor_edit_parlay_spam':
                assert level and evidence['similar']>=policy['repeated_requests'] and evidence['similar']>evidence['identical']
            elif reason=='large_concentrated_parlay_spam':
                assert level and evidence['large_concentrated_similar']>=policy['huge_repeated_requests']
            else:
                raise AssertionError(reason)
        eligible+=bool(level);count+=1
    active=set();confidence=defaultdict(int)
    for row in db.execute('SELECT * FROM blacklist'):
        history=db.execute('SELECT at,period_id FROM bursts WHERE creator=? AND block_eligible=1 AND at<=? ORDER BY at',
                           (row['creator'],row['last_at'])).fetchall()
        recent=[r for r in history if r['at']>row['last_at']-policy['burst_evidence_seconds']]
        assert len(recent)>=policy['bursts_to_blacklist']
        ttl=policy['blacklist_seconds'] if row['confidence']=='recurrent' else policy['provisional_blacklist_seconds']
        assert abs(row['expires_at']-row['last_at']-ttl)<1e-6
        if row['confidence']=='recurrent':
            periods=json.loads(row['qualifying_periods'])
            assert len(periods)>=2
            for period,qualified_at in periods.items():
                assert sum(r['period_id']==period and qualified_at-policy['burst_evidence_seconds']<r['at']<=qualified_at for r in history)>=policy['bursts_to_blacklist']
            assert any(r['period_id'] in periods and other!=r['period_id'] and r['at']-qualified_at>=policy['recurrence_minimum_seconds']
                       for r in history for other,qualified_at in periods.items())
        if row['expires_at']>summary['generated_at']:
            active.add(row['creator']);confidence[row['confidence']]+=1
    assert active==set(blacklist['creator_ids'])
    assert len(active)==summary['active_blacklist_ids']
    assert dict(confidence)==summary['active_confidence_counts']
    assert count==summary['observed_bursts'] and eligible==summary['block_eligible_bursts']
    total=db.execute('SELECT COUNT(*) FROM requests').fetchone()[0]
    assert total==summary['unique_requests']
    for column in ('trade_context','extended_trade_context'):
        counts=dict(db.execute(f'SELECT {column},COUNT(*) FROM requests GROUP BY {column}').fetchall())
        assert counts==summary[column] and sum(counts.values())==total and 'pending' not in counts
    assert not db.execute("SELECT 1 FROM requests WHERE trade_context='later_public_trade_same_market' AND extended_trade_context!='later_public_trade_same_market' LIMIT 1").fetchone()
    assert not db.execute("SELECT 1 FROM requests WHERE extended_trade_context='no_public_trade_observed_in_covered_window' AND trade_context!='no_public_trade_observed_in_covered_window' LIMIT 1").fetchone()
    db.close()
    return {'verified':True,'request_count':total,'verified_bursts':count,'block_eligible_bursts':eligible,
            'active_ids':len(active),'confidence':dict(confidence),'trade_horizons_consistent':True,
            'checks':'Stored evidence counts, sample membership, thresholds, separation, recurrence support, expiry, exports and horizon consistency. Not a calibration of malicious intent.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--db',required=True)
    parser.add_argument('--export',required=True)
    parser.add_argument('--out',required=True)
    args=parser.parse_args()
    result=verify(args.db,args.export)
    Path(args.out).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
