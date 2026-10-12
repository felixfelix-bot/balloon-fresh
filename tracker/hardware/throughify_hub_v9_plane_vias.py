#!/usr/bin/env python3
"""throughify_hub_v9_plane_vias.py -- replace the blind +3V3 vias with THROUGH
vias that JLCPCB can actually drill, placed where B.Cu is clear.

WHY (measured 2026-10-12, agentee `via-lamination`):
  14 vias are declared `(via blind (layers "F.Cu" "In2.Cu"))`.  agentee reports
  they "cannot be drilled".  JLCPCB's STANDARD 4-layer service offers plated
  through vias only -- blind/buried is an HDI upgrade (3-5x cost) or a reject.
  A board carrying 14 blind vias is not orderable at the target price.

The earlier through-via attempt shorted B.Cu signal tracks, which is WHY blind
vias were chosen.  The fix is not "blind vs through" -- it is PLACEMENT: search
a small neighbourhood around each pad for a spot where a through via clears
every B.Cu item on a foreign net, and only then convert.

Deterministic; refuses (leaves blind) if no clear spot exists, so it can never
make the board worse silently.
"""
import argparse
import math
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

MM = 1e6
VIA_DIA = 0.6
VIA_DRILL = 0.3
STEP = 0.2                      # search step, mm
RINGS = 10                      # 2.0 mm search radius
CLEAR = 0.20                    # via-to-foreign-B.Cu clearance, mm


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    args = ap.parse_args()

    b = pcbnew.LoadBoard(args.inp)

    bcu = b.GetLayerID("B.Cu")
    fcu = b.GetLayerID("F.Cu")

    # B.Cu AND F.Cu obstacle segments.  A through via carries copper on EVERY
    # layer, so a move that clears B.Cu can still land on an F.Cu track -- that
    # is exactly the short we measured at (41.645, 27.295) vs /VSCAP.
    obstacles = []
    for t in b.GetTracks():
        if t.GetClass() != "PCB_TRACK":
            continue
        if t.GetLayer() not in (bcu, fcu):
            continue
        s, e = t.GetStart(), t.GetEnd()
        obstacles.append((s.x, s.y, e.x, e.y, t.GetNetCode(),
                          t.GetWidth() / 2, t.GetLayer()))
    print(f"F/B.Cu obstacle tracks: {len(obstacles)}")

    def dist_pt_seg(px, py, x0, y0, x1, y1):
        dx, dy = x1 - x0, y1 - y0
        L2 = dx * dx + dy * dy
        if L2 == 0:
            return math.hypot(px - x0, py - y0)
        t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / L2))
        return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))

    def clear_on_bcu(cx, cy, netcode, half):
        for (x0, y0, x1, y1, nc, oh, _lyr) in obstacles:
            if nc == netcode:
                continue
            d = dist_pt_seg(cx, cy, x0, y0, x1, y1)
            if d < half + oh + CLEAR * MM:
                return False
        return True

    # the blind +3V3 vias
    blinds = [t for t in b.GetTracks()
              if t.GetClass() == "PCB_VIA"
              and t.GetViaType() == pcbnew.VIATYPE_BLIND_BURIED]
    print(f"blind vias found: {len(blinds)}")

    converted = kept = 0
    for v in blinds:
        net = v.GetNetCode()
        home = v.GetPosition()
        half = int(VIA_DIA / 2 * MM)
        spot = None
        if clear_on_bcu(home.x, home.y, net, half):
            spot = (home.x, home.y)
        else:
            for ring in range(1, RINGS + 1):
                rad = int(ring * STEP * MM)
                for a in range(0, 360, 30):
                    ang = math.radians(a)
                    cx = home.x + int(round(rad * math.cos(ang)))
                    cy = home.y + int(round(rad * math.sin(ang)))
                    if clear_on_bcu(cx, cy, net, half):
                        spot = (cx, cy)
                        break
                if spot:
                    break
        if spot is None:
            kept += 1
            print(f"  ({home.x/MM:.3f},{home.y/MM:.3f}): NO clear B.Cu spot "
                  f"within {RINGS*STEP:.1f} mm -- left blind")
            continue
        v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetLayerPair(fcu, bcu)
        v.SetPosition(pcbnew.VECTOR2I(*spot))
        if spot != (home.x, home.y):
            print(f"  ({home.x/MM:.3f},{home.y/MM:.3f}) -> "
                  f"({spot[0]/MM:.3f},{spot[1]/MM:.3f})")
        converted += 1

    print(f"converted to through: {converted}   left blind: {kept}")
    b.Save(args.out)
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
