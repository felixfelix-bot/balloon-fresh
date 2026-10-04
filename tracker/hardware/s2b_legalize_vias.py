#!/usr/bin/env python3.14
"""S2b: try to legalise the three via-in-pad clamps on the v8b fab candidate.

WHY
---
`v8b_krt_routed.kicad_pcb` (the fab candidate, sha 5c0193babc24) carries 3 vias at
0.45 mm / 0.20 mm drill where the frozen JLCPCB rule set (`jlcpcb-s1-frozen.kicad_dru`)
requires 0.60 mm / 0.30 mm. They are counted as 3 x `via_diameter` + 3 x
`drill_out_of_range`, i.e. 6 of the board's 10 residual violations, and they are the
only residual class that is not cosmetic silkscreen. PCB-S2 adjudicated them
"REAL - justified" on the grounds that no off-pad site exists for them.

That claim is checkable, so this script checks it instead of inheriting it.

METHOD
------
For each clamp via:
  1. enumerate the tracks that terminate on the via (per layer, per net);
  2. search a 0.025 mm grid over +/-6 mm for the nearest point where a 0.60 mm via
     disc keeps >= 0.20 mm to every FOREIGN pad / track / via, measured on exact
     geometry (rect distance for pads, point-segment for tracks), not bounding boxes;
  3. if a site exists, replace the via and re-attach the same tracks to the new
     position (topology preserved: same nets, same layers, same widths).

The board is written to a NEW file. The fab candidate is never edited: an experiment
that overwrites the artefact it is testing cannot be scored against it.

USAGE
-----
    /usr/bin/python3.14 s2b_legalize_vias.py <in.kicad_pcb> <out.kicad_pcb>
"""

from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

CLEAR_MM = 0.20
VIA_DIA_MM = 0.60
VIA_DRILL_MM = 0.30
GRID_MM = 0.025
SEARCH_MM = 6.0

NM = 1_000_000


def seg_point_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    l2 = dx * dx + dy * dy
    if l2 == 0.0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / l2))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def rect_dist(px, py, x1, y1, x2, y2):
    gx = max(x1 - px, 0.0, px - x2)
    gy = max(y1 - py, 0.0, py - y2)
    return math.hypot(gx, gy)


def build_obstacles(board):
    """Exact-geometry foreign-copper list. One entry per net-excluded object."""
    obst = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            net = pad.GetNetname()
            if not net:
                continue
            p = pad.GetPosition()
            s = pad.GetSize()
            obst.append((net, "rect",
                         (p.x - s.x / 2) / NM, (p.y - s.y / 2) / NM,
                         (p.x + s.x / 2) / NM, (p.y + s.y / 2) / NM,
                         f"{fp.GetReference()}.{pad.GetNumber()}"))
    for t in board.GetTracks():
        net = t.GetNetname()
        if not net:
            continue
        p = t.GetPosition()
        if t.Type() == pcbnew.PCB_VIA_T:
            r = t.GetWidth(t.TopLayer()) / 2 / NM
            obst.append((net, "circ", p.x / NM, p.y / NM, r, "via"))
        else:
            e = t.GetEnd()
            obst.append((net, "seg", p.x / NM, p.y / NM, e.x / NM, e.y / NM,
                         t.GetWidth() / 2 / NM, "seg"))
    return obst


def clear_gap(obst, cx, cy, net, vr):
    """Min clearance from a via disc (centre cx,cy, radius vr) to foreign copper."""
    worst = float("inf")
    for nnet, kind, *rest in obst:
        if nnet == net:
            continue
        if kind == "rect":
            d = rect_dist(cx, cy, *rest[:4])
        elif kind == "circ":
            d = math.hypot(cx - rest[0], cy - rest[1]) - rest[2]
        else:
            d = seg_point_dist(cx, cy, *rest[:4]) - rest[4]
        gap = d - vr
        if gap < worst:
            worst = gap
    return worst


def nearest_legal_site(obst, sx, sy, net):
    vr = VIA_DIA_MM / 2
    steps = int(SEARCH_MM / GRID_MM)
    best = None
    for ix in range(-steps, steps + 1):
        for iy in range(-steps, steps + 1):
            cx, cy = sx + ix * GRID_MM, sy + iy * GRID_MM
            gap = clear_gap(obst, cx, cy, net, vr)
            if gap < CLEAR_MM - 1e-9:
                continue
            dist = math.hypot(cx - sx, cy - sy)
            if best is None or dist < best[0]:
                best = (dist, cx, cy, gap)
    return best


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    src, dst = sys.argv[1], sys.argv[2]

    board = pcbnew.LoadBoard(src)

    # locate the clamps: vias whose geometry is below the frozen floor
    clamps = [t for t in board.GetTracks()
              if t.Type() == pcbnew.PCB_VIA_T
              and round(t.GetWidth(t.TopLayer()) / NM, 3) < VIA_DIA_MM - 1e-9]
    print(f"clamps found: {len(clamps)}")
    if not clamps:
        print("nothing to do")
        return 0

    obst = build_obstacles(board)
    moves = []

    for via in clamps:
        p = via.GetPosition()
        sx, sy = p.x / NM, p.y / NM
        net = via.GetNetname()

        # tracks terminating on this via, recorded as (other_end, layer, width)
        attached = []
        for t in board.GetTracks():
            if t is via or t.Type() == pcbnew.PCB_VIA_T:
                continue
            if t.GetNetname() != net:
                continue
            a, b = t.GetPosition(), t.GetEnd()
            if abs(a.x - p.x) < 2 and abs(a.y - p.y) < 2:
                attached.append((b, t.GetLayer(), t.GetWidth(), t))
            elif abs(b.x - p.x) < 2 and abs(b.y - p.y) < 2:
                attached.append((a, t.GetLayer(), t.GetWidth(), t))

        site = nearest_legal_site(obst, sx, sy, net)
        if site is None:
            print(f"  {net:9s} @({sx},{sy}) -> NO legal 0.6/0.3 site in "
                  f"+/-{SEARCH_MM} mm; left as-is (needs a re-route, not a nudge)")
            continue

        dist, cx, cy, gap = site
        print(f"  {net:9s} @({sx},{sy}) -> ({cx:.3f},{cy:.3f})  shift {dist:.3f} mm  "
              f"min gap {gap:.3f} mm   re-attaching {len(attached)} tracks")

        # pull the old copper, then re-lay it to the new via centre
        for _, _, _, t in attached:
            board.Remove(t)
        board.Remove(via)

        nv = pcbnew.PCB_VIA(board)
        nv.SetPosition(pcbnew.VECTOR2I(int(round(cx * NM)), int(round(cy * NM))))
        nv.SetWidth(int(round(VIA_DIA_MM * NM)))
        nv.SetDrill(int(round(VIA_DRILL_MM * NM)))
        nv.SetViaType(pcbnew.VIATYPE_THROUGH)
        nv.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        nv.SetNet(via.GetNet())
        board.Add(nv)

        for other, layer, width, t in attached:
            nt = pcbnew.PCB_TRACK(board)
            nt.SetStart(pcbnew.VECTOR2I(int(round(cx * NM)), int(round(cy * NM))))
            nt.SetEnd(other)
            nt.SetLayer(layer)
            nt.SetWidth(width)
            nt.SetNet(t.GetNet())
            board.Add(nt)

        moves.append((sx, sy, cx, cy, dist, gap, net))

    print(f"\nmoved {len(moves)}/{len(clamps)} clamps "
          f"({len(clamps) - len(moves)} have no legal site and are untouched)")

    pcbnew.SaveBoard(dst, board)
    print(f"wrote {dst}")

    # prove the edit landed and did not drift the placement
    chk = pcbnew.LoadBoard(dst)
    vias = [t for t in chk.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
    under = [v for v in vias if round(v.GetWidth(v.TopLayer()) / NM, 3) < VIA_DIA_MM - 1e-9]
    print(f"verify: footprints {len(list(chk.GetFootprints()))}  vias {len(vias)}  "
          f"still-under-floor {len(under)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
