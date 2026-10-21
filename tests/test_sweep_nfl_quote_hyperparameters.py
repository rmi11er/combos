import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('sweep', ROOT / 'scripts/sweep_nfl_quote_hyperparameters.py')
sweep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sweep)


def test_sweep_module_exposes_replay():
    assert sweep.replay.__name__ == 'replay'
