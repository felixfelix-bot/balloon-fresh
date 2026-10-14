#!/usr/bin/env python3
"""GPIO0 / strapping-pin audit for the balloon boards.

Operator report: a board went into a BOOT LOOP.

Hypothesis to test (do NOT assume): GPIO0 is a strapping pin on ESP32. If a net
that can pull it LOW at reset (a relay/opto coil, a transistor base, a driven
output, or an external pulldown) is assigned to GPIO0, the chip enters the
UART download/bootloader path on every reset -> boot loop.

This script greps every board's netlist/schematic source in the repo for GPIO0
(and the other S3 strapping pins) and prints every assignment, so the actual
conflict can be seen rather than guessed.

Run:  python3 audit_gpio0_strapping.py
"""
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STRAP = ["GPIO0", "IO0", "GPIO3", "IO3", "GPIO45", "IO45", "GPIO46", "IO46"]

# files that carry pin assignments
EXT = (".md", ".net", ".kicad_sch", ".h", ".cpp", ".c", ".py", ".csv", ".json")

hits = {}
for dirpath, dirnames, filenames in os.walk(ROOT):
    if any(p in dirpath for p in (".git", "node_modules", ".venv", "__pycache__")):
        continue
    for fn in filenames:
        if not fn.endswith(EXT):
            continue
        p = os.path.join(dirpath, fn)
        try:
            with open(p, "r", errors="ignore") as fh:
                for i, line in enumerate(fh, 1):
                    for s in STRAP:
                        # word-boundary match so GPIO01/GPIO0_ etc. don't false-hit
                        if re.search(r"\b" + s + r"\b", line):
                            hits.setdefault(s, []).append(
                                (os.path.relpath(p, ROOT), i, line.strip()[:150]))
                            break
        except OSError:
            continue

for s in STRAP:
    rows = hits.get(s, [])
    if not rows:
        continue
    print(f"\n{'='*78}\n{s} — {len(rows)} mention(s)\n{'='*78}")
    for path, ln, text in rows:
        print(f"  {path}:{ln}\n      {text}")

# The specific question: is GPIO0 assigned to something that can pull it LOW?
print(f"\n{'='*78}\nWHAT TO LOOK FOR\n{'='*78}")
print("""On ESP32-S3, GPIO0 is a STRAPPING pin. At reset it is sampled:
  LOW  -> UART download / bootloader mode
  HIGH -> normal flash boot
If any net that can hold it LOW at reset is wired to GPIO0 -- a relay or opto
coil, an NPN base with a pull-down, a driven push-pull output, or an external
pulldown resistor -- the chip re-enters the bootloader on EVERY reset and you
get a boot loop. A supercap ADC divider (per ADR-006) put on GPIO0 is exactly
this class of mistake: a divider to ground held by a charged cap can read LOW.
""")
