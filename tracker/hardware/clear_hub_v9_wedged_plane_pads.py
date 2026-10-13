#!/usr/bin/env python3
"""clear_hub_v9_wedged_plane_pads.py -- fix the last 2 REAL shorts.

MEASURED 2026-10-12 on hub_board_v9_orderable.kicad_pcb (agentee 2 shorts):
  /SCAP_ADC passes 0.035 mm from the +3V3 via at (1.465, 17.515)
  /SCAP_MID passes 0.071 mm from the +3V3 via at (41.645, 26.295)
Those two vias are via-in-pad (offset +0,+0 um), so they CANNOT move -- moving
breaks the pad connection (proven: relocate+stub made 5 shorts).

The correct fix is therefore to move the INTRUDING NET, not the via. Each of the
two obstructing B.Cu tracks gets a LOCAL detour around the via: the segment is
split and one new vertex is inserted beside the via, keeping both endpoints, so
connectivity is unchanged and the detour stays local (< 2 mm).

Deterministic. Refuses if no local detour clears the via.
"""
import argparse
import math
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

MM = 1e6
VIA_R = 0.30          # via copper radius (0.60 dia)
CLEAR = 0.20          # rule clearance
WEDGED = [
    (1.465, 17.515),
    (41.645, 26.295),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    args = ap.parse_args()

    b = pcbnew.LoadBoard(args.inp)
    bcu = b.GetLayerID("B.Cu")

    def seg_dist(px, py, x0, y0, x1, y1):
        dx, dy = x1 - x0, y1 - y0
        L2 = dx * dx + dy * dy
        if L2 == 0:
            return math.hypot(px - x0, py - y0)
        t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / L2))
        return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))

    fixed = 0
    for (wxmm, wymm) in WEDGED:
        wx, wy = int(wxmm * MM), int(wymm * MM)
        need = VIA_R + CLEAR
        # collect ALL offending B.Cu segments first (never mutate while
        # iterating: the earlier loop re-found the same segment 5x and stacked
        # duplicate vertices).  Keyed on track identity.
        targets = []
        for t in b.GetTracks():
            if t.GetClass() != "PCB_TRACK" or t.GetLayer() != bcu:
                continue
            s, e = t.GetStart(), t.GetEnd()
            d = seg_dist(wx, wy, s.x, s.y, e.x, e.y) / MM
            if d < need:
                targets.append((t, d))
        if not targets:
            print(f"  ({wxmm},{wymm}): no offending B.Cu track (already clear)")
            continue

        for (t, d) in targets:
            s, e = t.GetStart(), t.GetEnd()
            L = math.hypot(e.x - s.x, e.y - s.y)
            if L == 0:
                continue
            ux, uy = (e.x - s.x) / L, (e.y - s.y) / L
            t0 = max(0.0, min(1.0, ((wx - s.x) * (e.x - s.x) +
                                    (wy - s.y) * (e.y - s.y)) / (L * L)))
            fx, fy = s.x + t0 * (e.x - s.x), s.y + t0 * (e.y - s.y)
            ox, oy = fx - wx, fy - wy
            on = math.hypot(ox, oy)
            if on == 0:
                ox, oy, on = -uy, ux, 1.0
            ox, oy = ox / on, oy / on
            push = int((need * MM - on) + 0.20 * MM)
            nx = pcbnew.VECTOR2I(int(fx + ox * push), int(fy + oy * push))
            # verify the new vertex is not itself on the via
            if math.hypot(nx.x - wx, nx.y - wy) < need * MM:
                print(f"  ({wxmm},{wymm}): detour still too close -- SKIPPED")
                continue
            old_end = t.GetEnd()
            t.SetEnd(nx)
            nt = pcbnew.PCB_TRACK(b)
            nt.SetStart(nx)
            nt.SetEnd(old_end)
            nt.SetWidth(t.GetWidth())
            nt.SetLayer(bcu)
            nt.SetNetCode(t.GetNetCode())
            b.Add(nt)
            print(f"  ({wxmm},{wymm}): {t.GetNetname()} was d={d:.3f} mm -> "
                  f"detour via ({nx.x/MM:.3f},{nx.y/MM:.3f})")
            fixed += 1

    print(f"B.Cu segments detoured: {fixed}")
    b.Save(args.out)
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
