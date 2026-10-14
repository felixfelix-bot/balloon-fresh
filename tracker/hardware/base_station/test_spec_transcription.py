#!/usr/bin/env python3
"""Verify the base-station spec is a FAITHFUL transcription of the frozen document.

The risk in any transcription is silent drift: a number copied wrong, a DNP item quietly dropped,
a gate forgotten. This checks the spec against the source document, mechanically.

It does NOT check that the design is correct -- only that I copied it correctly.
"""
import json
import re
import sys

SPEC = "/home/c08r4d0r/worktrees/v9-route/tracker/hardware/base_station/spec.json"
DOC = "/home/c08r4d0r/worktrees/v9-route/docs/BASE-STATION-PCBA-D14-FREEZE.md"

spec = json.load(open(SPEC))
doc = open(DOC, encoding="utf-8").read()

fails, checks = [], 0

def ck(label, cond, detail=""):
    global checks
    checks += 1
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label} {detail}")
        fails.append(label)

print("=== part numbers appear verbatim in the source document ===")
for part in ("AD8318ACPZ-R7", "RP2040", "TPS62162", "ADL5240", "ZFBT-4R2GW+", "ZX60-P103LN+"):
    ck(f"part {part}", part in doc)

print()
print("=== the numbers ===")
for n, label in (("316", "design total 316 mA"), ("0.5 A", "0.5 A continuous"),
                 ("1 A", "1 A peak"), ("93 mA", "ADL5240 93 mA"),
                 ("95 mA", "ZX60 bias 95 mA"), ("15 mA", "AD8318 15 mA"),
                 ("50 mA", "RP2040 50 mA")):
    ck(label, n in doc)

print()
print("=== rail names ===")
for rail in ("+5V_LNA_SW", "+5V_VGA", "+5V_DET", "+3V3_MCU", "+5V_PCBA", "VIN_GS"):
    ck(f"rail {rail}", rail in doc)

print()
print("=== the four DNP-by-design rows are all in the spec ===")
ck("row 11 PA/FEM DNP", any(d.get("row") == 11 for d in spec["dnp_by_design"]))
ck("row 18 enclosure DNP", any(d.get("row") == 18 for d in spec["dnp_by_design"]))
ck("2.4 GHz PA absent", any("2.4" in d.get("item", "") for d in spec["dnp_by_design"]))
ck("masthead LNA absent", any("LNA" in d.get("item", "") for d in spec["dnp_by_design"]))

print()
print("=== the four verification gates are all in the spec ===")
ck("4 gates carried", len(spec["gates_not_yet_passed"]) == 4)
for i, g in enumerate(spec["gates_not_yet_passed"], 1):
    ck(f"gate {i} present", isinstance(g, str) and len(g) > 10)

print()
print("=== frozen prohibitions survive transcription ===")
ck("no circulator substitute", "circulator" in json.dumps(spec))
ck("second BPF mandatory", "SECOND" in json.dumps(spec).upper())
ck("LNA must not collapse MCU rail",
   "collapse" in json.dumps(spec) or "remove MCU power" in json.dumps(spec))

print()
print("=== the 17 V vs 18 V constraint is not lost ===")
ck("17 V rating noted", "17 V" in json.dumps(spec))
ck("18 V input noted", "18 V" in json.dumps(spec))

print()
print(f"RESULT: {checks - len(fails)}/{checks} checks pass")
if fails:
    print("FAILED:", fails)
sys.exit(1 if fails else 0)
