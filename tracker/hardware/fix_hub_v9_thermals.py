#!/usr/bin/env python3
"""fix_hub_v9_thermals.py -- clear the last REAL thermal/clearance DRC items.

Started from hub_board_v9_plane_rail_filled.kicad_pcb (40 viol / 21 unc).

WHY (measured 2026-10-12):
 1. starved_thermal x4 on GND pads U3.2, U3.8, U7.2, U5.1.
    Widening the ZONE spoke width to 0.40 mm did NOT clear them (the zone can
    only form 1-2 spokes into these pads).  A solid zone connection removes the
    thermal-relief requirement entirely -- which is also electrically better for
    GND lands.  Pad-level, not zone-level.
 2. clearance x1 caused by US: the +3V3 blind via at (47.300,4.000) is 1.0 mm
    from U4's GND pad 3 at (47.300,5.000).  Move ONLY that via, minimally, away
    from the foreign pad.  (The previous polish script nudged 12 vias and made
    things WORSE -- 40 -> 44.  Surgical, not blanket.)

Deterministic; no router.
"""
import argparse
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

MM = 1e6
SOLID_PADS = [("U3", "2"), ("U3", "8"), ("U7", "2"), ("U5", "1")]
VIA_MOVE = (47.300, 4.000, 0.30)   # x_mm, y_mm, shift_mm (-y = away from U4.3)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    args = ap.parse_args()

    b = pcbnew.LoadBoard(args.inp)

    full = None
    for name in ("ZONE_CONNECTION_FULL", "PAD_ZONE_CONN_FULL"):
        if hasattr(pcbnew, name):
            full = getattr(pcbnew, name)
            break
    if full is None:
        print("REFUSED: no FULL zone-connection constant", file=sys.stderr)
        return 2
    print(f"FULL zone connection constant = {full}")

    # --- 1. solid zone connection on the starved GND pads --------------------
    n = 0
    for ref, pnum in SOLID_PADS:
        fp = b.FindFootprintByReference(ref)
        if fp is None:
            print(f"REFUSED: {ref} not found", file=sys.stderr)
            return 2
        for p in fp.Pads():
            if p.GetNumber() != pnum:
                continue
            if p.GetNetname() != "GND":
                print(f"REFUSED: {ref}.{pnum} net={p.GetNetname()} != GND",
                      file=sys.stderr)
                return 2
            # KiCad 9: the PAD setter is SetLocalZoneConnection (NOT
            # SetZoneConnection), and ZONE_CONNECTION_FULL == 2.
            p.SetLocalZoneConnection(full)
            n += 1
            print(f"  {ref}.{pnum} -> solid zone connection")
    print(f"pads set to solid: {n}")
    if n != len(SOLID_PADS):
        print("REFUSED: not all pads found", file=sys.stderr)
        return 2

    # --- 2. move ONLY the one offending via ---------------------------------
    vx, vy, shift = VIA_MOVE
    tx, ty = int(round(vx * MM)), int(round(vy * MM))
    moved = 0
    for t in b.GetTracks():
        from math import hypot
        if t.GetClass() != "PCB_VIA" or t.GetNetname() != "+3V3":
            continue
        pos = t.GetPosition()
        if hypot(pos.x - tx, pos.y - ty) < 1000:      # 1 um tolerance
            nv = pcbnew.VECTOR2I(pos.x, pos.y - int(round(shift * MM)))
            print(f"  via ({pos.x/MM:.3f},{pos.y/MM:.3f}) -> "
                  f"({nv.x/MM:.3f},{nv.y/MM:.3f})")
            t.SetPosition(nv)
            moved += 1
            break
    print(f"vias moved: {moved}")

    b.Save(args.out)
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
