#!/usr/bin/python3
"""Read-only saved-copper audit. No refill, no board save. Exit 2 on crosscheck failure."""
import argparse, collections, hashlib, html, json, subprocess
from pathlib import Path
import pcbnew as p
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union

def uid(q): return q.m_Uuid.AsString()
def geom(ps):
    def co(c): return [(v.x/1e6,v.y/1e6) for v in c.CPoints()]
    return unary_union([Polygon(co(ps.COutline(i)),[co(ps.CHole(i,j)) for j in range(ps.HoleCount(i))]) for i in range(ps.OutlineCount())])
def components(adj):
    remaining=set(adj); out=[]
    while remaining:
        seen={min(remaining)}; stack=list(seen)
        while stack:
            for k in adj[stack.pop()]-seen: seen.add(k); stack.append(k)
        remaining-=seen; out.append(seen)
    return sorted(out,key=lambda s:min(s))
def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('board',type=Path); ap.add_argument('output',type=Path); ap.add_argument('--label',default='saved board'); a=ap.parse_args()
    a.output.mkdir(parents=True,exist_ok=True); before=hashlib.sha256(a.board.read_bytes()).hexdigest()
    b=p.LoadBoard(str(a.board)); assert b
    pads={f.GetReference()+'.'+q.GetNumber():q for f in b.GetFootprints() for q in f.Pads()}
    pairs=[('C10.1','U1.2'),('C10.2','U7.2')]; wanted={pads[x].GetNetname() for pair in pairs for x in pair}|{pads['U1.9'].GetNetname()}
    nodes={}; gs={}; shapes={}; objs={}
    items=[q for f in b.GetFootprints() for q in f.Pads()]+list(b.GetTracks())
    items+= [q for q in list(b.GetDrawings())+[g for f in b.GetFootprints() for g in f.GraphicalItems()] if hasattr(q,'GetNetname')]
    for q in items:
        if isinstance(q,p.PAD) and q.GetAttribute()==p.PAD_ATTRIB_NPTH: continue
        for l in q.GetLayerSet().CuStack():
            if not b.IsLayerEnabled(l): continue
            ps=p.SHAPE_POLY_SET(); q.TransformShapeToPolygon(ps,l,0,100,p.ERROR_INSIDE)
            g=geom(ps)
            if g.is_empty: continue
            k=f'{uid(q)}:{l}'; objs[uid(q)]=q
            nodes[k]={'uuid':uid(q),'layer':l,'net':q.GetNetname(),'name':q.GetParentFootprint().GetReference()+'.'+q.GetNumber() if isinstance(q,p.PAD) else uid(q),'type':type(q).__name__}
            gs[k]=g; shapes[k]=q.GetEffectivePolygon(l) if isinstance(q,p.PAD) else q.GetEffectiveShape(l)
    for z in b.Zones():
        for l in z.GetLayerSet().CuStack():
            ps=z.GetFilledPolysList(l)
            for i in range(ps.OutlineCount()):
                k=f'{uid(z)}:{l}:poly{i}'; shapes[k]=ps.UnitSet(i); gs[k]=geom(shapes[k]); nodes[k]={'uuid':uid(z),'layer':l,'net':z.GetNetname(),'name':k,'type':'polygon','outline':i}
    keys=[k for k in nodes if nodes[k]['net'] in wanted]; adj={k:set() for k in keys}; approx={k:set() for k in keys}; edges=[]; disagreements=[]
    def edge(graph,x,y): graph[x].add(y); graph[y].add(x)
    for i,x in enumerate(keys):
        for y in keys[i+1:]:
            nx,ny=nodes[x],nodes[y]
            if nx['net']!=ny['net']: continue
            if nx['layer']!=ny['layer']:
                if nx['uuid']==ny['uuid'] and nx['type']!='polygon':
                    q=objs[nx['uuid']]
                    if isinstance(q,p.PCB_VIA) or isinstance(q,p.PAD) and q.GetAttribute()==p.PAD_ATTRIB_PTH:
                        edge(adj,x,y); edge(approx,x,y); edges.append([x,y,'plated barrel'])
                continue
            native=bool(shapes[x].Collide(shapes[y],0)); geometric=gs[x].intersects(gs[y])
            if native: edge(adj,x,y); edges.append([x,y,'native copper collision'])
            if geometric: edge(approx,x,y)
            if native!=geometric: disagreements.append({'a':x,'b':y,'native':native,'polygon':geometric,'gap_mm':gs[x].distance(gs[y])})
    parts=components(adj); parts2=components(approx); failures=[]
    if {frozenset(c) for c in parts}!={frozenset(c) for c in parts2}: failures.append('Native collision and polygonized component partitions disagree')
    # Native DRC's per-net spanning forest must have components-1 opens.
    drc=a.output/'native-drc.json'
    run=subprocess.run(['kicad-cli','pcb','drc','--format','json','--severity-all','--output',str(drc),str(a.board)],capture_output=True,text=True)
    (a.output/'native-drc.log').write_text(run.stdout+run.stderr)
    if run.returncode: failures.append('Native DRC failed')
    counts=collections.Counter(); unknown=[]
    if drc.exists():
        report=json.loads(drc.read_text()); uuidnets=collections.defaultdict(set)
        for n in nodes.values(): uuidnets[n['uuid']].add(n['net'])
        for rec in report.get('unconnected_items',[]):
            nets=set().union(*(uuidnets.get(it.get('uuid'),set()) for it in rec['items']))
            if len(nets)==1: counts[next(iter(nets))]+=1
            else: unknown.append(rec)
    checks={}
    for net in wanted:
        count=sum(nodes[next(iter(c))]['net']==net for c in parts)
        checks[net]={'components':count,'native_unconnected_records':counts[net],'expected_unconnected':count-1}
        if count-1!=counts[net]: failures.append('Native per-net count mismatch: '+net)
    if unknown: failures.append('Unresolved native DRC unconnected record identities')
    membership={k:i for i,c in enumerate(parts) for k in c}
    def padkeys(name): return [k for k in keys if nodes[k]['name']==name]
    results=[]
    for src,dst in pairs:
        ss,tt=padkeys(src),padkeys(dst); assert ss and tt
        results.append({'from':src,'to':dst,'same_net':nodes[ss[0]]['net']==nodes[tt[0]]['net'],'connected':membership[ss[0]]==membership[tt[0]],'source_component':membership[ss[0]],'target_component':membership[tt[0]]})
    misonet=pads['U1.9'].GetNetname(); point=Point(8.75,41.25)
    hits=[k for k in keys if nodes[k]['net']==misonet and gs[k].distance(point)<=0.000001]
    if not hits: failures.append('No MISO copper at external endpoint')
    roots={membership[k] for k in hits}
    if len(roots)>1: failures.append('External MISO point ambiguous across layers')
    results.append({'from':'external (8.75,41.25)','to':'U1.9','endpoint_copper_nodes':hits,'connected':bool(hits) and membership[padkeys('U1.9')[0]] in roots})
    result={'board':str(a.board.resolve()),'sha256':before,'label':a.label,'checks':checks,'failures':failures,'valid':not failures,'pairs':results if not failures else [],'provisional_pairs':results if failures else [],'components':[sorted(c) for c in parts],'nodes':nodes,'edges':edges,'collision_disagreements':disagreements,'limitations':['Saved filled copper only; no refill or fabrication/DRC-clean assertion.','Per-polygon geometric connectivity, crosschecked against native collisions and per-net DRC totals; native polygon membership API unavailable.','Polygon render approximation <=0.0001 mm; native pad effective polygon used for collision.','Copper drill removal and fabrication-process reliability not independently modeled.']}
    (a.output/'audit.json').write_text(json.dumps(result,indent=2))
    assert before==hashlib.sha256(a.board.read_bytes()).hexdigest(),'INPUT CHANGED'
    if failures:
        print(json.dumps({'valid':False,'failures':failures,'checks':checks},indent=2)); return 2
    # Layer-separated measured copper, same fixed crop for before/after comparison.
    centers={name:(q.GetPosition().x/1e6,q.GetPosition().y/1e6) for name,q in pads.items() if name in ['C10.1','C10.2','U1.2','U1.9','U7.2']}
    xmin=min(6.5,min(x for x,y in centers.values())-2); xmax=max(19,min(x for x,y in centers.values())+2,max(x for x,y in centers.values())+2)
    ymin=min(36,min(y for x,y in centers.values())-2); ymax=max(45,max(y for x,y in centers.values())+2)
    colors={pads['C10.1'].GetNetname():'#df9216',pads['C10.2'].GetNetname():'#24a889',misonet:'#ce509d'}
    scale=65; W=(xmax-xmin)*scale; H=(ymax-ymin)*scale
    for l in sorted({n['layer'] for n in nodes.values()}):
        svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W+40}" height="{H+100}" viewBox="0 0 {W+40} {H+100}"><rect width="100%" height="100%" fill="white"/>',f'<text x="20" y="22" font-size="16">{html.escape(a.label)} — {b.GetLayerName(l)} — {before[:12]}</text>',f'<g transform="translate(20,50) scale({scale}) translate({-xmin},{-ymin})">']
        svg.append(f'<clipPath id="crop"><rect x="{xmin}" y="{ymin}" width="{xmax-xmin}" height="{ymax-ymin}"/></clipPath><g clip-path="url(#crop)">')
        for k,g in gs.items():
            if nodes[k]['layer']!=l: continue
            polys=list(g.geoms) if hasattr(g,'geoms') else [g]
            for poly in polys:
                if poly.geom_type!='Polygon': continue
                path=' '.join('M '+' L '.join(f'{x},{y}' for x,y in ring.coords)+' Z' for ring in [poly.exterior]+list(poly.interiors))
                svg.append(f'<path d="{path}" fill="{colors.get(nodes[k]["net"],"#a8afb8")}" fill-opacity="{0.35 if nodes[k]["type"]=="polygon" else 0.9}" fill-rule="evenodd"/>')
        svg.append('</g>')
        for i,(name,(x,y)) in enumerate(centers.items()):
            right=x>(xmin+xmax)/2; tx=x+(-0.8 if right else 0.8); ty=y+(-0.9 if i%2 else 0.9)
            anchor='end' if right else 'start'
            svg.append(f'<path d="M{x},{y} L{tx},{ty}" stroke="#101010" stroke-width="0.018"/><text x="{tx}" y="{ty}" text-anchor="{anchor}" font-size="0.24" stroke="white" stroke-width="0.065" paint-order="stroke">{name} ({x:.3f},{y:.3f})</text>')
        svg.append('<circle cx="8.75" cy="41.25" r="0.18" fill="none" stroke="black" stroke-width="0.025"/><text x="6.7" y="40.8" font-size="0.2">MISO external (8.75,41.25)</text>')
        svg.append(f'</g><text x="20" y="{H+75}" font-size="12">Amber +3V3 | Green GND | Magenta MISO | Grey other copper; mm; saved fill; not fab approval</text></svg>')
        path=a.output/(b.GetLayerName(l)+'.svg'); path.write_text('\n'.join(svg)); subprocess.run(['rsvg-convert',str(path),'-o',str(path.with_suffix('.png'))],check=True)
    print(json.dumps({'valid':True,'pairs':results,'checks':checks,'output':str(a.output)},indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
