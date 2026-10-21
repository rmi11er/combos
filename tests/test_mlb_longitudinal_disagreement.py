import gzip
import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from mlb_longitudinal_disagreement import analyze
from mlb_longitudinal_disagreement import main


def fixture(tmp_path, *, missing=False, mismatch=False):
    summary = {'coverage':{'observed_dates':['2026-07-01'],'missing_dates':[]},
               'records':[{'model':m,'regime':'unlimited','variant':'edge_0_3c',
                           'configuration':{'minimum_net_edge_per_share':.004 if mismatch and m=='polymarket' else .003}}
                          for m in ('kalshi','polymarket')]}
    (tmp_path/'summary.json').write_text(json.dumps(summary))
    for m in ('kalshi','polymarket'):
        with gzip.open(tmp_path/f'{m}__edge_0_3c__unlimited.decisions.jsonl.gz','wt') as f:
            if missing and m=='polymarket': continue
            row = dict(model=m,evaluation_id='a',at=1,quantity=10,yes_price=.3,maker_fee=.1,
                       yes_settlement=0,fair_point=.2 if m=='polymarket' else .4,
                       accepted=m=='polymarket',reason='accepted' if m=='polymarket' else 'insufficient_edge',
                       buckets={'combo':['c'],'fixture':['f','g']},source={'nlegs':2,'series':['KXMLBGAME']})
            f.write(json.dumps(row)+'\n')
    return tmp_path


def test_source_selection_omissions_remove_whole_shared_fixture(tmp_path):
    result=analyze(fixture(tmp_path),'edge_0_3c')
    assert result['all_common']['known_net_seller_pnl']==pytest.approx(2.9)
    assert len(result['selection_fixture_sensitivity']['polymarket_only'])==2
    assert all(r['prints']==0 for r in result['selection_fixture_sensitivity']['polymarket_only'])
    assert len(result['provenance']['input_hashes'])==3


@pytest.mark.parametrize('kwargs,match', [({'missing':True},'complete_common'),({'mismatch':True},'inconsistent_source_policies')])
def test_refuses_incomplete_pairing_or_different_policies(tmp_path,kwargs,match):
    with pytest.raises(ValueError,match=match):
        analyze(fixture(tmp_path,**kwargs),'edge_0_3c')


def test_unresolved_report_retains_bounds_and_no_brier(tmp_path, monkeypatch):
    version = fixture(tmp_path)
    for p in version.glob('*.jsonl.gz'):
        with gzip.open(p,'rt') as f:
            row=json.loads(f.readline())
        row['yes_settlement']=None
        with gzip.open(p,'wt') as f:
            f.write(json.dumps(row)+'\n')
    out=tmp_path/'report'
    monkeypatch.setattr(sys,'argv',['audit','--version',str(version),'--out',str(out)])
    main()
    result=json.loads((out/'results.json').read_text())
    assert result['all_common']['loose_final_pnl_bounds']==pytest.approx([-7.1,2.9])
    assert 'N/A (unresolved)' in (out/'REPORT.md').read_text()


def test_zstd_and_legacy_gzip_have_identical_economics(tmp_path):
    from replay_artifact_io import text_writer, ZSTD
    if not ZSTD.exists():
        pytest.skip('Zstandard CLI unavailable')
    version = fixture(tmp_path)
    legacy = analyze(version, 'edge_0_3c')
    for path in version.glob('*.jsonl.gz'):
        with gzip.open(path, 'rt') as source, text_writer(path.with_suffix('.zst')) as target:
            target.write(source.read())
    summary_path = version/'summary.json'
    summary = json.loads(summary_path.read_text())
    summary['artifact_codec'] = {'name': 'zstd'}
    summary_path.write_text(json.dumps(summary))
    compressed = analyze(version, 'edge_0_3c')
    assert compressed.pop('provenance')['artifact_codec'] == 'zstd'
    assert legacy.pop('provenance')['artifact_codec'] == 'gzip'
    assert compressed == legacy


def test_rejects_unknown_declared_codec(tmp_path):
    version = fixture(tmp_path)
    path = version/'summary.json'
    summary = json.loads(path.read_text())
    summary['artifact_codec'] = {'name': 'unknown'}
    path.write_text(json.dumps(summary))
    with pytest.raises(ValueError, match='unsupported_artifact_codec'):
        analyze(version, 'edge_0_3c')
