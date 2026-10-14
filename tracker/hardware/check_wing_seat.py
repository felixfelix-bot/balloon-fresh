#!/usr/bin/env python3
"""Prove the wing-tab seat defect and the fix, with coordinates.

The defect: EDGE_SEATS seats each J_W footprint with offset=0.0, i.e. its DATUM
sits exactly ON the outline edge. But the footprint's 4.0x1.2 mm lands are at
local +3.0 mm, and the footprint's datum is defined as the INTERFACE (outer)
edge with +x INBOARD -- so the whole land set lands ~1.0 mm OFF the board, and
pads at local y=-2.7..+2.7 from a 0.5-frac seat run past the north/east edges.

This script loads the generated seed and prints, per wing socket, the board
outline and each pad's coordinates, flagging any pad outside the outline.
"""
import sys
sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew

path = sys.argv[1] if len(sys.argv) > 1 else "seed"
b = pcbnew.LoadBoard(path)
assert b is not None, f"cannot load {path}"

# board outline from board-level Edge.Cuts only (footprint graphics excluded)
xs, ys = [], []
for d in b.GetDrawings():
    if d.GetLayer() == pcbnew.Edge_Cuts:
        bb = d.GetBoundingBox()
        xs += [pcbnew.ToMM(bb.GetX()), pcbnew.ToMM(bb.GetX() + bb.GetWidth())]
        ys += [pcbnew.ToMM(bb.GetY()), pcbnew.ToMM(bb.GetY() + bb.GetHeight())]
x0, x1 = min(xs), max(xs)
y0, y1 = min(ys), max(ys)
print(f"board outline: x {x0:.3f}..{x1:.3f}  y {y0:.3f}..{y1:.3f}  "
      f"({x1-x0:.2f} x {y1-y0:.2f} mm)")
print()

# DRC copper-edge clearance (JLCPCB): pads must be ON the board
E = 0.2
bad_total = 0
for ref in ("J_W1", "J_W2", "J_W3", "J_W4"):
    fp = b.FindFootprintByReference(ref)
    if fp is None:
        print(f"{ref}: NOT PLACED")
        continue
    print(f"{ref} @ ({pcbnew.ToMM(fp.GetPosition().x):.3f}, "
          f"{pcbnew.ToMM(fp.GetPosition().y):.3f}) rot {fp.GetOrientationDegrees():g}")
    bad = []
    for p in fp.Pads():
        px, py = pcbnew.ToMM(p.GetPosition().x), pcbnew.ToMM(p.GetPosition().y)
        outside = px < x0 + E or px > x1 - E or py < y0 + E or py > y1 - E
        if outside:
            bad.append((p.GetNumber(), px, py))
    bad_total += len(bad)
    if bad:
        print(f"   {len(bad)} pad(s) OUTSIDE the board outline (min {E} mm edge rule):")
        for n, px, py in bad:
            print(f"     pad {n:>2} @ ({px:.3f}, {py:.3f})")
    else:
        print("   all pads on-board: OK")

print()
print(f"RESULT: {bad_total} off-board wing-socket pads total")
sys.exit(1 if bad_total else 0)
