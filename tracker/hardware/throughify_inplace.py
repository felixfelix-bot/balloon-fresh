#!/usr/bin/env python3
"""throughify_inplace.py -- convert blind vias to THROUGH vias IN PLACE.

WHY (measured 2026-10-12, corrected): the earlier throughify script MOVED vias
to find clear B.Cu, and every move risked a new short against F.Cu pads/zones.
That was unnecessary.  The +3V3 plane is on In2.Cu; B.Cu is a GND plane.  A
through via from F.Cu to In2.Cu passes through B.Cu BY DESIGN -- the GND zone
forms an antipad around it automatically (that is what a zone fill is for).  The
only real question is whether the via is on a foreign net's TRACK, and the three
such cases were already cleared by clear_hub_v9_bcu_for_plane_vias.py.

So: change VIATYPE_BLIND_BURIED -> VIATYPE_THROUGH and set the layer pair to
F.Cu..B.Cu, WITHOUT touching the position.  Then refill the zones.

Deterministic.
"""
import argparse
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    args = ap.parse_args()

    b = pcbnew.LoadBoard(args.inp)
    fcu, bcu = b.GetLayerID("F.Cu"), b.GetLayerID("B.Cu")

    n = 0
    for t in b.GetTracks():
        if t.GetClass() != "PCB_VIA":
            continue
        if t.GetViaType() != pcbnew.VIATYPE_BLIND_BURIED:
            continue
        pos = t.GetPosition()
        t.SetViaType(pcbnew.VIATYPE_THROUGH)
        t.SetLayerPair(fcu, bcu)
        n += 1
        print(f"  ({pos.x/1e6:.3f},{pos.y/1e6:.3f}) -> through (in place)")

    print(f"converted in place: {n}")
    b.Save(args.out)
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
