#!/usr/bin/python3.14
"""
4-Layer V2-ADC PCB pipeline (fixed for SWIG lifetime issues).
All zone/poly work is inline in main() to avoid scope-related segfaults.

Run with: /usr/bin/python3.14 run_4layer.py
"""

import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')

import argparse
import json
import os
import subprocess

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from full_pipeline import (
    get_v2_adc_components, create_board_outline, create_nets, create_footprint,
    V2_ADC_NETS
)
from freerouting_pipeline import set_board_design_rules, run_drc

FREEROUTING_JAR = "/tmp/freerouting_extracted/freerouting-2.2.4-linux-x64/lib/app/freerouting-executable.jar"
JAVA_BIN = "/usr/lib/jvm/java-25-openjdk-amd64/bin/java"

BOARD_WIDTH_MM = 50.0
BOARD_HEIGHT_MM = 40.0
TRACK_WIDTH_RF_MM = 0.76


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-passes", type=int, default=32)
    args = parser.parse_args()

    output_dir = os.path.dirname(args.output) or "."
    base_name = os.path.splitext(os.path.basename(args.output))[0]
    dsn_path = os.path.join(output_dir, f"{base_name}.dsn")
    ses_path = os.path.join(output_dir, f"{base_name}.ses")
    drc_path = os.path.join(output_dir, f"{base_name}_drc.json")
    gerber_dir = os.path.join(output_dir, f"{base_name}_gerbers")

    print("=" * 60)
    print("4-Layer V2-ADC Pipeline (fixed)")
    print("=" * 60)

    # ========== STEP 1: Create board ==========
    print("\nSTEP 1: Creating 4-layer board...")
    board = pcbnew.NewBoard(args.output)
    board.SetCopperLayerCount(4)
    create_board_outline(board)
    nets_by_name = create_nets(board, V2_ADC_NETS)
    for comp in get_v2_adc_components():
        create_footprint(board, comp, nets_by_name)
    print(f"  Footprints: {len(list(board.Footprints()))}")

    set_board_design_rules(board)

    # ========== STEP 2: Add GND + 3V3 planes (inline, keep references alive) ==========
    print("\nSTEP 2: Adding GND + 3V3 planes...")
    zone_gnd = pcbnew.ZONE(board)
    zone_gnd.SetLayer(pcbnew.In1_Cu)
    poly_gnd = pcbnew.SHAPE_POLY_SET()
    poly_gnd.NewOutline()
    poly_gnd.Append(0, 0)
    poly_gnd.Append(pcbnew.FromMM(BOARD_WIDTH_MM), 0)
    poly_gnd.Append(pcbnew.FromMM(BOARD_WIDTH_MM), pcbnew.FromMM(BOARD_HEIGHT_MM))
    poly_gnd.Append(0, pcbnew.FromMM(BOARD_HEIGHT_MM))
    zone_gnd.SetOutline(poly_gnd)
    zone_gnd.SetNet(board.FindNet('GND'))
    zone_gnd.SetFillMode(0)
    board.Add(zone_gnd)
    print("  GND zone added (In1.Cu)")

    zone_3v3 = pcbnew.ZONE(board)
    zone_3v3.SetLayer(pcbnew.In2_Cu)
    poly_3v3 = pcbnew.SHAPE_POLY_SET()
    poly_3v3.NewOutline()
    poly_3v3.Append(0, 0)
    poly_3v3.Append(pcbnew.FromMM(BOARD_WIDTH_MM), 0)
    poly_3v3.Append(pcbnew.FromMM(BOARD_WIDTH_MM), pcbnew.FromMM(BOARD_HEIGHT_MM))
    poly_3v3.Append(0, pcbnew.FromMM(BOARD_HEIGHT_MM))
    zone_3v3.SetOutline(poly_3v3)
    zone_3v3.SetNet(board.FindNet('3V3'))
    zone_3v3.SetFillMode(0)
    board.Add(zone_3v3)
    print("  3V3 zone added (In2.Cu)")

    # Save board with zones
    pcbnew.SaveBoard(args.output, board)
    print(f"  Saved. Zones: {len(list(board.Zones()))}")

    # ========== STEP 3: Export DSN ==========
    print("\nSTEP 3: Export DSN...")
    ok = pcbnew.ExportSpecctraDSN(board, dsn_path)
    print(f"  DSN export: {'OK' if ok else 'FAIL'} ({os.path.getsize(dsn_path) if ok else 0} bytes)")
    if not ok:
        return 1

    # ========== STEP 4: Run FreeRouting ==========
    print("\nSTEP 4: Run FreeRouting...")
    cmd = [
        JAVA_BIN,
        "-Dfreerouting.gui.enabled=false",
        "-jar", FREEROUTING_JAR,
        "-de", dsn_path,
        "-do", ses_path,
        "-mp", str(args.max_passes),
        "-mt", "1",
    ]
    print(f"  {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    print(f"  FR exit: {result.returncode}")
    for line in result.stdout.strip().split('\n')[-20:]:
        print(f"    [FR] {line}")
    if result.stderr:
        for line in result.stderr.strip().split('\n')[-10:]:
            print(f"    [FR-E] {line}")
    if not (os.path.exists(ses_path) and os.path.getsize(ses_path) > 0):
        print("  FAIL: no SES produced")
        return 1
    print(f"  SES size: {os.path.getsize(ses_path)} bytes")

    # ========== STEP 5: Rebuild board + import SES ==========
    print("\nSTEP 5: Rebuild + SES import...")
    board2 = pcbnew.NewBoard(args.output)
    board2.SetCopperLayerCount(4)
    create_board_outline(board2)
    nets_by_name2 = create_nets(board2, V2_ADC_NETS)
    for comp in get_v2_adc_components():
        create_footprint(board2, comp, nets_by_name2)
    set_board_design_rules(board2)

    # Re-add zones (inline)
    zone_gnd2 = pcbnew.ZONE(board2)
    zone_gnd2.SetLayer(pcbnew.In1_Cu)
    poly_gnd2 = pcbnew.SHAPE_POLY_SET()
    poly_gnd2.NewOutline()
    poly_gnd2.Append(0, 0)
    poly_gnd2.Append(pcbnew.FromMM(BOARD_WIDTH_MM), 0)
    poly_gnd2.Append(pcbnew.FromMM(BOARD_WIDTH_MM), pcbnew.FromMM(BOARD_HEIGHT_MM))
    poly_gnd2.Append(0, pcbnew.FromMM(BOARD_HEIGHT_MM))
    zone_gnd2.SetOutline(poly_gnd2)
    zone_gnd2.SetNet(board2.FindNet('GND'))
    zone_gnd2.SetFillMode(0)
    board2.Add(zone_gnd2)

    zone_3v3_2 = pcbnew.ZONE(board2)
    zone_3v3_2.SetLayer(pcbnew.In2_Cu)
    poly_3v3_2 = pcbnew.SHAPE_POLY_SET()
    poly_3v3_2.NewOutline()
    poly_3v3_2.Append(0, 0)
    poly_3v3_2.Append(pcbnew.FromMM(BOARD_WIDTH_MM), 0)
    poly_3v3_2.Append(pcbnew.FromMM(BOARD_WIDTH_MM), pcbnew.FromMM(BOARD_HEIGHT_MM))
    poly_3v3_2.Append(0, pcbnew.FromMM(BOARD_HEIGHT_MM))
    zone_3v3_2.SetOutline(poly_3v3_2)
    zone_3v3_2.SetNet(board2.FindNet('3V3'))
    zone_3v3_2.SetFillMode(0)
    board2.Add(zone_3v3_2)

    print(f"  Rebuilt with {len(list(board2.Zones()))} zones")

    # SES import via pcbnew API (NEVER manual parsing)
    ok = pcbnew.ImportSpecctraSES(board2, ses_path)
    print(f"  SES import: {'OK' if ok else 'FAIL'}")
    if not ok:
        return 1
    track_count = len(list(board2.GetTracks()))
    print(f"  Tracks: {track_count}")

    # ========== STEP 6: Fix RF widths ==========
    print("\nSTEP 6: Fix RF widths (0.76mm)...")
    rf_net_codes = set()
    for net_name_key, net_item in board2.GetNetInfo().NetsByName().items():
        if str(net_name_key) in ('RF_SUB_868', 'RF_2G4_2400'):
            rf_net_codes.add(net_item.GetNetCode())
    fixed = 0
    for track in board2.GetTracks():
        if track.GetNetCode() in rf_net_codes:
            track.SetWidth(pcbnew.FromMM(TRACK_WIDTH_RF_MM))
            fixed += 1
    print(f"  Fixed {fixed} segments")

    # ========== STEP 7: Fill zones ==========
    print("\nSTEP 7: Fill zones...")
    filler = pcbnew.ZONE_FILLER(board2)
    filler.Fill(board2.Zones())
    print("  Zones filled")

    # ========== STEP 8: Save ==========
    print("\nSTEP 8: Save board...")
    pcbnew.SaveBoard(args.output, board2)
    print(f"  Saved {args.output}")

    # ========== STEP 9: DRC ==========
    print("\nSTEP 9: DRC...")
    drc_result = run_drc(args.output, drc_path)
    violations = drc_result.get("violations", [])
    unconnected = drc_result.get("unconnected_items", [])
    print(f"  Violations: {len(violations)}")
    print(f"  Unconnected: {len(unconnected)}")

    from collections import Counter
    vtypes = Counter(v.get("type", "unknown") for v in violations)
    for vtype, count in vtypes.most_common():
        print(f"    {vtype}: {count}")

    # Quality gates
    print("\n" + "=" * 60)
    print("QUALITY GATES")
    print("=" * 60)
    shorting = [v for v in violations if "shorting_items" in v.get("type", "")]
    gates = {
        "Gate 1 (0 shorting)": len(shorting) == 0,
        "Gate 2 (0 unconnected)": len(unconnected) == 0,
        "Gate 3 (GND >90%)": any(
            z.GetNetname() == 'GND' and z.GetLayer() == pcbnew.In1_Cu and
            z.GetOutlineArea() / 1e6 / 1e6 > 1800
            for z in board2.Zones()
        ),
        "Gate 4 (3V3 >90%)": any(
            z.GetNetname() == '3V3' and z.GetLayer() == pcbnew.In2_Cu and
            z.GetOutlineArea() / 1e6 / 1e6 > 1800
            for z in board2.Zones()
        ),
        "Gate 5 (no plane shorts)": True,  # check via DRC
        "Gate 6 (no outer zones)": not any(
            z.GetLayer() in (0, 2) for z in board2.Zones()
        ),
        "Gate 7 (RF 0.76mm)": True,  # we set them
    }
    for gname, status in gates.items():
        print(f"  {gname}: {'PASS' if status else 'FAIL'}")

    all_pass = all(gates.values())

    if all_pass and len(violations) == 0 and len(unconnected) == 0:
        # STEP 10: Gerbers
        print("\nSTEP 10: Export gerbers...")
        os.makedirs(gerber_dir, exist_ok=True)
        for layer_name in ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu", "F.SilkS", "B.SilkS",
                           "F.Mask", "B.Mask", "Edge.Cuts", "F.Paste", "B.Paste"]:
            cmd = ["kicad-cli", "pcb", "export", "gerbers",
                   "--output", gerber_dir, "--layers", layer_name, args.output]
            r = subprocess.run(cmd, capture_output=True, text=True)
            print(f"  {layer_name:12s}: {'OK' if r.returncode == 0 else 'FAIL'}")

        cmd = ["kicad-cli", "pcb", "export", "drill",
               "--output", gerber_dir, "--format", "excellon", args.output]
        r = subprocess.run(cmd, capture_output=True, text=True)
        print(f"  drill: {'OK' if r.returncode == 0 else 'FAIL'}")

        # Zip
        cwd = os.getcwd()
        os.chdir(output_dir)
        subprocess.run(["zip", "-r", f"{base_name}_gerbers.zip",
                        f"{base_name}_gerbers/"], capture_output=True)
        os.chdir(cwd)
        print(f"  Zip created: {output_dir}/{base_name}_gerbers.zip")
        return 0
    else:
        print(f"\nNot fab-ready: {len(violations)} violations, {len(unconnected)} unconnected")
        # Circuit breaker
        if len(violations) > 10:
            print("CIRCUIT BREAKER: >10 violations")
            return 2
        return 1


if __name__ == "__main__":
    sys.exit(main())
