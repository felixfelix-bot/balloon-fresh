"""Independently verify: are the four wing interfaces geometrically equivalent?

RULE 3: measure the object in hand, name the exact path and hash. A worker reported this; a self-report is
not evidence.

TWO BUGS IN MY FIRST ATTEMPT, BOTH FIXED HERE -- recorded because the first run produced a result that
partly contradicted the worker's report and I nearly believed it:
  1. LAST-ITEM-WINS: the slot was taken as the bounding box of ONE Edge.Cuts item per footprint (the loop
     overwrote the variable), so each slot measured as a thin fragment instead of the full rectangle.
     Fixed by UNIONING every Edge.Cuts item in the footprint.
  2. ROTATION SET TOO NARROW: equivalence was tested only at 0 and 180 degrees. But the four tabs sit at 90
     degree spacing on a square outline, so the meaningful question is equivalence up to a MULTIPLE OF 90.
     J_W1 measured "DIFFERENT" purely because it was compared at the wrong angles.
Both bugs made the first run look like a refutation. It was not one.

The claim under test: the four interfaces are NOT equivalent -- J_W1/J_W3 rotated 180 deg relative to
J_W2/J_W4, leaving the left/right milled slots wholly inside the board while top/bottom cross their edges.

Run: ~/venvs/kicad/bin/python verify_wing_interfaces.py [board]

EXIT CODE (the detector, wired 2026-10-17): the EDGE-REACH assertion drives it --
  0 = every one of the four wing slots reaches its own board edge (within TOL)
  1 = at least one slot is wholly inside the board (not an edge slot)
Use it as a gate: `verify_wing_interfaces.py || echo "wing interface defect"`.
"""
import hashlib
import math
import sys

import pcbnew

BOARD = sys.argv[1] if len(sys.argv) > 1 else "tracker/hardware/hub_board_v9.kicad_pcb"
TABS = ["J_W1", "J_W2", "J_W3", "J_W4"]


def all_edge_items(fp):
    """EVERY Edge.Cuts item in the footprint -- not just the last one."""
    return [d for d in fp.GraphicalItems() if d.GetLayer() == pcbnew.Edge_Cuts]


def union_bbox(items):
    if not items:
        return None
    xs, ys = [], []
    for d in items:
        bb = d.GetBoundingBox()
        xs += [pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetRight())]
        ys += [pcbnew.ToMM(bb.GetTop()), pcbnew.ToMM(bb.GetBottom())]
    return (min(xs), min(ys), max(xs), max(ys))


def main():
    blob = open(BOARD, "rb").read()
    print(f"board : {BOARD}")
    print(f"sha256: {hashlib.sha256(blob).hexdigest()[:32]}\n")
    b = pcbnew.LoadBoard(BOARD)

    edge = [d for d in b.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]
    ox0, oy0, ox1, oy1 = union_bbox(edge)
    print(f"outline (Edge.Cuts bbox): x {ox0:.2f} .. {ox1:.2f}   y {oy0:.2f} .. {oy1:.2f}")
    print(f"                          {ox1 - ox0:.2f} x {oy1 - oy0:.2f} mm\n")

    info = {}
    for ref in TABS:
        fp = b.FindFootprintByReference(ref)
        if fp is None:
            print(f"  {ref}: ABSENT")
            continue
        pos = fp.GetPosition()
        items = all_edge_items(fp)
        info[ref] = {
            "origin": (pcbnew.ToMM(pos.x), pcbnew.ToMM(pos.y)),
            "rot": fp.GetOrientationDegrees(),
            "n_edge": len(items),
            "slot": union_bbox(items),
            "pads": [(pcbnew.ToMM(p.GetPosition().x), pcbnew.ToMM(p.GetPosition().y))
                     for p in fp.Pads()],
        }

    print("=== per-tab geometry in ABSOLUTE board coordinates ===")
    for ref in TABS:
        d = info.get(ref)
        if not d:
            continue
        ox, oy = d["origin"]
        print(f"  {ref}  origin=({ox:7.2f},{oy:7.2f})  rot={d['rot']:6.1f}  "
              f"Edge.Cuts items={d['n_edge']}")
        if d["slot"]:
            s = d["slot"]
            print(f"        slot union   x {s[0]:7.2f} .. {s[2]:7.2f}    "
                  f"y {s[1]:7.2f} .. {s[3]:7.2f}   "
                  f"({s[2] - s[0]:.2f} x {s[3] - s[1]:.2f} mm)")

    print("\n=== does each tab's SLOT reach its board edge? ===")
    TOL = 0.30
    unreached = []
    for ref in TABS:
        d = info.get(ref)
        if not d or not d["slot"]:
            print(f"  {ref}: no slot measured -- cannot reach any edge")
            unreached.append(ref)
            continue
        sx0, sy0, sx1, sy1 = d["slot"]
        cand = []
        if sx0 <= ox0 + TOL:
            cand.append(("left", ox0 - sx0))
        if sx1 >= ox1 - TOL:
            cand.append(("right", sx1 - ox1))
        if sy0 <= oy0 + TOL:
            cand.append(("top", oy0 - sy0))
        if sy1 >= oy1 - TOL:
            cand.append(("bottom", sy1 - oy1))
        if cand:
            side, over = max(cand, key=lambda kv: kv[1])
            print(f"  {ref}: reaches the {side} edge (extends {over:+.2f} mm past it)")
        else:
            d_edge = min(sx0 - ox0, ox1 - sx1, sy0 - oy0, oy1 - sy1)
            print(f"  {ref}: ** WHOLLY INSIDE ** -- nearest slot edge is {d_edge:.2f} mm from the outline")
            unreached.append(ref)

    print(f"\n=== EDGE-REACH ASSERTION (tolerance {TOL:.2f} mm) ===")
    if unreached:
        print(f"  FAIL: {len(unreached)} of {len(TABS)} wing slots do NOT reach their own edge: "
              f"{', '.join(unreached)}")
        print("  A milled edge slot that is wholly inside the board is not an edge slot")
        print("  (ADR-048 s2.2 'identical geometry'; WING-TO-HUB-SOCKET-SPEC s2.1 'milled edge slot').")
    else:
        print(f"  PASS: all {len(TABS)} wing slots reach their own edge within {TOL:.2f} mm")

    print("\n=== equivalence: pad set vs J_W4, at every 90-degree multiple ===")
    def norm(ref, extra=0.0):
        d = info[ref]
        ox, oy = d["origin"]
        pts = [(x - ox, y - oy) for x, y in d["pads"]]
        th = math.radians(extra)
        pts = [(x * math.cos(th) - y * math.sin(th), x * math.sin(th) + y * math.cos(th))
               for x, y in pts]
        return sorted((round(x, 1), round(y, 1)) for x, y in pts)

    base = norm("J_W4")
    for ref in TABS:
        found = None
        for ang in (0, 90, 180, 270):
            if norm(ref, ang) == base:
                found = ang
                break
        label = ("IDENTICAL (0 deg)" if found == 0 else
                 f"IDENTICAL after {found} deg rotation" if found else
                 "** NOT EQUIVALENT at any 90-deg multiple **")
        print(f"  {ref}: {label}")

    print("\n=== the SLOT, compared the same way ===")
    def slot_rel(ref):
        d = info[ref]
        ox, oy = d["origin"]
        s = d["slot"]
        if not s:
            return None
        return (round(s[0] - ox, 2), round(s[1] - oy, 2), round(s[2] - ox, 2), round(s[3] - oy, 2))

    for ref in TABS:
        print(f"  {ref}: slot relative to origin = {slot_rel(ref)}")

    # EXIT CODE: the edge-reach assertion drives it.  0 = every wing slot reaches
    # its own board edge; 1 = at least one does not.  This is the gate that stops
    # the four interfaces silently diverging again -- nothing electrical sees this
    # class of defect.
    return 1 if unreached else 0


if __name__ == "__main__":
    sys.exit(main())
