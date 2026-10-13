#!/usr/bin/env python3.14
"""Courtyard overlap on the v8b board — pcbnew, BOARD coordinates.

Uses fp_line/fp_rect GetStart()/GetEnd(), which pcbnew returns in board mm, and
sanity-checks U1's courtyard size against the ESP32-C3-WROOM-02 datasheet
(module 18x20 mm -> courtyard ~18.5x20.6 mm). If the sanity check fails the run
stops, because every number after it would be meaningless.
"""
import sys
sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew

BOARD = "/home/c03rad0r/worktrees/t_157df236/tracker/hardware/output/v8b_krt_routed.kicad_pcb"
b = pcbnew.LoadBoard(BOARD)
mm = lambda v: v / 1e6

def crtyd_boxes(fp):
    """Return [(x1,y1,x2,y2)] board-mm for every CrtYd shape on the footprint."""
    out = []
    for d in fp.GraphicalItems():
        if d.GetLayer() not in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
            continue
        try:
            s, e = d.GetStart(), d.GetEnd()
        except Exception:
            continue
        out.append((min(mm(s.x), mm(e.x)), min(mm(s.y), mm(e.y)),
                    max(mm(s.x), mm(e.x)), max(mm(s.y), mm(e.y))))
    return out

fps = {fp.GetReference(): fp for fp in b.GetFootprints()}
print("footprints:", len(fps))

u1 = fps["U1"]
ub = crtyd_boxes(u1)
if not ub:
    print("U1 has NO courtyard geometry — cannot judge; stopping"); sys.exit(1)
u1box = (min(r[0] for r in ub), min(r[1] for r in ub), max(r[2] for r in ub), max(r[3] for r in ub))
print(f"U1 (ESP32-C3-WROOM-02) pos={mm(u1.GetPosition().x):.2f},{mm(u1.GetPosition().y):.2f} "
      f"courtyard={u1box[2]-u1box[0]:.2f}x{u1box[3]-u1box[1]:.2f} mm "
      f"@ ({u1box[0]:.2f},{u1box[1]:.2f})-({u1box[2]:.2f},{u1box[3]:.2f})")
if not (16.0 < (u1box[2] - u1box[0]) < 22.0 and 18.0 < (u1box[3] - u1box[1]) < 24.0):
    print(f"SANITY FAIL: U1 courtyard size {u1box[2]-u1box[0]:.2f}x{u1box[3]-u1box[1]:.2f} "
          f"is not plausible for an 18x20 mm module — numbers below are suspect")

print("\n=== pair report ===")
def inter(A, B):
    x1, y1 = max(A[0], B[0]), max(A[1], B[1])
    x2, y2 = min(A[2], B[2]), min(A[3], B[3])
    return None if (x2 <= x1 or y2 <= y1) else (x2 - x1, y2 - y1, (x2 - x1) * (y2 - y1))

report = []
names = sorted(fps)
for i in range(len(names)):
    for j in range(i + 1, len(names)):
        A, B = fps[names[i]], fps[names[j]]
        Ab, Bb = crtyd_boxes(A), crtyd_boxes(B)
        best = None
        for ra in Ab:
            for rb in Bb:
                r = inter(ra, rb)
                if r and (best is None or r[2] > best[2]):
                    best = r
        if best:
            report.append((names[i], names[j], best))
for a, bb, r in sorted(report, key=lambda t: -t[2][2]):
    print(f"  {a:8s} <-> {bb:8s} overlap {r[2]:7.3f} mm^2  ({r[0]:.2f} x {r[1]:.2f} mm)")
print("total overlapping pairs:", len(report))

print("\n=== C2 / U1 detail ===")
for ref in ("C2", "U1"):
    fp = fps[ref]
    box = crtyd_boxes(fp)
    bx = (min(r[0] for r in box), min(r[1] for r in box), max(r[2] for r in box), max(r[3] for r in box))
    print(f"  {ref} value={fp.GetValue()!r} pos=({mm(fp.GetPosition().x):.2f},{mm(fp.GetPosition().y):.2f}) "
          f"courtyard=({bx[0]:.2f},{bx[1]:.2f})-({bx[2]:.2f},{bx[3]:.2f})")
    for r in box:
        print(f"      shape ({r[0]:.2f},{r[1]:.2f})-({r[2]:.2f},{r[3]:.2f})")

# pad gap C2<->U1
def pads(fp):
    out = []
    for p in fp.Pads():
        bb = p.GetBoundingBox()
        out.append(((mm(bb.GetX()), mm(bb.GetY()), mm(bb.GetRight()), mm(bb.GetBottom())), p.GetNetname()))
    return out

def gap(A, B):
    dx = max(A[0] - B[2], B[0] - A[2], 0.0)
    dy = max(A[1] - B[3], B[1] - A[3], 0.0)
    return (dx * dx + dy * dy) ** 0.5

best = None
for ba, na in pads(fps["C2"]):
    for bx2, nb in pads(fps["U1"]):
        g = gap(ba, bx2)
        if best is None or g < best[0]:
            best = (g, na, nb)
print(f"\nC2->U1 min pad-to-pad gap: {best[0]:.3f} mm (nets {best[1]!r} / {best[2]!r})")

# body (F.Fab) over U1's pads?
def fab_box(fp):
    out = []
    for d in fp.GraphicalItems():
        if d.GetLayer() != pcbnew.F_Fab:
            continue
        try:
            s, e = d.GetStart(), d.GetEnd()
        except Exception:
            continue
        out.append((min(mm(s.x), mm(e.x)), min(mm(s.y), mm(e.y)),
                    max(mm(s.x), mm(e.x)), max(mm(s.y), mm(e.y))))
    if not out:
        return None
    return (min(r[0] for r in out), min(r[1] for r in out),
            max(r[2] for r in out), max(r[3] for r in out))

c2fab = fab_box(fps["C2"])
print(f"C2 body (F.Fab) box: {tuple(round(v,2) for v in c2fab) if c2fab else None}")
hits = [n for bb, n in pads(fps["U1"]) if c2fab and inter(c2fab, bb)]
print(f"U1 pads under C2's body: {len(hits)} {hits[:6]}")
