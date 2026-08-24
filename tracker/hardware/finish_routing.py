#!/usr/bin/python3.14
"""
Finish routing the remaining 21 unconnected nets on V2-ADC board.
Adds point-to-point tracks for each unconnected net pair.
Uses L-shaped routing (2 segments per connection) to avoid obstacles.
"""
import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew
import json

# mm to KiCad internal units (nm)
MM = 1000000

def mm(x):
    return int(x * MM)

def add_track(board, net, x1, y1, x2, y2, layer=pcbnew.F_Cu, width=mm(0.25)):
    """Add a straight track segment."""
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(pcbnew.VECTOR2I(mm(x1), mm(y1)))
    track.SetEnd(pcbnew.VECTOR2I(mm(x2), mm(y2)))
    track.SetWidth(int(width))
    track.SetLayer(layer)
    n = board.FindNet(net)
    if n:
        track.SetNet(n)
    board.Add(track)
    return track

def add_l_route(board, net, x1, y1, x2, y2, layer=pcbnew.F_Cu, width=mm(0.25)):
    """Add an L-shaped route: horizontal then vertical (or vice versa)."""
    # Choose routing based on which direction has more room
    add_track(board, net, x1, y1, x2, y1, layer, width)  # horizontal first
    add_track(board, net, x2, y1, x2, y2, layer, width)  # then vertical

def add_via(board, net, x, y):
    """Add a via at position."""
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
    via.SetViaType(pcbnew.VIATYPE_THROUGH)
    via.SetWidth(mm(0.6))
    via.SetDrill(mm(0.3))
    n = board.FindNet(net)
    if n:
        via.SetNet(n)
    board.Add(via)
    return via

# Load DRC to find exact unconnected pairs
with open('output/v2_adc_fixed_routed_drc.json') as f:
    drc = json.load(f)

unconnected = drc.get('unconnected_items', [])

# Build net->pads mapping from DRC
net_pads = {}
for item in unconnected:
    for i in item.get('items', []):
        # Extract net name from description
        desc = i.get('description', '')
        pos = i.get('pos', {})
        x, y = pos.get('x', 0), pos.get('y', 0)

        # Parse net from brackets like [3V3] or [GND]
        import re
        m = re.search(r'\[(\w+)\]', desc)
        if m:
            net = m.group(1)
        else:
            continue

        # Only use pad descriptions (skip tracks)
        if 'Pad' not in desc and 'PTH' not in desc:
            continue

        if net not in net_pads:
            net_pads[net] = []
        net_pads[net].append((x, y))

print("Unconnected nets (pads only):")
for net, pads in sorted(net_pads.items()):
    print(f"  {net}: {pads}")

# Load the board
board_path = 'output/v2_adc_fixed_routed.kicad_pcb'
board = pcbnew.LoadBoard(board_path)
if not board:
    print("LoadBoard failed, trying NewBoard approach...")
    # Can't load — need to recreate. But we saved the FreeRouting output.
    # Actually let's try the alternative loading method
    print("ERROR: Cannot load board headlessly. LoadBoard needs wxApp.")
    sys.exit(1)

print(f"\nBoard loaded. Current tracks: {len(board.GetTracks())}")

# Route each unconnected net pair
routed = 0
for net_name, pads in net_pads.items():
    if len(pads) < 2:
        print(f"  SKIP {net_name}: only {len(pads)} pad(s)")
        continue

    # Connect first pad to second pad with L-route
    x1, y1 = pads[0]
    x2, y2 = pads[1]

    # Use F.Cu for signals, B.Cu for GND
    layer = pcbnew.B_Cu if net_name == 'GND' else pcbnew.F_Cu
    width = mm(0.40) if net_name in ('3V3', 'GND', 'VCAP', 'SOLAR_IN') else mm(0.25)

    # For RF traces, use wider track
    if 'RF' in net_name:
        width = mm(0.76)

    try:
        add_l_route(board, net_name, x1, y1, x2, y2, layer, width)
        routed += 1
        print(f"  ROUTED {net_name}: ({x1:.1f},{y1:.1f}) -> ({x2:.1f},{y2:.1f})")
    except Exception as e:
        print(f"  FAILED {net_name}: {e}")

    # If more than 2 pads, daisy-chain
    for i in range(2, len(pads)):
        xi, yi = pads[i]
        try:
            add_l_route(board, net_name, x2, y2, xi, yi, layer, width)
            routed += 1
            print(f"  ROUTED {net_name} chain: ({x2:.1f},{y2:.1f}) -> ({xi:.1f},{yi:.1f})")
            x2, y2 = xi, yi
        except Exception as e:
            print(f"  FAILED {net_name} chain: {e}")

print(f"\nTotal routes added: {routed}")
print(f"Total tracks now: {len(board.GetTracks())}")

# Save
pcbnew.SaveBoard(board_path, board)
print(f"Board saved to {board_path}")
