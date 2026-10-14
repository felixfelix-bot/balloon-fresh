#!/usr/bin/env python3
"""Set the board thickness to 0.8 mm in the v9 board files, then verify.

The checklist claimed the file was "fixed to 0.8" -- MEASURED 2026-10-14 it was still 0.6.
Gerbers do not carry thickness, so this is belt-and-braces (the order form governs), but
the file should match the decision so the document and the artefact agree.
"""
import re
import sys

FILES = ["seed", "hub_board_v9.kicad_pcb"]
NEW = "0.8"

for f in FILES:
    with open(f) as fh:
        s = fh.read()
    m = re.search(r"\(thickness ([0-9.]+)\)", s)
    if not m:
        print(f"{f}: NO thickness field found -- skipped")
        continue
    old = m.group(1)
    s2 = re.sub(r"\(thickness [0-9.]+\)", f"(thickness {NEW})", s, count=1)
    with open(f, "w") as fh:
        fh.write(s2)
    print(f"{f}: thickness {old} -> {NEW}")

# verify
print()
for f in FILES:
    s = open(f).read()
    m = re.search(r"\(thickness ([0-9.]+)\)", s)
    print(f"  verify {f}: thickness {m.group(1) if m else '??'}")
