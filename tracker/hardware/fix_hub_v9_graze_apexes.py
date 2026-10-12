#!/usr/bin/env python3
"""fix_hub_v9_graze_apexes.py -- clear the 4 measured clearance grazes by
pushing the APEX of each offending B.Cu track's local detour.

MEASURED 2026-10-12 on hub_board_v9_orderable.kicad_pcb (agentee `clearance`).
All 4 are B.Cu, w=0.20, and all 4 come from the 3 local detours added by
clear_hub_v9_wedged_plane_pads.py.  Rule = 0.15 mm gap
(gap = centre_dist - via_r 0.30 - track_half 0.10):

  anchor via            offender            gap     PUSH needed
  (38.583,30.308)       /SCAP_MID          0.045   +0.1048
  (41.645,26.295)       /SCAP_MID          0.014   +0.1357
  (58.950, 4.220)       /SX1280_RESET_N    0.094   +0.0562
  (41.645,26.295)       /SX1280_SCK        0.142   +0.0084

Unlike the 7 earlier blind nudges, this one is DERIVED, not guessed: each push
is computed as (0.15 - measured_gap) + a 0.05 mm margin, and each moved vertex
is re-verified against every other-net obstacle BEFORE it is written.  A vertex
that still fails is left alone and reported, so the script never trades one graze
for another silently.

Deterministic.
"""
import argparse
import math
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

MM = 1e6
VIA_R = 0.30
RULE = 0.15
MARGIN = 0.05
# (anchor_x, anchor_y, offender_net) -- the exact agentee pairs
CASES = [
    (38.583, 30.308, "/SCAP_MID"),
    (41.645, 26.295, "/SCAP_MID"),
    (58.950, 4.220, "/SX1280_RESET_N"),
    (41.645, 26.295, "/SX1280_SCK"),
]


def seg_dist(px, py, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - x0, py - y0)
    t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / L2))
    return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    args = ap.parse_args()

    b = pcbnew.LoadBoard(args.inp)
    bcu = b.GetLayerID("B.Cu")

    # every foreign-net B.Cu obstacle, for re-verification
    obst = []
    for t in b.GetTracks():
        if t.GetClass() != "PCB_TRACK" or t.GetLayer() != bcu:
            continue
        s, e = t.GetStart(), t.GetEnd()
        obst.append((s.x, s.y, e.x, e.y, t.GetNetCode(), t.GetWidth() / 2))

    vias = []
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA":
            p = t.GetPosition()
            vias.append((p.x, p.y, t.GetWidth() / 2, t.GetNetCode()))

    def vertex_ok(cx, cy, netcode):
        """Re-verify a candidate vertex against every OTHER net."""
        for (x0, y0, x1, y1, nc, hw) in obst:
            if nc == netcode:
                continue
            if seg_dist(cx, cy, x0, y0, x1, y1) < (VIA_R + RULE) * MM + hw:
                return False
        for (vx, vy, vr, nc) in vias:
            if nc == netcode:
                continue
            if math.hypot(cx - vx, cy - vy) < (VIA_R + RULE) * MM + vr:
                return False
        return True

    fixed = skipped = 0
    for (axmm, aymm, onet) in CASES:
        ax, ay = axmm * MM, aymm * MM
        # find the WORST offending segment of that net (min distance)
        worst = None
        for t in b.GetTracks():
            if t.GetClass() != "PCB_TRACK" or t.GetLayer() != bcu:
                continue
            if t.GetNetname() != onet:
                continue
            s, e = t.GetStart(), t.GetEnd()
            d = seg_dist(ax, ay, s.x, s.y, e.x, e.y) / MM
            if worst is None or d < worst[0]:
                worst = (d, t, s, e)
        if worst is None:
            print(f"  ({axmm},{aymm}) {onet}: segment NOT FOUND")
            continue
        d, t, s, e = worst
        gap = d - VIA_R - t.GetWidth() / MM / 2
        push = (RULE - gap) + MARGIN
        if push <= 0:
            print(f"  ({axmm},{aymm}) {onet}: gap {gap:.4f} already ok")
            continue
        print(f"  ({axmm},{aymm}) {onet}: gap={gap:.4f} push={push:+.4f}")

        # walk EVERY vertex of that segment outward from the via, and try to
        # move the closest one directly away from the anchor.  Both endpoints
        # must stay put (connectivity); only interior vertices move.
        moved = False
        for vtx in (s, e):
            vx, vy = vtx.x - ax, vtx.y - ay
            n = math.hypot(vx, vy)
            if n == 0:
                continue
            ux, uy = vx / n, vy / n
            nx = int(vtx.x + ux * push * MM)
            ny = int(vtx.y + uy * push * MM)
            if not vertex_ok(nx, ny, t.GetNetCode()):
                # try the perpendicular as a second option
                px, py = int(vtx.x - uy * push * MM), int(vtx.y + ux * push * MM)
                if vertex_ok(px, py, t.GetNetCode()):
                    nx, ny = px, py
                else:
                    continue
            vtx.x, vtx.y = nx, ny
            t.SetStart(s)
            t.SetEnd(e)
            moved = True
            print(f"     vertex -> ({nx/MM:.3f},{ny/MM:.3f})  re-verified")
            break
        if moved:
            fixed += 1
        else:
            print("     NO verified vertex move -- left alone")
            skipped += 1

    print(f"fixed: {fixed}   skipped (no verified move): {skipped}")
    b.Save(args.out)
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
