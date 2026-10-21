import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import compress_completed_exchange_catalogs as m


def test_requires_completed_date_and_exchange_and_hashes(tmp_path):
    date='2026-07-01';exchange=tmp_path/date/'exchange';exchange.mkdir(parents=True)
    outputs={}
    for name in ['acquisition.json','polymarket_mapping_reviewed.json']:
        p=exchange/name;p.write_text('{}');outputs[str(p)]=m.sha(p)
    stage={'status':'complete','exit_code':0,'output_sha256':outputs};state={'days':{date:{'status':'ready'}},'stages':{date+'/exchange':stage}}
    p=tmp_path/'batch_status.json';p.write_text(json.dumps(state));assert m.certificate(tmp_path,date) is None
    state['days'][date]['status']='complete';stage['status']='running';p.write_text(json.dumps(state));assert m.certificate(tmp_path,date) is None
    stage['status']='complete';p.write_text(json.dumps(state));assert m.certificate(tmp_path,date)['date']==date
    (exchange/'acquisition.json').write_text('changed')
    import pytest
    with pytest.raises(ValueError,match='certificate_output_changed'):m.certificate(tmp_path,date)
