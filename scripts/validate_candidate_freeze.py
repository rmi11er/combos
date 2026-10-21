#!/usr/bin/env python3
"""Verify a research candidate freeze without contacting an exchange."""
import argparse, hashlib, json
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--freeze',type=Path,required=True); args=p.parse_args()
    freeze=json.loads(args.freeze.read_text())
    errors=[]
    if freeze.get('status')!='research_frozen_shadow_only': errors.append('invalid_status')
    if freeze.get('orders_enabled') is not False: errors.append('orders_must_be_disabled')
    if freeze.get('automatic_promotion') is not False: errors.append('automatic_promotion_must_be_disabled')
    hashes=freeze.get('evidence',{}).get('source_hashes',{})
    for filename,expected in hashes.items():
        path=Path(filename)
        if not path.is_file(): errors.append('missing:'+filename); continue
        actual=hashlib.sha256(path.read_bytes()).hexdigest()
        if actual!=expected: errors.append('changed:'+filename)
    result={'freeze_id':freeze.get('freeze_id'),'orders_enabled':freeze.get('orders_enabled'),
            'source_files':len(hashes),'errors':errors,'valid':not errors}
    print(json.dumps(result,indent=2))
    return 0 if not errors else 2


if __name__=='__main__': raise SystemExit(main())
