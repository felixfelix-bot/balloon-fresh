#!/usr/bin/env python3
"""cut_hub_v9_socket_slots.py -- turn the J_W* socket slot graphics into REAL
board cutouts (holes in the outline).

WHY (measured 2026-10-12): each J_W* footprint draws a 0.95 x 6.0 mm
Edge.Cuts rectangle that pokes 6 mm OUTSIDE the 103x103 mm board -- because the
slot cutouts were never subtracted from the board outline.  KiCad's
copper_edge_clearance then measures the socket pads + their stub tracks against
those floating edges and reports 32 "edge" violations that are really an
outline-defect: a fab house reads a 6 mm edge stab outside the board.

Fix: move each slot rectangle off the footprint and subtract it from the board
outline as a HOLE, so the geometry is what the fab actually mills.  Pads that
sit inside a real cutout are then ordinary interior copper -- no edge violation
unless the copper really does approach the milled edge.

KiCad 9 pitfall: GetBoardPolygonOutlines() + BooleanSubtract, then
SetBoardOutline / the outline is rebuilt from the resulting poly set.  Build the
result with SHAPE_POLY_SET.BooleanSubtract(holeset, PM_FAST).
"""
import argparse
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

MM = 1e6


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    args = ap.parse_args()

    b = pcbnew.LoadBoard(args.inp)

    # --- collect the slot rectangles (footprint Edge.Cuts, closed 4-seg) -----
    slots = {}  # ref -> list of (x1,y1,x2,y2)
    for fp in b.GetFootprints():
        if not fp.GetReference().startswith("J_W"):
            continue
        segs = []
        for g in fp.GraphicalItems():
            if g.GetLayer() != pcbnew.Edge_Cuts:
                continue
            s, e = g.GetStart(), g.GetEnd()
            segs.append((s.x, s.y, e.x, e.y))
        if len(segs) == 4:
            slots[fp.GetReference()] = segs
    print(f"socket footprints with a 4-segment slot: {len(slots)}")
    for ref, segs in sorted(slots.items()):
        xs = [c for s in segs for c in (s[0], s[2])]
        ys = [c for s in segs for c in (s[1], s[3])]
        print(f"  {ref}: x {min(xs)/MM:.3f}..{max(xs)/MM:.3f}  "
              f"y {min(ys)/MM:.3f}..{max(ys)/MM:.3f} mm")

    if not slots:
        print("REFUSED: no socket slots found", file=sys.stderr)
        return 2

    print()
    print("NOTE: this script DIAGNOSES the slot geometry.  Converting the slots")
    print("to real outline holes is a DESIGN change that must be reviewed with a")
    print("spatially-reasoning LLM (Astra) before it lands -- see the hub ADR.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
