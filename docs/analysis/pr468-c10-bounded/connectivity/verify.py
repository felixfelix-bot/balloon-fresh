#!/usr/bin/python3
"""Read-only actual copper graph, native polygons at 1nm tessellation, 3nm contact allowance.
Same-net graph (shorts are independently a native DRC concern). No netname-only edges.
"""
import sys,json,hashlib,pathlib,collections,itertools
import pcbnew as k
from shapely.geometry import Point
import graph_kernel as g
root=pathlib.Path(__file__).parent.parent
out={}
for name in sys.argv[1:] or ['before','after']:
 p=root/name/'board.kicad_pcb'; before=hashlib.sha256(p.read_bytes()).hexdigest()
 b=k.LoadBoard(str(p)); g.CU_LAYERS=[b.GetLayerName(l) for l in b.GetEnabledLayers().Seq() if b.GetLayerName(l).endswith('.Cu')]
 # This kernel only enumerates single-layer zone objects. Explicitly refuse others.
 for z in b.Zones():
  if not z.GetIsRuleArea():
   assert len([l for l in z.GetLayerSet().Seq() if b.GetLayerName(l).endswith('.Cu')])==1,'multilayer zone unsupported'
 items,nodes,byitem,comps,roots,ci,_=g.build_copper_graph(b,contact_tolerance=0.000003)
 counts=collections.Counter(items[v[0]]['net'] for v in comps.values())
 pads={it['meta']['uuid']:{'label':it['meta']['ref']+'.'+it['meta']['num'],'net':it['net'],'component':ci[it['id']]} for it in items if it['kind']=='pad'}
 def pad(label):
  return [it['id'] for it in items if it['kind']=='pad' and it['meta']['ref']+'.'+it['meta']['num']==label]
 def target(a,z):
  aa=pad(a) if isinstance(a,str) else sorted(set(i for i,l,geom in nodes if geom.distance(Point(*a))<=0.000003 and 'MISO' in items[i]['net']))
  zz=pad(z)
  return {'a':a,'b':z,'a_items':aa,'b_items':zz,'connected':bool(aa and zz and any(ci[x]==ci[y] for x in aa for y in zz)),'a_components':[ci[x] for x in aa],'b_components':[ci[y] for y in zz]}
 b.BuildConnectivity()
 result={'sha256':before,'tolerance_mm':0.000003,'item_counts':dict(collections.Counter(it['kind'] for it in items)), 'net_component_counts':dict(counts),'component_deficit':sum(v-1 for v in counts.values()),'native_GetUnconnectedCount':b.GetConnectivity().GetUnconnectedCount(False),'targets':[target((8.75,41.25),'U1.9'),target('C10.1','U1.2'),target('C10.2','U7.2')],'pads':pads,'items':items,'components':dict(comps)}
 assert hashlib.sha256(p.read_bytes()).hexdigest()==before
 (root/'connectivity'/f'{pathlib.Path(name).name}.json').write_text(json.dumps(result,indent=2))
 out[name]=result
 print(name,json.dumps({a:result[a] for a in ['item_counts','component_deficit','native_GetUnconnectedCount','targets']}),flush=True)
if len(out)==2:
 names=list(out); a,c=[out[n]['pads'] for n in names]; common=set(a)&set(c)
 broken=[]; joined=[]
 for x,y in itertools.combinations(sorted(common),2):
  was=a[x]['component']==a[y]['component']; now=c[x]['component']==c[y]['component']
  if was and not now: broken.append([a[x]['label'],a[y]['label'],a[x]['net'],x,y])
  if now and not was: joined.append([a[x]['label'],a[y]['label'],a[x]['net'],x,y])
 result={'states':names,'common_pad_count':len(common),'removed_pad_uuids':list(set(a)-set(c)),'added_pad_uuids':list(set(c)-set(a)),'broken_pairs':broken,'joined_pairs':joined}
 (root/'connectivity'/('partition-'+ '-'.join(pathlib.Path(n).name for n in names)+'.json')).write_text(json.dumps(result,indent=2))
 print('partition',len(common),'broken',len(broken),'joined',len(joined),flush=True)
