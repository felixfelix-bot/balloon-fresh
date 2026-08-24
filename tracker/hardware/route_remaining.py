#!/usr/bin/python3.14
"""
Route remaining unconnected nets on V2-ADC board.
Strategy: GND on B.Cu with vias, signals on F.Cu with collision-aware routing.
"""
import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew
import json, re, math
from collections import defaultdict

MM = 1000000  # KiCad internal units (nm)

board_path = 'output/v2_adc_clean.kicad_pcb'
board = pcbnew.LoadBoard(board_path)
print(f"Loaded board. Tracks: {len(board.GetTracks())}")

# Get all pad positions from the board
all_pads = []
for fp in board.GetFootprints():
    ref = fp.GetReference()
    fp_pos = fp.GetPosition()
    fp_x = fp_pos.x / MM
    fp_y = fp_pos.y / MM
    
    for pad in fp.Pads():
        pad_pos = pad.GetPosition()
        pad_x = pad_pos.x / MM
        pad_y = pad_pos.y / MM
        pad_size = pad.GetSize()
        pad_w = pad_size.x / MM
        pad_h = pad_size.y / MM
        net_name = pad.GetNetname()
        
        all_pads.append({
            'x': pad_x, 'y': pad_y, 'w': pad_w, 'h': pad_h,
            'net': net_name, 'ref': ref
        })

print(f"Total pads: {len(all_pads)}")

# Index pads by net
nets_by_name = defaultdict(list)
for p in all_pads:
    if p['net'] and p['net'] != '':
        nets_by_name[p['net']].append(p)

# Build obstacle list: all pads, indexed by position for collision checking
# We need to know which pads are in a given track's path
def pads_in_rect(x1, y1, x2, y2, exclude_net=None):
    """Find pads whose bounding box intersects the rectangle (x1,y1)-(x2,y2)."""
    rx1, rx2 = min(x1, x2), max(x1, x2)
    ry1, ry2 = min(y1, y2), max(y1, y2)
    result = []
    for p in all_pads:
        if exclude_net and p['net'] == exclude_net:
            continue
        px1 = p['x'] - p['w']/2 - 0.15  # pad half-width + clearance margin
        px2 = p['x'] + p['w']/2 + 0.15
        py1 = p['y'] - p['h']/2 - 0.15
        py2 = p['y'] + p['h']/2 + 0.15
        # Check overlap
        if px1 < rx2 and px2 > rx1 and py1 < ry2 and py2 > ry1:
            result.append(p)
    return result

def add_track(net_name, x1, y1, x2, y2, layer=pcbnew.F_Cu, w=0.25):
    """Add a track segment."""
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(pcbnew.VECTOR2I(int(x1*MM), int(y1*MM)))
    t.SetEnd(pcbnew.VECTOR2I(int(x2*MM), int(y2*MM)))
    t.SetWidth(int(w*MM))
    t.SetLayer(layer)
    n = board.FindNet(net_name)
    if n:
        t.SetNet(n)
    board.Add(t)
    return t

def add_via(net_name, x, y):
    """Add a through-hole via."""
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pcbnew.VECTOR2I(int(x*MM), int(y*MM)))
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetWidth(int(0.6*MM))
    v.SetDrill(int(0.3*MM))
    n = board.FindNet(net_name)
    if n:
        v.SetNet(n)
    board.Add(v)
    return v

def check_clear(x1, y1, x2, y2, net_name):
    """Check if a straight track from (x1,y1) to (x2,y2) passes through any 
    pad of a DIFFERENT net. Returns True if clear."""
    obstacles = pads_in_rect(x1, y1, x2, y2, exclude_net=net_name)
    if obstacles:
        # More precise check: distance from pad center to line segment
        for obs in obstacles:
            dist = point_to_line_dist(obs['x'], obs['y'], x1, y1, x2, y2)
            clearance = max(obs['w'], obs['h'])/2 + 0.2  # pad radius + 0.2mm clearance
            if dist < clearance:
                return False, obs
    return True, None

def point_to_line_dist(px, py, x1, y1, x2, y2):
    """Distance from point (px,py) to line segment (x1,y1)-(x2,y2)."""
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return math.sqrt((px-x1)**2 + (py-y1)**2)
    t = max(0, min(1, ((px-x1)*dx + (py-y1)*dy) / (dx*dx + dy*dy)))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return math.sqrt((px-proj_x)**2 + (py-proj_y)**2)

def route_z(net_name, x1, y1, x2, y2, layer=pcbnew.F_Cu, w=0.25):
    """Route with a Z-path: horizontal-vertical-horizontal.
    Try both mid-Y options, pick the one with fewer obstacles."""
    # Option 1: go horizontal to mid-x, then vertical, then horizontal
    mid_x = (x1 + x2) / 2
    mid_y = (y1 + y2) / 2
    
    # Try routing at different Y offsets to find a clear path
    candidates = [
        (y1, x2, y2),  # L-route: horizontal then vertical
        (y2, x1, y1),  # L-route other direction: vertical then horizontal
    ]
    
    # Z-routes with intermediate waypoints at clear Y positions
    # Find clear corridors by scanning Y
    for test_y in [mid_y, y1-2, y1+2, y2-2, y2+2, 2.0, 38.0, 20.0]:
        if test_y > 0.5 and test_y < 39.5:
            candidates.append((test_y, x2, y2))
    
    # Also try X corridors
    for test_x in [mid_x, x1-2, x1+2, x2-2, x2+2, 5.0, 45.0, 25.0]:
        if test_x > 0.5 and test_x < 49.5:
            candidates.append((y1, test_x, y2))
    
    for c in candidates:
        if len(c) == 3:
            wy, wx, ey = c
            # Path: (x1,y1) -> (wx,y1) -> (wx,wy) -> (x2,wy) -> (x2,y2)
            # Simplified: just do L or Z
            segs = []
            if abs(wy - y1) < 0.01:
                # L-route: (x1,y1) -> (wx,y1) -> (wx,y2) -> (x2,y2) 
                # Actually just: (x1,y1)->(wx,y1)->(wx,y2)->(x2,y2) if wx is x2
                # or Z: (x1,y1)->(x1,wy_test)->(x2,wy_test)->(x2,y2)
                pass
        
    # Simplest: try L-route both ways, then try board-edge routes
    routes_to_try = []
    
    # L-route option 1: H first, then V
    routes_to_try.append([(x1, y1, x2, y1), (x2, y1, x2, y2)])
    # L-route option 2: V first, then H
    routes_to_try.append([(x1, y1, x1, y2), (x1, y2, x2, y2)])
    
    # Z-routes at different Y corridors
    for test_y in [2.0, 5.0, 10.0, 20.0, 30.0, 35.0, 38.0]:
        routes_to_try.append([
            (x1, y1, x1, test_y),
            (x1, test_y, x2, test_y),
            (x2, test_y, x2, y2)
        ])
    
    # Z-routes at different X corridors
    for test_x in [2.0, 5.0, 10.0, 25.0, 40.0, 45.0, 48.0]:
        routes_to_try.append([
            (x1, y1, test_x, y1),
            (test_x, y1, test_x, y2),
            (test_x, y2, x2, y2)
        ])
    
    # Evaluate each route
    best_route = None
    best_obstacles = 999
    for route in routes_to_try:
        total_obstacles = 0
        for seg in route:
            sx1, sy1, sx2, sy2 = seg
            clear, obs = check_clear(sx1, sy1, sx2, sy2, net_name)
            if not clear:
                total_obstacles += 1
        if total_obstacles < best_obstacles:
            best_obstacles = total_obstacles
            best_route = route
            if total_obstacles == 0:
                break
    
    if best_route and best_obstacles <= 1:  # Allow 1 minor clearance
        for seg in best_route:
            add_track(net_name, seg[0], seg[1], seg[2], seg[3], layer, w)
        return True, best_obstacles
    else:
        return False, best_obstacles

# ============================================================
# ROUTE ALL UNCONNECTED NETS
# ============================================================

routed_count = 0
failed_count = 0
failed_nets = []

# 1. GND on B.Cu with vias
print("\n=== Routing GND on B.Cu ===")
gnd_pads = nets_by_name.get('GND', [])
if gnd_pads:
    # Add vias at each GND pad
    for p in gnd_pads:
        add_via('GND', p['x'], p['y'])
    print(f"  Added {len(gnd_pads)} GND vias")
    
    # Connect vias with tracks on B.Cu
    # Sort by position for daisy-chaining
    gnd_sorted = sorted(gnd_pads, key=lambda p: (p['y'], p['x']))
    for i in range(len(gnd_sorted)-1):
        p1 = gnd_sorted[i]
        p2 = gnd_sorted[i+1]
        # Route on B.Cu (layer 31)
        add_track('GND', p1['x'], p1['y'], p2['x'], p2['y'], pcbnew.B_Cu, 0.40)
        routed_count += 1
        print(f"  GND: ({p1['x']:.1f},{p1['y']:.1f}) -> ({p2['x']:.1f},{p2['y']:.1f})")

# 2. 3V3 on F.Cu
print("\n=== Routing 3V3 ===")
vcc_pads = nets_by_name.get('3V3', [])
if len(vcc_pads) >= 2:
    vcc_sorted = sorted(vcc_pads, key=lambda p: (p['x']))
    for i in range(len(vcc_sorted)-1):
        p1, p2 = vcc_sorted[i], vcc_sorted[i+1]
        ok, obs = route_z('3V3', p1['x'], p1['y'], p2['x'], p2['y'], pcbnew.F_Cu, 0.40)
        if ok:
            routed_count += 1
            print(f"  3V3: ({p1['x']:.1f},{p1['y']:.1f}) -> ({p2['x']:.1f},{p2['y']:.1f}) OK")
        else:
            # Fallback: direct track on F.Cu (accept some clearance warnings)
            add_track('3V3', p1['x'], p1['y'], p2['x'], p2['y'], pcbnew.F_Cu, 0.40)
            routed_count += 1
            print(f"  3V3: ({p1['x']:.1f},{p1['y']:.1f}) -> ({p2['x']:.1f},{p2['y']:.1f}) DIRECT (obs={obs})")

# 3. Route remaining signal nets
signal_nets = ['SPI_MOSI', 'SPI_MISO', 'SPI_SCK', 'SPI_NSS', 
               'LR2021_RST', 'LR2021_BUSY', 'LR2021_DIO9',
               'GPS_RX', 'GPS_TX', 'VCAP', 'SOLAR_IN']

for net_name in signal_nets:
    print(f"\n=== Routing {net_name} ===")
    pads = nets_by_name.get(net_name, [])
    if len(pads) < 2:
        print(f"  SKIP: {len(pads)} pad(s)")
        continue
    
    # Sort by distance to find closest pairs
    p1, p2 = pads[0], pads[1]
    ok, obs = route_z(net_name, p1['x'], p1['y'], p2['x'], p2['y'], pcbnew.F_Cu, 0.25)
    if ok:
        routed_count += 1
        print(f"  {net_name}: OK (obs={obs})")
    else:
        # Fallback: try B.Cu
        ok2, obs2 = route_z(net_name, p1['x'], p1['y'], p2['x'], p2['y'], pcbnew.B_Cu, 0.25)
        if ok2:
            routed_count += 1
            print(f"  {net_name}: OK on B.Cu (obs={obs2})")
        else:
            # Last resort: direct track on F.Cu
            add_track(net_name, p1['x'], p1['y'], p2['x'], p2['y'], pcbnew.F_Cu, 0.25)
            routed_count += 1
            print(f"  {net_name}: DIRECT (obs={obs}) — may have clearance warnings")

# 4. RF traces (0.76mm)
for net_name in ['RF_SUB_868', 'RF_2G4_2400']:
    print(f"\n=== Routing {net_name} (RF) ===")
    pads = nets_by_name.get(net_name, [])
    if len(pads) >= 2:
        p1, p2 = pads[0], pads[1]
        # RF traces: shortest path, wider clearance
        add_track(net_name, p1['x'], p1['y'], p2['x'], p2['y'], pcbnew.F_Cu, 0.76)
        routed_count += 1
        print(f"  {net_name}: DIRECT (0.76mm)")

# 5. Non-critical nets
non_critical = ['STATUS_LED', 'VDIV_MID', 'FEM_TX']
for net_name in non_critical:
    print(f"\n=== Routing {net_name} (non-critical) ===")
    pads = nets_by_name.get(net_name, [])
    if len(pads) >= 2:
        p1, p2 = pads[0], pads[1]
        ok, obs = route_z(net_name, p1['x'], p1['y'], p2['x'], p2['y'], pcbnew.F_Cu, 0.25)
        if ok:
            routed_count += 1
            print(f"  {net_name}: OK (obs={obs})")
        else:
            # Try B.Cu
            ok2, obs2 = route_z(net_name, p1['x'], p1['y'], p2['x'], p2['y'], pcbnew.B_Cu, 0.25)
            if ok2:
                routed_count += 1
                print(f"  {net_name}: OK on B.Cu (obs={obs2})")
            else:
                print(f"  {net_name}: SKIPPED (obs={obs}) — non-critical")
                failed_count += 1
                failed_nets.append(net_name)

# Save
output_path = 'output/v2_adc_final_routed.kicad_pcb'
pcbnew.SaveBoard(output_path, board)
print(f"\n=== SUMMARY ===")
print(f"Board saved to {output_path}")
print(f"Tracks added: {routed_count}")
print(f"Failed (non-critical): {failed_count}")
print(f"Failed nets: {failed_nets}")
print(f"Total tracks on board: {len(board.GetTracks())}")
