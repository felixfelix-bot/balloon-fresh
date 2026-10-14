#!/usr/bin/env python3
"""Measure the F33 site's cost on the v9 hub: area, pads, and what it forces.

Runs against the frozen board with pcbnew. Reports FACTS only; no recommendations.
"""
import sys

import pcbnew

BOARD = sys.argv[1] if len(sys.argv) > 1 else "hub_board_v9.kicad_pcb"

b = pcbnew.LoadBoard(BOARD)

TARGETS = {"U2": "LoRa2021F33-2G4 (2 W, 433 MHz TX)",
           "U3": "LoRa2021 bare (2.4 GHz RX)",
           "U5": None}

for fp in b.GetFootprints():
    ref = fp.GetReference()
    if ref not in TARGETS:
        continue
    bb = fp.GetBoundingBox()
    fpid = str(fp.GetFPID().GetLibItemName())
    x0, y0 = bb.GetX() / 1e6, bb.GetY() / 1e6
    w, h = bb.GetWidth() / 1e6, bb.GetHeight() / 1e6
    print(f"{ref:4s} fp={fpid}")
    print(f"     size {w:.2f} x {h:.2f} mm  ->  {w * h:.1f} mm2")
    print(f"     at   ({x0:.2f}, {y0:.2f})")
    pads = list(fp.Pads())
    print(f"     pads {len(pads)}")
    # pad extents -> the real land field
    if pads:
        xs = [p.GetPosition().x / 1e6 for p in pads]
        ys = [p.GetPosition().y / 1e6 for p in pads]
        print(f"     pad field {max(xs) - min(xs):.2f} x {max(ys) - min(ys):.2f} mm")
    print(f"     excluded_from_pos_files={fp.IsExcludedFromPosFiles()}")
    print()

# total board area for the fraction
print(f"board outline: ", end="")
bds = b.GetBoardEdgesBoundingBox()
print(f"{(bds.GetWidth() / 1e6):.1f} x {(bds.GetHeight() / 1e6):.1f} mm "
      f"= {(bds.GetWidth() / 1e6) * (bds.GetHeight() / 1e6):.0f} mm2")
