#!/usr/bin/env python3
"""Extend completed XZ audit with installed zstd, retaining <=3 temp outputs."""
import argparse,gzip,hashlib,json,re,resource,subprocess,time
from pathlib import Path
ZSTD='/opt/homebrew/bin/zstd';CHUNK=1024*1024

def main():
 p=argparse.ArgumentParser();p.add_argument('--audit',type=Path,required=True);a=p.parse_args();path=a.audit/'measurement.json';result=json.loads(path.read_text())
 if not all(r['lossless_verified'] for r in result['files']) or len(result['files'])!=3:raise ValueError('requires_completed_three_file_xz_audit')
 # Delete only this audit's verified disposable codec outputs, never source data.
 for r in result['files']:
  old=Path(r['destination'])
  if old.parent.resolve()!=a.audit.resolve() or old.suffix!='.xz':raise ValueError('unexpected_temporary_path')
  old.unlink();r['temporary_removed_after_verification']=True
 result['zstd_version']=subprocess.check_output([ZSTD,'--version'],text=True).strip();result['zstd_files']=[]
 for r in result['files']:
  source=Path(r['source']);destination=a.audit/(source.name[:-3]+'.zst');began=time.monotonic();h=hashlib.sha256();size=rows=0
  with destination.open('wb') as output,gzip.open(source,'rb') as inp:
   with subprocess.Popen(['/usr/bin/time','-l',ZSTD,'-q','-6','-c'],stdin=subprocess.PIPE,stdout=output,stderr=subprocess.PIPE) as process:
    for data in iter(lambda:inp.read(CHUNK),b''):
     h.update(data);size+=len(data);rows+=data.count(b'\n');process.stdin.write(data)
    process.stdin.close();stderr=process.stderr.read().decode();status=process.wait()
    if status:raise RuntimeError(stderr)
  compression=time.monotonic()-began;peak=int(re.search(r'(\d+)\s+maximum resident set size',stderr).group(1));began=time.monotonic();actual=hashlib.sha256();actualsize=actualrows=0
  with subprocess.Popen([ZSTD,'-q','-d','-c',str(destination)],stdout=subprocess.PIPE) as process:
   for data in iter(lambda:process.stdout.read(CHUNK),b''):
    actual.update(data);actualsize+=len(data);actualrows+=data.count(b'\n')
   if process.wait():raise RuntimeError('zstd_decode_failed')
  decoded={'sha256':actual.hexdigest(),'bytes':actualsize,'rows':actualrows}
  if decoded!=r['decoded'] or decoded!={'sha256':h.hexdigest(),'bytes':size,'rows':rows}:raise ValueError('zstd_lossless_verification_failed')
  measured={'kind':r['kind'],'source':str(source),'destination':str(destination),'gzip_bytes':r['gzip_bytes'],'zstd_bytes':destination.stat().st_size,'zstd_fraction_of_gzip':destination.stat().st_size/r['gzip_bytes'],'compression_seconds':compression,'verification_seconds':time.monotonic()-began,'compressor_peak_rss_bytes':peak,'decoded':decoded,'lossless_verified':True}
  result['zstd_files'].append(measured);print(json.dumps(measured),flush=True);path.write_text(json.dumps(result,indent=2)+'\n')
 result['estimated_48_zstd_bytes']={r['kind']:result['full_48_gzip_bytes'][r['kind']]*r['zstd_fraction_of_gzip'] for r in result['zstd_files']}
 result['zstd_driver_peak_rss_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss;path.write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
