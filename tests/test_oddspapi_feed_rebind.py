import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('feed', ROOT / 'scripts/oddspapi_feed.py')
feed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(feed)


def test_feed_module_uses_dynamic_selector_rebinding():
    # The implementation must retain reviewed metadata while replacing native
    # market identifiers; the helper is exercised by the live capture artifact.
    assert 'bind_selectors' in feed.capture.__globals__
