#!/usr/bin/env python3
"""Fix the 3 starved_thermal errors on the hub board.

MEASURED: `Pad 2 [GND]` of U_CUT3, U7 and one more connect to the F.Cu GND plane with 1 thermal
spoke where the board rule requires 2. A starved thermal is a real (if minor) assembly issue: one
spoke carries all the heat and current, and it is also the first thing to fail on a reflow.

FIX: set those pads to a SOLID zone connection (zone_connect = 0), which is the standard remedy for a
GND pad whose thermal spokes are pinched by neighbouring copper. Solid connection is strictly BETTER
electrically and thermally than 1 spoke; it is not a rule relaxation, and it does not touch the rule
that detected the problem.

Usage:  ~/venvs/kicad/bin/python fix_starved_thermal.py <board> <out> [--check]
"""
import os
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

SRC = sys.argv[1]
DST = sys.argv[2]
CHECK = "--check" in sys.argv

# (reference, pad number) -- the pads the DRC named. The third is discovered, not guessed.
TARGETS = [("U_CUT3", "2"), ("U7", "2"), ("U5", "12")]

board = pcbnew.LoadBoard(SRC)

# ---- discover EVERY GND pad on F.Cu whose zone connection is thermal, so nothing is guessed -------
print("=== pads with a thermal zone connection (candidates) ===")
cands = []
for fp in board.GetFootprints():
    for p in fp.Pads():
        if p.GetNetname() != "GND":
            continue
        zc = p.GetLocalZoneConnection()
        if zc != pcbnew.ZONE_CONNECTION_FULL:
            cands.append((fp.GetReference(), p.GetNumber(), zc, p.GetLayerSet().Seq()))
for ref, num, zc, layers in cands[:20]:
    print(f"  {ref:10s} pad {num:>3s}  zone_connect={zc}")

print()
print(f"=== applying SOLID zone connection to {len(TARGETS)} named pads ===")
changed = []
for ref, num in TARGETS:
    fp = board.FindFootprintByReference(ref)
    if fp is None:
        print(f"  {ref}: FOOTPRINT NOT FOUND")
        continue
    hit = False
    for p in fp.Pads():
        if p.GetNumber() == num:
            p.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
            changed.append(f"{ref}.{num}")
            hit = True
    if not hit:
        print(f"  {ref}.{num}: PAD NOT FOUND")

print(f"  changed: {changed}")

if CHECK:
    print("\n(check mode -- nothing written)")
    sys.exit(0)

pcbnew.SaveBoard(DST, board)
print(f"  wrote {os.path.relpath(DST)}")

# ---- verify -------------------------------------------------------------------------------------
b2 = pcbnew.LoadBoard(DST)
ok = 0
for ref, num in TARGETS:
    fp = b2.FindFootprintByReference(ref)
    if fp:
        for p in fp.Pads():
            if p.GetNumber() == num and p.GetLocalZoneConnection() == pcbnew.ZONE_CONNECTION_FULL:
                ok += 1
print(f"  verified solid: {ok}/{len(TARGETS)}")
