import gzip
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import pytest

spec=importlib.util.spec_from_file_location('validation_clones',Path(__file__).parents[1]/'scripts/deduplicate_validation_clones.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def gz(path,payload,mtime):
    with path.open('wb') as f:
        with gzip.GzipFile(filename='',fileobj=f,mode='wb',mtime=mtime) as g:g.write(payload)


def test_header_only_clone_preserves_all_original_bytes(tmp_path,monkeypatch):
    a=tmp_path/'a.gz';b=tmp_path/'b.gz';gz(a,b'abc'*1000,1);gz(b,b'abc'*1000,2);original=b.read_bytes();canonical=a.read_bytes()
    monkeypatch.setattr(m,'clone',lambda s,d:shutil.copyfile(s,d))
    result=m.replace_with_clone(a,b,lambda p:True)
    assert b.read_bytes()==original and a.read_bytes()==canonical
    assert result['original_sha256']==result['after_sha256']


def test_different_payload_and_open_file_refused(tmp_path,monkeypatch):
    a=tmp_path/'a.gz';b=tmp_path/'b.gz';gz(a,b'abc',1);gz(b,b'def',2)
    with pytest.raises(ValueError,match='beyond_mtime'):m.replace_with_clone(a,b,lambda p:True)
    gz(b,b'abc',2)
    with pytest.raises(ValueError,match='open_file'):m.replace_with_clone(a,b,lambda p:False)


def test_bad_clone_preserves_destination(tmp_path,monkeypatch):
    a=tmp_path/'a.gz';b=tmp_path/'b.gz';gz(a,b'abc',1);gz(b,b'abc',2);original=b.read_bytes()
    monkeypatch.setattr(m,'clone',lambda s,d:Path(d).write_bytes(b'corrupt clone'))
    with pytest.raises(ValueError,match='reconstructed_bytes'):m.replace_with_clone(a,b,lambda p:True)
    assert b.read_bytes()==original


def test_only_certified_terminal_versions(tmp_path):
    folder=tmp_path/'validation/v';folder.mkdir(parents=True);file=folder/'validation.json';file.write_text('{}')
    stage={'status':'running','exit_code':0,'output_sha256':{str(file):m.sha(file)}};state={'stages':{'validation/v':stage}};(tmp_path/'batch_status.json').write_text(json.dumps(state));assert not m.certificates(tmp_path)
    stage['status']='complete';(tmp_path/'batch_status.json').write_text(json.dumps(state));assert folder in m.certificates(tmp_path)
    file.write_text('changed')
    with pytest.raises(ValueError,match='certificate_changed'):m.certificates(tmp_path)


@pytest.mark.skipif(sys.platform!='darwin',reason='APFS clone integration requires macOS')
def test_native_copy_on_write_probe(tmp_path):
    assert m.probe(tmp_path)['status']=='clonefile_copy_on_write_verified'
