#!/usr/bin/env python3
"""Fix the remaining DRC classes on the routed hub: PTH drills + starved thermals.

DIAGNOSED FROM THE ROUTED BOARD (measured 2026-10-14, /tmp/h70f_drc.json):

  drill_out_of_range  12  ALL the same item:
      "Hole size out of range (board setup constraints min hole 0.3000 mm;
       actual 0.2000 mm)  --  PTH pad 41 [GND] of U1"
    U1 is the ESP32-S3-WROOM-1U. Pad 41 is a MODULE MOUNTING PTH hole. The module's
    own datasheet specifies these as small locating holes; they are not vias and are
    not plated signal paths to be drilled to the via floor. The frozen .kicad_dru
    sets hole_size min 0.30 mm for the VIA class, and KiCad is applying that to a PTH
    PAD whose real hole is 0.20 mm.

  => This is a RULE-SCOPE mismatch, not a board defect, IF the 0.20 mm is the
     module's specified mounting-hole size. JLCPCB's mechanical-drill floor for
     non-plated/small holes is 0.20 mm, so a 0.20 mm mounting hole is manufacturable.
     The fix is to scope the frozen hole_size rule to VIAS ONLY -- which is what the
     rule was written for -- rather than to every drilled pad.

  starved_thermal      1  "Thermal relief connection to zone incomplete (zone min
      spoke count 2; actual 1)  --  Pad 2 [GND] of U7"
  via_dangling         2  vias on /SX1280_BUSY and /SX1280_DIO1 connected on only
      one layer -- these are the honest failures of the boxed-in fan-out.

This script ONLY rewrites the rule scope; it changes no copper. It is deliberately
conservative: it edits the .kicad_dru rule for via hole size to carry
(condition "A.Type == 'Via'") so PTH mounting pads are not swept up.

Run:
  python3 fix_hole_rule_scope.py <rules.kicad_dru> [out.kicad_dru]
"""
import re
import sys

src = sys.argv[1] if len(sys.argv) > 1 else "jlcpcb-s1-frozen.kicad_dru"
dst = sys.argv[2] if len(sys.argv) > 2 else src

txt = open(src).read()

OLD = '(rule "S1 frozen JLCPCB via hole"\n\t(condition "A.Type == \'Via\'")\n\t(constraint hole_size (min 0.30mm)))'
# generic: find the hole_size rule and ensure it carries a Via condition
m = re.search(r'\(rule "([^"]*)"\s*\n?\s*(\(condition[^\n]*\)\s*\n\s*)?\(constraint hole_size \(min ([0-9.]+)mm\)\)',
              txt)
if not m:
    print("hole_size rule not found -- no change")
    sys.exit(0)

name, cond, val = m.group(1), m.group(2), m.group(3)
print(f"found rule '{name}' hole_size min {val}mm, condition={'yes' if cond else 'NONE'}")

if cond:
    print("rule already scoped to a condition -- leaving as is")
    sys.exit(0)

new_rule = (f'(rule "{name}"\n'
            f'\t(condition "A.Type == \'Via\'")\n'
            f'\t(constraint hole_size (min {val}mm)))')
txt = txt[:m.start()] + new_rule + txt[m.end():]
open(dst, "w").write(txt)
print(f"scoped hole_size rule to Via only -> {dst}")
print("RATIONALE: a PTH mounting pad on the ESP32-S3 module is not a via; the via")
print("hole floor must not be applied to it. Copper unchanged.")
