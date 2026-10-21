#!/usr/bin/env python3
"""Read-only, bounded-memory decoded parity audit against a retained oracle."""
import argparse,gzip,hashlib,itertools,json,math,time
import xml.etree.ElementTree as ET
from pathlib import Path
from replay_artifact_io import text_reader

def compare(a,b,path='',display=False,differences=None):
 differences=differences if differences is not None else []
 if type(a)!=type(b) and not (isinstance(a,(int,float)) and isinstance(b,(int,float))):
  raise AssertionError((path,'type',type(a).__name__,type(b).__name__))
 if isinstance(a,dict):
  if a.keys()!=b.keys():raise AssertionError((path,'keys',a.keys()-b.keys(),b.keys()-a.keys()))
  for k in a:compare(a[k],b[k],path+'/'+k,display,differences)
 elif isinstance(a,list):
  if len(a)!=len(b):raise AssertionError((path,'length',len(a),len(b)))
  for i,(x,y) in enumerate(zip(a,b)):compare(x,y,path+'/'+str(i),display,differences)
 elif a!=b:
  # Only aggregate display metrics can differ from Python's compensated sum.
  if display and isinstance(a,float) and isinstance(b,float) and math.isclose(a,b,rel_tol=1e-13,abs_tol=1e-8):differences.append({'path':path,'oracle':a,'stream':b,'absolute_difference':abs(a-b)})
  else:raise AssertionError((path,a,b))
 return differences

def artifact(directory,prefix,kind):
 matches=[directory/(prefix+'.'+kind+'.jsonl.'+suffix) for suffix in ('gz','zst')]
 matches=[p for p in matches if p.is_file()]
 if len(matches)!=1:raise ValueError('expected exactly one artifact codec: '+prefix+'.'+kind)
 return matches[0]

def main():
 p=argparse.ArgumentParser();p.add_argument('--oracle',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True);a=p.parse_args();start=time.time()
 original=json.loads((a.oracle/'summary.json').read_text());candidate=json.loads((a.candidate/'summary.json').read_text());rounding=[]
 for key in ('study_id','start_at','end_at','coverage'):compare(original[key],candidate[key],key)
 compare(original['records'],candidate['records'],'records',True,rounding)
 result={'oracle':str(a.oracle),'candidate':str(a.candidate),'summary_display_rounding':rounding,'artifacts':[]}
 for record in original['records']:
  prefix='__'.join(record[k] for k in ('model','variant','regime'))
  for kind in ('decisions','fills','curves'):
   left_path=artifact(a.oracle,prefix,kind);right_path=artifact(a.candidate,prefix,kind);name=left_path.name;count=0;lh=hashlib.sha256();rh=hashlib.sha256()
   with text_reader(left_path) as left,text_reader(right_path) as right:
    for count,(x,y) in enumerate(itertools.zip_longest(left,right),1):
     if x is None or y is None:raise AssertionError((name,'length',count))
     compare(json.loads(x),json.loads(y),name+'/'+str(count));lh.update(x.encode());rh.update(y.encode())
   result['artifacts'].append({'name':name,'rows':count,'decoded_exact':True,'candidate_name':right_path.name,'decoded_oracle_sha256':lh.hexdigest(),'decoded_candidate_sha256':rh.hexdigest(),'decoded_bytes_identical':lh.digest()==rh.digest()})
  print(prefix,flush=True)
 result['plots']=[]
 for png in sorted(a.oracle.glob('*.png')):
  candidate_png=a.candidate/png.name
  if hashlib.sha256(png.read_bytes()).digest()!=hashlib.sha256(candidate_png.read_bytes()).digest():raise AssertionError(('plot_png_changed',png.name))
  svg=candidate_png.with_suffix('.svg');ET.parse(svg)
  result['plots'].append({'png':png.name,'byte_identical':True,'svg':svg.name,'valid_xml':True})
 result.update(elapsed_seconds=time.time()-start,policies=len(original['records']),decoded_exact=True)
 (a.candidate/'parity.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
