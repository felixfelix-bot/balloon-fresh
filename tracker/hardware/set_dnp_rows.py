#!/usr/bin/env python3
"""Set the DNP flags from the LOCKED order split, then report.

LOCKED SPLIT (docs/fab/hub-v9/PRE-ORDER-CHECKLIST.md line 28):
  "1 variant, platform populated on all 10 | no baro; GPS as DNP rows + 4 loose"

So: U5 (MAX-M10S GPS) and U6 (MS5611 baro) are the TWO DNP ROWS the checklist claimed
were "verified" -- measured, NO footprint carried the flag.

I set ONLY what the locked decision states. The supercap question is reported, not decided.
"""
import pcbnew

B = "/home/c08r4d0r/worktrees/v9-route/docs/fab/hub-v9/gerbers/hub_v9.kicad_pcb"
b = pcbnew.LoadBoard(B)

DNP_SET = {"U5", "U6"}  # GPS + baro, per the locked split

changed = []
for fp in b.GetFootprints():
    ref = fp.GetReference()
    want = ref in DNP_SET
    if fp.IsDNP() != want:
        fp.SetDNP(want)
        changed.append((ref, want))

pcbnew.SaveBoard(B, b)
print("DNP flags set:")
for r, w in changed:
    print(f"  {r} -> DNP={w}")

print()
print("verify:")
for fp in sorted(b.GetFootprints(), key=lambda f: f.GetReference()):
    if fp.IsDNP():
        print(f"  {fp.GetReference():6s} {fp.GetValue()}  DNP")

print()
print("=== SUPERCAP CAVEAT (reported, not decided) ===")
print("  C_CAP1/C_CAP2 are through-hole supercaps. The checklist's accepted-risks list says")
print("  'Supercap DNP: no buffer for TX bursts at dawn/dusk -> cold-start untested', which")
print("  implies they are NOT populated. I have NOT set that flag: it changes stored energy,")
print("  not just the CPL, and it is a functional decision for the operator.")
