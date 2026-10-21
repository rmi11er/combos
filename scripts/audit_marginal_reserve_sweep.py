"""Audit source preservation, reserve policy, admissions and point-baseline parity."""
import argparse
import hashlib
from itertools import zip_longest
import json
from pathlib import Path
import sqlite3
from deployment_exposure_audit import audit_decisions
from mlb_disk_index import file_digest, iter_model
from replay_artifact_io import text_reader


def check_row(original, row, feature, fraction, config, funded):
    for key, value in original.items():
        if key not in ('source', 'stressed_upper'):
            assert row[key] == value, ('changed_source_field', key, original['evaluation_id'])
    source = dict(row['source'])
    candidate = source.pop('quote_reserve_candidate')
    assert source == original['source']
    assert candidate['original_joint_upper'] == original['stressed_upper']
    assert candidate['fraction'] == fraction
    assert abs(feature[0]-original['fair_point']) < 1e-9
    expected = original['fair_point']+fraction*(feature[1]-original['fair_point'])
    assert abs(row['stressed_upper']-expected) < 1e-12
    assert candidate['independent_marginal_upper'] == feature[1]
    q, p, fee = row['quantity'], row['yes_price'], row['maker_fee']
    edge = q*(p-row['stressed_upper'])-fee
    hurdle = q*config['minimum_net_edge_per_share']
    assert row['selected_net_edge'] == edge and row['required_net_edge'] == hurdle
    qualifies = row['quote_allowed'] and edge >= hurdle
    if funded:
        assert ('risk' in row) == qualifies, 'risk_gate_did_not_follow_pricing'
        if not qualifies:
            assert not row['accepted']
    else:
        assert row['accepted'] == qualifies


def rows(path):
    with text_reader(path) as handle:
        yield from (json.loads(line) for line in handle)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--study', type=Path, required=True)
    p.add_argument('--index', type=Path, required=True)
    p.add_argument('--features', type=Path, required=True)
    p.add_argument('--point-funded', type=Path, required=True)
    p.add_argument('--point-unlimited', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--completed-only', action='store_true')
    a = p.parse_args()
    summary_path = a.study/('progress.json' if a.completed_only else 'summary.json')
    summary_bytes = summary_path.read_bytes()
    summary = json.loads(summary_bytes)
    summary_hash = hashlib.sha256(summary_bytes).hexdigest()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.with_suffix('.input.json').write_bytes(summary_bytes)
    if not a.completed_only:
        complete = json.loads((a.study/'complete.json').read_text())
        assert summary_hash == complete['summary_sha256'] and complete['portfolios'] == 24
    start = json.loads((a.study/'started.json').read_text())
    root = Path(__file__).resolve().parents[1]
    for name, digest in start['source_hashes'].items():
        assert file_digest(root/name) == digest, name
    assert file_digest(a.index) == start['index_sha256']
    feature_hash = file_digest(a.features/'features.sqlite')
    assert feature_hash == start['feature_database_sha256']
    feature_db = sqlite3.connect((a.features/'features.sqlite').resolve().as_uri()+'?mode=ro', uri=True)
    checks = []
    for record in summary['records']:
        model, variant, regime = (record[k] for k in ('model', 'variant', 'regime'))
        prefix = a.study/(model+'__'+variant+'__'+regime)
        path = prefix.with_suffix('.decisions.jsonl.zst')
        before = file_digest(path)
        totals = {'decisions': 0, 'fills': 0, 'pnl': 0.}
        def checked():
            for original, row in zip_longest(iter_model(a.index, model), rows(path)):
                assert original is not None and row is not None
                feature = feature_db.execute('SELECT point,independent_upper FROM features WHERE evaluation_id=? AND model=?',
                    (row['evaluation_id'], model)).fetchone()
                assert feature is not None
                assert row['source']['quote_reserve_candidate']['feature_reference'] == 'sha256:'+feature_hash
                check_row(original, row, feature, record['marginal_reserve_fraction'], record['configuration'], regime=='funded')
                totals['decisions'] += 1
                if row['accepted']:
                    totals['fills'] += 1
                    if row['yes_settlement'] is not None:
                        totals['pnl'] += row['quantity']*(row['yes_price']-row['yes_settlement'])-row['maker_fee']
                yield row
        if regime == 'funded':
            exposure = audit_decisions(checked(), record['configuration'])
        else:
            for _ in checked():
                pass
            exposure = None
        assert totals['decisions'] == record['portfolio']['evaluations'] == 467583
        assert totals['fills'] == record['portfolio']['fills']
        assert abs(totals['pnl']-record['portfolio']['trade_attributed_pnl']) < .01
        assert before == file_digest(path)
        parity = None
        if record['marginal_reserve_fraction'] == 0:
            ref = (a.point_funded/(model+'__balanced1000.fills.jsonl.zst') if regime=='funded' else
                   a.point_unlimited/(model+'__edge_0_3c__unlimited.fills.jsonl.zst'))
            fields = ('fill_id', 'filled_at', 'quantity', 'yes_price', 'maker_fee', 'yes_settlement', 'settled_at', 'eventual_net_pnl')
            count = 0
            for x, y in zip_longest(rows(prefix.with_suffix('.fills.jsonl.zst')), rows(ref)):
                assert x is not None and y is not None
                assert all(x[k] == y[k] for k in fields), ('baseline_fill_mismatch', model, regime, count)
                count += 1
            parity = {'fills': count, 'reference_sha256': file_digest(ref)}
        checks.append({'model':model, 'variant':variant, 'regime':regime, 'totals':totals,
                       'exposure':exposure, 'point_baseline_parity':parity, 'decisions_sha256':before})
        print('verified', model, variant, regime, flush=True)
    feature_db.close()
    assert file_digest(a.index) == start['index_sha256']
    assert file_digest(a.features/'features.sqlite') == feature_hash
    a.out.write_text(json.dumps({'passed':True, 'all_24_complete':not a.completed_only,
        'checks':checks, 'summary_snapshot_sha256':summary_hash, 'audit_source_sha256':file_digest(Path(__file__))},indent=2)+'\n')


if __name__ == '__main__':
    main()
