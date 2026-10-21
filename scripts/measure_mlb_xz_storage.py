#!/usr/bin/env python3
"""Read-only source audit: three lossless xz files and payload-size measurements."""
import argparse,gzip,hashlib,json,lzma,resource,sqlite3,time,zlib
from pathlib import Path
CHUNK=1024*1024

def decoded_digest(path,opener):
 h=hashlib.sha256();size=rows=0
 with opener(path,'rb') as source:
  for chunk in iter(lambda:source.read(CHUNK),b''):
   h.update(chunk);size+=len(chunk);rows+=chunk.count(b'\n')
 return {'sha256':h.hexdigest(),'bytes':size,'rows':rows}

def main():
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 result={'source':str(a.source),'codec':'xz/LZMA2 preset 6 (stdlib lzma), default CRC64','chunk_bytes':CHUNK,'files':[],'index_payloads':[]}
 for kind in ('decisions','fills','curves'):
  path=a.source/('kalshi__sell_every_priced_print__unlimited.'+kind+'.jsonl.gz');dest=a.out/(path.name[:-3]+'.xz');before=time.monotonic();h=hashlib.sha256();size=rows=0
  with gzip.open(path,'rb') as inp,lzma.open(dest,'wb',preset=6) as out:
   for chunk in iter(lambda:inp.read(CHUNK),b''):
    h.update(chunk);size+=len(chunk);rows+=chunk.count(b'\n');out.write(chunk)
  compression=time.monotonic()-before;before=time.monotonic();verification=decoded_digest(dest,lzma.open);verification_seconds=time.monotonic()-before
  expected={'sha256':h.hexdigest(),'bytes':size,'rows':rows}
  if expected!=verification:raise ValueError('lossless_verification_failed')
  record={'kind':kind,'source':str(path),'destination':str(dest),'gzip_bytes':path.stat().st_size,'xz_bytes':dest.stat().st_size,'compression_seconds':compression,'verification_seconds':verification_seconds,'decoded':expected,'lossless_verified':True,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
  record['xz_fraction_of_gzip']=record['xz_bytes']/record['gzip_bytes'];result['files'].append(record);print(json.dumps(record),flush=True)
  (a.out/'measurement.json').write_text(json.dumps(result,indent=2)+'\n')
 with sqlite3.connect('file:'+str((a.source/'input.sqlite').resolve())+'?mode=ro',uri=True) as db:
  db.execute('PRAGMA cache_size=-16384');result['index_pages']={p:db.execute('PRAGMA '+p).fetchone()[0] for p in ('page_count','freelist_count','page_size')}
  for table,column in (('prints','shared'),('models','payload')):
   before=time.monotonic();count=raw_size=zsize=0
   for (raw,) in db.execute('SELECT '+column+' FROM '+table):
    data=raw.encode('utf-8');packed=zlib.compress(data,6)
    if zlib.decompress(packed)!=data:raise ValueError('payload_roundtrip_failed')
    count+=1;raw_size+=len(data);zsize+=len(packed)
   result['index_payloads'].append({'table':table,'column':column,'rows':count,'utf8_bytes':raw_size,'zlib6_bytes':zsize,'lossless_all_rows_verified':True,'elapsed_seconds':time.monotonic()-before})
 totals={kind:sum(p.stat().st_size for p in a.source.glob('*.'+kind+'.jsonl.gz')) for kind in ('decisions','fills','curves')};result['full_48_gzip_bytes']=totals
 result['estimated_48_xz_bytes']={r['kind']:totals[r['kind']]*r['xz_fraction_of_gzip'] for r in result['files']}
 result['peak_rss_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
 (a.out/'measurement.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
