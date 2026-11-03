#!/usr/bin/env python3
"""DIAGNOSTIC: for one solar pair, locate the exact blocking obstruction.

A "NO PATH" from an A* is only evidence if the search is known to work on that geometry. This does
not search: it walks outward from each pad and reports the FIRST other-net copper object that
blocks, with its net, layer, distance and size. That distinguishes

  "the pair is boxed in by real copper"   (obstruction present, named)
  "my grid/clearance model is too strict" (no obstruction found, yet no path)

and it is the measurement the earlier finding was missing.

Usage: diag_pair.py <board.kicad_pcb> <net> <ref.pad> [<ref.pad>]
"""
import math
import sys

import pcbnew

UM = 1_000_000.0


def find_pad(board, spec):
    ref, num = spec.split(".", 1)
    fp = next((f for f in board.GetFootprints() if f.GetReference() == ref), None)
    return None if fp is None else next((p for p in fp.Pads() if p.GetNumber() == num), None)


def main():
    board_path, net, specA = sys.argv[1], sys.argv[2], sys.argv[3]
    specB = sys.argv[4] if len(sys.argv) > 4 else None
    board = pcbnew.LoadBoard(board_path)
    pad = find_pad(board, specA)
    if pad is None:
        print(f"no pad {specA}")
        return 2
    p = pad.GetPosition()
    px, py = p.x / UM, p.y / UM
    side = [pcbnew.LayerName(l) for l in pad.GetLayerSet().Seq()
            if l in (pcbnew.F_Cu, pcbnew.B_Cu)]
    lay = pcbnew.F_Cu if pcbnew.F_Cu in pad.GetLayerSet().Seq() else pcbnew.B_Cu
    print(f"{specA} net={pad.GetNetname()!r} at ({px:.3f},{py:.3f}) copper layers={side}")
    print(f"size {pad.GetSize().x / UM:.2f}x{pad.GetSize().y / UM:.2f}  type={pad.GetAttribute()}")

    # every other-net object on the pad's own copper layer, nearest first
    hits = []
    for t in board.GetTracks():
        if t.GetNetname() == pad.GetNetname():
            continue
        if t.Type() == pcbnew.PCB_VIA_T:
            q = t.GetPosition()
            d = math.hypot(q.x / UM - px, q.y / UM - py) - t.GetWidth(pcbnew.F_Cu) / UM / 2
            hits.append((d, "via", t.GetNetname(), "both"))
        elif t.GetLayer() == lay:
            sx, sy = t.GetStart().x / UM, t.GetStart().y / UM
            ex, ey = t.GetEnd().x / UM, t.GetEnd().y / UM
            dx, dy = ex - sx, ey - sy
            L2 = dx * dx + dy * dy
            tt = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - sx) * dx + (py - sy) * dy) / L2))
            d = math.hypot(px - (sx + tt * dx), py - (sy + tt * dy)) - t.GetWidth() / UM / 2
            hits.append((d, "track", t.GetNetname(), t.GetLayerName()))
    for fp in board.GetFootprints():
        for q in fp.Pads():
            if q.GetNetname() == pad.GetNetname():
                continue
            if lay not in q.GetLayerSet().Seq():
                continue
            if q is pad:
                continue
            bb = q.GetBoundingBox()
            bx0, by0, bx1, by1 = (bb.GetLeft() / UM, bb.GetTop() / UM,
                                  bb.GetRight() / UM, bb.GetBottom() / UM)
            ddx = max(bx0 - px, 0, px - bx1)
            ddy = max(by0 - py, 0, py - by1)
            hits.append((math.hypot(ddx, ddy), "pad", f"{fp.GetReference()}.{q.GetNumber()}",
                         q.GetLayerName()))
    hits.sort()
    print(f"\nnearest other-net copper on {pcbnew.LayerName(lay)} (gap from pad CENTRE, "
          f"minus object half-size):")
    for d, kind, name, where in hits[:10]:
        print(f"   {d:7.3f} mm  {kind:6s} {name:24s} {where}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
