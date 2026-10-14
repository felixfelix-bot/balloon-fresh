#!/usr/bin/env python3
"""List every footprint on the shipped v9 board with the fields the BOM needs.

The checklist claimed "2 DNP rows verified"; measured, NO footprint carries the DNP flag.
This lists the truth so the DNP set can be set from the LOCKED decisions rather than guessed.
"""
import pcbnew

B = "/home/c08r4d0r/worktrees/v9-route/docs/fab/hub-v9/gerbers/hub_v9.kicad_pcb"
b = pcbnew.LoadBoard(B)

print(f"{'ref':10s} {'value':22s} {'footprint':30s} {'DNP':4s} {'attrs'}")
for fp in sorted(b.GetFootprints(), key=lambda f: f.GetReference()):
    ref = fp.GetReference()
    val = fp.GetValue()
    fpid = str(fp.GetFPID().GetLibItemName())
    dnp = "DNP" if fp.IsDNP() else "-"
    # SMD vs TH
    smd = any(p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD for p in fp.Pads())
    th = any(p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH for p in fp.Pads())
    kind = ("SMD" if smd else "") + ("+TH" if th else "")
    print(f"{ref:10s} {val[:22]:22s} {fpid[:30]:30s} {dnp:4s} {kind}")
