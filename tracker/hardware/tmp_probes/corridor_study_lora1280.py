#!/usr/bin/env python3
"""Corridor study for the LoRa1280 site on hub v10 (ADR-139 step 4).

Answers ONE question by measurement: for the new 16x16 / 2.00 mm-pitch / 14.30 mm-row land
pattern on B.Cu, which of the four escape directions from each pad row has clear copper?

Method
------
Rasterise copper obstacles onto a 0.25 mm grid per copper layer:
  * tracks   -> point-to-segment distance <= half_width + clearance
  * vias     -> point-to-via distance <= via_radius + clearance (all copper layers)
  * pads     -> point-to-pad distance <= pad_half + clearance, on the layers the pad covers
Zones are deliberately EXCLUDED: pours re-clear around new copper on refill, so counting
them as obstacles would report "blocked" for copper that will simply step aside.

Then, from each pad row's midpoint, march a 2.0 mm-wide corridor outward in each of the
four directions and record how far it stays free. That is the number that decides whether
a net can escape.

This is the same measured-not-assumed discipline as docs/analysis/HUB-RADIO-LINK-BLOCKER.md.
"""
from __future__ import annotations

import argparse
import math
import sys

import pcbnew

MM = 1_000_000
STEP = 0.25          # grid, mm
CORRIDOR_HALF = 1.0  # corridor half-width, mm  (2.0 mm wide)
REACH = 16.0         # how far to march, mm


def seg_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / L2))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


class Obstacles:
    def __init__(self, board, skip_ref):
        self.board = board
        self.seg = {pcbnew.F_Cu: [], pcbnew.B_Cu: []}
        self.circ = {pcbnew.F_Cu: [], pcbnew.B_Cu: []}
        self.clearance = board.GetDesignSettings().m_MinClearance / MM
        if self.clearance <= 0:
            self.clearance = 0.2
        for t in board.GetTracks():
            if isinstance(t, pcbnew.PCB_VIA):
                r = (t.GetWidth() / 2.0) / MM
                for lay in (pcbnew.F_Cu, pcbnew.B_Cu):
                    if t.IsOnLayer(lay):
                        self.circ[lay].append((t.GetPosition().x / MM,
                                               t.GetPosition().y / MM, r))
            else:
                lay = t.GetLayer()
                if lay in self.seg:
                    w = (t.GetWidth() / 2.0) / MM
                    s, e = t.GetStart(), t.GetEnd()
                    self.seg[lay].append((s.x / MM, s.y / MM, e.x / MM, e.y / MM, w))
        for f in board.GetFootprints():
            if f.GetReference() == skip_ref:
                continue
            for p in f.Pads():
                try:
                    if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                        continue
                    sz = p.GetSize()
                    r = max(sz.x, sz.y) / 2.0 / MM
                    c = p.GetPosition()
                    ls = p.GetLayerSet()
                    for lay in (pcbnew.F_Cu, pcbnew.B_Cu):
                        if ls.Contains(lay):
                            self.circ[lay].append((c.x / MM, c.y / MM, r))
                except Exception:
                    continue

    def blocked(self, lay, x, y) -> bool:
        m = self.clearance
        for x1, y1, x2, y2, w in self.seg[lay]:
            if seg_dist(x, y, x1, y1, x2, y2) <= w + m:
                return True
        for cx, cy, r in self.circ[lay]:
            if math.hypot(x - cx, y - cy) <= r + m:
                return True
        return False

    def corridor(self, lay, x, y, dx, dy) -> float:
        """March from (x,y) along (dx,dy). Returns free length in mm."""
        d = 0.0
        while d <= REACH:
            cx, cy = x + dx * d, y + dy * d
            for off in (-CORRIDOR_HALF, 0.0, CORRIDOR_HALF):
                # offset perpendicular to travel
                ox, oy = -dy * off, dx * off
                if self.blocked(lay, cx + ox, cy + oy):
                    return d
            d += STEP
        return REACH


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", default="tracker/hardware/hub_board_v10.kicad_pcb")
    a = ap.parse_args(argv)

    b = pcbnew.LoadBoard(a.board)
    fp = next((f for f in b.GetFootprints() if f.GetReference() == "U_LORA1280"), None)
    if fp is None:
        print("no U_LORA1280 on the board")
        return 1
    occ = Obstacles(b, "U_LORA1280")
    print(f"clearance {occ.clearance:.2f} mm | obstacles F.Cu "
          f"{len(occ.seg[pcbnew.F_Cu])}seg+{len(occ.circ[pcbnew.F_Cu])}cir, "
          f"B.Cu {len(occ.seg[pcbnew.B_Cu])}seg+{len(occ.circ[pcbnew.B_Cu])}cir")

    # geometry of the placed part: rows are the two lines carrying pins 1-8 and 9-16
    pads = {int(p.GetNumber()): p for p in fp.Pads()}
    rowA = [pads[i] for i in range(1, 9)]
    rowB = [pads[i] for i in range(9, 17)]
    for name, row in (("row 1-8", rowA), ("row 9-16", rowB)):
        xs = [p.GetPosition().x / MM for p in row]
        ys = [p.GetPosition().y / MM for p in row]
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        print(f"\n{name}: midpoint ({mx:.2f},{my:.2f})  span {max(xs)-min(xs):.2f} mm  "
              f"x {min(xs):.2f}..{max(xs):.2f}  y {min(ys):.2f}..{max(ys):.2f}")
        for label, dx, dy in (("NORTH(-y)", 0, -1), ("SOUTH(+y)", 0, 1),
                              ("WEST(-x)", -1, 0), ("EAST(+x)", 1, 0)):
            for lay, lname in ((pcbnew.B_Cu, "B.Cu"), (pcbnew.F_Cu, "F.Cu")):
                got = occ.corridor(lay, mx, my, dx, dy)
                flag = "  <-- CLEAR to reach" if got >= REACH else ""
                print(f"   {label:<10} {lname:<5} {got:5.2f} mm{flag}")

    # board edges
    bb = b.GetBoardEdgesBoundingBox()
    print(f"\nboard {bb.GetWidth()/MM:.2f} x {bb.GetHeight()/MM:.2f} mm")
    return 0


if __name__ == "__main__":
    sys.exit(main())
