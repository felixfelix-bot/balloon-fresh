#!/usr/bin/env python3
"""Apply the two APPROVED rule-scope decisions to the v9 hub.

OPERATOR APPROVED, 2026-10-14:
  1. SCOPE the copper_edge_clearance rule to exempt the edge-launched wing
     interface -- rather than lowering the board-wide floor (which would let
     UNINTENDED copper reach 0.2 mm everywhere).
  2. Set min_through_hole_diameter = 0.2 mm WITH A RECORDED RATIONALE.

WHY EACH IS CORRECT (the measurements behind them)

(1) copper_edge_clearance, 68 items, "required 0.500 mm; actual 0.000 / 0.200 /
    0.2025 mm". The wing-socket land sets J_W1..J_W4 are EDGE-LAUNCHED: ADR-046/048
    place the land set ON the board edge so the pads meet the wing tab. An
    `actual 0.0000 mm` there is not a mistake -- it IS the interface. 0.500 mm is
    KiCad's default board-setup value and is simply the wrong rule for an
    edge-launched connector. The fix is a SCOPED rule in the .kicad_dru that
    relaxes the edge clearance ONLY for those footprints, leaving 0.5 mm in force
    for everything else.

(2) drill_out_of_range, 12 items, "min hole 0.3000 mm; actual 0.2000 mm", ALL on
    `PTH pad 41 of U1` = the ESP32-S3-WROOM-1U's THERMAL/HEATSINK vias
    (`pad_prop_heatsink`, KiCad official RF_Module footprint). 0.2 mm is
    ESPRESSIF'S OWN recommended land pattern and JLCPCB's mechanical drill floor is
    0.20 mm, so it is manufacturable. The board's own 0.3 mm rule is STRICTER THAN
    THE FAB REQUIRES for this pad class. Lowering it to 0.2 is therefore a decision
    with a rationale -- NOT the silent fab-floor relaxation refused earlier; the
    frozen .kicad_dru's own via/hole floors (0.60 / 0.30) are UNCHANGED.

Run:
  python3 apply_rule_scopes.py [--dry-run]
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PRO = os.path.join(HERE, "hub_board_v9.kicad_pro")
DRU = os.path.join(HERE, "jlcpcb-s1-frozen.kicad_dru")
dry = "--dry-run" in sys.argv

# --- 1. the scoped edge rule -------------------------------------------------
SCOPED_EDGE_RULE = """
# =====================================================================
# SCOPED EDGE-CLEARANCE RULE  (operator-approved 2026-10-14)
#
# The wing-socket land sets J_W1..J_W4 are EDGE-LAUNCHED by design: ADR-046/048
# place the land set ON the board edge so the pads meet the wing tab (insert depth
# 6.0 mm). Their copper therefore reaches the edge ON PURPOSE -- an "actual
# 0.000 mm" against the board's default 0.5 mm edge rule is the INTERFACE, not a
# defect. 68 such items were reported.
#
# This rule relaxes the edge clearance ONLY for those land sets. The board-wide
# 0.5 mm floor STAYS IN FORCE for every other net, so unintended copper still
# cannot approach the edge. (Lowering the board default instead would have let any
# trace reach 0.2 mm everywhere -- refused.)
# =====================================================================
(rule "S1 hub wing-socket edge-launch (ADR-046/048) - scoped exemption"
	(condition "A.Reference == 'J_W1' || A.Reference == 'J_W2' || A.Reference == 'J_W3' || A.Reference == 'J_W4'")
	(constraint edge_clearance (min 0.00mm)))
"""

want_dru = "S1 hub wing-socket edge-launch" not in open(DRU).read()
if want_dru:
    if not dry:
        with open(DRU, "a") as fh:
            fh.write(SCOPED_EDGE_RULE)
    print("[1] appended the SCOPED edge-clearance rule for J_W1..J_W4")
else:
    print("[1] scoped edge rule already present")

# --- 2. min_through_hole_diameter 0.3 -> 0.2 ---------------------------------
d = json.load(open(PRO))
rules = d["board"]["design_settings"]["rules"]
cur = rules.get("min_through_hole_diameter")
print(f"[2] min_through_hole_diameter currently {cur}")
if cur != 0.2:
    if not dry:
        rules["min_through_hole_diameter"] = 0.2
        # record the rationale where a reader will find it
        d.setdefault("_rationale", {})[
            "min_through_hole_diameter"] = (
            "0.2 mm (lowered from 0.3, operator-approved 2026-10-14). The "
            "ESP32-S3-WROOM-1U (RF_Module library, KiCad official) carries 13 "
            "thermal/heatsink through-vias at 0.2 mm (pad_prop_heatsink, "
            "zone_connect 2) -- 0.2 mm is ESPRESSIF'S OWN recommended land "
            "pattern and equals JLCPCB's mechanical drill floor, so it is "
            "manufacturable and intended, not a defect. The via/hole FLOORS in "
            "jlcpcb-s1-frozen.kicad_dru (via 0.60 / hole 0.30) are UNCHANGED: "
            "this is a decision with a rationale, NOT a fab-floor relaxation.")
        json.dump(d, open(PRO, "w"), indent=2)
        # keep a trailing newline, KiCad prefers it
        with open(PRO, "a") as fh:
            fh.write("\n")
    print("[2] set to 0.2 mm with recorded rationale")
else:
    print("[2] already 0.2 mm")

print("dry-run" if dry else "applied")
