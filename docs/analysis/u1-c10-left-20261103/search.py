#!/usr/bin/python3
"""Bounded local grid search; native DRC is final authority, not geometric screening."""
from pathlib import Path
import pcbnew as p, shapely, json, hashlib, shutil, signal, time, heapq, math, subprocess, sys
from shapely.geometry import Polygon,Point,LineString,box
from shapely.ops import unary_union
import numpy as np
O=Path(__file__).parent; AB={'1ff5869f-6f46-4150-8373-c567dd3e9ac7','da354532-2da3-493b-ab31-1ff70243289f'}
def xy(v):return(v.x/1e6,v.y/1e6)
def geom(ps):
 def co(c):return [xy(v) for v in c.CPoints()]
 return unary_union([Polygon(co(ps.COutline(i)),[co(ps.CHole(i,j)) for j in range(ps.HoleCount(i))]) for i in range(ps.OutlineCount())])
def items(b):
 out=[]
 for q in [q for f in b.GetFootprints() for q in f.Pads()]+list(b.GetTracks())+[g for g in b.GetDrawings() if hasattr(g,'GetNetname')]:
  for l in q.GetLayerSet().CuStack():
   if b.IsLayerEnabled(l):
    ps=p.SHAPE_POLY_SET();q.TransformShapeToPolygon(ps,l,0,100,p.ERROR_OUTSIDE);out.append((q,l,geom(ps)))
 return out
def track(b,pts,net):
 for a,c in zip(pts,pts[1:]):
  if a==c:continue
  t=p.PCB_TRACK(b);t.SetStart(p.VECTOR2I(round(a[0]*1e6),round(a[1]*1e6)));t.SetEnd(p.VECTOR2I(round(c[0]*1e6),round(c[1]*1e6)));t.SetWidth(200000);t.SetLayer(0);t.SetNetCode(net);b.Add(t)
def path(start,end,free):
 # Fixed absolute 0.05 mm grid, bounded local area. Exact endpoint edges checked.
 step=.05; xmin,ymin,xmax,ymax=6,39,12,46
 def pos(n):return(xmin+n[0]*step,ymin+n[1]*step)
 def node(pt):return(round((pt[0]-xmin)/step),round((pt[1]-ymin)/step))
 xs=np.arange(xmin,xmax+step/2,step);ys=np.arange(ymin,ymax+step/2,step);xx,yy=np.meshgrid(xs,ys,indexing='ij'); legal=shapely.contains_xy(free,xx,yy)
 s,t=node(start),node(end)
 def link(a,b):return Point(a) if math.dist(a,b)<1e-9 else LineString([a,b])
 if not free.covers(link(start,pos(s))) or not free.covers(link(pos(t),end)):return None
 legal[s]=True;legal[t]=True
 dist={s:0};prev={};h=[(math.dist(s,t),0,s)];done=set()
 while h:
  _,cost,u=heapq.heappop(h)
  if u in done:continue
  done.add(u)
  if u==t:
   rev=[u]
   while rev[-1]!=s:rev.append(prev[rev[-1]])
   pts=[start]+[pos(n) for n in reversed(rev)]+[end]
   # Greedy string-pull within exact screened free region.
   result=[pts[0]];i=0
   while i<len(pts)-1:
    j=len(pts)-1
    while j>i+1 and not free.covers(LineString([pts[i],pts[j]])):j-=1
    result.append(pts[j]);i=j
   return result
  for dx,dy in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]:
   v=(u[0]+dx,u[1]+dy)
   if not (0<=v[0]<len(xs) and 0<=v[1]<len(ys)) or not legal[v] or v in done:continue
   nc=cost+math.hypot(dx,dy)
   if nc<dist.get(v,1e99) and free.covers(LineString([pos(u),pos(v)])):
    dist[v]=nc;prev[v]=u;heapq.heappush(h,(nc+math.dist(v,t),nc,v))
 return None
def run(n):
 signal.alarm(180); d=O/f'trial-{n:02d}';d.mkdir(exist_ok=True);b=p.LoadBoard(str(O/'baseline/board.kicad_pcb'));log={'trial':n,'deadline_seconds':180,'grid_mm':.05,'stages':[]};(d/'progress.json').write_text(json.dumps(log))
 for q in list(b.GetTracks()):
  if q.m_Uuid.AsString() in AB:b.Delete(q)
 pads={f.GetReference()+'.'+q.GetNumber():q for f in b.GetFootprints() for q in f.Pads()}
 net=pads['U1.9'].GetNetCode();obs=items(b);free=box(6,39,12,46).difference(unary_union([g.buffer(.3002) for q,l,g in obs if l==0 and q.GetNetCode()!=net]))
 waypoint=(8.75-[.4,.8,1.2][n-1],42.5)
 p1=path((8.75,41.25),waypoint,free);p2=path(waypoint,(11.05,44.05),free)
 log['stages'].append({'net':'MISO','waypoint':waypoint,'paths':[p1,p2]})
 if p1 and p2:track(b,p1+p2[1:],net)
 else:
  # Save the rejected open-rip witness, never label as a routing candidate.
  log['stopped']='No MISO path via constrained left waypoint; C10 not attempted because joint prerequisite failed'
 if p1 and p2:
  for label in ['C10.1','C10.2']:
   pad=pads[label];net=pad.GetNetCode();obs=items(b);foreign=[(q,l,g) for q,l,g in obs if q.GetNetCode()!=net]
   free=box(6,39,12,46).difference(unary_union([g.buffer(.3002) for q,l,g in foreign if l==0]))
   # Via envelopes across ALL enabled copper layers; exclude ALL pads even same-net (no via-in-pad).
   forbidden=unary_union([g.buffer(.5002) for q,l,g in foreign]+[g.buffer(.3002) for q,l,g in obs if isinstance(q,p.PAD)])
   options=[]
   for x in np.arange(8,10.01,.1):
    for y in np.arange(40.5,44.01,.1):
     pt=(round(float(x),3),round(float(y),3))
     if not forbidden.intersects(Point(pt)) and free.contains(Point(pt)):options.append(pt)
   options.sort(key=lambda pt:math.dist(pt,xy(pad.GetPosition())))
   found=None
   for pt in options[:40]:
    route=path(xy(pad.GetPosition()),pt,free)
    if route:found=(pt,route);break
   log['stages'].append({'net':label,'legal_screen_sites':len(options),'chosen':found})
   if found:
    pt,route=found;track(b,route,net);v=p.PCB_VIA(b);v.SetPosition(p.VECTOR2I(round(pt[0]*1e6),round(pt[1]*1e6)));v.SetWidth(600000);v.SetDrill(300000);v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(net);b.Add(v)
   else:log['stopped']='No off-pad via+stub found for '+label;break
 for ext in ['kicad_pro','kicad_dru']:shutil.copy2(O/'input'/f'board.{ext}',d/f'board.{ext}')
 filler=p.ZONE_FILLER(b);log['refill_ok']=bool(filler.Fill(b.Zones()));p.SaveBoard(str(d/'board.kicad_pcb'),b)
 for ext in ['kicad_pro','kicad_dru']:assert (d/f'board.{ext}').read_bytes()==(O/'input'/f'board.{ext}').read_bytes()
 log['sha256']=hashlib.sha256((d/'board.kicad_pcb').read_bytes()).hexdigest();(d/'result.json').write_text(json.dumps(log,indent=2));print(json.dumps(log))
if __name__=='__main__':run(int(sys.argv[1]))
