#!/usr/bin/env python3.14
"""Does a legal 0.6/0.3 site exist for the 2 under-size GND vias at U5?

Exact geometry, BOTH constraints the fleet's earlier relocation script missed:
  * foreign COPPER clearance  >= 0.20 mm  (pads, tracks, vias — per layer)
  * copper-to-HOLE clearance  >= 0.25 mm  (board's own min_hole_clearance)
  * board-edge clearance      >= 0.50 mm
Grid search 0.025 mm over +-3 mm. Reports the best candidates; writes nothing.
"""
import sys, math
sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew

BOARD = "output/v8g_krt_routed.kicad_pcb"
MM = 1_000_000
mm = lambda v: v / MM

CLEAR = 0.20 + 0.01          # safety over the rule
HOLE = 0.25 + 0.01
VIA_R = 0.30                 # 0.6 mm via radius
DRILL_R = 0.15               # 0.3 mm drill radius
GRID = 0.025
SEARCH = 3.0
EDGE = 0.50

b = pcbnew.LoadBoard(BOARD)
layers = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
lnames = {l: b.GetLayerName(l) for l in layers}

# --- obstacles ---------------------------------------------------------------
pads = []      # (net, x1,y1,x2,y2, layerset_str)
hole_pads = []
for fp in b.GetFootprints():
    for p in fp.Pads():
        bb = p.GetBoundingBox()
        box = (mm(bb.GetX()), mm(bb.GetY()), mm(bb.GetRight()), mm(bb.GetBottom()))
        pads.append((p.GetNetname(), box))
        # through-hole pads have holes too
        if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
            hole_pads.append((p.GetNetname(), mm(p.GetPosition().x), mm(p.GetPosition().y),
                              mm(p.GetDrillSize().x) / 2))
tracks = []
for t in b.GetTracks():
    if t.Type() == pcbnew.PCB_TRACE_T:
        s, e = t.GetStart(), t.GetEnd()
        tracks.append((t.GetNetname(), t.GetLayer(),
                       (mm(s.x), mm(s.y)), (mm(e.x), mm(e.y)), mm(t.GetWidth()) / 2))
    elif t.Type() == pcbnew.PCB_VIA_T:
        v_tracks = None
vias = [(v.GetNetname(), mm(v.GetPosition().x), mm(v.GetPosition().y),
         mm(v.GetWidth(v.TopLayer())) / 2, mm(v.GetDrillValue()) / 2)
        for v in b.GetTracks() if v.Type() == pcbnew.PCB_VIA_T]

edge = b.GetBoardEdgesBoundingBox()
EX1, EY1, EX2, EY2 = mm(edge.GetX()), mm(edge.GetY()), mm(edge.GetRight()), mm(edge.GetBottom())

def rect_dist(px, py, box):
    dx = max(box[0] - px, px - box[2], 0.0)
    dy = max(box[1] - py, py - box[3], 0.0)
    return math.hypot(dx, dy)

def seg_dist(px, py, a, c):
    ax, ay = a; cx, cy = c
    vx, vy = cx - ax, cy - ay
    L2 = vx * vx + vy * vy
    if L2 == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / L2))
    return math.hypot(px - (ax + t * vx), py - (ay + t * vy))

def legal(px, py, net):
    """Return (ok, worst_gap) for a 0.6/0.3 via centred at (px,py) on net `net`."""
    worst = 99.0
    for pnet, box in pads:
        if pnet == net:
            continue
        g = rect_dist(px, py, box) - VIA_R
        worst = min(worst, g)
        if g < CLEAR:
            return False, g
    for tnet, layer, a, c, tw in tracks:
        if tnet == net:
            continue
        g = seg_dist(px, py, a, c) - VIA_R - tw
        worst = min(worst, g)
        if g < CLEAR:
            return False, g
    for vnet, vx, vy, vr, vd in vias:
        if vnet == net:
            continue
        g = math.hypot(px - vx, py - vy) - VIA_R - vr
        if g < CLEAR:
            return False, g
        gh = math.hypot(px - vx, py - vy) - DRILL_R - vd     # hole-to-hole
        if gh < HOLE:
            return False, gh
        worst = min(worst, g)
    for hnet, hx, hy, hr in hole_pads:
        gh = math.hypot(px - hx, py - hy) - DRILL_R - hr
        if gh < HOLE:
            return False, gh
    if (px - VIA_R) - EX1 < EDGE or (EX2 - (px + VIA_R)) < EDGE \
       or (py - VIA_R) - EY1 < EDGE or (EY2 - (py + VIA_R)) < EDGE:
        return False, -1
    return True, worst

targets = [(v.GetNetname(), mm(v.GetPosition().x), mm(v.GetPosition().y), v)
           for v in b.GetTracks()
           if v.Type() == pcbnew.PCB_VIA_T and round(mm(v.GetWidth(v.TopLayer())), 3) < 0.6]

print(f"board edge box ({EX1:.2f},{EY1:.2f})-({EX2:.2f},{EY2:.2f})  obstacles: "
      f"{len(pads)} pads, {len(tracks)} tracks, {len(vias)} vias")

for net, vx, vy, v in targets:
    print(f"\n=== under-size via net={net!r} at ({vx:.3f},{vy:.3f})")
    best = None
    n = int(SEARCH / GRID)
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            px, py = round(vx + i * GRID, 4), round(vy + j * GRID, 4)
            ok, gap = legal(px, py, net)
            if ok:
                d = math.hypot(px - vx, py - vy)
                if best is None or d < best[0]:
                    best = (d, px, py, gap)
    if best:
        d, px, py, gap = best
        print(f"  LEGAL SITE FOUND: shift {d:.3f} mm -> ({px:.3f},{py:.3f}) worst foreign gap {gap:.3f} mm")
    else:
        print("  NO legal site within +-3.0 mm")
