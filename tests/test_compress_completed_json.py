from pathlib import Path
import sys
import shutil
import pytest
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import compress_completed_json as m


def test_open_source_skipped(tmp_path):
    p=tmp_path/'a.json';p.write_text('{}');assert m.replace_compressed(p,lambda p:False)['status']=='open_file_skipped'


def test_corrupt_copy_preserves_original(tmp_path,monkeypatch):
    p=tmp_path/'a.json';p.write_text('{"a":1}');original=p.read_bytes()
    monkeypatch.setattr(m,'compress_copy',lambda s,d:Path(d).write_bytes(b'bad'))
    with pytest.raises(ValueError,match='logical_bytes_mismatch'):m.replace_compressed(p,lambda p:True)
    assert p.read_bytes()==original


def test_uncompressed_copy_skipped(tmp_path,monkeypatch):
    p=tmp_path/'a.json';p.write_bytes(b'hello'*1000);original=p.read_bytes()
    monkeypatch.setattr(m,'compress_copy',lambda s,d:shutil.copyfile(s,d))
    assert m.replace_compressed(p,lambda p:True)['status']=='no_physical_benefit_skipped'
    assert p.read_bytes()==original


@pytest.mark.skipif(sys.platform!='darwin',reason='macOS native compression')
def test_native_compression_roundtrip(tmp_path):
    assert m.probe(tmp_path)['status']=='native_transparent_compression_verified'
    p=tmp_path/'data.json';p.write_bytes(b'{"key":"test value"}\n'*40000);h=m.sha(p)
    result=m.replace_compressed(p,lambda p:True)
    assert result['allocated_bytes_saved']>0 and m.sha(p)==h
    assert m.replace_compressed(p,lambda p:True)['status']=='already_native_compressed'


def test_candidate_completion_and_target_only_attestation(tmp_path):
    import json
    date='2026-07-01';p=tmp_path/date/'replay/opportunities.json';p.parent.mkdir(parents=True);p.write_text('{}')
    stage={'status':'complete','exit_code':0,'output_sha256':{str(p):m.sha(p)}};state={'days':{date:{'status':'running'}},'stages':{date+'/replay':stage}}
    (tmp_path/'batch_status.json').write_text(json.dumps(state));assert not m.candidates(tmp_path,[])
    state['days'][date]['status']='complete';(tmp_path/'batch_status.json').write_text(json.dumps(state));cert=m.candidates(tmp_path,[])[p]
    m.attest_target(p,cert,tmp_path)
    state['days'][date]['status']='running';(tmp_path/'batch_status.json').write_text(json.dumps(state))
    with pytest.raises(ValueError,match='target_completion'):m.attest_target(p,cert,tmp_path)


@pytest.mark.skipif(sys.platform!='darwin',reason='macOS native compression')
def test_already_compressed_candidate_skips_content_hash(tmp_path,monkeypatch):
    import json
    date='2026-07-01';p=tmp_path/date/'replay/opportunities.json';p.parent.mkdir(parents=True);p.write_bytes(b'{"k":"value"}\n'*100000)
    h=m.sha(p);m.replace_compressed(p,lambda p:True)
    state={'days':{date:{'status':'complete'}},'stages':{date+'/replay':{'status':'complete','exit_code':0,'output_sha256':{str(p):h}}}}
    (tmp_path/'batch_status.json').write_text(json.dumps(state))
    monkeypatch.setattr(m,'sha',lambda p:pytest.fail('already compressed file must not be rehashed'))
    assert not m.candidates(tmp_path,[])
