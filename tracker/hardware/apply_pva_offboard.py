#!/usr/bin/env python3
"""APPLY THE OPERATOR'S PVA RULING: the solar cells are OFF-BOARD mechanical parts.

Operator, 2026-10-14: "yes keep them off board and rout them through the connector. The solar panels
don't belong on the board."

MEASURED ROOT CAUSE of PVA1/PVA2 being "unplaceable": the schematic INSTANCES carry
    (property "Footprint" "")
while a working instance (U2) carries
    (property "Footprint" "balloon_flight_v9:LoRa2021F33_2G4")
So the empty property is the defect, and for the cells the correct resolution is NOT to invent a
footprint -- it is to mark them off-board.

WHAT THIS DOES, and why it is the faithful reading of the ruling:
  * `on_board no`  -> the part is NOT a PCBA placement, so it stops being "unplaceable"
  * `in_bom no`    -> it leaves the ORDER BOM, becoming a mechanical drawing (the operator's words)
  * `dnp no`       -> unchanged; DNP means "do not populate", which is a different statement from
                      "not on this board at all"
  * Value stays `SolarCell_78x39mm` so the mechanical drawing identity is preserved

It does NOT touch the string topology: D_HUB1/D_HUB2 (the bypass diodes) stay on the PCBA and the
netlist's HUB_PV_P -> D_HUB1 -> HUB_PV_MID1 -> D_HUB2 -> HUB_PV_N chain is unchanged. The cells
terminate at the connector, exactly as the wing solar already does at J_W1..J_W4.

Usage:  python3 apply_pva_offboard.py --check | --write
"""
import argparse
import os
import re
import shutil

SCH = ("/home/c08r4d0r/worktrees/v9-route/tracker/hardware/schematics/flight_board/"
       "v9_flight.kicad_sch")
REFS = ["PVA1", "PVA2"]


def instance_span(s, ref):
    """Span of the enclosing (symbol ...) block for a Reference property."""
    m = re.search(r'\(property "Reference" "' + re.escape(ref) + r'"', s)
    if not m:
        return None
    start = s.rfind("(symbol", 0, m.start())
    # walk forward balancing parens
    depth = 0
    j = start
    while j < len(s):
        if s[j] == "(":
            depth += 1
        elif s[j] == ")":
            depth -= 1
            if depth == 0:
                break
        j += 1
    return start, j + 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    s = open(SCH, encoding="utf-8").read()
    orig = s
    report = []

    for ref in REFS:
        span = instance_span(s, ref)
        if span is None:
            report.append((ref, "NOT FOUND"))
            continue
        start, end = span
        blk = s[start:end]
        before = blk
        blk = re.sub(r"\(on_board yes\)", "(on_board no)", blk)
        blk = re.sub(r"\(in_bom yes\)", "(in_bom no)", blk)
        changed = (blk != before)
        s = s[:start] + blk + s[end:]
        report.append((ref, "changed" if changed else "ALREADY off-board"))

    for ref, status in report:
        print(f"  {ref:6s} {status}")

    if a.check or not a.write:
        print("\n(check mode -- nothing written)")
        return 0

    if s == orig:
        print("\nnothing to change")
        return 0

    shutil.copy2(SCH, SCH + ".bak")
    open(SCH, "w", encoding="utf-8").write(s)
    print(f"\nwrote {os.path.relpath(SCH)}  (backup at {os.path.basename(SCH)}.bak)")

    # verify
    s2 = open(SCH, encoding="utf-8").read()
    for ref in REFS:
        span = instance_span(s2, ref)
        blk = s2[span[0]:span[1]]
        empty_fp = '("Footprint" "")' in blk or '(property "Footprint" "")' in blk
        print(f"  verify {ref}: on_board no={'on_board no' in blk}  "
              f"in_bom no={'in_bom no' in blk}  footprint_empty={empty_fp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
