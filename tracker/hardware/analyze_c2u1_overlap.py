#!/usr/bin/env python3.14
"""Adjudicate the C2<->U1 courtyard overlap on the v8b fab candidate.

Answers: is it a REAL physical conflict (bodies/pads collide) or a cosmetic
courtyard-keepout artifact? Reports pad-to-pad min distance too.
"""
import sys
sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew

BOARD = "/home/c03rad0r/worktrees/t_157df236/tracker/hardware/output/v8b_krt_routed.kicad_pcb"
b = pcbnew.LoadBoard(BOARD)
print("board:", BOARD, "| fp:", len(list(b.GetFootprints())))

def poly_bbox(poly):
    """Accept either a SHAPE_POLY_SET (has .BBox()) or a BOX2I (has .GetX()...)."""
    if hasattr(poly, "BBox"):
        box = poly.BBox()
    else:
        box = poly
    return (box.GetX() / 1e6, box.GetY() / 1e6, box.GetRight() / 1e6, box.GetBottom() / 1e6)

def mm(v):
    return v / 1e6

fps = {fp.GetReference(): fp for fp in b.GetFootprints()}
print("refs:", sorted(fps))
for ref in ("U1", "C2", "U2", "C4", "D1"):
    fp = fps.get(ref)
    if not fp:
        print(f"{ref}: MISSING"); continue
    pos = fp.GetPosition()
    print(f"\n== {ref} value={fp.GetValue()!r} fp={fp.GetFPID().GetLibItemName()!r}")
    print(f"   pos=({mm(pos.x):.3f},{mm(pos.y):.3f}) rot={fp.GetOrientationDegrees()}")
    for layer, name in ((pcbnew.F_CrtYd, "F.CrtYd"), (pcbnew.F_Fab, "F.Fab")):
        shapes = [d for d in fp.GraphicalItems() if d.GetLayer() == layer]
        if not shapes:
            print(f"   {name}: none on footprint")
        else:
            x1, y1, x2, y2 = poly_bbox(fp.GetBoundingBox(False, False))
            allbb = None
            for s in shapes:
                bb = s.GetBoundingBox()
                bx = (mm(bb.GetX()), mm(bb.GetY()), mm(bb.GetRight()), mm(bb.GetBottom()))
                allbb = bx if allbb is None else (min(allbb[0], bx[0]), min(allbb[1], bx[1]),
                                                  max(allbb[2], bx[2]), max(allbb[3], bx[3]))
            print(f"   {name}: {len(shapes)} shape(s) bbox={tuple(round(v,3) for v in allbb)} "
                  f"size=({allbb[2]-allbb[0]:.3f}x{allbb[3]-allbb[1]:.3f})")
    pads = list(fp.Pads())
    print(f"   pads={len(pads)}")

# --- courtyard intersection test for the reported pair
def courtyard_bbox(fp):
    bb = None
    for d in fp.GraphicalItems():
        if d.GetLayer() == pcbnew.F_CrtYd:
            b2 = d.GetBoundingBox()
            bx = (mm(b2.GetX()), mm(b2.GetY()), mm(b2.GetRight()), mm(b2.GetBottom()))
            bb = bx if bb is None else (min(bb[0], bx[0]), min(bb[1], bx[1]),
                                        max(bb[2], bx[2]), max(bb[3], bx[3]))
    return bb

print("\n=== courtyard bbox overlap checks ===")
def overlap(a, b_):
    if not a or not b_:
        return None
    ox = min(a[2], b_[2]) - max(a[0], b_[0])
    oy = min(a[3], b_[3]) - max(a[1], b_[1])
    return (ox, oy, ox * oy if ox > 0 and oy > 0 else 0.0)

pairs = []
names = sorted(fps)
for i in range(len(names)):
    for j in range(i + 1, len(names)):
        A, B = fps[names[i]], fps[names[j]]
        r = overlap(courtyard_bbox(A), courtyard_bbox(B))
        if r and r[2] > 0:
            pairs.append((names[i], names[j], r))
for a, bb, r in pairs:
    print(f"  {a} <-> {bb}: dx={r[0]:.3f}mm dy={r[1]:.3f}mm area={r[2]:.4f}mm^2")

# --- min pad-to-pad distance for the reported pair (electrical risk proxy)
def pad_boxes(fp):
    out = []
    for p in fp.Pads():
        bb = p.GetBoundingBox()
        out.append(((mm(bb.GetX()), mm(bb.GetY()), mm(bb.GetRight()), mm(bb.GetBottom())), p.GetNetname()))
    return out

def box_gap(A, B):
    dx = max(A[0] - B[2], B[0] - A[2], 0.0)
    dy = max(A[1] - B[3], B[1] - A[3], 0.0)
    return (dx * dx + dy * dy) ** 0.5

print("\n=== pad-to-pad min gaps (reported pair + neighbours) ===")
for a, bb in [("C2", "U1"), ("U1", "U2"), ("D1", "U1")]:
    if a in fps and bb in fps:
        best = None
        for (ba, na) in pad_boxes(fps[a]):
            for (bx, nb) in pad_boxes(fps[bb]):
                g = box_gap(ba, bx)
                if best is None or g < best[0]:
                    best = (g, na, nb)
        print(f"  {a}<->{bb}: min pad gap {best[0]:.3f}mm (nets {best[1]!r} / {best[2]!r})")

# --- vias: diameter + drill distribution
vias = [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
sizes = {}
for v in vias:
    key = (round(mm(v.GetWidth()), 3), round(mm(v.GetDrillValue()), 3))
    sizes[key] = sizes.get(key, 0) + 1
print("\n=== via (diameter, drill) mm -> count ===")
for k, c in sorted(sizes.items()):
    print(f"  dia {k[0]:.2f} / drill {k[1]:.2f} : {c}")
print("tracks:", len(list(b.GetTracks())), "| vias:", len(vias))
