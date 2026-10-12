#!/usr/bin/env python3
"""polish_hub_v9_drc.py -- clear the last REAL DRC items on the hub plane rail.

Two deterministic fixes, both measured 2026-10-12:

1. starved_thermal (4: U3 pads 2/8, U7 pad 2, U5 pad 1).
   Root cause: the GND zones use thermal spoke width 0.300 mm, below the
   ~0.4 mm these pads need to get a full spoke. Widen to 0.4 mm.

2. clearance (1 of 3 caused by us: U4 pad3 [GND] vs our +3V3 blind via).
   Root cause: the via was placed dead-centre on a +3V3 pad at (47.300,4.000),
   which is only 1.0 mm from U4's GND pad 3 at (47.300,5.000). Move that via
   away from the foreign pad (to the far side of its own pad).

Deterministic -- no LLM, no router.
"""
import argparse
import json
import math
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

MM = 1e6
SPOKE_MM = 0.40
CLEAR_MM = 0.50          # via-to-foreign-copper target


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    args = ap.parse_args()

    b = pcbnew.LoadBoard(args.inp)

    # --- fix 1: widen thermal spokes on every zone ---------------------------
    n = 0
    for z in b.Zones():
        if z.GetThermalReliefSpokeWidth() < int(SPOKE_MM * MM):
            z.SetThermalReliefSpokeWidth(int(SPOKE_MM * MM))
            n += 1
    print(f"zones with widened spokes: {n} (-> {SPOKE_MM} mm)")

    # --- fix 2: nudge +3V3 vias that sit too close to a foreign pad ----------
    # Gather foreign copper: every pad not on +3V3, with its position + radius.
    foreign = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() == "+3V3":
                continue
            pos = p.GetPosition()
            r = max(p.GetSize().x, p.GetSize().y) / 2
            foreign.append((pos.x, pos.y, r, f"{fp.GetReference()}.{p.GetNumber()}"))

    moved = 0
    for t in b.GetTracks():
        if t.GetClass() != "PCB_VIA" or t.GetNetname() != "+3V3":
            continue
        vpos = t.GetPosition()
        half = t.GetWidth(pcbnew.F_Cu) / 2
        for (fx, fy, fr, name) in foreign:
            d = math.hypot(vpos.x - fx, vpos.y - fy)
            need = half + fr + int(CLEAR_MM * MM)
            if d < need:
                # push the via directly away from the foreign pad
                if d == 0:
                    continue
                ux, uy = (vpos.x - fx) / d, (vpos.y - fy) / d
                shift = need - d + int(0.05 * MM)
                nv = pcbnew.VECTOR2I(int(vpos.x + ux * shift),
                                     int(vpos.y + uy * shift))
                print(f"  via ({vpos.x/MM:.3f},{vpos.y/MM:.3f}) -> "
                      f"({nv.x/MM:.3f},{nv.y/MM:.3f})  away from {name}")
                t.SetPosition(nv)
                moved += 1
                break
    print(f"+3V3 vias nudged: {moved}")

    b.Save(args.out)
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
