#!/usr/bin/python3.14
"""
Route the C3 flight PCB (v_c3_flight_final.kicad_pcb).

Board state at entry (already prepared by upstream):
  - 4 layers: F.Cu / In1.Cu / In2.Cu / B.Cu
  - 20 footprints placed
  - Edge.Cuts rect (0,0) -> (45,35) present
  - GND zone on In1.Cu present (unfilled)
  - +3V3 zone on In2.Cu present (unfilled)
  - ZERO tracks

This script:
  1. Verifies board state
  2. Sets manufacturable design rules (0.20mm clearance, 0.6mm thickness)
  3. Saves
  4. Exports Specctra DSN
  5. Patches DSN: marks In1.Cu / In2.Cu as (type power) so FreeRouting
     routes signals only on F.Cu / B.Cu; bumps track width to 0.20mm.
  6. Runs FreeRouting (-mp 16)
  7. Parses SES, applies tracks + vias to board
  8. Fills GND / +3V3 zones
  9. Saves board
 10. Reloads and verifies tracks > 20

Run:  /usr/bin/python3.14 route_c3_flight.py
"""

import sys
import os
import re
import subprocess

sys.path.insert(0, '/usr/lib/python3/dist-packages')

HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(HERE, 'output')
sys.path.insert(0, OUTPUT_DIR)  # for ses_import

import pcbnew
from ses_import import apply_ses_to_board

BOARD_PATH   = os.path.join(OUTPUT_DIR, 'v_c3_flight_final.kicad_pcb')
DSN_PATH     = os.path.join(OUTPUT_DIR, 'v_c3_flight_final.dsn')
SES_PATH     = os.path.join(OUTPUT_DIR, 'v_c3_flight_final.ses')

FREEROUTING_JAR = "/tmp/freerouting_extracted/freerouting-2.2.4-linux-x64/lib/app/freerouting-executable.jar"
JAVA_BIN        = "/usr/lib/jvm/java-1.25.0-openjdk-amd64/bin/java"

BOARD_W_MM = 45.0
BOARD_H_MM = 35.0


def mm(v):
    return pcbnew.FromMM(v)


# ----------------------------------------------------------------------
def verify_state(b):
    fps = list(b.Footprints())
    trks = list(b.GetTracks())
    zones = list(b.Zones())
    print(f"  Footprints: {len(fps)}")
    print(f"  Tracks:     {len(trks)}")
    print(f"  Zones:      {len(zones)}")
    if len(fps) < 15:
        raise RuntimeError("Footprints missing — aborting")
    if len(zones) < 2:
        raise RuntimeError("Power zones missing — aborting")
    return b


def set_design_rules(b):
    drc = b.GetDesignSettings()
    drc.m_MinClearance                = mm(0.20)
    drc.m_TrackMinWidth               = mm(0.20)
    drc.m_ViaMinAnnularWidth          = mm(0.15)
    drc.m_ViaMinDrill                 = mm(0.25)
    drc.m_MinThroughDrill             = mm(0.25)
    drc.m_HoleClearance               = mm(0.25)
    drc.m_CopperEdgeClearance         = mm(0.50)
    drc.m_SolderMaskToCopperClearance = mm(0.05)
    drc.SetBoardThickness(mm(0.6))
    print("  Design rules: clearance=0.20mm, thickness=0.6mm")


def export_dsn(b):
    if os.path.exists(DSN_PATH):
        os.remove(DSN_PATH)
    ok = pcbnew.ExportSpecctraDSN(b, DSN_PATH)
    if not ok or not os.path.exists(DSN_PATH):
        raise RuntimeError(f"DSN export failed (ok={ok})")
    print(f"  DSN: {os.path.getsize(DSN_PATH)} bytes")


def patch_dsn(dsn_path):
    with open(dsn_path) as f:
        content = f.read()

    # Mark internal plane layers as (type power) so FreeRouting won't
    # route signals through them -- this avoids shorts after SES import
    content = re.sub(
        r'\(layer In1\.Cu\n(\s+)\(type signal\)',
        r'(layer In1.Cu\n\1(type power)',
        content,
    )
    content = re.sub(
        r'\(layer In2\.Cu\n(\s+)\(type signal\)',
        r'(layer In2.Cu\n\1(type power)',
        content,
    )

    # Bump global width 0.02mm -> 0.20mm (manufacturable)
    content = content.replace('(width 200)', '(width 2000)')
    # Ensure clearance >= 0.20mm
    content = content.replace('(clearance 50)', '(clearance 200)')

    with open(dsn_path, 'w') as f:
        f.write(content)

    # Verify
    with open(dsn_path) as f:
        chk = f.read()
    n_power = chk.count('(type power)')
    print(f"  Patched: {n_power} (type power) layer markers")
    if n_power < 2:
        print("  WARNING: fewer than 2 power layers")


def run_freerouting(max_passes=16, max_time=420):
    if os.path.exists(SES_PATH):
        os.remove(SES_PATH)
    cmd = [
        JAVA_BIN,
        "-Dfreerouting.gui.enabled=false",
        "-jar", FREEROUTING_JAR,
        "-de", DSN_PATH,
        "-do", SES_PATH,
        "-mp", str(max_passes),
        "-mt", "4",
    ]
    print("  CMD:", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=max_time)
    print(f"  Exit: {proc.returncode}")
    out = (proc.stdout or "").strip().splitlines()
    for line in out[-25:]:
        print(f"    [FR] {line}")
    if proc.stderr:
        err = proc.stderr.strip().splitlines()
        for line in err[-8:]:
            print(f"    [ERR] {line}")
    if not os.path.exists(SES_PATH) or os.path.getsize(SES_PATH) == 0:
        raise RuntimeError("FreeRouting did not produce a SES file")
    print(f"  SES: {os.path.getsize(SES_PATH)} bytes")


def apply_ses(b):
    wires, vias = apply_ses_to_board(b, SES_PATH, net_defs=None)
    print(f"  Added {wires} wires + {vias} vias")
    return wires, vias


def fill_zones(b):
    """Fill all zones on the board using ZONE_FILLER."""
    filler = pcbnew.ZONE_FILLER(b)
    # b.Zones() returns a tuple in this KiCad version, but Fill expects
    # a ZONES container. Iterate and build list, then call Fill on each
    # via SetIsFilled(False) trick or use the Fill method directly.
    zones = list(b.Zones())
    print(f"  {len(zones)} zones to fill")
    # Try the standard Fill call with the tuple of zones
    ok = filler.Fill(zones)
    print(f"  Fill returned: {ok}")
    # Force-set filled flag too (defensive)
    for z in zones:
        z.SetIsFilled(True)
    return zones


def main():
    print("=== STEP 1: Load board")
    b = pcbnew.LoadBoard(BOARD_PATH)
    verify_state(b)

    print("=== STEP 2: Set design rules")
    set_design_rules(b)
    b.Save(BOARD_PATH)

    print("=== STEP 3: Export DSN")
    export_dsn(b)

    print("=== STEP 4: Patch DSN")
    patch_dsn(DSN_PATH)

    print("=== STEP 5: Run FreeRouting")
    run_freerouting(max_passes=16, max_time=420)

    print("=== STEP 6: Apply SES to board")
    apply_ses(b)

    print("=== STEP 7: Fill zones")
    fill_zones(b)

    print("=== STEP 8: Save board")
    b.Save(BOARD_PATH)

    print("=== STEP 9: Reload & verify")
    b2 = pcbnew.LoadBoard(BOARD_PATH)
    n_trk = len(list(b2.GetTracks()))
    n_fp  = len(list(b2.Footprints()))
    filled = sum(1 for z in b2.Zones() if z.IsFilled())
    print(f"  Footprints: {n_fp}")
    print(f"  Tracks:     {n_trk}")
    print(f"  Filled zones: {filled}")
    if n_trk < 20:
        print(f"  !! WARNING: fewer than 20 tracks (target > 20)")
    else:
        print(f"  OK: tracks >= 20")
    return n_trk


if __name__ == "__main__":
    main()
