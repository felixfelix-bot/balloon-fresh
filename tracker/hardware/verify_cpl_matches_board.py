#!/usr/bin/env python3
"""DECISIVE: does the CPL match the GERBERS' board?

If the placement file's coordinates disagree with the board the gerbers were plotted from,
JLCPCB places every part in the wrong place -- a fatal, silent, expensive failure.

Checks my exported CPL against the actual footprint positions on the exported board.
"""
import csv
import pcbnew

BOARD = "/home/c08r4d0r/worktrees/v9-route/docs/fab/hub-v9/gerbers/hub_v9.kicad_pcb"
CPL = "/home/c08r4d0r/worktrees/v9-route/docs/fab/hub-v9/gerbers/hub_v9-cpl.csv"
OLD = "/home/c08r4d0r/jlc-pcba-work/upload_hub_cpl.csv"

b = pcbnew.LoadBoard(BOARD)
actual = {}
for fp in b.GetFootprints():
    p = fp.GetPosition()
    actual[fp.GetReference()] = (p.x / 1e6, p.y / 1e6)

print("=== board footprint positions (pcbnew, mm) ===")
for r in ("ANT1", "ANT2", "U1"):
    print(f"  {r}: {actual.get(r)}")

print()
print("=== my CPL rows ===")
for row in csv.DictReader(open(CPL)):
    if row["Ref"] in ("ANT1", "ANT2", "U1"):
        print(f"  {row['Ref']}: PosX={row['PosX']} PosY={row['PosY']}")

print()
print("=== the earlier upload CPL rows ===")
for row in csv.DictReader(open(OLD)):
    if row["Designator"] in ("ANT1", "ANT2", "U1"):
        print(f"  {row['Designator']}: MidX={row['Mid X']} MidY={row['Mid Y']}")

print()
print("=== max |CPL - board| over every ref in my CPL ===")
worst = 0.0
worst_ref = None
n = 0
for row in csv.DictReader(open(CPL)):
    ref = row["Ref"]
    if ref not in actual:
        print(f"  {ref}: NOT ON BOARD")
        continue
    dx = abs(float(row["PosX"]) - actual[ref][0])
    dy = abs(float(row["PosY"]) - actual[ref][1])
    d = max(dx, dy)
    n += 1
    if d > worst:
        worst, worst_ref = d, ref
print(f"  checked {n} refs; worst deviation {worst:.4f} mm on {worst_ref}")
print("  VERDICT:", "MATCH" if worst < 0.01 else f"MISMATCH ({worst:.2f} mm)")
