#!/usr/bin/env python3
"""For each of the 4 cardinal escape directions from a pad, name EVERY object that blocks it.

The point: the earlier diag named only the NEAREST object, which reads as "one thing blocks this".
This lists all blockers per direction, so "boxed in" is a complete statement or it is not made.
Usage: verify_blocks.py <board> <ref.pad> [--clear 0.20 --track-w 0.20 --step 0.25 --reach 3.0]
"""
import argparse, math, sys
import pcbnew
UM = 1_000_000.0

def find_pad(b, spec):
    ref, num = spec.split(".", 1)
    fp = next((f for f in b.GetFootprints() if f.GetReference() == ref), None)
    return None if fp is None else next((p for p in fp.Pads() if p.GetNumber() == num), None)

def seg_point(px, py, x1, y1, x2, y2):
    dx, dy = x2-x1, y2-y1
    if dx == 0 and dy == 0: return math.hypot(px-x1, py-y1)
    t = max(0.0, min(1.0, ((px-x1)*dx + (py-y1)*dy)/(dx*dx+dy*dy)))
    return math.hypot(px-(x1+t*dx), py-(y1+t*dy))

def seg_seg(a1,a2,b1,b2):
    def o(p,q,r): return (q[0]-p[0])*(r[1]-p[1])-(q[1]-p[1])*(r[0]-p[0])
    o1,o2,o3,o4 = o(a1,a2,b1),o(a1,a2,b2),o(b1,b2,a1),o(b1,b2,a2)
    if o1*o2<0 and o3*o4<0: return 0.0
    return min(seg_point(*b1,*a1,*a2), seg_point(*b2,*a1,*a2),
               seg_point(*a1,*b1,*b2), seg_point(*a2,*b1,*b2))

ap = argparse.ArgumentParser()
ap.add_argument("board"); ap.add_argument("spec")
ap.add_argument("--clear", type=float, default=0.20)
ap.add_argument("--track-w", type=float, default=0.20)
ap.add_argument("--reach", type=float, default=3.0)
ap.add_argument("--step", type=float, default=0.25)
a = ap.parse_args()
b = pcbnew.LoadBoard(a.board)
pad = find_pad(b, a.spec)
p = pad.GetPosition(); cx, cy = p.x/UM, p.y/UM
lay = pcbnew.F_Cu if pcbnew.F_Cu in pad.GetLayerSet().Seq() else pcbnew.B_Cu
need = a.track_w/2 + a.clear
obs = []
for t in b.GetTracks():
    if t.GetNetname() == pad.GetNetname(): continue
    if t.Type() == pcbnew.PCB_VIA_T:
        q = t.GetPosition()
        for L in (pcbnew.F_Cu, pcbnew.B_Cu):
            obs.append(((q.x/UM,q.y/UM,q.x/UM,q.y/UM), t.GetWidth(pcbnew.F_Cu)/UM/2, L, "via "+t.GetNetname()))
    elif t.GetLayer() == lay:
        obs.append(((t.GetStart().x/UM,t.GetStart().y/UM,t.GetEnd().x/UM,t.GetEnd().y/UM),
                    t.GetWidth()/UM/2, lay, "track "+t.GetNetname()))
for fp in b.GetFootprints():
    for q in fp.Pads():
        if q is pad or q.GetNetname() == pad.GetNetname(): continue
        if lay not in q.GetLayerSet().Seq(): continue
        bb = q.GetBoundingBox()
        obs.append(((bb.GetLeft()/UM,bb.GetTop()/UM,bb.GetRight()/UM,bb.GetBottom()/UM), 0.0, lay,
                    f"pad {fp.GetReference()}.{q.GetNumber()}"))
print(f"{a.spec} net={pad.GetNetname()!r} size {pad.GetSize().x/UM:.2f}x{pad.GetSize().y/UM:.2f} "
      f"layer={pcbnew.LayerName(lay)} centre=({cx:.2f},{cy:.2f})")
print(f"rule: track {a.track_w} + clearance {a.clear} -> every point of the corridor needs {need:.2f} mm\n")
for name,(dx,dy) in (("EAST",(1,0)),("WEST",(-1,0)),("NORTH",(0,-1)),("SOUTH",(0,1))):
    blockers=[]
    n = int(a.reach/a.step)
    for i in range(1, n+1):
        px, py = cx+dx*i*a.step, cy+dy*i*a.step
        # corridor segment from centre to this probe point
        for (seg, r, L, tag) in obs:
            if L != lay: continue
            d = seg_seg((cx,cy),(px,py), seg[:2], seg[2:])
            if d < r + need:
                blockers.append((round(d-r,3), tag)); break
        else:
            continue
        break
    uniq=[]
    for t in blockers:
        if t not in uniq: uniq.append(t)
    if uniq:
        print(f"  {name:6s}: BLOCKED at {a.step + 0*a.step:.2f}..{a.reach:.1f}mm by "
              + "; ".join(f"{tag} (gap {g:.3f})" for g,tag in uniq[:4]))
    else:
        print(f"  {name:6s}: CLEAR for {a.reach:.1f} mm")
