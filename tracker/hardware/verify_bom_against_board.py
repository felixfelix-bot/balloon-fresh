#!/usr/bin/env python3
"""Verify the LCSC BOM against the shipped board: every populated ref must have a BOM line.

This is the deterministic check that catches the classes of error this campaign keeps
finding: a BOM that quietly omits a part, or names a ref the board does not have.

Exit 0 = consistent; exit 1 = inconsistency (prints the diff).
"""
import csv
import sys
import pcbnew

BOARD = "/home/c08r4d0r/worktrees/v9-route/docs/fab/hub-v9/gerbers/hub_v9.kicad_pcb"
# the CORRECTED JLC BOM, not the malformed jlc-pcba-work source
BOM = "/home/c08r4d0r/worktrees/v9-route/docs/fab/hub-v9/gerbers/hub_v9-bom-jlc.csv"

b = pcbnew.LoadBoard(BOARD)
populated, dnp = set(), set()
for fp in b.GetFootprints():
    ref = fp.GetReference()
    (dnp if fp.IsDNP() else populated).add(ref)

bom_refs = set()
rows = list(csv.DictReader(open(BOM)))
for r in rows:
    for d in r["Designator"].split(","):
        bom_refs.add(d.strip())

bom_assemble = set()
for r in rows:
    if r["LCSC Part #"].strip().upper() == "DNP":
        continue
    for d in r["Designator"].split(","):
        bom_assemble.add(d.strip())

missing = sorted(populated - bom_refs)
extra = sorted(bom_refs - (populated | dnp))
routed_not_assemble = sorted(populated - bom_assemble)
assemble_but_dnp = sorted(bom_assemble & dnp)

print(f"board: {len(populated)} populated, {len(dnp)} DNP  ({len(populated)+len(dnp)} total)")
print(f"bom:   {len(bom_refs)} refs across {len(rows)} lines; {len(bom_assemble)} to assemble")
print()
print(f"populated but ABSENT from the BOM ({len(missing)}): {missing}")
print(f"in the BOM but NOT on the board ({len(extra)}): {extra}")
print(f"populated but marked DNP/ineligible for assembly ({len(routed_not_assemble)}): {routed_not_assemble}")
print(f"in the assemble set but DNP on the board ({len(assemble_but_dnp)}): {assemble_but_dnp}")
print()

ok = not missing and not extra and not assemble_but_dnp
if ok:
    print("RESULT: BOM is consistent with the board (every populated ref has a BOM line)")
else:
    print("RESULT: INCONSISTENT -- see the diffs above")
sys.exit(0 if ok else 1)
