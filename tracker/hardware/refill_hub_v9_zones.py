#!/usr/bin/env python3
"""refill_hub_v9_zones.py -- refill every zone after geometry changes.

WHY (measured 2026-10-12): adding +3V3 vias without refilling left the GND
zones with stale fills that had no antipads for the new vias -> 67 bogus
clearance/hole_clearance violations.  A fill is only valid for the geometry it
was computed against.  Any script that adds/removes vias or tracks MUST refill
before DRC, exactly like the GND-stitching step.

KiCad 9 pitfall: the zone filler must be run via ZONE_FILLER with a progress
reporter, and board.BuildConnectivity() first.
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

    board = pcbnew.LoadBoard(args.inp)
    board.BuildConnectivity()
    filler = pcbnew.ZONE_FILLER(board)
    zones = list(board.Zones())
    print(f"zones: {len(zones)}")
    ok = filler.Fill(zones)
    print(f"fill returned: {ok}")
    for z in zones:
        print(f"  {board.GetLayerName(z.GetLayer()):6s} {z.GetNetname():8s} "
              f"{z.GetFilledArea()/1e12:9.0f} mm2")
    board.Save(args.out)
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
