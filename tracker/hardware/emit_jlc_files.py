#!/usr/bin/env python3
"""Emit the JLC-format BOM + CPL (their header contract), from board-verified data.

THREE FIXES over what existed:
 1. BOM header: JLC's BOM tab expects `JLCPCB Part #`; the earlier mapping used `LCSC Part #`.
    Emit BOTH so either validator accepts it.
 2. CPL header: kicad-cli writes `Ref,Val,Package,PosX,PosY,Rot,Side`; JLC expects
    `Designator,Mid X,Mid Y,Layer,Rotation` with `mm` suffixes. Convert.
 3. CPL Y is negated by KiCad's position export; JLC expects the board convention. Use the
    BOARD's own coordinates (pcbnew) as the source of truth and write those directly.
"""
import csv
import pcbnew

BOARD = "/home/c08r4d0r/worktrees/v9-route/docs/fab/hub-v9/gerbers/hub_v9.kicad_pcb"
BOM_IN = "/home/c08r4d0r/worktrees/v9-route/docs/fab/hub-v9/gerbers/hub_v9-bom-jlc.csv"
BOM_OUT = "/home/c08r4d0r/worktrees/v9-route/docs/fab/hub-v9/gerbers/hub_v9-bom-jlcpcb.csv"
CPL_OUT = "/home/c08r4d0r/worktrees/v9-route/docs/fab/hub-v9/gerbers/hub_v9-cpl-jlcpcb.csv"

# ---- 1. BOM with BOTH part-number header names -----------------------------
rows = list(csv.DictReader(open(BOM_IN)))
with open(BOM_OUT, "w", newline="") as f:
    w = csv.DictWriter(
        f, fieldnames=["Comment", "Designator", "Footprint", "JLCPCB Part #", "LCSC Part #"],
        quoting=csv.QUOTE_MINIMAL)
    w.writeheader()
    for r in rows:
        w.writerow({
            "Comment": r["Comment"],
            "Designator": r["Designator"],
            "Footprint": r["Footprint"],
            "JLCPCB Part #": r["LCSC Part #"],
            "LCSC Part #": r["LCSC Part #"],
        })
print(f"wrote {BOM_OUT}: {len(rows)} lines")

# ---- 2 + 3. CPL in JLC's contract, from the BOARD -------------------------
b = pcbnew.LoadBoard(BOARD)
dnp = {fp.GetReference() for fp in b.GetFootprints() if fp.IsDNP()}
written = 0
with open(CPL_OUT, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
    for fp in sorted(b.GetFootprints(), key=lambda x: x.GetReference()):
        ref = fp.GetReference()
        if ref in dnp:
            continue
        p = fp.GetPosition()
        x = p.x / 1e6
        y = p.y / 1e6
        # KiCad's Y grows DOWNWARD on the board; JLC's convention matches the board file,
        # so write the board value directly (the earlier stale set was ~10mm off instead).
        layer = "Top" if fp.GetLayer() == pcbnew.F_Cu else "Bottom"
        if layer == "Bottom":
            x = -x  # JLC mirrors bottom-side X, as kicad-cli's --bottom-negate-x does
        rot = fp.GetOrientationDegrees()
        w.writerow([ref, f"{x:.4f}mm", f"{y:.4f}mm", layer, f"{rot:.1f}"])
        written += 1
print(f"wrote {CPL_OUT}: {written} placements (DNP excluded)")

# verify against the earlier upload set's expectations
print()
print("=== header contract ===")
print("  BOM:", open(BOM_OUT).readline().strip())
print("  CPL:", open(CPL_OUT).readline().strip())
print()
for line in open(CPL_OUT).readlines()[1:3]:
    print("  sample:", line.strip())
