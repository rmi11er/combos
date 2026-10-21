import json
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from report_frozen_validation import verified_summary, digest
from report_frozen_validation import curve
from replay_artifact_io import text_writer


def case(tmp_path):
    records=[{'variant':str(i),'regime':regime} for i in range(14) for regime in ('funded','unlimited')]
    p=tmp_path/'summary.json';p.write_text(json.dumps({'records':records}))
    audit={'passed':True,'summary_sha256':digest(p),'portfolios':[
        {'policy':r['variant'],'regime':r['regime'],'artifact_hashes':{}} for r in records]}
    (tmp_path/'independent_verification.json').write_text(json.dumps(audit))
    (tmp_path/'complete.json').write_text(json.dumps({'summary_sha256':digest(p)}))
    return audit


def test_summary_requires_matching_audit_and_full_census(tmp_path):
    audit=case(tmp_path)
    assert len(verified_summary(tmp_path)[0]['records'])==28
    audit['portfolios'].pop()
    (tmp_path/'independent_verification.json').write_text(json.dumps(audit))
    with pytest.raises(ValueError,match='census'):verified_summary(tmp_path)


def test_changed_audited_artifact_blocks_report(tmp_path):
    audit=case(tmp_path);p=tmp_path/'fills';p.write_text('original')
    audit['portfolios'][0]['artifact_hashes']={str(p):digest(p)}
    (tmp_path/'independent_verification.json').write_text(json.dumps(audit))
    p.write_text('changed')
    with pytest.raises(ValueError,match='artifact changed'):verified_summary(tmp_path)


def test_notional_endpoint_must_reconcile(tmp_path):
    row={'at':1,'trade_attributed_pnl':5,'committed_cash':0,
         'filled_yes_premium':10,'filled_payout_notional':100,'accepted_point_edge':1}
    with text_writer(tmp_path/'p__funded.curves.jsonl.zst') as f:f.write(json.dumps(row)+'\n')
    record={'variant':'p','regime':'funded','portfolio':{'trade_attributed_pnl':5,'ending_committed_cash':0},
            'selected':{'yes_premium':10,'payout_notional':100}}
    assert curve(tmp_path,record)[0]==[row]
    record['selected']['payout_notional']=101
    with pytest.raises(ValueError,match='filled_payout_notional'):curve(tmp_path,record)
