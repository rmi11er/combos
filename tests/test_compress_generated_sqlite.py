import json
from pathlib import Path
import sqlite3
import sys
import pytest
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import compress_generated_sqlite as m


def fixture(tmp):
    p=tmp/'data.sqlite';db=sqlite3.connect(p);db.execute('create table sample (id integer, value text)');db.executemany('insert into sample values (?,?)',((i,'repeat me '*30) for i in range(5000)));db.commit();db.close()
    proof=tmp/'complete.json';proof.write_text('{"complete":true}')
    return p,{'path':str(p),'file_sha256':m.sha(p),'logical_bytes':p.stat().st_size,'completion_evidence':[{'path':str(proof),'sha256':m.sha(proof),'expected_fields':{'complete':True}}]}


def test_hard_allowlist_refuses_arbitrary_path(tmp_path):
    p,item=fixture(tmp_path)
    with pytest.raises(ValueError,match='allowlist'):m.validate_manifest({'schema_version':1,'databases':[item]})


def test_nonempty_sidecar_and_open_db_rejected(tmp_path):
    p,item=fixture(tmp_path);side=Path(str(p)+'-wal');side.write_bytes(b'pending transaction')
    with pytest.raises(ValueError,match='nonempty_sqlite_sidecar'):m.process(item,lambda p:True)
    side.unlink()
    with pytest.raises(ValueError,match='sqlite_or_sidecar_open'):m.process(item,lambda p:False)


def test_changed_pinned_database_refused(tmp_path):
    p,item=fixture(tmp_path)
    with p.open('ab') as f:f.write(b'changed')
    with pytest.raises(ValueError,match='pinned_database_changed'):m.process(item,lambda p:True)


@pytest.mark.skipif(sys.platform!='darwin',reason='native macOS filesystem compression')
def test_native_sqlite_preserves_hash_queries_mode_mtime(tmp_path):
    p,item=fixture(tmp_path);before=p.stat();result=m.process(item,lambda p:True)
    assert result['allocated_bytes_saved']>0 and m.sha(p)==item['file_sha256']
    assert p.stat().st_mode==before.st_mode and p.stat().st_mtime_ns==before.st_mtime_ns
    db=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True);assert db.execute('select count(*) from sample').fetchone()[0]==5000;db.close()
    assert m.process(item,lambda p:True)['status']=='already_native_compressed'


@pytest.mark.skipif(sys.platform!='darwin',reason='native macOS filesystem compression')
@pytest.mark.parametrize('mutation',['sidecar','certificate','fingerprint'])
def test_preswap_change_refused_and_original_preserved(tmp_path,monkeypatch,mutation):
    p,item=fixture(tmp_path);original=m.sha(p);copy=m.compress_copy
    def changed(source,dest):
        copy(source,dest)
        if mutation=='sidecar':Path(str(p)+'-journal').write_bytes(b'new active journal')
        elif mutation=='certificate':Path(item['completion_evidence'][0]['path']).write_text('{"complete":false}')
        else:
            import os
            st=p.stat();os.utime(p,ns=(st.st_atime_ns,st.st_mtime_ns+1000000))
    monkeypatch.setattr(m,'compress_copy',changed)
    with pytest.raises(ValueError):m.process(item,lambda p:True)
    assert m.sha(p)==original and not p.stat().st_flags & 32
