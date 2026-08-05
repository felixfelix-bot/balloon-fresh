#!/usr/bin/python3.14
"""
4-Layer V2-ADC PCB pipeline: Create board -> GND/3V3 planes -> FreeRouting -> SES import -> DRC
Run with: /usr/bin/python3.14 create_4layer.py --output output/v2_adc_4layer.kicad_pcb

MANDATORY: Uses pcbnew.NewBoard() NOT the banned loader.
MANDATORY: 4-layer stackup — GND on In1.Cu, 3V3 on In2.Cu.
MANDATORY: Run with /usr/bin/python3.14 (python3.11 segfaults with pcbnew).
MANDATORY: Use pcbnew.ImportSpecctraSES() for SES import, NOT manual parsing.
"""

import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')

import argparse
import json
import os
import subprocess

import pcbnew

# Import board creation functions from full_pipeline
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from full_pipeline import (
    get_v2_adc_components, create_board_outline, create_nets, create_footprint,
    V2_ADC_NETS, run_drc, ripup_all_tracks
)
from freerouting_pipeline import set_board_design_rules

# FreeRouting paths
FREEROUTING_JAR = "/tmp/freerouting_extracted/freerouting-2.2.4-linux-x64/lib/app/freerouting-executable.jar"
JAVA_BIN = "/usr/lib/jvm/java-25-openjdk-amd64/bin/java"

# Constants
BOARD_WIDTH_MM = 50.0
BOARD_HEIGHT_MM = 40.0
TRACK_WIDTH_RF_MM = 0.76
IN1_CU = pcbnew.In1_Cu  # 4
IN2_CU = pcbnew.In2_Cu  # 6
F_CU = pcbnew.F_Cu      # 0
B_CU = pcbnew.B_Cu      # 2


def create_board_v2_adc_4layer(output_path: str) -> pcbnew.BOARD:
    """Create 4-layer V2-ADC board with GND and 3V3 internal planes."""
    board = pcbnew.NewBoard(output_path)
    board.SetCopperLayerCount(4)
    create_board_outline(board)
    nets_by_name = create_nets(board, V2_ADC_NETS)
    comps = get_v2_adc_components()
    for comp in comps:
        create_footprint(board, comp, nets_by_name)
    return board


def add_power_planes(board: pcbnew.BOARD):
    """Add GND plane on In1.Cu and 3V3 plane on In2.Cu covering full board."""
    for net_name, layer in [('GND', IN1_CU), ('3V3', IN2_CU)]:
        zone = pcbnew.ZONE(board)
        zone.SetLayer(layer)
        poly = pcbnew.SHAPE_POLY_SET()
        poly.NewOutline()
        poly.Append(0, 0)
        poly.Append(pcbnew.FromMM(BOARD_WIDTH_MM), 0)
        poly.Append(pcbnew.FromMM(BOARD_WIDTH_MM), pcbnew.FromMM(BOARD_HEIGHT_MM))
        poly.Append(0, pcbnew.FromMM(BOARD_HEIGHT_MM))
        zone.SetOutline(poly)
        zone.SetNet(board.FindNet(net_name))
        zone.SetFillMode(0)  # solid fill
        board.Add(zone)
        print(f"  Added {net_name} zone on layer {layer}")


def fill_zones(board: pcbnew.BOARD):
    """Fill all zones on the board."""
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    print("  Zones filled")


def export_dsn(board: pcbnew.BOARD, dsn_path: str) -> bool:
    print(f"  Exporting DSN to {dsn_path}...")
    result = pcbnew.ExportSpecctraDSN(board, dsn_path)
    if result:
        print(f"  DSN exported successfully ({os.path.getsize(dsn_path)} bytes)")
    else:
        print(f"  ERROR: DSN export failed")
    return result


def run_freerouting(dsn_path: str, ses_path: str, max_passes: int = 32) -> bool:
    print(f"  Running FreeRouting...")
    print(f"    Input:  {dsn_path}")
    print(f"    Output: {ses_path}")
    print(f"    Passes: {max_passes}")

    cmd = [
        JAVA_BIN,
        "-Dfreerouting.gui.enabled=false",
        "-jar", FREEROUTING_JAR,
        "-de", dsn_path,
        "-do", ses_path,
        "-mp", str(max_passes),
        "-mt", "1",
    ]

    print(f"  Command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

    print(f"  FreeRouting exit code: {result.returncode}")
    if result.stdout:
        lines = result.stdout.strip().split('\n')
        for line in lines[-30:]:
            print(f"    [FR-OUT] {line}")
    if result.stderr:
        lines = result.stderr.strip().split('\n')
        for line in lines[-10:]:
            print(f"    [FR-ERR] {line}")

    if os.path.exists(ses_path) and os.path.getsize(ses_path) > 0:
        print(f"  SES file created ({os.path.getsize(ses_path)} bytes)")
        return True
    else:
        print(f"  ERROR: No SES file produced")
        return False


def import_ses(board: pcbnew.BOARD, ses_path: str) -> bool:
    """Import Specctra SES session into board using pcbnew API.
    NEVER parse SES manually — ImportSpecctraSES handles all coordinate transforms.
    """
    print(f"  Importing SES from {ses_path}...")
    try:
        result = pcbnew.ImportSpecctraSES(board, ses_path)
        if result:
            track_count = len(list(board.GetTracks()))
            print(f"  SES imported: {track_count} track segments")
        else:
            print(f"  ERROR: SES import returned False")
        return result
    except Exception as e:
        print(f"  ERROR: SES import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def fix_rf_track_widths(board: pcbnew.BOARD, net_defs: dict):
    """Ensure RF traces use 0.76mm width for 50ohm on 1.6mm FR4."""
    rf_nets = set()
    for name, props in net_defs.items():
        if props.get("width") == TRACK_WIDTH_RF_MM:
            rf_nets.add(name)

    if not rf_nets:
        return 0

    rf_net_codes = set()
    for net_name_key, net_item in board.GetNetInfo().NetsByName().items():
        if str(net_name_key) in rf_nets:
            rf_net_codes.add(net_item.GetNetCode())

    fixed = 0
    for track in board.GetTracks():
        if track.GetNetCode() in rf_net_codes:
            current_width = track.GetWidth()
            target_width = pcbnew.FromMM(TRACK_WIDTH_RF_MM)
            if current_width != target_width:
                track.SetWidth(target_width)
                fixed += 1

    if fixed > 0:
        print(f"  Fixed {fixed} RF track segments to {TRACK_WIDTH_RF_MM}mm width")
    return fixed


def count_tracks(board: pcbnew.BOARD) -> int:
    return len(list(board.GetTracks()))


def check_zones_only_on_inner(board: pcbnew.BOARD) -> bool:
    """Verify no zones on F.Cu or B.Cu."""
    for zone in board.Zones():
        layer = zone.GetLayer()
        if layer == F_CU or layer == B_CU:
            print(f"  FAIL: Zone found on outer layer {layer}")
            return False
    print("  PASS: No zones on F.Cu or B.Cu")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="4-Layer V2-ADC pipeline: NewBoard -> planes -> FreeRouting -> SES -> DRC")
    parser.add_argument("--output", required=True,
                        help="Output .kicad_pcb file path")
    parser.add_argument("--max-passes", type=int, default=32,
                        help="Max FreeRouting passes (default: 32)")
    args = parser.parse_args()

    print("=" * 60)
    print("4-Layer V2-ADC Pipeline")
    print("=" * 60)
    print(f"Output:     {args.output}")
    print(f"Max passes: {args.max_passes}")
    print()

    output_dir = os.path.dirname(args.output) or "."
    base_name = os.path.splitext(os.path.basename(args.output))[0]
    dsn_path = os.path.join(output_dir, f"{base_name}.dsn")
    ses_path = os.path.join(output_dir, f"{base_name}.ses")
    drc_path = os.path.join(output_dir, f"{base_name}_drc.json")
    gerber_dir = os.path.join(output_dir, f"{base_name}_gerbers")

    # STEP 1: Create board with footprints and internal planes
    print("STEP 1: Creating 4-layer board with internal planes...")
    board = create_board_v2_adc_4layer(args.output)
    set_board_design_rules(board)
    add_power_planes(board)
    pcbnew.SaveBoard(args.output, board)
    print(f"  Board created with {len(list(board.Footprints()))} footprints")
    print(f"  Zones: {len(list(board.Zones()))}")

    # STEP 2: Verify zones only on inner layers
    print("\nSTEP 2: Verifying zones...")
    if not check_zones_only_on_inner(board):
        print("FATAL: Zones on outer layers detected")
        return 1

    # STEP 3: Export DSN
    print("\nSTEP 3: Exporting Specctra DSN...")
    if not export_dsn(board, dsn_path):
        print("FATAL: DSN export failed")
        return 1

    # STEP 4: Run FreeRouting
    print("\nSTEP 4: Running FreeRouting autorouter...")
    if not run_freerouting(dsn_path, ses_path, max_passes=args.max_passes):
        print("FATAL: FreeRouting failed")
        return 1

    # STEP 5: Recreate board with planes and import SES
    print("\nSTEP 5: Recreating board and importing SES...")
    board = create_board_v2_adc_4layer(args.output)
    set_board_design_rules(board)
    add_power_planes(board)
    if not import_ses(board, ses_path):
        print("FATAL: SES import failed")
        return 1
    print(f"  Tracks after SES import: {count_tracks(board)}")

    # STEP 6: Fix RF track widths
    print("\nSTEP 6: Fixing RF track widths...")
    fix_rf_track_widths(board, V2_ADC_NETS)

    # STEP 7: Fill zones
    print("\nSTEP 7: Filling zones...")
    fill_zones(board)

    # STEP 8: Save board
    print("\nSTEP 8: Saving board...")
    pcbnew.SaveBoard(args.output, board)
    print(f"  Saved to {args.output}")

    # STEP 9: Run DRC
    print("\nSTEP 9: Running DRC...")
    drc_result = run_drc(args.output, drc_path)

    violations = drc_result.get("violations", [])
    unconnected = drc_result.get("unconnected_items", [])

    print(f"\n  DRC Results:")
    print(f"    Violations:   {len(violations)}")
    print(f"    Unconnected:  {len(unconnected)}")

    # Categorize violations
    from collections import Counter
    vtypes = Counter(v.get("type", "unknown") for v in violations)
    print(f"\n  Violation breakdown:")
    for vtype, count in vtypes.most_common():
        print(f"    {vtype}: {count}")

    # Check quality gates
    print("\n" + "=" * 60)
    print("QUALITY GATES")
    print("=" * 60)

    # Gate 1: 0 shorting_items violations
    shorting = [v for v in violations if "shorting_items" in v.get("type", "")]
    gate1 = len(shorting) == 0
    print(f"Gate 1 (0 shorting_items): {'PASS' if gate1 else 'FAIL'} ({len(shorting)} found)")

    # Gate 2: 0 unconnected items
    gate2 = len(unconnected) == 0
    print(f"Gate 2 (0 unconnected): {'PASS' if gate2 else 'FAIL'} ({len(unconnected)} found)")

    # Gate 3: GND zone covers >90% of board
    gnd_zone_area = 0
    for zone in board.Zones():
        if zone.GetNetname() == 'GND' and zone.GetLayer() == IN1_CU:
            gnd_zone_area = zone.GetOutlineArea()
    board_area = BOARD_WIDTH_MM * BOARD_HEIGHT_MM
    gnd_coverage = gnd_zone_area / board_area if board_area > 0 else 0
    gate3 = gnd_coverage > 0.90
    print(f"Gate 3 (GND zone >90%): {'PASS' if gate3 else 'FAIL'} ({gnd_coverage:.1%})")

    # Gate 4: 3V3 zone covers >90% of board
    v33_zone_area = 0
    for zone in board.Zones():
        if zone.GetNetname() == '3V3' and zone.GetLayer() == IN2_CU:
            v33_zone_area = zone.GetOutlineArea()
    v33_coverage = v33_zone_area / board_area if board_area > 0 else 0
    gate4 = v33_coverage > 0.90
    print(f"Gate 4 (3V3 zone >90%): {'PASS' if gate4 else 'FAIL'} ({v33_coverage:.1%})")

    # Gate 5: No shorting between planes
    plane_shorts = [v for v in violations
                    if "short" in v.get("type", "").lower()
                    and ("plane" in str(v).lower() or "zone" in str(v).lower())]
    gate5 = len(plane_shorts) == 0
    print(f"Gate 5 (no plane shorts): {'PASS' if gate5 else 'FAIL'} ({len(plane_shorts)} found)")

    # Gate 6: No copper pours on F.Cu or B.Cu
    outer_zones = [z for z in board.Zones() if z.GetLayer() in (F_CU, B_CU)]
    gate6 = len(outer_zones) == 0
    print(f"Gate 6 (no outer zones): {'PASS' if gate6 else 'FAIL'} ({len(outer_zones)} found)")

    # Gate 7: RF traces use 0.76mm width
    rf_ok = True
    rf_nets = {'RF_SUB_868', 'RF_2G4_2400'}
    for net_name in rf_nets:
        for net_name_key, net_item in board.GetNetInfo().NetsByName().items():
            if str(net_name_key) == net_name:
                net_code = net_item.GetNetCode()
                for track in board.GetTracks():
                    if track.GetNetCode() == net_code:
                        w_mm = track.GetWidth() / 1e6
                        if abs(w_mm - TRACK_WIDTH_RF_MM) > 0.01:
                            print(f"  RF width issue: {net_name} track {w_mm}mm != {TRACK_WIDTH_RF_MM}mm")
                            rf_ok = False
    gate7 = rf_ok
    print(f"Gate 7 (RF 0.76mm): {'PASS' if gate7 else 'FAIL'}")

    all_gates = gate1 and gate2 and gate3 and gate4 and gate5 and gate6 and gate7

    if all_gates:
        print("\n" + "=" * 60)
        print("ALL QUALITY GATES PASSED!")
        print("=" * 60)

        # STEP 10: Export gerbers
        print(f"\nSTEP 10: Exporting gerbers to {gerber_dir}...")
        os.makedirs(gerber_dir, exist_ok=True)

        # Export all layers including inner layers
        for layer_name in ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu", "F.SilkS", "B.SilkS",
                           "F.Mask", "B.Mask", "Edge.Cuts", "F.Paste", "B.Paste"]:
            cmd = [
                "kicad-cli", "pcb", "export", "gerbers",
                "--output", gerber_dir,
                "--layers", layer_name,
                args.output,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            status = "OK" if result.returncode == 0 else f"FAIL({result.returncode})"
            print(f"  {layer_name:12s}: {status}")

        # Drill export
        cmd = [
            "kicad-cli", "pcb", "export", "drill",
            "--output", gerber_dir,
            "--format", "excellon",
            args.output,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        status = "OK" if result.returncode == 0 else f"FAIL({result.returncode})"
        print(f"  {'drill':12s}: {status}")

        # Create zip
        zip_path = os.path.join(output_dir, f"{base_name}_gerbers.zip")
        cwd = os.getcwd()
        os.chdir(output_dir)
        result = subprocess.run(
            ["zip", "-r", f"{base_name}_gerbers.zip", f"{base_name}_gerbers/"],
            capture_output=True, text=True)
        os.chdir(cwd)
        print(f"  Created {zip_path}")

        return 0
    else:
        print(f"\nViolations: {len(violations)} found")
        if len(violations) > 10:
            print("CIRCUIT BREAKER: >10 violations — manual routing forbidden")
            return 2
        elif len(violations) > 5:
            print("WARNING: 6-10 violations — manual review recommended")
            return 1
        else:
            print("<=5 violations — may be fixable manually")
            return 1


if __name__ == "__main__":
    sys.exit(main())
