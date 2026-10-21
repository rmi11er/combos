from supervise_frozen_validation import pending_dates
import json
import sys
import pytest


def test_only_certified_day_statuses_release_wait():
    dates = ['a','b','c','d','e']
    batch = {'status':'complete','days':{'a':{'status':'complete'},
        'b':{'status':'complete_empty_eligible_scope'},'c':{'status':'ready'},
        'd':{'status':'collected_unpriced_identity'}}}
    assert pending_dates(batch,dates) == ['c','d','e']


@pytest.mark.parametrize('fails',[False,True])
def test_stages_run_once_and_failure_preserves_output(tmp_path,monkeypatch,fails):
    import supervise_frozen_validation as supervisor
    batch=tmp_path/'batch.json';batch.write_text(json.dumps({'days':{'a':{'status':'complete'}}}))
    stages=[{'name':n,'command':[n],'expected_receipt':str(tmp_path/(n+'.json')),
             'required_receipt_fields':{'passed':True}} for n in ('replay','audit')]
    plan={'cwd':str(tmp_path),'pinned_sha256':{},'batch_status':str(batch),
          'validation_dates':['a'],'minimum_free_bytes':0,'lock_path':str(tmp_path/'lock'),
          'stages':stages}
    path=tmp_path/'plan.json';path.write_text(json.dumps(plan))
    calls=[]
    def launch(command,**kwargs):
        name=command[0];calls.append(name)
        receipt=tmp_path/(name+'.json');receipt.write_text(json.dumps({'passed':True}))
        class Child:
            pid=123
            returncode=1 if fails and name=='replay' else 0
            def poll(self):return self.returncode
        return Child()
    monkeypatch.setattr(supervisor.subprocess,'Popen',launch)
    out=tmp_path/'supervisor'
    monkeypatch.setattr(sys,'argv',['supervisor','--plan',str(path),'--out',str(out)])
    if fails:
        with pytest.raises(RuntimeError,match='stage_failed'):
            supervisor.main()
        assert calls==['replay']
    else:
        supervisor.main()
        assert calls==['replay','audit']
    status=json.loads((out/'status.json').read_text())
    assert status['status']==('stopped' if fails else 'complete')
    assert (tmp_path/'replay.json').exists()
