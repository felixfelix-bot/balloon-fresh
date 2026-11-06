#!/home/c08r4d0r/venvs/kicad/bin/python
"""Immutable-original hard-copper comparison; excludes all zone fills intentionally."""
from pathlib import Path
import sys,json,hashlib,math,html,subprocess,xml.etree.ElementTree as ET
import pcbnew
sys.path.insert(0,'/home/c08r4d0r/.hermes/profiles/manager/skills/firmware/kicad-board-audit-rules/scripts')
import pad_geometry_kernel as K
ROOT=Path('/home/c08r4d0r/reports/pr468-c10-bounded'); OUT=ROOT/'visuals'; OUT.mkdir(exist_ok=True)
boards={s:pcbnew.LoadBoard(str(ROOT/s/'board.kicad_pcb')) for s in ['before','after']}
hashes={s:hashlib.sha256((ROOT/s/'board.kicad_pcb').read_bytes()).hexdigest() for s in boards}
layers=[pcbnew.F_Cu,pcbnew.In1_Cu,pcbnew.In2_Cu,pcbnew.B_Cu]
def xy(p): return (p.x/1e6,p.y/1e6)
def color(net): return '#57cf91' if net=='GND' else '#ffb74d' if net=='+3V3' else '#a1a8b8'
def polys(poly,fill):
    paths=[]
    for i in range(poly.OutlineCount()):
        chains=[poly.Outline(i)]+[poly.Hole(i,j) for j in range(poly.HoleCount(i))]
        d=[]
        for c in chains:
            pts=[xy(c.CPoint(j)) for j in range(c.PointCount())]
            if pts: d.append('M '+' L '.join(f'{x},{y}' for x,y in pts)+' Z')
        paths.append(f'<path d="{" ".join(d)}" fill="{fill}" fill-rule="evenodd"/>')
    return ''.join(paths)
def copper(b,l):
    out=[]
    for t in list(b.GetTracks())+list(b.GetDrawings()):
        if not t.IsOnLayer(l): continue
        if t.Type()==pcbnew.PCB_VIA_T:
            x,y=xy(t.GetPosition()); out.append(f'<circle cx="{x}" cy="{y}" r="{t.GetWidth(l)/2e6}" fill="{color(t.GetNetname())}"/><circle cx="{x}" cy="{y}" r="{t.GetDrillValue()/2e6}" fill="#101923"/>')
        elif t.Type()==pcbnew.PCB_TRACE_T or (t.GetClass()=='PCB_SHAPE' and int(t.GetShape())==0):
            x,y=xy(t.GetStart()); xx,yy=xy(t.GetEnd())
            out.append(f'<path d="M {x},{y} L {xx},{yy}" fill="none" stroke="{color(t.GetNetname())}" stroke-width="{t.GetWidth()/1e6}" stroke-linecap="round"/>')
        elif hasattr(t,'TransformShapeToPolygon'):
            p=pcbnew.SHAPE_POLY_SET(); t.TransformShapeToPolygon(p,l,0,100,pcbnew.ERROR_INSIDE); out.append(polys(p,color(t.GetNetname())))
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.IsOnLayer(l) and p.GetAttribute()!=pcbnew.PAD_ATTRIB_NPTH: out.append(polys(p.GetEffectivePolygon(l),color(p.GetNetname())))
    return ''.join(out)
metrics={'source_sha256':hashes,'scope':'Original boards; hard copper only, no zones. All physical copper layers checked for via-pad overlap. Kernel d_point minus via outer radius (negative = overlap); no net exclusions.','via_pad_checks':[]}
for state, targets in [('before',[(8.15,40.25)]),('after',[(8.15,40.25),(8.52,43)])]:
    b=boards[state]
    for target in targets:
        vs=[v for v in b.GetTracks() if v.Type()==pcbnew.PCB_VIA_T and math.dist(xy(v.GetPosition()),target)<1e-5]
        assert len(vs)==1, (state,target,len(vs))
        v=vs[0]; rec={'state':state,'xy_mm':target,'net':v.GetNetname(),'drill_mm':v.GetDrillValue()/1e6,'layers':{}}
        for l in layers:
            if not v.IsOnLayer(l): continue
            radius=v.GetWidth(l)/2e6; gaps=[]
            for f in b.GetFootprints():
                for p in f.Pads():
                    if p.IsOnLayer(l) and p.GetAttribute()!=pcbnew.PAD_ATTRIB_NPTH:
                        it=K.pad_item(p,l); gap=it.d_point(*target)-radius
                        gaps.append({'pad':f.GetReference()+'.'+p.GetNumber(),'net':p.GetNetname(),'gap_mm':gap})
            gaps.sort(key=lambda x:x['gap_mm'])
            rec['layers'][b.GetLayerName(l)]={'diameter_mm':2*radius,'overlaps':[g for g in gaps if g['gap_mm']<0],'nearest':gaps[:3],'pads_checked':len(gaps)}
        metrics['via_pad_checks'].append(rec)
try: metrics['kernel_validation']=K.validate(boards['after'],sample=100)
except Exception as e: metrics['kernel_validation_error']=str(e)
files=[]
for region,y0 in [('local',39),('rail-context',34)]:
    scale=65; ph=(47-y0)*scale; w=1560; h=ph+150
    for l in layers:
        name=boards['after'].GetLayerName(l); body=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',f'<rect width="{w}" height="{h}" fill="#101923"/>',f'<text x="25" y="28" fill="white" font-size="20">PR468 — {name} — {region} — x 6–14 mm, y {y0}–47 mm</text>', '<text x="25" y="51" fill="#c5cedb" font-size="14">Hard copper only; unchanged refilled candidate; C10 still OPEN; zone fills omitted. Green GND | orange +3V3 | gray other nets. All layers viewed from top.</text>']
        for idx,(state,b) in enumerate(boards.items()):
            ox=30+idx*780; oy=95
            body += [f'<text x="{ox}" y="79" fill="white" font-size="18">{state.upper()} · SHA256 {hashes[state][:12]}</text>',f'<defs><clipPath id="clip{idx}"><rect x="6" y="{y0}" width="8" height="{47-y0}"/></clipPath></defs>',f'<g transform="translate({ox},{oy}) scale({scale}) translate(-6,-{y0})"><g clip-path="url(#clip{idx})">']
            for x in range(6,15): body.append(f'<path d="M{x},{y0} V47" stroke="#263747" stroke-width="0.012"/>')
            for y in range(y0,48): body.append(f'<path d="M6,{y} H14" stroke="#263747" stroke-width="0.012"/>')
            body.append(copper(b,l)); body.append('</g></g>')
            marks=[]
            for ref,pn in [('C10','1'),('C10','2'),('U1','9'),('U1','2')]:
                p=next(p for f in b.GetFootprints() if f.GetReference()==ref for p in f.Pads() if p.GetNumber()==pn)
                marks.append((ref+'.'+pn+(' rail target' if (ref,pn)==('U1','2') else ''),xy(p.GetPosition()),p.IsOnLayer(l)))
            marks += [('GND via '+('existing'),(8.15,40.25) if state=='before' else (8.15,40.25),True)]
            if state=='after': marks.append(('Existing +3V3 via',(8.52,43),True))
            for j,(label,(x,y),present) in enumerate(marks):
                lx=ox+535; ly=oy+35+j*66
                suffix='' if present else ' (other layer)'
                if y<y0:
                    body.append(f'<text x="{lx}" y="{ly}" fill="#f0d8fc" font-size="13">{html.escape(label)} (above crop)</text>'); continue
                px=ox+(x-6)*scale; py=oy+(y-y0)*scale
                body += [f'<path d="M{px},{py} L{lx-10},{ly-5}" stroke="#f0d8fc" stroke-width="1" fill="none"/>',f'<circle cx="{px}" cy="{py}" r="4" fill="none" stroke="#f0d8fc"/>',f'<text x="{lx}" y="{ly}" fill="#f0d8fc" font-size="13">{html.escape(label+suffix)}</text>',f'<text x="{lx}" y="{ly+17}" fill="#b3bfcd" font-size="12">({x:.5f}, {y:.5f}) mm</text>']
            body.append(f'<text x="{ox}" y="{oy+ph+22}" fill="#c5cedb" font-size="13">6 mm ← x → 14 mm; y increases downward; 1 mm grid</text>')
        body.append('</svg>'); path=OUT/f'{region}-{name}-before-after.svg'; path.write_text(''.join(body)); ET.parse(path)
        subprocess.run(['rsvg-convert',str(path),'-o',str(path.with_suffix('.png'))],check=True)
        texts=[e.text or '' for e in ET.parse(path).getroot().iter() if e.tag.endswith('text')]
        assert all(any(label in t for t in texts) for label in ['C10.1','C10.2','U1.9','U1.2','GND via','Existing +3V3 via'])
        files.append(str(path)); print(path)
metrics['svg_validation']={'files':files,'xml_parse':'passed','required_annotations':'passed','fixed_label_baseline_spacing_px':66,'label_line_height_px':17,'note':'Annotation columns outside copper crop; leader lines do not alter geometry.'}
(OUT/'measurements.json').write_text(json.dumps(metrics,indent=2,default=str))
assert hashes=={s:hashlib.sha256((ROOT/s/'board.kicad_pcb').read_bytes()).hexdigest() for s in boards}
print(json.dumps(metrics['via_pad_checks'],indent=2))
