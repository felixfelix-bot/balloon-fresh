#!/usr/bin/python3
"""Layer-aware copper polygons, split zone islands, UUID endpoints and path witnesses.
KiCad polygon conversion handles rotations/custom pads/arcs. 1 nm contact tolerance;
polygon approximation 1 um. Opposite-face SMD never joins merely by XY overlap.
"""
import pcbnew as k, json, pathlib, collections, hashlib
from shapely.geometry import Polygon, Point
from shapely.strtree import STRtree
R=pathlib.Path.cwd(); O=R/'docs/analysis/hub-endpoint-audit-20261030'
b=k.LoadBoard(str(R/'.audit-hub-copy/hub_board_v10_lora1280_7of9.kicad_pcb'))
layers=list(b.GetEnabledLayers().CuStack()); nodes=[]; geometries=[]; objects={}; byuuid=collections.defaultdict(list)
def pts(c): return [(c.CPoint(i).x/1e6,c.CPoint(i).y/1e6) for i in range(c.PointCount())]
def polys(s):
 for i in range(s.OutlineCount()):
  p=Polygon(pts(s.COutline(i)),[pts(s.CHole(i,j)) for j in range(s.HoleCount(i))])
  if not p.is_valid: p=p.buffer(0)
  yield p
items=list(b.GetPads())+list(b.GetTracks())+list(b.Zones())+list(b.GetDrawings())
for f in b.GetFootprints(): items+=list(f.GraphicalItems())
for obj in items:
 if not hasattr(obj,'GetNetname'): continue
 uid=str(obj.m_Uuid.AsString()); objects[uid]=obj
 for layer in layers:
  if not obj.IsOnLayer(layer): continue
  if isinstance(obj,k.ZONE): pp=list(polys(obj.GetFilledPolysList(layer)))
  else:
   s=k.SHAPE_POLY_SET()
   try: obj.TransformShapeToPolygon(s,layer,0,1000,k.ERROR_INSIDE)
   except (TypeError,AttributeError): continue
   pp=list(polys(s))
  for island,p in enumerate(pp):
   if p.is_empty: continue
   n=dict(id=len(nodes),uuid=uid,kind=obj.GetClass(),net=obj.GetNetname(),layer=b.GetLayerName(layer),island=island)
   if isinstance(obj,k.PAD): n.update(ref=obj.GetParentFootprint().GetReference(),pad=obj.GetNumber(),attribute=obj.GetAttribute())
   nodes.append(n); geometries.append(p); byuuid[uid].append(n['id'])
adj=[set() for _ in nodes]
def join(i,j): adj[i].add(j);adj[j].add(i)
# Same-layer copper overlaps only on the same assigned net; netless shapes are
# inventoried, not assumed to bridge named nets. This limitation is surfaced.
groups=collections.defaultdict(list)
for n in nodes: groups[n['layer'],n['net']].append(n['id'])
for ids in groups.values():
 tree=STRtree([geometries[i] for i in ids])
 for i in ids:
  for jj in tree.query(geometries[i].buffer(0.000001)):
   j=ids[int(jj)]
   if j>i and geometries[i].distance(geometries[j])<=0.000001: join(i,j)
# Only plated hole/barrel nodes join layers. Distinct zone islands stay distinct.
for uid,ids in byuuid.items():
 obj=objects[uid]
 if isinstance(obj,k.PCB_VIA) or (isinstance(obj,k.PAD) and obj.GetAttribute()==k.PAD_ATTRIB_PTH):
  for j in ids[1:]: join(ids[0],j)
comp={}; components=[]
for i in range(len(nodes)):
 if i in comp: continue
 cid=len(components); stack=[i]; members=[];comp[i]=cid
 while stack:
  u=stack.pop(); members.append(u)
  for v in adj[u]:
   if v not in comp: comp[v]=cid;stack.append(v)
 components.append(dict(id=cid,net=nodes[i]['net'],nodes=sorted(members)))
for n in nodes: n['component']=comp[n['id']]
def endpoint(item):
 ids=byuuid.get(item['uuid'],[]); pos=Point(item['pos']['x'],item['pos']['y'])
 # DRC zone UUID can name many islands: select the island at the reported point.
 if ids and isinstance(objects[item['uuid']],k.ZONE): ids=[i for i in ids if geometries[i].distance(pos)<0.002]
 all_ids=byuuid.get(item['uuid'],[])
 obj=objects.get(item['uuid'])
 return dict(**item,node_ids=ids,components=sorted(set(comp[i] for i in ids)),candidate_components=sorted(set(comp[i] for i in all_ids)),nets=[obj.GetNetname()] if obj is not None else [],attribution='island unresolved: DRC reports zone outline anchor rather than island location' if all_ids and not ids else 'resolved')
d=json.loads((O/'drc.json').read_text()); ledger=[]
for idx,row in enumerate(d['unconnected_items'],1):
 ends=[endpoint(x) for x in row['items']]; nets=sorted(set(n for e in ends for n in e['nets']))
 separated=len(ends)==2 and all(e['components'] for e in ends) and not(set(ends[0]['components'])&set(ends[1]['components']))
 ledger.append(dict(id=idx,nets=nets,endpoints=ends,classification='real' if separated else 'unresolved',reason='DRC missing connection and distinct layer-aware copper components; no intentional waiver established' if separated else 'DRC missing connection; polygon component attribution needs adjudication'))
proof=[]
for n in nodes:
 if n.get('ref')!='U_LORA1280' or n['net'] in ('','GND','+3V3'): continue
 candidates=[x for x in nodes if x.get('ref')=='U1' and x['net']==n['net']]
 targets={x['id'] for x in candidates}; q=collections.deque([n['id']]); prev={n['id']:None}; found=None
 while q:
  u=q.popleft()
  if u in targets: found=u;break
  for v in adj[u]:
   if v not in prev: prev[v]=u;q.append(v)
 path=[]
 while found is not None: path.append(found);found=prev[found]
 proof.append(dict(net=n['net'],module_pad=n['pad'],module_uuid=n['uuid'],U1_candidates=[dict(pad=x['pad'],uuid=x['uuid'],component=x['component']) for x in candidates],connected=bool(path),path_nodes=list(reversed(path))))
summary=dict(drc_classes=dict(collections.Counter(x['type'] for x in d['violations'])),records=len(ledger),classification=dict(collections.Counter(x['classification'] for x in ledger)),by_net=dict(collections.Counter(n for x in ledger for n in x['nets'])),radio_proven=sum(p['connected'] for p in proof),radio_total=len(proof),copper_graphics=[n for n in nodes if n['kind']=='PCB_SHAPE'],geometry_method='KiCad polygons, 1um approximation / 1nm contact; PTH/via layer span only; netless graphics not used to bridge named nets')
for name,data in [('ledger',ledger),('connectivity',dict(nodes=nodes,components=components,edges=[[i,j] for i,a in enumerate(adj) for j in a if i<j])),('radio-paths',proof),('summary',summary)]: (O/(name+'.json')).write_text(json.dumps(data,indent=2))
print(json.dumps(summary,indent=2)); print(json.dumps(proof,indent=2))
