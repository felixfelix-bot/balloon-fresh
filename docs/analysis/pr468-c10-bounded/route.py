#!/usr/bin/python3
import sys,pathlib,shutil,json,time,heapq,math,collections
import pcbnew as k
from shapely.geometry import Point,LineString,box
from shapely.ops import unary_union
from shapely.prepared import prep
sys.path.insert(0,'/home/c08r4d0r/reports/pr468-verification-853f648c/connectivity')
import graph_kernel as g
ROOT=pathlib.Path(__file__).parent
SRC=pathlib.Path('/home/c08r4d0r/reports/pr468-verification-853f648c/connectivity/refilled-after')
DST=ROOT/'candidate'
shutil.copytree(SRC,DST)
b=k.LoadBoard(str(DST/'board.kicad_pcb'))
g.CU_LAYERS=[b.GetLayerName(l) for l in b.GetEnabledLayers().Seq() if b.GetLayerName(l).endswith('.Cu')]
report={'source':str(SRC),'grid_mm':0.1,'track_mm':0.2,'via_mm':[0.6,0.3],'routes':[]}
def graph(): return g.build_copper_graph(b,contact_tolerance=0.000003)
def pos(p): return (g.mm(p.GetPosition().x),g.mm(p.GetPosition().y))
def vec(p): return k.VECTOR2I(round(p[0]*1e6),round(p[1]*1e6))
def route(startlabel,targetlabel,landinglayer):
 started=time.monotonic(); items,nodes,byitem,comps,roots,ci,netless=graph()
 def pid(label): return next(i['id'] for i in items if i['kind']=='pad' and i['meta']['ref']+'.'+i['meta']['num']==label)
 sid,tid=pid(startlabel),pid(targetlabel); net=items[sid]['netcode']
 pad=next(p for f in b.GetFootprints() for p in f.Pads() if f.GetReference()+'.'+p.GetNumber()==startlabel)
 start=pos(pad); roi=Point(start).buffer(4).envelope
 # Hard geometry includes net-bearing graphics from frozen kernel. Filled foreign zones retreat on refill.
 hard={lay:[] for lay in g.CU_LAYERS}; pads=[]; holes=[]
 for i,lay,geom in nodes:
  if items[i]['kind']=='pad': pads.append(geom)
  if items[i]['kind']!='island' and items[i]['netcode']!=net and geom.intersects(roi.buffer(1)):
   hard[lay].append(geom)
 for p,geom,drill,layers in netless:
  pads.append(geom)
  for lay in layers: hard[lay].append(geom)
 for t in b.GetTracks():
  if isinstance(t,k.PCB_VIA): holes.append(g.hole_poly(t))
  if t.GetNetCode()<=0:
   for lay in g.CU_LAYERS:
    if t.IsOnLayer(b.GetLayerID(lay)): hard[lay].append(g.native_copper(t,b.GetLayerID(lay)))
 for f in b.GetFootprints():
  for p in f.Pads():
   if max(p.GetDrillSize().x,p.GetDrillSize().y)>0: holes.append(g.hole_poly(p))
 for d in list(b.GetDrawings())+[d for f in b.GetFootprints() for d in f.GraphicalItems()]:
  lay=b.GetLayerName(d.GetLayer())
  if lay in hard and d.GetNetCode()<=0: hard[lay].append(g.drawing_poly(d))
 edge=unary_union(g.edge_segments(b))
 # Conservative .5 edge gate, .25 drill-to-drill, no overlap even same-net pads.
 via_block=unary_union([x.buffer(.501) for xs in hard.values() for x in xs]+[x.buffer(.301) for x in pads]+[x.buffer(.401) for x in holes]+[edge.buffer(.801)])
 track_block=unary_union([x.buffer(.301) for x in hard['F.Cu']]+[edge.buffer(.601)])
 vb,tb=prep(via_block),prep(track_block)
 landing=unary_union([geom for i,lay,geom in nodes if ci[i]==ci[tid] and lay==landinglayer])
 # Must overlap annulus, not just have netname. Need robust contact >10um.
 land=prep(landing.buffer(.28))
 N=40; step=.1
 def xy(v): return (round(start[0]+v[0]*step,6),round(start[1]+v[1]*step,6))
 q=[(0,(0,0))]; dist={(0,0):0}; prev={}; seen=set(); found=None
 moves=[(x,y) for x in [-1,0,1] for y in [-1,0,1] if x or y]
 while q and time.monotonic()-started<90:
  cost,v=heapq.heappop(q)
  if v in seen: continue
  seen.add(v); p=Point(xy(v))
  if land.intersects(p) and not vb.intersects(p): found=v;break
  for dx,dy in moves:
   w=(v[0]+dx,v[1]+dy)
   if max(abs(w[0]),abs(w[1]))>N or w in seen: continue
   nc=cost+math.hypot(dx,dy)*step
   if nc>=dist.get(w,1e99):continue
   if tb.intersects(LineString([xy(v),xy(w)])):continue
   dist[w]=nc;prev[w]=v;heapq.heappush(q,(nc,w))
 r={'start':startlabel,'target':targetlabel,'landing_layer':landinglayer,'visited':len(seen),'seconds':time.monotonic()-started,'success':found is not None}
 if found is None: report['routes'].append(r);return
 path=[found]
 while path[-1]!=(0,0):path.append(prev[path[-1]])
 path.reverse(); simple=[path[0]]
 for j in range(1,len(path)-1):
  a,c,d=path[j-1],path[j],path[j+1]
  if (c[0]-a[0],c[1]-a[1])!=(d[0]-c[0],d[1]-c[1]): simple.append(c)
 simple.append(path[-1]); coords=[xy(v) for v in simple]
 for a,z in zip(coords,coords[1:]):
  t=k.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(k.FromMM(.2));t.SetLayer(k.F_Cu);t.SetNetCode(net);b.Add(t)
 v=k.PCB_VIA(b);v.SetPosition(vec(coords[-1]));v.SetWidth(k.FromMM(.6));v.SetDrill(k.FromMM(.3));v.SetViaType(k.VIATYPE_THROUGH);v.SetLayerPair(k.F_Cu,k.B_Cu);v.SetNetCode(net);b.Add(v)
 r.update(path_mm=coords,via_mm=coords[-1],via_uuid=v.m_Uuid.AsString());report['routes'].append(r)
# Route U1 rail onto existing C10 In1 copper, rather than incorrectly ending an inner trace at an SMD pad.
route('U1.2','C10.1','In1.Cu')
route('C10.2','U7.2','B.Cu')
k.SaveBoard(str(DST/'board.kicad_pcb'),b)
shutil.copyfile(DST/'board.kicad_pcb',ROOT/'before-refill.kicad_pcb')
k.ZONE_FILLER(b).Fill(b.Zones());k.SaveBoard(str(DST/'board.kicad_pcb'),b)
(ROOT/'search.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2),flush=True)
