#!/usr/bin/env python3
"""REFILL THE ZONES, THEN GRADE -- the procedure the honest state said was owed.

WHY THIS MATTERS: the strict route measured 770 DRC violations, but 699 of them were copper against
UNREFILLED GND zones (311 track+zone, 189 via+zone, 199 via+zone hole clearance, ZERO pad+pad). A
filed/stale polygon fires DRC against copper that the real fill would clear, so grading before the
refill produces a FALSE verdict -- the same class of error as the broken CPL checker.

METHOD: drive pcbnew's ZONE_FILLER headless (the fill-fidelity ground-truth recipe), save, then run
kicad-cli DRC on the REFILLED board and report the composition by pair type.

NOTE ON pcbnew SCRIPTING: pcbnew segfaults when board work happens inside functions/loops, so the
fill is done in STRAIGHT-LINE MODULE SCOPE, matching the proven pattern in KRT's kicad_exact_fill.py.

Usage:
    ~/venvs/kicad/bin/python refill_and_grade.py <input.kicad_pcb> <output.kicad_pcb>
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

SRC = sys.argv[1] if len(sys.argv) > 1 else (
    "/home/c08r4d0r/worktrees/v9-route/tracker/hardware/base_station/output/"
    "bs_v1_routed_strict.kicad_pcb")
DST = sys.argv[2] if len(sys.argv) > 2 else (
    "/home/c08r4d0r/worktrees/v9-route/tracker/hardware/base_station/output/"
    "bs_v1_routed_strict_filled.kicad_pcb")

# ---- straight-line module scope: load, fill, save ---------------------------------------------
board = pcbnew.LoadBoard(SRC)
zones = board.Zones()
print(f"board: {os.path.basename(SRC)}")
print(f"zones declared: {len(zones)}")
for z in zones:
    print(f"   zone '{z.GetZoneName()}' net={z.GetNetname()} "
          f"layers={[board.GetLayerName(l) for l in z.GetLayerSet().Seq()]}")

before_filled = sum(1 for z in zones if z.IsFilled())
print(f"filled BEFORE: {before_filled}/{len(zones)}")

pcbnew.ZONE_FILLER(board).Fill(zones)

after_filled = sum(1 for z in zones if z.IsFilled())
print(f"filled AFTER : {after_filled}/{len(zones)}")
pcbnew.SaveBoard(DST, board)
print(f"saved: {os.path.relpath(DST)}")

# ---- grade the REFILLED board ----------------------------------------------------------------
rep = DST.replace(".kicad_pcb", "-drc.json")
r = subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--output", rep, DST],
                   capture_output=True, text=True, timeout=900)
for line in (r.stdout + r.stderr).splitlines():
    if line.strip():
        print("   " + line.strip())

d = json.load(open(rep))
v = d.get("violations", [])
unc = d.get("unconnected_items", [])

print()
print("=" * 70)
print(f"REFILLED BOARD: {len(v)} violations, {len(unc)} unconnected")
print("=" * 70)

from collections import Counter  # noqa: E402

kinds = Counter()
for x in v:
    descs = [i.get("description", "") for i in x.get("items", [])]
    has = {k: any(s.startswith(p) or f" {p}" in s for s in descs)
           for k, p in (("track", "Track"), ("pad", "Pad"), ("via", "Via"), ("zone", "Zone"))}
    key = "+".join(sorted(k for k, ok in has.items() if ok)) or "other"
    kinds[f"{x.get('type')} :: {key}"] += 1

for k, n in kinds.most_common(15):
    print(f"  {n:5}  {k}")

print()
print("--- the question that matters: PAD+PAD clearance (real routing faults) ---")
padpad = [x for x in v if x.get("type") == "clearance"
          and sum(1 for i in x.get("items", []) if i.get("description", "").startswith("Pad")) == 2]
print(f"  pad+pad clearance violations: {len(padpad)}")

print()
print("--- unconnected items (real opens) ---")
names = Counter()
for u in unc:
    for i in u.get("items", []):
        names[i.get("description", "")[:60]] += 1
for n, c in names.most_common(24):
    print(f"  {c:3}  {n}")
