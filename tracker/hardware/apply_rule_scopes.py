#!/usr/bin/env python3
"""Restore the S1 frozen rule file and add the edge scope as a SEPARATE, additive rule.

MY ERROR TO FIX: apply_rule_scopes.py replaced the whole jlcpcb-s1-frozen.kicad_dru with
a short block, destroying the S1 frozen rule set whose sha256 the campaign depends on for
comparability. Restore it from git and APPEND only the approved edge scopes.

ALSO CORRECTED: the remaining 26 edge items are NOT interface exemptions.
  - 26 TRACK items (+3V3 0.218mm, F33_VCC 0.400mm, GNSS_VCC, W1_SOLAR_N) cite MY OWN new
    rule 'edge_clearance_default' and have REAL clearances below the 0.5mm board-setup
    value. These are genuine manufacturing risks, NOT the ADR-046/048 interface.
  - The wing lands (J_W1..J_W4) ARE the interface, but their segments are Edge.Cuts
    graphics, so a Pad/Via/Track condition cannot reach them -- they need an item-type
    scope or a documented waiver.
  - The 31 "Rectangle on Edge.Cuts" items are the OUTLINE measured against itself -- a
    rule-applicability artifact.

So this script does the honest, minimal thing: restore the frozen file, then append ONLY
the wing-socket-land scope (which is unambiguously by-design) and leave the track items
visible as real violations for the operator to rule on.
"""
import subprocess
import sys

REPO = "/home/c08r4d0r/worktrees/v9-route"
DRU = f"{REPO}/tracker/hardware/jlcpcb-s1-frozen.kicad_dru"

APPEND = '''
# =====================================================================
# v9 hub ADDITIONS, 2026-10-14 (operator-approved). ADDITIVE ONLY -- the S1
# frozen rules above are UNCHANGED so their sha256 and comparability survive.
#
# SCOPE 1: the EDGE-LAUNCHED WING INTERFACE (ADR-046/048). J_W1..J_W4 land sets sit ON
# the board edge by design so the pads meet the wing tab; `actual 0.0000 mm` IS the
# interface. Exempt those lands from the board edge clearance.
#
#   HONESTY NOTE: their Edge.Cuts SEGMENTS cannot be reached by a copper condition, so
#   this scope only reaches the PADS of those connectors. The leftover Edge.Cuts
#   graphics items (outline rectangles + connector segments) are a rule-APPLICABILITY
#   artifact, not a copper defect, and are left visible rather than suppressed.
#
# SCOPE 2 is deliberately NOT applied: the 26 TRACK items (+3V3 at 0.218 mm,
#   F33_VCC at 0.400 mm, GNSS_VCC, W1_SOLAR_N) are REAL edge-clearance shortfalls
#   against the 0.5 mm board-setup value, NOT interface exemptions. They stay visible
#   for the operator to rule on. See docs/fab/hub-v9/RULE-SCOPE-APPLICATION.md.
# =====================================================================
(rule "edge_clearance_wing_socket_lands_44"
  (constraint edge_clearance (min 0.0mm))
  (condition "A.Reference == 'J_W1' || A.Reference == 'J_W2' || A.Reference == 'J_W3' || A.Reference == 'J_W4'"))
'''


def main():
    frozen = subprocess.run(
        ["git", "-C", REPO, "show", "HEAD:tracker/hardware/jlcpcb-s1-frozen.kicad_dru"],
        capture_output=True, text=True, check=True).stdout
    body = frozen.rstrip("\n") + "\n" + APPEND
    with open(DRU, "w") as f:
        f.write(body)
    print(f"restored S1 frozen rules from git ({len(frozen)} bytes) + appended {len(APPEND)} bytes of scope")
    # verify the frozen sha256 line is intact
    for ln in body.splitlines():
        if "sha256" in ln.lower():
            print("  ", ln[:100])


if __name__ == "__main__":
    main()
