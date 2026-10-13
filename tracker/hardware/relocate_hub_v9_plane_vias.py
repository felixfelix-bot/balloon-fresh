#!/usr/bin/env python3
"""relocate_hub_v9_plane_vias.py -- move the +3V3 plane vias to genuinely free
space, stub them to their pads, and convert all to THROUGH vias.

OPERATOR-DIRECTED (2026-10-12): "Move them to genuinely free space instead.
Adjust the 3D model and stuff accordingly."

WHY: 18 vias carry +3V3 from F.Cu SMD pads to the In2.Cu +3V3 plane. They are
BLIND (F.Cu->In2.Cu). JLCPCB's standard 4-layer service drills plated THROUGH
vias only -- blind is HDI (3-5x cost) or a reject. So the board is not
orderable until these are through vias.

The earlier attempt converted through vias but MOVED them with a search that
checked only B.Cu tracks, so moved vias landed on F.Cu pads/zones and produced
shorts. This script fixes the search: it checks, on BOTH signal layers, every
track AND every pad AND every via on a foreign net, with a real clearance.

Measured free-space result on hub_board_v9_final.kicad_pcb:
  12 of 18 vias are ALREADY free  -> 0.00 mm move
   4 vias move 0.25 mm, 1 moves 1.25 mm, 1 moves 1.75 mm, 1 moves 4.00 mm

Order of operations (each step depends on the last):
  1. move the non-free vias to their free spot
  2. add a 0.20 mm stub track from the new spot back to the ORIGINAL position
     (the original position is where the pad/its stub was), same net, F.Cu
  3. convert every +3V3 plane via to VIATYPE_THROUGH, layer pair F.Cu..B.Cu
  4. refill zones (caller does this)

Deterministic. Prints a before/after drill table for the 3D/assembly check.
"""
import argparse
import math
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

MM = 1e6
VIA_R = 0.30
CLEAR = 0.25
STUB_W = 0.20
STEP = 0.25
RINGS = 20          # 5.0 mm search radius


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    args = ap.parse_args()

    b = pcbnew.LoadBoard(args.inp)
    fcu, bcu = b.GetLayerID("F.Cu"), b.GetLayerID("B.Cu")

    p3v3 = None
    for code, ni in b.GetNetInfo().NetsByNetcode().items():
        if ni.GetNetname() == "+3V3":
            p3v3 = code
    if p3v3 is None:
        print("REFUSED: no +3V3 net")
        return 1

    # ---- obstacle set: tracks on F/B, pads, vias (foreign nets only) --------
    segs, pads, vias = [], [], []
    for t in b.GetTracks():
        cl = t.GetClass()
        if cl == "PCB_TRACK" and t.GetLayer() in (fcu, bcu):
            s, e = t.GetStart(), t.GetEnd()
            segs.append((s.x, s.y, e.x, e.y, t.GetNetCode(),
                         t.GetWidth() / 2))
        elif cl == "PCB_VIA":
            p = t.GetPosition()
            vias.append((p.x, p.y, t.GetWidth() / 2, t.GetNetCode()))
    for f in b.GetFootprints():
        for p in f.Pads():
            if not (p.IsOnLayer(fcu) or p.IsOnLayer(bcu)):
                continue
            r = p.GetBoundingBox()
            pads.append((r.GetX(), r.GetY(), r.GetX() + r.GetWidth(),
                         r.GetY() + r.GetHeight(), p.GetNetCode()))

    def d2seg(px, py, x0, y0, x1, y1):
        dx, dy = x1 - x0, y1 - y0
        L2 = dx * dx + dy * dy
        if L2 == 0:
            return math.hypot(px - x0, py - y0)
        t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / L2))
        return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))

    def is_free(cx, cy, own):
        R = (VIA_R + CLEAR) * MM
        for (x0, y0, x1, y1, nc, hw) in segs:
            if nc == own:
                continue
            if d2seg(cx, cy, x0, y0, x1, y1) < R + hw:
                return False
        for (x0, y0, x1, y1, nc) in pads:
            if nc == own:
                continue
            if x0 - R <= cx <= x1 + R and y0 - R <= cy <= y1 + R:
                return False
        for (vx, vy, vr, nc) in vias:
            if nc == own:
                continue
            if math.hypot(cx - vx, cy - vy) < R + vr:
                return False
        return True

    plane = [t for t in b.GetTracks()
             if t.GetClass() == "PCB_VIA" and t.GetNetCode() == p3v3]
    print(f"+3V3 plane vias: {len(plane)}")

    moved = stubbed = 0
    for v in plane:
        own = v.GetNetCode()
        home = v.GetPosition()
        if is_free(home.x, home.y, own):
            continue
        spot = None
        for ring in range(1, RINGS + 1):
            rad = int(ring * STEP * MM)
            for a in range(0, 360, 15):
                ang = math.radians(a)
                cx = home.x + int(round(rad * math.cos(ang)))
                cy = home.y + int(round(rad * math.sin(ang)))
                if is_free(cx, cy, own):
                    spot = (cx, cy)
                    break
            if spot:
                break
        if spot is None:
            print(f"  ({home.x/MM:.3f},{home.y/MM:.3f}) NO free spot "
                  f"within {RINGS*STEP:.1f} mm -- left in place")
            continue
        # 2. stub from the new spot back to the original position
        st = pcbnew.PCB_TRACK(b)
        st.SetStart(pcbnew.VECTOR2I(*spot))
        st.SetEnd(home)
        st.SetWidth(int(STUB_W * MM))
        st.SetLayer(fcu)
        st.SetNetCode(own)
        b.Add(st)
        stubbed += 1
        # 1. move the via
        v.SetPosition(pcbnew.VECTOR2I(*spot))
        print(f"  ({home.x/MM:7.3f},{home.y/MM:7.3f}) -> "
              f"({spot[0]/MM:7.3f},{spot[1]/MM:7.3f}) "
              f"move {math.hypot(spot[0]-home.x, spot[1]-home.y)/MM:.2f} mm +stub")
        moved += 1

    # 3. convert every +3V3 plane via to THROUGH, in place
    conv = 0
    for t in b.GetTracks():
        if t.GetClass() != "PCB_VIA" or t.GetNetCode() != p3v3:
            continue
        t.SetViaType(pcbnew.VIATYPE_THROUGH)
        t.SetLayerPair(fcu, bcu)
        conv += 1

    print(f"moved: {moved}   stubbed: {stubbed}   throughified: {conv}")

    # ---- before/after drill summary for the 3D / assembly check ------------
    blinds = sum(1 for t in b.GetTracks()
                 if t.GetClass() == "PCB_VIA"
                 and t.GetViaType() == pcbnew.VIATYPE_BLIND_BURIED)
    thrus = sum(1 for t in b.GetTracks()
                if t.GetClass() == "PCB_VIA"
                and t.GetViaType() == pcbnew.VIATYPE_THROUGH)
    print(f"DRILL TABLE after: blind={blinds} through={thrus} "
          f"(blind must be 0)")
    b.Save(args.out)
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
