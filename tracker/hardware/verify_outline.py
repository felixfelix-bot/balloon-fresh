#!/usr/bin/env python3
"""DECISIVE: which outline does the EXPORTED gerber board actually have?

ADR-068 fixed the v9 hub at 70x70 mm. The source hub_board_v9.kicad_pcb measures 103.2x115.0.
If the shipped gerbers carry 103x115, we would order the WRONG, superseded board.
"""
import glob
import os
import pcbnew

targets = [
    "/home/c08r4d0r/worktrees/v9-route/docs/fab/hub-v9/gerbers/hub_v9.kicad_pcb",
    "/home/c08r4d0r/worktrees/v9-route/tracker/hardware/hub_board_v9.kicad_pcb",
    "/tmp/h08_fill.kicad_pcb",
    "/home/c08r4d0r/worktrees/v9-route/tracker/hardware/seed",
]

for f in targets:
    if not os.path.exists(f):
        print(f"{f}: MISSING")
        continue
    b = pcbnew.LoadBoard(f)
    if b is None:
        print(f"{f}: NOT LOADABLE")
        continue
    bb = b.GetBoardEdgesBoundingBox()
    w, h = bb.GetWidth() / 1e6, bb.GetHeight() / 1e6
    n = len(list(b.GetFootprints()))
    print(f"{w:7.1f} x {h:6.1f} mm  ({n:2d} fp)  {f}")

# and the Edge.Cuts extents inside the SHIPPED gerber set
print()
print("=== Edge.Cuts gerber extents (the outline actually plotted) ===")
gc = "/home/c08r4d0r/worktrees/v9-route/docs/fab/hub-v9/gerbers/hub_v9-Edge_Cuts.gm1"
xs, ys = [], []
for line in open(gc):
    line = line.strip()
    for pre in ("X",):
        if line.startswith("X"):
            # format X<x>Y<y>D0n
            try:
                body = line.split("D")[0]
                x, y = body[1:].split("Y")
                xs.append(int(x) / 1e6)
                ys.append(int(y) / 1e6)
            except Exception:
                pass
if xs:
    print(f"  plotted outline bbox: {max(xs)-min(xs):.1f} x {max(ys)-min(ys):.1f} mm")
    print(f"  min/max X: {min(xs):.2f} / {max(xs):.2f}")
    print(f"  min/max Y: {min(ys):.2f} / {max(ys):.2f}")
else:
    print("  (could not parse; showing head)")
    print("".join(open(gc).readlines()[:12]))
