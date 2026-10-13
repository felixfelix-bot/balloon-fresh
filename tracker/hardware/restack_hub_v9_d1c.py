#!/usr/bin/env python3
"""restack_hub_v9_d1c.py -- implement D1-corrected per the Astra verdict
(2026-10-13, CHANGES_REQUESTED; docs/CONSULT-astra-stackup-2026-10-13.txt).

BEFORE (measured):
  F.Cu   signal (385 tracks)      AFTER:
  In1.Cu GND plane (10 286 mm2)     F.Cu   signal     (unchanged)
  In2.Cu +3V3 plane (10 111 mm2)    In1.Cu GND plane  (unchanged -- F.Cu RF ref)
  B.Cu   signal (153 tracks)        In2.Cu SIGNAL     (freed escape layer)
                                    B.Cu   signal + +3V3 POUR (new)

Steps (deterministic, reversible from git):
  1. Move the In2.Cu +3V3 zone to B.Cu as a POUR (keepout-shaped, same net).
     A power PLANE becomes a POUR: lower priority than B.Cu signal so tracks
     keep clearances; refill carves around them.
  2. Leave In2.Cu EMPTY for the router.
  3. Report: zone areas before/after, layer track counts, the 14 +3V3 pads
     that the consultant made the first verification gate.

Does NOT route anything -- routing happens after, via agentee on the freed
In2.Cu. Refill + pad-connectivity + DRC are separate verification steps.
"""
import argparse
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
    in2 = b.GetLayerID("In2.Cu")
    bcu = b.GetLayerID("B.Cu")

    print("=== BEFORE ===")
    moved = 0
    for z in list(b.Zones()):
        if z.GetLayer() == in2:
            net = z.GetNetname()
            area = z.GetFilledArea() / 1e12
            print(f"  In2.Cu zone: net={net} filled={area:.0f} mm2 -> moving to B.Cu")
            z.SetLayer(bcu)
            # a pour, not a plane: lower priority than signal so refill carves
            z.SetAssignedPriority(1)
            # stale In2.Cu fill polys are per-layer; refill regenerates on B.Cu
            z.UnFill()
            moved += 1
    if moved == 0:
        print("  (no In2.Cu zone found -- nothing to do?)")

    b.Save(args.out)

    # verify by re-loading
    b2 = pcbnew.LoadBoard(args.out)
    print("=== AFTER (reloaded) ===")
    for ln in ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu"):
        lid = b2.GetLayerID(ln)
        tracks = sum(1 for t in b2.GetTracks()
                     if t.GetClass() != "PCB_VIA" and t.GetLayer() == lid)
        zones = [(z.GetNetname(), z.GetFilledArea() / 1e12)
                 for z in b2.Zones() if z.GetLayer() == lid]
        zs = " ".join(f"{n}:{a:.0f}mm2" for n, a in zones)
        print(f"  {ln:6s} tracks={tracks:4d} zones=[{zs}]")

    # the consultant's first verification gate: the 14 +3V3 F.Cu pads
    p3 = None
    for code, ni in b2.GetNetInfo().NetsByNetcode().items():
        if ni.GetNetname() == "+3V3":
            p3 = code
    pads = [(f.GetReference(), p.GetNumber()) for f in b2.GetFootprints()
            for p in f.Pads() if p.GetNetCode() == p3]
    print(f"=== +3V3 pads (gate: ALL must connect on the B.Cu pour): {len(pads)} ===")
    print("   " + " ".join(f"{r}.{n}" for r, n in pads))
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
