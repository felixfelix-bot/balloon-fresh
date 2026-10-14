#!/usr/bin/env python3
"""Fix the two REAL wing issues found by the audit:
 1. thickness 0.6 -> 0.8 (the decision; same defect class as the hub's stale file)
 2. FB1 / RF1 DNP flag: value text says "DNP_V2only"/"v2only" but IsDNP()==False, so a
    BOM/CPL generator reading the flag would try to PLACE v2-only parts on a v1 board.
    Set the flags so the artefact agrees with the intent.

Only these two are touched. Nothing else on the board is modified.
"""
import re
import pcbnew

WT = "/home/c08r4d0r/worktrees/v9-route"
B = f"{WT}/tracker/hardware/wing_board/wing_board_v9.kicad_pcb"

# --- 1. thickness ---
s = open(B).read()
m = re.search(r"\(thickness ([0-9.]+)\)", s)
old = m.group(1)
s2 = re.sub(r"\(thickness [0-9.]+\)", "(thickness 0.8)", s, count=1)
open(B, "w").write(s2)
print(f"1. thickness {old} -> 0.8")

# --- 2. DNP flags ---
b = pcbnew.LoadBoard(B)
changed = []
for fp in b.GetFootprints():
    if fp.GetReference() in ("FB1", "RF1"):
        fp.SetDNP(True)
        changed.append(fp.GetReference())
pcbnew.SaveBoard(B, b)
print(f"2. DNP set True on: {changed}")

# verify both
b = pcbnew.LoadBoard(B)
print()
print("=== verify ===")
print("  thickness:", re.search(r"\(thickness ([0-9.]+)\)", open(B).read()).group(1))
for fp in b.GetFootprints():
    if fp.GetReference() in ("FB1", "RF1"):
        print(f"  {fp.GetReference()}: IsDNP={fp.IsDNP()}")
