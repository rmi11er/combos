"""Codec-only regression: identical rows/economics for both ledgers and curves."""
import json,sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from mlb_streaming_longitudinal import evaluate_one,artifact_path
from replay_artifact_io import text_reader,ZSTD
from verify_mlb_streaming_parity import artifact
from test_mlb_longitudinal_sweep import plan,opportunity
from combos.backtest import BacktestConfig

@pytest.mark.skipif(not ZSTD.exists(),reason='native zstd unavailable')
@pytest.mark.parametrize('funded',[False,True])
@pytest.mark.parametrize('empty',[False,True])
def test_lossless_codec_economics_and_rows(tmp_path,funded,empty):
 p=plan();rows=[] if empty else [opportunity('2026-07-01','a'),opportunity('2026-07-03','b',settlement=1783065600,result=1)]
 cfg=BacktestConfig(entry_basis='point',entry_filter='all_priced',**p['baseline_limits']);results=[];decoded={}
 for codec in ('gzip','zstd'):
  prefix=tmp_path/codec
  results.append(evaluate_one(iter(rows),'kalshi','all','all',cfg,funded,{'observed_dates':list(p['dates'])},p,prefix,artifact_codec=codec))
  for kind in ('decisions','fills','curves'):
   with text_reader(artifact_path(prefix,kind,codec)) as f:decoded[codec,kind]=f.read()
 assert results[0]==results[1]
 for kind in ('decisions','fills','curves'):assert decoded['gzip',kind]==decoded['zstd',kind]
 assert not list(tmp_path.glob('*.scratch.sqlite*'))

def test_reader_refuses_ambiguous_suffix_and_invalid_codec(tmp_path):
 (tmp_path/'x.fills.jsonl.gz').touch();(tmp_path/'x.fills.jsonl.zst').touch()
 with pytest.raises(ValueError,match='exactly one'):artifact(tmp_path,'x','fills')
 with pytest.raises(ValueError,match='unsupported'):artifact_path(tmp_path/'x','fills','bad')
