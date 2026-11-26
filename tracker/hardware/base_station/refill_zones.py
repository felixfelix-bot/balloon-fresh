#!/usr/bin/env python3
"""Refill every zone on a board and save -- the step that makes pad-vs-zone DRC meaningful.

WHY THIS EXISTS
---------------
`kicad-cli pcb drc` grades copper against the zone's FILLED polygons. A board whose
`filled_polygon` blocks were written before the parts were placed carries a pour that is a
single unbroken rectangle covering every non-GND pad, so DRC reports each of them as a
clearance violation with `actual 0.0000 mm` -- a number that cannot change because the
polygon contains the pad by construction.

Measured on the base station: 37 `clearance` + 37 `solder_mask_bridge`, ALL of them
pad-vs-zone, ALL on two footprints (U_FLASH, U_VGA). One refill takes the board from
143 violations to 69 with the same 63 unconnected records, and the measured pad-to-pour gap
on those same 74 items goes from 0.0000 mm to exactly 0.2005 mm against a 0.200 mm zone
rule. Nothing about the parts moved; only the pour was recomputed.

This is NOT a rule relaxation. The zone rule is untouched (`(connect_pads (clearance 0.2))`
in the board, read back after the fill). It is the difference between grading against copper
that exists and copper that was never computed.

Usage:
  refill_zones.py BOARD.kicad_pcb [-o OUT.kicad_pcb] [--json REPORT.json]

Exit: 0 = all zones filled and saved, 1 = a zone stayed unfilled, 2 = could not run.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("board")
    ap.add_argument("-o", "--out")
    ap.add_argument("--json")
    a = ap.parse_args()

    try:
        import pcbnew
    except ImportError as exc:
        print(f"REFUSED: pcbnew not importable under {sys.executable}: {exc}")
        print("  run with: PYTHONPATH=/usr/lib/python3/dist-packages /usr/bin/python3")
        return 2

    if not os.path.exists(a.board):
        print(f"REFUSED: board not found: {a.board}")
        return 2

    b = pcbnew.LoadBoard(a.board)
    if b is None:
        print(f"REFUSED: cannot load {a.board}")
        return 2

    zones = list(b.Zones())
    before = [(z.GetNetname(), pcbnew.LayerName(z.GetLayer()), z.IsFilled()) for z in zones]
    print(f"board        : {a.board}")
    print(f"zones        : {len(zones)}")
    for n, l, f in before:
        print(f"   {n:10s} {l:8s} filled={f}")

    if not zones:
        print("REFUSED: no zones -- nothing to fill, and this script is not a no-op gate")
        return 2

    filler = pcbnew.ZONE_FILLER(b)
    filler.Fill(zones)

    still = [f"{z.GetNetname()} on {pcbnew.LayerName(z.GetLayer())}" for z in zones if not z.IsFilled()]
    out = a.out or a.board
    pcbnew.SaveBoard(out, b)
    print(f"saved        : {out}")
    if still:
        print(f"UNFILLED     : {len(still)} zone(s) still unfilled: {still}")
        return 1

    # read the saved file back: a fill that did not persist is not a fill
    check = pcbnew.LoadBoard(out)
    n_poly = sum(1 for z in check.Zones())
    unfilled = [pcbnew.LayerName(z.GetLayer()) for z in check.Zones() if not z.IsFilled()]
    print(f"read-back    : {n_poly} zone(s), unfilled={len(unfilled)}")

    doc = {
        "board": a.board,
        "out": out,
        "zones": len(zones),
        "zones_unfilled_after_readback": len(unfilled),
        "layer_clearances_mm": {
            f"{z.GetNetname()}/{pcbnew.LayerName(z.GetLayer())}":
                round(z.GetOwnClearance(z.GetLayer()) / 1e6, 3) for z in check.Zones()
        },
    }
    if a.json:
        with open(a.json, "w") as fh:
            json.dump(doc, fh, indent=1)
    if unfilled:
        print(f"REFUSED: {len(unfilled)} zone(s) unfilled after save/read-back")
        return 1
    print("refill       : OK -- every zone has a filled polygon on disk")
    return 0


if __name__ == "__main__":
    sys.exit(main())
