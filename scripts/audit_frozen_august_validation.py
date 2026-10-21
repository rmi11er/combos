"""Independent policy, cohort, fill and integer-risk audit of frozen validation."""
import argparse
from collections import Counter
from datetime import datetime
from itertools import zip_longest
import json
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo
from deployment_exposure_audit import audit_decisions
from mlb_disk_index import file_digest, iter_model
from replay_artifact_io import text_reader
from run_mlb_streaming_snapshot import source_hashes


def rows(path):
    with text_reader(path) as handle:
        for line in handle:
            yield json.loads(line)


def check_policy(original, decision, policy, feature=None):
    fraction = policy['marginal_reserve_fraction']
    for key, value in original.items():
        if key not in ('source', 'stressed_upper'):
            assert decision[key] == value, ('changed_source_field', key)
    source = dict(decision['source'])
    reference = original['stressed_upper']
    if fraction:
        candidate = source.pop('quote_reserve_candidate')
        assert feature is not None and abs(feature[0]-original['fair_point']) < 1e-9
        reference = original['fair_point']+fraction*(feature[1]-original['fair_point'])
        assert candidate['fraction'] == fraction
        assert candidate['original_joint_upper'] == original['stressed_upper']
        assert candidate['independent_marginal_upper'] == feature[1]
    assert source == original['source']
    assert abs(decision['stressed_upper']-reference) < 1e-12
    c = policy['configuration']
    q, price, fee = (original[k] for k in ('quantity','yes_price','maker_fee'))
    fair = original['fair_point'] if c['entry_basis']=='point' else reference
    edge = q*(price-fair)-fee
    multiplier = original['source']['nlegs'] if c['minimum_net_edge_unit']=='leg_contract' else 1
    required = q*c['minimum_net_edge_per_share']*multiplier
    assert decision['selected_net_edge'] == edge
    assert decision['required_net_edge'] == (required if c['entry_filter']=='minimum_edge' else None)
    for key in ('entry_basis','entry_filter','minimum_net_edge_unit'):
        assert decision[key] == c[key]
    return original['quote_allowed'] and (c['entry_filter']=='all_priced' or edge>=required)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('study','spec','freeze','out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    audit_sources = source_hashes()
    spec = json.loads(a.spec.read_text())
    assert file_digest(a.spec) == json.loads(a.freeze.read_text())['specification_sha256']
    start = json.loads((a.study/'started.json').read_text())
    complete = json.loads((a.study/'complete.json').read_text())
    summary = json.loads((a.study/'summary.json').read_text())
    summary_hash = file_digest(a.study/'summary.json')
    assert summary_hash == complete['summary_sha256'] and complete['portfolios'] == 28
    assert summary['specification_sha256'] == start['specification_sha256'] == file_digest(a.spec)
    root = Path(__file__).resolve().parents[1]
    for name, digest in start['source_hashes'].items():
        assert file_digest(root/name) == digest, name
    exclusion = Path(spec['exclusion_manifest']['path'])
    assert file_digest(exclusion) == spec['exclusion_manifest']['sha256']
    excluded = set(json.loads(exclusion.read_text())['fixtures'])
    index = a.study/'input.sqlite'; feature_path = a.study/'features.sqlite'
    cert = json.loads((a.study/'feature_certificate.json').read_text())
    assert cert['index_sha256'] == file_digest(index) and cert['database_sha256'] == file_digest(feature_path)
    db = sqlite3.connect(feature_path.resolve().as_uri()+'?mode=ro',uri=True)
    policies = {p['id']:p for p in spec['policies']}
    expected = {(p,r) for p in policies for r in spec['regimes']}
    assert len(summary['records']) == len(expected) == 28
    assert {(r['variant'],r['regime']) for r in summary['records']} == expected
    results = []
    for record in summary['records']:
        policy = policies[record['variant']]; regime = record['regime']; c = policy['configuration']
        assert record['configuration'] == c and record['model'] == policy['model']
        assert record['frozen_role'] == policy['role'] and record['marginal_reserve_fraction'] == policy['marginal_reserve_fraction']
        prefix = a.study/(policy['id']+'__'+regime)
        decision_path = prefix.with_suffix('.decisions.jsonl.zst')
        fill_path = prefix.with_suffix('.fills.jsonl.zst')
        digests = {str(p):file_digest(p) for p in (decision_path,fill_path)}
        counts = Counter(); totals = {'decisions':0,'fills':0,'pnl':0.}
        def original_rows():
            for row in iter_model(index,policy['model']):
                date = datetime.fromtimestamp(row['at'],ZoneInfo(spec['timezone'])).date().isoformat()
                assert date in spec['dates']
                counts[date,'input'] += 1
                if excluded.intersection(row['buckets']['fixture']):
                    counts[date,'excluded'] += 1
                else:
                    counts[date,'retained'] += 1
                    yield row
        fills = iter(rows(fill_path))
        def checked():
            for original, decision in zip_longest(original_rows(), rows(decision_path)):
                assert original is not None and decision is not None, 'missing_or_extra_decision'
                feature = db.execute('SELECT point,independent_upper FROM features WHERE evaluation_id=? AND model=?',
                    (original['evaluation_id'],policy['model'])).fetchone()
                eligible = check_policy(original,decision,policy,feature)
                if policy['marginal_reserve_fraction']:
                    assert decision['source']['quote_reserve_candidate']['feature_reference'] == 'sha256:'+cert['database_sha256']
                if regime=='funded':
                    assert ('risk' in decision) == eligible
                else:
                    assert decision['accepted'] == eligible
                totals['decisions'] += 1
                if decision['accepted']:
                    fill = next(fills, None); assert fill is not None
                    for target, source in (('fill_id','evaluation_id'),('filled_at','at'),('quantity','quantity'),('yes_price','yes_price'),('maker_fee','maker_fee'),('yes_settlement','yes_settlement')):
                        assert fill[target] == original[source]
                    settled = None if original['settled_at'] is None else original['settled_at']+c['settlement_delay_seconds']
                    assert fill['settled_at'] == settled
                    pnl = None if settled is None else original['quantity']*(original['yes_price']-original['yes_settlement'])-original['maker_fee']
                    assert fill['eventual_net_pnl'] == pnl
                    totals['fills'] += 1; totals['pnl'] += pnl or 0.
                yield decision
        if regime=='funded':
            exposure = audit_decisions(checked(),c)
        else:
            for _ in checked(): pass
            exposure = None
        assert next(fills,None) is None, 'extra_fill'
        assert totals['decisions'] == record['portfolio']['evaluations']
        assert totals['fills'] == record['portfolio']['fills']
        assert abs(totals['pnl']-record['portfolio']['trade_attributed_pnl']) < .01
        for date in spec['dates']:
            assert {k:counts[date,k] for k in ('input','excluded','retained')} == summary['purge']['dates'][date]
        assert digests == {str(p):file_digest(p) for p in (decision_path,fill_path)}
        results.append({'policy':policy['id'],'regime':regime,'totals':totals,'exposure':exposure,'artifact_hashes':digests})
        print('verified',policy['id'],regime,flush=True)
    db.close()
    assert cert['index_sha256'] == file_digest(index) and cert['database_sha256'] == file_digest(feature_path)
    assert summary_hash == file_digest(a.study/'summary.json')
    assert audit_sources == source_hashes()
    a.out.write_text(json.dumps({'passed':True,'portfolios':results,'summary_sha256':summary_hash,
        'audit_source_sha256':file_digest(Path(__file__)), 'audit_source_hashes':audit_sources},indent=2)+'\n')


if __name__ == '__main__':
    main()
