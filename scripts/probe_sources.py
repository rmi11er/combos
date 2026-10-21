import datetime as dt
import json
import os
from pathlib import Path
import sys
import requests

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://external-api.kalshi.com/trade-api/v2"
def save(name, url, params=None, headers=None):
    r = requests.get(url, params=params, headers=headers, timeout=30)
    try:
        payload = r.json()
    except ValueError:
        payload = r.text[:2000]
    envelope = {"url": r.url, "status": r.status_code, "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(), "payload": payload}
    dest = ROOT / "data/raw/probes" / (name + ".json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(envelope, indent=2))
    print(name, r.status_code, (list(payload) if isinstance(payload,dict) else "list:" + str(len(payload))), flush=True)
    return payload

if __name__ == "__main__":
    save("kalshi_cutoff", BASE + "/historical/cutoff")
    save("kalshi_series", BASE + "/series")
    for series in ["KXNCAAFGAME", "KXNCAAFSPREAD", "KXNCAAFTOTAL", "KXMVESPORTSMULTIGAMEEXTENDED", "KXMVECROSSCATEGORY"]:
        save("series_" + series, BASE + "/series/" + series)
        save("fees_" + series, BASE + "/series/fee_changes", {"series_ticker":series,"show_historical":"true"})
    save("polymarket_sports", "https://gamma-api.polymarket.com/sports")
    save("polymarket_slate", "https://gamma-api.polymarket.com/events", {"limit":100,"start_date_min":"2026-09-05T00:00:00Z","start_date_max":"2026-09-07T00:00:00Z","tag_slug":"ncaa-football"})
    sys.path.insert(0, "../kalshi_mm")
    from src.kalshi_v2 import KalshiRequestSigner
    key_path = os.environ.get("KALSHI_PRIVATE_KEY_PATH")
    if key_path:
        signer = KalshiRequestSigner(os.environ["KALSHI_API_KEY_ID"], Path(key_path).expanduser().read_text())
        for status in [None,"closed"]:
            params={"limit":2}
            if status:
                params["status"] = status
            save("rfqs_" + str(status), BASE + "/communications/rfqs",params,signer.headers("GET","/trade-api/v2/communications/rfqs"))
