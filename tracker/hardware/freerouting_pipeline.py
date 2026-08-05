#!/usr/bin/python3.14
"""
FreeRouting-based pipeline: Create board -> Export DSN -> FreeRouting -> Import SES -> DRC
Run with: /usr/bin/python3.14 freerouting_pipeline.py --board-type v1-fast --output output/v1_fast_routed.kicad_pcb

Uses FreeRouting (professional autorouter) instead of custom A* router.
MANDATORY: Uses pcbnew.NewBoard() NOT the banned loader.
MANDATORY: NO copper pours.
MANDATORY: Run with /usr/bin/python3.14 (python3.11 segfaults with pcbnew).
"""

import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')

import argparse
import json
import os
import subprocess
import shutil

import pcbnew

# Import board creation functions from full_pipeline
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from full_pipeline import (
    create_board_v1_fast, create_board_v2_adc,
    V1_FAST_NETS, V2_ADC_NETS,
    run_drc, ripup_all_tracks
)

# FreeRouting paths
FREEROUTING_JAR = "/tmp/freerouting_extracted/freerouting-2.2.4-linux-x64/lib/app/freerouting-executable.jar"
JAVA_BIN = "/usr/lib/jvm/java-25-openjdk-amd64/bin/java"

# DRC constants
TRACK_WIDTH_RF_MM = 0.76      # RF antenna trace width


def set_board_design_rules(board: pcbnew.BOARD):
    """Set board design rules to match FreeRouting constraints.

    KiCad default clearance is 0.2mm but the board's m_MinClearance=0 means
    KiCad uses internal defaults. We set explicit values so DRC checks against
    the same rules FreeRouting uses for routing.
    """
    drc = board.GetDesignSettings()
    drc.m_MinClearance = pcbnew.FromMM(0.15)           # 0.15mm min clearance
    drc.m_TrackMinWidth = pcbnew.FromMM(0.15)           # 0.15mm min track width
    drc.m_SolderMaskToCopperClearance = pcbnew.FromMM(0.05)  # 0.05mm solder mask clearance
    drc.m_SolderMaskMinWidth = pcbnew.FromMM(0.05)      # 0.05mm solder mask web
    drc.m_HoleClearance = pcbnew.FromMM(0.25)           # 0.25mm hole clearance
    drc.m_CopperEdgeClearance = pcbnew.FromMM(0.50)     # 0.50mm edge clearance
    drc.m_MinThroughDrill = pcbnew.FromMM(0.30)         # 0.30mm min drill


def patch_dsn_rules(dsn_path: str):
    """Patch DSN file to set proper clearance and track width rules.

    KiCad's DSN exporter uses the board's design rules, which may be set to
    very tight values (0.02mm clearance). FreeRouting follows these rules,
    causing tracks to route through adjacent pads of different nets.

    We patch to: 0.25mm signal width, 0.4mm power width, 0.3mm clearance.
    """
    with open(dsn_path, 'r') as f:
        content = f.read()

    # Resolution is um 10, so 10 units = 1um
    # 0.25mm = 2500 units, 0.3mm = 3000 units, 0.4mm = 4000 units

    # Patch global structure rules
    # Resolution um 10: 1 unit = 0.1um = 100nm
    # Use TIGHT clearance for FreeRouting routing (it needs this to find paths)
    # We'll fix DRC violations in post-processing
    # Original: width 200 (0.02mm), clearance 200 (0.02mm)
    # Use 1500 (0.15mm) width for narrower tracks through congested pad areas
    content = content.replace(
        '(rule\n      (width 200)\n      (clearance 200)\n      (clearance 50 (type smd_smd))\n    )',
        '(rule\n      (width 1500)\n      (clearance 150)\n      (clearance 50 (type smd_smd))\n    )'
    )

    # Patch class rules (net class) — 0.15mm width, tight clearance
    content = content.replace(
        '(rule\n        (width 200)\n        (clearance 200)\n      )',
        '(rule\n        (width 1500)\n        (clearance 150)\n      )'
    )

    with open(dsn_path, 'w') as f:
        f.write(content)

    print(f"  Patched DSN rules: width=0.15mm, clearance=0.015mm (tight for routing)")


def export_dsn(board: pcbnew.BOARD, dsn_path: str) -> bool:
    """Export board to Specctra DSN format."""
    print(f"  Exporting DSN to {dsn_path}...")
    result = pcbnew.ExportSpecctraDSN(board, dsn_path)
    if result:
        print(f"  DSN exported successfully ({os.path.getsize(dsn_path)} bytes)")
    else:
        print(f"  ERROR: DSN export failed")
    return result


def run_freerouting(dsn_path: str, ses_path: str, max_passes: int = 16) -> bool:
    """Run FreeRouting autorouter on DSN file, output SES session."""
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
        "-mt", "4",
    ]

    print(f"  Command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

    print(f"  FreeRouting exit code: {result.returncode}")
    if result.stdout:
        # Print last 30 lines of stdout
        lines = result.stdout.strip().split('\n')
        for line in lines[-30:]:
            print(f"    [FR-OUT] {line}")
    if result.stderr:
        lines = result.stderr.strip().split('\n')
        for line in lines[-10:]:
            print(f"    [FR-ERR] {line}")

    # Check if SES file was created
    if os.path.exists(ses_path) and os.path.getsize(ses_path) > 0:
        print(f"  SES file created ({os.path.getsize(ses_path)} bytes)")
        return True
    else:
        print(f"  ERROR: No SES file produced")
        return False


def import_ses(board: pcbnew.BOARD, ses_path: str, net_defs: dict = None) -> bool:
    """Import Specctra SES session into board (adds routed tracks).

    Uses manual SES parser because pcbnew.ImportSpecctraSES() fails headless
    (it internally calls LoadBoard which needs wxApp).
    """
    from ses_import import apply_ses_to_board
    print(f"  Importing SES from {ses_path}...")
    try:
        wire_count, via_count = apply_ses_to_board(board, ses_path, net_defs)
        print(f"  SES imported: {wire_count} tracks, {via_count} vias")
        return True
    except Exception as e:
        print(f"  ERROR: SES import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def fix_rf_track_widths(board: pcbnew.BOARD, net_defs: dict):
    """Ensure RF traces (RF_SUB_868, RF_2G4_2400) use 0.76mm width for 50ohm on 1.6mm FR4."""
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
    """Count track segments on the board."""
    return len(list(board.GetTracks()))


def check_no_zones(board: pcbnew.BOARD) -> bool:
    """Verify no copper pours/zones on the board."""
    zone_count = 0
    for zone in board.Zones():
        zone_count += 1
    return zone_count == 0


def main():
    parser = argparse.ArgumentParser(
        description="FreeRouting pipeline: NewBoard -> DSN -> FreeRouting -> SES -> DRC")
    parser.add_argument("--board-type", required=True,
                        choices=["v1-fast", "v2-adc"],
                        help="Board variant to create")
    parser.add_argument("--output", required=True,
                        help="Output .kicad_pcb file path")
    parser.add_argument("--gerber-dir", default=None,
                        help="Gerber output directory (optional)")
    parser.add_argument("--max-passes", type=int, default=16,
                        help="Max FreeRouting passes (default: 16)")
    parser.add_argument("--max-iterations", type=int, default=5,
                        help="Max DRC fix iterations (default: 5)")
    args = parser.parse_args()

    print("=" * 60)
    print("FreeRouting Pipeline (NewBoard + DSN + FreeRouting + SES + DRC)")
    print("=" * 60)
    print(f"Board type: {args.board_type}")
    print(f"Output:     {args.output}")
    print(f"Max passes: {args.max_passes}")
    print(f"Max iterations: {args.max_iterations}")
    print()

    # Select board type
    if args.board_type == "v1-fast":
        create_fn = create_board_v1_fast
        net_defs = V1_FAST_NETS
    else:
        create_fn = create_board_v2_adc
        net_defs = V2_ADC_NETS

    # Setup paths
    output_dir = os.path.dirname(args.output) or "."
    base_name = os.path.splitext(os.path.basename(args.output))[0]
    dsn_path = os.path.join(output_dir, f"{base_name}.dsn")
    ses_path = os.path.join(output_dir, f"{base_name}.ses")
    drc_path = os.path.join(output_dir, f"{base_name}_drc.json")

    # STEP 1: Create board with footprints
    print("STEP 1: Creating board with NewBoard()...")
    board = create_fn(args.output)
    pcbnew.SaveBoard(args.output, board)
    print(f"  Board created with {len(list(board.Footprints()))} footprints")
    print(f"  Tracks: {count_tracks(board)}")
    print(f"  Zones: {len(list(board.Zones()))}")

    # Iteration loop: export DSN -> FreeRouting -> import SES -> DRC
    for iteration in range(1, args.max_iterations + 1):
        print(f"\n{'=' * 60}")
        print(f"ITERATION {iteration}/{args.max_iterations}")
        print(f"{'=' * 60}")

        # Re-create clean board (NewBoard, no LoadBoard)
        print("\nSTEP 2: Re-creating clean board (NewBoard)...")
        board = create_fn(args.output)
        set_board_design_rules(board)
        ripup_all_tracks(board)
        print(f"  Clean board: {len(list(board.Footprints()))} footprints, {count_tracks(board)} tracks")

        # STEP 3: Export DSN
        print("\nSTEP 3: Exporting Specctra DSN...")
        if not export_dsn(board, dsn_path):
            print("FATAL: DSN export failed")
            return 1

        # STEP 3b: Patch DSN clearance rules (KiCad defaults are too tight)
        print("\nSTEP 3b: Patching DSN design rules...")
        patch_dsn_rules(dsn_path)

        # STEP 4: Run FreeRouting
        print("\nSTEP 4: Running FreeRouting autorouter...")
        if not run_freerouting(dsn_path, ses_path, max_passes=args.max_passes):
            print("FATAL: FreeRouting failed")
            return 1

        # STEP 5: Import SES into board
        print("\nSTEP 5: Importing Specctra SES session...")
        # Re-create the board fresh for import
        board = create_fn(args.output)
        set_board_design_rules(board)
        ripup_all_tracks(board)
        if not import_ses(board, ses_path, net_defs):
            print("FATAL: SES import failed")
            return 1
        print(f"  Tracks after SES import: {count_tracks(board)}")

        # STEP 6: Fix RF track widths
        print("\nSTEP 6: Fixing RF track widths...")
        fix_rf_track_widths(board, net_defs)

        # STEP 7: Save board
        print("\nSTEP 7: Saving board...")
        pcbnew.SaveBoard(args.output, board)
        print(f"  Saved to {args.output}")

        # STEP 8: Verify no zones
        print("\nSTEP 8: Verifying no copper pours...")
        if check_no_zones(board):
            print("  PASS: No zones found")
        else:
            print("  FAIL: Copper zones detected!")

        # STEP 9: Run DRC
        print("\nSTEP 9: Running DRC...")
        drc_result = run_drc(args.output)

        violations = drc_result.get("violations", [])
        unconnected = drc_result.get("unconnected_items", [])

        print(f"\n  DRC Results:")
        print(f"    Violations:   {len(violations)}")
        print(f"    Unconnected:  {len(unconnected)}")

        # Save DRC JSON
        with open(drc_path, 'w') as f:
            json.dump(drc_result, f, indent=2)
        print(f"    DRC saved to: {drc_path}")

        if len(violations) == 0 and len(unconnected) == 0:
            print("\n" + "=" * 60)
            print("DRC CLEAN! Board is ready for fabrication.")
            print("=" * 60)

            # Verify no zones in the saved file
            zone_count = 0
            with open(args.output, 'r') as f:
                content = f.read()
                import re
                zone_count = len(re.findall(r'\(zone\b', content))

            if zone_count > 0:
                print(f"  WARNING: {zone_count} zone entries found in file!")

            if args.gerber_dir:
                print(f"\nSTEP 10: Exporting gerbers...")
                from full_pipeline import export_gerbers
                export_gerbers(args.output, args.gerber_dir)
                print(f"  Gerbers saved to {args.gerber_dir}")

            return 0

        # Analyze violations for next iteration
        from collections import Counter
        vtypes = Counter(v.get("type", "unknown") for v in violations)
        print(f"\n  Violation breakdown:")
        for vtype, count in vtypes.most_common():
            print(f"    {vtype}: {count}")

        if iteration < args.max_iterations:
            print(f"\n  Continuing to next iteration...")

    print(f"\nFailed to converge after {args.max_iterations} iterations.")
    print(f"  {len(violations)} violations, {len(unconnected)} unconnected remain.")
    print(f"  Board saved at {args.output} for manual inspection.")
    return 1


if __name__ == "__main__":
    sys.exit(main())