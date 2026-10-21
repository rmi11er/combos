"""Read-only, resumable public trade tape; retain source pages compressed."""
import concurrent.futures as cf
import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path
import time
import urllib.parse
import requests

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://external-api.kalshi.com/trade-api/v2"
START = int(dt.datetime(2026, 9, 5, 5, tzinfo=dt.timezone.utc).timestamp())
END = START + 86400

def partition(hour):
    lo = START + hour * 3600
    hi = lo + 3600
    root = ROOT / "data/raw/trades" / f"hour_{hour:02d}"
    root.mkdir(parents=True, exist_ok=True)
    done = root / "manifest.json"
    if done.exists():
        return json.loads(done.read_text())
    session = requests.Session()
    cursor = ""
    cursors = set()
    count = 0
    combos = 0
    page = 0
    while True:
        params = {"min_ts": lo - 1, "max_ts": hi + 1, "limit": 1000}
        if cursor:
            params["cursor"] = cursor
        dest = root / f"page_{page:05d}.json.gz"
        if dest.exists():
            with gzip.open(dest, "rt") as f:
                envelope = json.load(f)
        else:
            for attempt in range(8):
                response = session.get(BASE + "/markets/trades", params=params, timeout=30)
                if response.status_code == 429 or response.status_code >= 500:
                    time.sleep(min(10, 1 + 2 ** attempt))
                    continue
                response.raise_for_status()
                break
            else:
                raise RuntimeError("retries exhausted")
            envelope = {"url": response.url, "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(), "payload": response.json()}
            with gzip.open(dest.with_suffix(".tmp"), "wt") as f:
                json.dump(envelope, f, separators=(",", ":"))
            dest.with_suffix(".tmp").replace(dest)
        payload = envelope["payload"]
        count += len(payload["trades"])
        combos += sum(t["ticker"].startswith("KXMVE") for t in payload["trades"])
        page += 1
        nxt = payload.get("cursor", "")
        if not nxt:
            break
        if nxt in cursors:
            raise RuntimeError("repeated cursor")
        cursors.add(nxt)
        cursor = nxt
        if page % 25 == 0:
            print(json.dumps({"hour": hour, "pages": page, "raw_trades": count, "raw_combos": combos}), flush=True)
        time.sleep(0.08)
    result = {"hour": hour, "start": lo, "end": hi, "pages": page, "raw_rows": count, "raw_combos": combos, "complete": True}
    done.write_text(json.dumps(result, indent=2))
    print(json.dumps(result), flush=True)
    return result

if __name__ == "__main__":
    with cf.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(partition, range(24)))
    (ROOT / "data/raw/trades/manifest.json").write_text(json.dumps({"start": START, "end": END, "timezone": "America/Chicago", "partitions": results}, indent=2))
