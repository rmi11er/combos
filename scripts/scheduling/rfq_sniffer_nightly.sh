#!/bin/zsh
set -eu
set -a
source ~/.codex/.env
set +a
cd ~/projects/combos
if [[ "${1:-}" == "--preflight" ]]; then
  .venv/bin/python -c 'import sys; sys.path.insert(0,"src"); from combos.shadow import auth_headers; auth_headers(); print("Credential signing preflight passed")'
  exit 0
fi
run_directory="$1"
.venv/bin/python -u scripts/rfq_sniffer.py run \
  --root "$run_directory" --seconds 3600 \
  --db data/derived/rfq_sniffer/evidence_v2.sqlite \
  --out output/rfq_sniffer --policy config/rfq_sniffer.json
mkdir -p "$run_directory/report"
.venv/bin/python research/rfq_flow_design/verify_v2.py \
  --db data/derived/rfq_sniffer/evidence_v2.sqlite \
  --export output/rfq_sniffer --out "$run_directory/report/validation.json"
cp output/rfq_sniffer/{blacklist.json,summary.json,creators.csv,evidence.jsonl,watchlist.jsonl} "$run_directory/report/"
