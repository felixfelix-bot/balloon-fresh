#!/usr/bin/python3.14
"""
Parse Specctra SES file and create tracks on a KiCad board.
Used because pcbnew.ImportSpecctraSES() fails headless (needs wxApp/LoadBoard).

SES format:
  (net "NETNAME"
    (wire
      (path F.Cu 2000
        x1 y1
        x2 y2
        ...
      )
    )
    (via "Via[0-1]_600:300_um" x y)
    ...
  )

Coordinates are in units of (resolution um 10) = 0.01um = 10nm
Width is in same units (2000 = 2000 * 0.01um = 20um = 0.02mm... wait no)
Actually: resolution um 10 means 10 units = 1 um, so 1 unit = 0.1 um = 100nm
Width 2000 = 2000 * 0.1 um = 200 um = 0.2mm
Coordinates: 40000 = 40000 * 0.1 um = 4000 um = 4mm (matches U3 at x=4mm)
"""

import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import re
import pcbnew

F_CU = 0  # pcbnew.F_Cu
B_CU = 2  # pcbnew.B_Cu

# SES resolution: um 10 means 10 units = 1 um, so 1 unit = 0.1 um = 100 nm
# pcbnew uses nm internally, so: nm = ses_units * 100
SES_UNIT_TO_NM = 100  # 1 SES unit = 100 nm = 0.1 um


def parse_ses_layer(layer_str: str) -> int:
    """Convert SES layer name to KiCad layer constant."""
    if layer_str == "F.Cu":
        return F_CU
    elif layer_str == "B.Cu":
        return B_CU
    else:
        print(f"  WARNING: Unknown SES layer '{layer_str}', defaulting to F.Cu")
        return F_CU


def ses_to_nm_x(val: int) -> int:
    """Convert SES X coordinate to KiCad nanometers. X is same direction."""
    return val * SES_UNIT_TO_NM


def ses_to_nm_y(val: int) -> int:
    """Convert SES Y coordinate to KiCad nanometers. Y is INVERTED (DSN uses math convention, KiCad uses screen convention)."""
    return -val * SES_UNIT_TO_NM


def ses_to_mm(val: int) -> float:
    """Convert SES coordinate/width to millimeters."""
    return val * SES_UNIT_TO_NM / 1_000_000.0


def parse_ses_file(ses_path: str):
    """
    Parse SES file and return list of (net_name, layer, width_nm, points_nm, is_via, via_x_nm, via_y_nm) tuples.
    Each wire is a track segment series. Vias are separate.
    """
    with open(ses_path, 'r') as f:
        content = f.read()

    # Find the network_out section
    net_match = re.search(r'\(network_out\s+', content)
    if not net_match:
        print("  ERROR: No network_out section in SES file")
        return []

    # Parse nets
    results = []

    # Find all net blocks
    net_pattern = re.compile(r'\(net\s+"([^"]+)"\s', re.MULTILINE)
    for net_match in net_pattern.finditer(content):
        net_name = net_match.group(1)
        net_start = net_match.start()

        # Find the end of this net block (next net or end of network_out)
        next_net = net_pattern.search(content, net_match.end())
        if next_net:
            net_end = next_net.start()
        else:
            # Find closing paren of network_out
            net_end = content.rfind(')')

        net_content = content[net_start:net_end]

        # Parse wires in this net
        # (wire (path LAYER WIDTH\n  x1 y1\n  x2 y2\n  ...) )
        wire_pattern = re.compile(
            r'\(wire\s+\(path\s+(\S+)\s+(\d+)\s+([\d\s\-]+)\)',
            re.DOTALL
        )
        for wire_match in wire_pattern.finditer(net_content):
            layer_str = wire_match.group(1)
            width_ses = int(wire_match.group(2))
            coords_str = wire_match.group(3).strip()

            # Parse coordinates (Y axis is inverted between DSN and KiCad)
            coords = coords_str.split()
            points = []
            for i in range(0, len(coords) - 1, 2):
                x = ses_to_nm_x(int(coords[i]))
                y = ses_to_nm_y(int(coords[i + 1]))
                points.append((x, y))

            if len(points) >= 2:
                layer = parse_ses_layer(layer_str)
                width_nm = ses_to_nm_x(width_ses)  # width is not affected by Y inversion
                results.append({
                    'type': 'wire',
                    'net': net_name,
                    'layer': layer,
                    'width_nm': width_nm,
                    'points': points
                })

        # Parse vias (match any via span, e.g. Via[0-1], Via[0-3], Via[1-2])
        via_pattern = re.compile(
            r'\(via\s+"Via\[\d+-\d+\]_\d+:\d+_um"\s+(-?\d+)\s+(-?\d+)\s*\)'
        )
        for via_match in via_pattern.finditer(net_content):
            x = ses_to_nm_x(int(via_match.group(1)))
            y = ses_to_nm_y(int(via_match.group(2)))
            results.append({
                'type': 'via',
                'net': net_name,
                'x_nm': x,
                'y_nm': y,
                'via_size_nm': ses_to_nm_x(6000),  # 600um = 0.6mm
                'drill_size_nm': ses_to_nm_x(3000),  # 300um = 0.3mm
            })

    return results


def apply_ses_to_board(board: pcbnew.BOARD, ses_path: str, net_defs: dict = None):
    """Parse SES file and create tracks + vias on the board."""
    routes = parse_ses_file(ses_path)

    print(f"  Parsed {len(routes)} routes from SES file")

    # Get net info from board
    # NOTE: NetsByName keys are wxString, not plain str — convert explicitly
    net_info = board.GetNetInfo()
    nets_by_name = {}
    for net_name_key, net_item in net_info.NetsByName().items():
        net_name = str(net_name_key)
        if net_name:
            nets_by_name[net_name] = net_item.GetNetCode()

    # RF net width overrides
    rf_width_nm = pcbnew.FromMM(0.76)
    rf_nets = set()
    if net_defs:
        for name, props in net_defs.items():
            if props.get("width") == 0.76:  # TRACK_WIDTH_RF_MM
                rf_nets.add(name)

    wire_count = 0
    via_count = 0

    for route in routes:
        net_name = route['net']
        if net_name not in nets_by_name:
            print(f"  WARNING: Net '{net_name}' not found on board, skipping")
            continue

        net_code = nets_by_name[net_name]

        if route['type'] == 'wire':
            layer = route['layer']
            width = route['width_nm']

            # Override width for RF nets
            if net_name in rf_nets:
                width = rf_width_nm

            points = route['points']

            # Create track segments for consecutive point pairs
            for i in range(len(points) - 1):
                track = pcbnew.PCB_TRACK(board)
                track.SetLayer(layer)
                track.SetWidth(width)
                track.SetNetCode(net_code)

                start = pcbnew.VECTOR2I(points[i][0], points[i][1])
                end = pcbnew.VECTOR2I(points[i + 1][0], points[i + 1][1])
                track.SetStart(start)
                track.SetEnd(end)

                board.Add(track)
                wire_count += 1

        elif route['type'] == 'via':
            via = pcbnew.PCB_VIA(board)
            via.SetNetCode(net_code)
            via.SetPosition(pcbnew.VECTOR2I(route['x_nm'], route['y_nm']))
            via.SetViaType(pcbnew.VIATYPE_THROUGH)
            via.SetWidth(route['via_size_nm'])
            via.SetDrill(route['drill_size_nm'])
            board.Add(via)
            via_count += 1

    print(f"  Created {wire_count} track segments and {via_count} vias")
    return wire_count, via_count


if __name__ == "__main__":
    import os

    if len(sys.argv) < 3:
        print("Usage: ses_import.py <board.kicad_pcb> <session.ses> [output.kicad_pcb]")
        sys.exit(1)

    board_path = sys.argv[1]
    ses_path = sys.argv[2]
    output_path = sys.argv[3] if len(sys.argv) > 3 else board_path

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from full_pipeline import create_board_v1_fast, create_board_v2_adc, ripup_all_tracks

    # Determine board type from filename
    if "v1_fast" in board_path.lower() or "v1-fast" in board_path.lower():
        create_fn = create_board_v1_fast
    else:
        create_fn = create_board_v2_adc

    # Create fresh board
    print(f"Creating fresh board...")
    board = create_fn(output_path)
    ripup_all_tracks(board)

    # Apply SES routes
    print(f"Importing SES from {ses_path}...")
    apply_ses_to_board(board, ses_path)

    # Save
    pcbnew.SaveBoard(output_path, board)
    print(f"Saved to {output_path}")
    print(f"  Tracks: {len(list(board.GetTracks()))}")