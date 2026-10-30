#!/usr/bin/python3
"""Read-only frozen-ref reconciliation and KiCad geometry inventory."""
import subprocess,json,pathlib,hashlib,collections,pcbnew as k
O=pathlib.Path(__file__).resolve().parent
R=O.parents[2]
def git(*args):return subprocess.check_output(['git',*args],cwd=R,text=True).strip()
def ancestor(a,b):return subprocess.run(['git','merge-base','--is-ancestor',a,b],cwd=R).returncode==0
board='tracker/hardware/hub_board_v10_lora1280_7of9.kicad_pcb'
base=git('rev-parse','origin/master');result={'master':base,'prs':{}}
for n in (372,373,374,377):
 ref=git('rev-parse',f'origin/reconcile-{n}');mb=git('merge-base',base,ref)
 files=git('diff','--name-only',mb,ref).splitlines()
 result['prs'][str(n)]={'head':ref,'merge_base':mb,'head_ancestor_master':ancestor(ref,base),'unique_commits':git('log','--oneline',base+'..'+ref),'patch_equivalence':git('cherry',base,ref),'files':[]}
 for f in files:
  def blob(r):
   p=subprocess.run(['git','rev-parse',r+':'+f],cwd=R,text=True,capture_output=True)
   return p.stdout.strip() if p.returncode==0 else None
  a,b=blob(base),blob(ref)
  result['prs'][str(n)]['files'].append({'path':f,'master_blob':a,'pr_blob':b,'identical':a==b})
result['same_tree_372_373']=git('rev-parse','origin/reconcile-372^{tree}')==git('rev-parse','origin/reconcile-373^{tree}')
result['ancestry_pairs']={f'{a}->{b}':ancestor(f'origin/reconcile-{a}',f'origin/reconcile-{b}') for a in (372,373,374) for b in (372,373,374) if a!=b}
# Extract snapshots only to evidence-local scratch; never save a loaded board.
scratch=R/'.reconcile-snapshots';scratch.mkdir(exist_ok=True)
geometry={};sets={}
for label,ref in [('master',base),('operator','7129c584'),('372','origin/reconcile-372'),('373','origin/reconcile-373'),('374','origin/reconcile-374')]:
 raw=subprocess.check_output(['git','show',ref+':'+board],cwd=R);p=scratch/(label+'.kicad_pcb');p.write_bytes(raw)
 b=k.LoadBoard(str(p));layers={name:{'tracks':0,'length_mm':0.0,'nets':collections.Counter(),'zones':[]} for name in ['F.Cu','In1.Cu','In2.Cu','B.Cu']};geom=[];vias=0
 for t in b.GetTracks():
  if isinstance(t,k.PCB_VIA):
   vias+=1;geom.append(('via',t.GetNetname(),t.GetPosition().x,t.GetPosition().y,t.GetWidth(t.TopLayer()),t.GetDrillValue(),t.TopLayer(),t.BottomLayer()));continue
  name=b.GetLayerName(t.GetLayer());d=layers[name];d['tracks']+=1;d['length_mm']+=t.GetLength()/1e6;d['nets'][t.GetNetname()]+=1
  ends=sorted([(t.GetStart().x,t.GetStart().y),(t.GetEnd().x,t.GetEnd().y)])
  geom.append(('track',t.GetNetname(),name,*ends,t.GetWidth()))
 for z in b.Zones():
  for name,d in layers.items():
   if z.IsOnLayer(b.GetLayerID(name)):d['zones'].append({'net':z.GetNetname(),'uuid':z.m_Uuid.AsString(),'filled':z.IsFilled()})
 for d in layers.values():d['length_mm']=round(d['length_mm'],6)
 sets[label]=set(map(str,geom));geometry[label]={'sha256':hashlib.sha256(raw).hexdigest(),'vias':vias,'layers':layers,'track_via_geometry_sha256':hashlib.sha256('\n'.join(sorted(sets[label])).encode()).hexdigest()}
result['geometry']=geometry
result['geometry_comparison_to_master']={label:{'only_snapshot':len(s-sets['master']),'only_master':len(sets['master']-s)} for label,s in sets.items() if label!='master'}
(O/'evidence.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'master':base,'geometry_comparison':result['geometry_comparison_to_master'],'layers':geometry['master'],'same_tree_372_373':result['same_tree_372_373']},indent=2))
