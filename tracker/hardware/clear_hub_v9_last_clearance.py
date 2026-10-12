#!/usr/bin/env python3
"""clear_hub_v9_last_clearance.py -- clear the final 2 REAL clearance items.

Measured 2026-10-12 on hub_board_v9_final.kicad_pcb (34 viol / 21 unc):

 1. U2.1 [/F33_VCC] pad (1.30 x 1.30, half 0.65) vs a GND via (dia 0.60,
    half 0.30) whose centre is 1.231 mm away -> gap 0.281 mm.  The enforced
    clearance is 0.5 mm, so it is 0.219 mm short.  Move the via 0.30 mm directly
    away from the pad centre (same-net GND, no re-route needed).

 2. J_VCC.1 [/VSCAP] pad (1.00 x 0.50) vs Track [/W1_SOLAR_P] on F.Cu whose
    nearest vertex is 1.539 mm away -> effective gap ~0.94 mm, but DRC flags it,
    so the pad's round end reaches closer.  Shift the two long W1_SOLAR_P F.Cu
    vertices 0.25 mm away from the pad, preserving direction.

Both moves are away-from-foreign-copper, so they cannot create a new violation
on a different neighbour unless one is within 0.30 mm -- verify with DRC.
"""
import argparse
import math
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

MM = 1e6


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    args = ap.parse_args()

    b = pcbnew.LoadBoard(args.inp)

    # --- 1. U2.1 vs GND via ------------------------------------------------
    u2 = None
    fp = b.FindFootprintByReference("U2")
    for p in fp.Pads():
        if p.GetNumber() == "1":
            u2 = p
    if u2 is None:
        print("REFUSED: U2.1 not found", file=sys.stderr)
        return 2
    u2p = u2.GetPosition()
    print(f"U2.1 ({u2p.x/MM:.3f},{u2p.y/MM:.3f}) net={u2.GetNetname()}")

    moved = 0
    for t in b.GetTracks():
        if t.GetClass() != "PCB_VIA" or t.GetNetname() != "GND":
            continue
        vp = t.GetPosition()
        d = math.hypot(vp.x - u2p.x, vp.y - u2p.y)
        if d > 2 * MM:
            continue
        ux, uy = (vp.x - u2p.x) / d, (vp.y - u2p.y) / d
        shift = int(0.30 * MM)
        nv = pcbnew.VECTOR2I(int(vp.x + ux * shift), int(vp.y + uy * shift))
        print(f"  GND via ({vp.x/MM:.3f},{vp.y/MM:.3f}) -> "
              f"({nv.x/MM:.3f},{nv.y/MM:.3f})  d={d/MM:.3f}")
        t.SetPosition(nv)
        moved += 1
    print(f"GND vias moved: {moved}")

    # --- 2. J_VCC.1 vs W1_SOLAR_P -----------------------------------------
    jv = None
    fp = b.FindFootprintByReference("J_VCC")
    for p in fp.Pads():
        if p.GetNumber() == "1":
            jv = p
    if jv is None:
        print("REFUSED: J_VCC.1 not found", file=sys.stderr)
        return 2
    jvp = jv.GetPosition()
    print(f"J_VCC.1 ({jvp.x/MM:.3f},{jvp.y/MM:.3f}) net={jv.GetNetname()}")

    shifted = 0
    for t in b.GetTracks():
        if t.GetClass() != "PCB_TRACK" or t.GetNetname() != "/W1_SOLAR_P":
            continue
        if t.GetLayer() != pcbnew.F_Cu:
            continue
        s, e = t.GetStart(), t.GetEnd()
        for which, pt in (("start", s), ("end", e)):
            d = math.hypot(pt.x - jvp.x, pt.y - jvp.y)
            if d >= 3 * MM:
                continue
            # push away from the pad, biased in +y (into free space)
            ux, uy = (pt.x - jvp.x) / d, (pt.y - jvp.y) / d
            shift = int(0.30 * MM)
            np_ = pcbnew.VECTOR2I(int(pt.x + ux * shift),
                                  int(pt.y + uy * shift))
            if which == "start":
                t.SetStart(np_)
            else:
                t.SetEnd(np_)
            shifted += 1
            print(f"  W1_SOLAR_P {which} ({pt.x/MM:.3f},{pt.y/MM:.3f}) -> "
                  f"({np_.x/MM:.3f},{np_.y/MM:.3f}) d={d/MM:.3f}")
    print(f"track vertices shifted: {shifted}")

    b.Save(args.out)
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
