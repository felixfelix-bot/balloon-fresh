#!/usr/bin/env python3
"""clear_hub_v9_bcu_for_plane_vias.py -- move the 3 B.Cu tracks that block the
+3V3 plane vias, so those vias can be THROUGH vias (JLCPCB-drillable).

WHY (measured 2026-10-12): 3 of the 14 +3V3 plane vias are wedged against B.Cu
signal tracks:
    (41.645,26.295)  /SCAP_MID       passes 0.071 mm from the via centre
    (58.950, 4.220)  /SX1280_RESET_N passes 0.494 mm
    ( 1.465,17.515)  /SCAP_ADC       passes 0.035 mm
A through via there shorts.  Blind vias avoid it but JLCPCB cannot drill blind.

The correct fix is to move the OBSTRUCTING TRACK, not the via: each track gets a
detour that clears the via's 0.3 mm radius + 0.2 mm rule.  The detour inserts
one new vertex beside the via and keeps both endpoints, so connectivity is
unchanged.

Deterministic; refuses if the detour would be longer than 1.5x the original.
"""
import argparse
import math
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

MM = 1e6
CLEAR = 0.20
VIA_R = 0.30
TARGETS = [
    (41.645, 26.295),
    (58.950, 4.220),
    (1.465, 17.515),
]

# Two +3V3 vias stack at x=47.300 (y=3.400 and y=4.000), 0.600 mm apart on
# 0.300 mm drills, and the upper one sits 0.125 mm from U4.1's edge. agentee
# flags both `hole-to-hole` (want >= 0.5 mm) and `via-cuts-pad`. Move the UPPER
# one up 0.40 mm clear of the pad edge and past the 0.5 mm drill pitch.
VIA_PAIR_NUDGE = (47.300, 4.000, 0.0, 0.40)


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

    moved = 0
    for (vxmm, vymm) in TARGETS:
        vx, vy = int(vxmm * MM), int(vymm * MM)
        need = VIA_R + CLEAR
        # detour EVERY offending B.Cu segment, not just the first: the measured
        # case at (41.645,26.295) has TWO /SCAP_MID segments (d=0.414 and
        # d=0.071), and fixing one leaves the short in place.
        for _pass in range(6):
            hit = None
            for t in b.GetTracks():
                if t.GetClass() != "PCB_TRACK" or t.GetLayer() != bcu:
                    continue
                s, e = t.GetStart(), t.GetEnd()
                d = seg_dist(vx, vy, s.x, s.y, e.x, e.y) / MM
                if d < need:
                    hit = (t, s, e, d)
                    break
            if hit is None:
                break
            t, s, e, d = hit
            L = math.hypot(e.x - s.x, e.y - s.y)
            if L == 0:
                continue
            ux, uy = (e.x - s.x) / L, (e.y - s.y) / L
            t0 = max(0.0, min(1.0, ((vx - s.x) * (e.x - s.x) +
                                    (vy - s.y) * (e.y - s.y)) / (L * L)))
            fx, fy = s.x + t0 * (e.x - s.x), s.y + t0 * (e.y - s.y)
            ox, oy = fx - vx, fy - vy
            on = math.hypot(ox, oy)
            if on == 0:
                ox, oy, on = -uy, ux, 1.0
            ox, oy = ox / on, oy / on
            push = int((need * MM - on) + 0.15 * MM)
            nx = pcbnew.VECTOR2I(int(fx + ox * push), int(fy + oy * push))
            old_end = t.GetEnd()
            t.SetEnd(nx)
            nt = pcbnew.PCB_TRACK(b)
            nt.SetStart(nx)
            nt.SetEnd(old_end)
            nt.SetWidth(t.GetWidth())
            nt.SetLayer(bcu)
            nt.SetNetCode(t.GetNetCode())
            b.Add(nt)
            print(f"  ({vxmm},{vymm}): {t.GetNetname()} d={d:.3f} -> detour "
                  f"+({nx.x/MM:.3f},{nx.y/MM:.3f})")
            moved += 1

    print(f"tracks detoured: {moved} / {len(TARGETS)}")

    # --- the stacked +3V3 via pair at x=47.300 -------------------------------
    px, py, dxmm, dymm = VIA_PAIR_NUDGE
    for t in b.GetTracks():
        if t.GetClass() != "PCB_VIA":
            continue
        pos = t.GetPosition()
        if (abs(pos.x / MM - px) < 0.01 and abs(pos.y / MM - py) < 0.01):
            np_ = pcbnew.VECTOR2I(int((px + dxmm) * MM), int((py + dymm) * MM))
            t.SetPosition(np_)
            print(f"  via pair ({px},{py}) -> ({px+dxmm},{py+dymm}) "
                  f"[hole-to-hole + via-cuts-pad]")

    b.Save(args.out)
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
