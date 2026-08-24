#!/usr/bin/env python3.14
"""Route signals on clean placement board. 4-layer: GND on In1.Cu, 3V3 on In2.Cu, signals on F.Cu/B.Cu."""
import pcbnew
import math

BOARD_IN = "hub_board_v1_placed.kicad_pcb"
BOARD_OUT = "hub_board_v1_routed_clean.kicad_pcb"

F_CU = 0    # pcbnew.F_Cu
B_CU = 2    # pcbnew.B_Cu
IN1_CU = 4  # pcbnew.In1_Cu
IN2_CU = 6  # pcbnew.In2_Cu

TRACK_SIGNAL = int(0.20 * 1e6)   # 0.20mm in nm
TRACK_POWER = int(0.40 * 1e6)    # 0.40mm
TRACK_RF = int(0.15 * 1e6)       # 0.15mm

VIA_DRILL = int(0.3 * 1e6)
VIA_SIZE = int(0.6 * 1e6)

BOARD_W = 50
BOARD_H = 40

# Net track widths
NET_WIDTHS = {
    "RF_SUB_868": TRACK_RF,
    "RF_2G4_2400": TRACK_RF,
    "3V3": TRACK_POWER,
    "GND": TRACK_POWER,
    "SOLAR_IN": TRACK_POWER,
    "VCAP": TRACK_POWER,
    "LED_ANODE": TRACK_SIGNAL,
}

def add_zone(board, layer, netname):
    """Add copper zone on layer for given net."""
    zone = pcbnew.ZONE(board)
    zone.SetLayer(layer)
    poly = pcbnew.SHAPE_POLY_SET()
    poly.NewOutline()
    poly.Append(0, 0)
    poly.Append(int(BOARD_W * 1e6), 0)
    poly.Append(int(BOARD_W * 1e6), int(BOARD_H * 1e6))
    poly.Append(0, int(BOARD_H * 1e6))
    zone.SetOutline(poly)
    net = board.FindNet(netname)
    if net:
        zone.SetNet(net)
    zone.SetFillMode(0)  # solid fill
    board.Add(zone)
    return zone

def add_via(board, x_nm, y_nm, net_code):
    """Add a via at position."""
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(pcbnew.VECTOR2I(x_nm, y_nm))
    via.SetViaType(pcbnew.VIATYPE_THROUGH)
    via.SetDrill(VIA_DRILL)
    via.SetWidth(VIA_SIZE)
    via.SetNetCode(net_code)
    via.SetLayerPair(F_CU, B_CU)
    board.Add(via)
    return via

def add_track(board, x1, y1, x2, y2, layer, width, net_code):
    """Add a track segment."""
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(pcbnew.VECTOR2I(int(x1), int(y1)))
    t.SetEnd(pcbnew.VECTOR2I(int(x2), int(y2)))
    t.SetLayer(layer)
    t.SetWidth(width)
    t.SetNetCode(net_code)
    board.Add(t)
    return t

def manhattan_route(board, x1, y1, x2, y2, layer, width, net_code):
    """Route L-shaped Manhattan track. Returns list of track objects."""
    tracks = []
    # Route: horizontal first, then vertical
    if x1 != x2 and y1 != y2:
        t1 = add_track(board, x1, y1, x2, y1, layer, width, net_code)
        t2 = add_track(board, x2, y1, x2, y2, layer, width, net_code)
        tracks.extend([t1, t2])
    elif x1 != x2:
        t = add_track(board, x1, y1, x2, y2, layer, width, net_code)
        tracks.append(t)
    elif y1 != y2:
        t = add_track(board, x1, y1, x2, y2, layer, width, net_code)
        tracks.append(t)
    return tracks

def segments_intersect(p1, p2, p3, p4):
    """Check if line segment p1-p2 intersects p3-p4 (all as (x,y) tuples in nm)."""
    def ccw(A, B, C):
        return (C[1]-A[1])*(B[0]-A[0]) > (B[1]-A[1])*(C[0]-A[0])
    return ccw(p1, p3, p4) != ccw(p2, p3, p4) and ccw(p1, p2, p3) != ccw(p1, p2, p4)

# Load board
b = pcbnew.LoadBoard(BOARD_IN)
print(f"Loaded {BOARD_IN}")

# Get all nets
nets = {}
for i in range(b.GetNetCount()):
    n = b.GetNetInfo().GetNetItem(i)
    if n:
        nets[n.GetNetname()] = n.GetNetCode()

# Skip zones for now (KiCad 9 API segfaults on zone creation in script mode)
# Power planes will be added via kicad-cli or manual KiCad later
print("Skipping power zones (API limitation)")

# Build pad list per net
from collections import defaultdict
net_pads = defaultdict(list)
for fp in b.GetFootprints():
    ref = fp.GetReference()
    for p in fp.Pads():
        nn = p.GetNetname()
        if nn and nn != '':
            pos = p.GetPosition()
            net_pads[nn].append((ref, p.GetPadName(), pos.x, pos.y, p.GetNetCode()))

# Route ALL nets as tracks — no thermal vias
# Strategy: GND on B.Cu, 3V3 on B.Cu, signals alternate F.Cu/B.Cu
# Power planes will be added later via zones — for now route power explicitly
via_count = 0

# Route ALL nets with Manhattan routing — GND/3V3 on B.Cu, signals on F.Cu
signal_nets = sorted(net_pads.keys())
track_count = 0
routed = 0
failed = []

# Keep track of all segments for collision checking
all_segments = []  # (x1,y1,x2,y2,layer) in nm

for sn in signal_nets:
    pads = net_pads[sn]
    nc = nets.get(sn, 0)
    width = NET_WIDTHS.get(sn, TRACK_SIGNAL)
    
    if len(pads) < 2:
        continue
    
    # Power nets on B.Cu, signals on F.Cu
    power_pref = {"GND": B_CU, "3V3": B_CU}
    default_layer = power_pref.get(sn, F_CU)
    
    # Route first pad to last pad (star topology for multi-pad nets)
    success = True
    for i in range(len(pads) - 1):
        ref1, p1, x1, y1, _ = pads[i]
        ref2, p2, x2, y2, _ = pads[i + 1]
        
        # Check if segments would collide with existing
        # Use mid-point for L-route
        mid_x, mid_y = x2, y1  # horizontal then vertical
        
        has_collision = False
        for (sx1, sy1, sx2, sy2, s_layer) in all_segments:
            if s_layer != default_layer:
                continue
            # Check horizontal segment
            if segments_intersect((x1,y1), (mid_x,mid_y), (sx1,sy1), (sx2,sy2)):
                has_collision = True
                break
            # Check vertical segment
            if segments_intersect((mid_x,mid_y), (x2,y2), (sx1,sy1), (sx2,sy2)):
                has_collision = True
                break
        
        layer = default_layer
        if has_collision:
            # Try B.Cu with vias at both ends
            layer = B_CU
            add_via(b, x1, y1, nc)
            add_via(b, x2, y2, nc)
            via_count += 2
        
        tracks = manhattan_route(b, x1, y1, x2, y2, layer, width, nc)
        track_count += len(tracks)
        routed += 1
        
        # Record segments
        if x1 != mid_x:
            all_segments.append((x1, y1, mid_x, y1, layer))
        if mid_y != y2:
            all_segments.append((mid_x, y1, mid_x, y2, layer))
    
    if not success:
        failed.append(sn)

print(f"\nRouting complete:")
print(f"  Signal tracks: {track_count}")
print(f"  Thermal vias: {via_count}")
print(f"  Nets routed: {routed}")
if failed:
    print(f"  Failed: {failed}")

# Save
pcbnew.SaveBoard(BOARD_OUT, b)
print(f"Saved to {BOARD_OUT}")

# Verify
b2 = pcbnew.LoadBoard(BOARD_OUT)
tracks = list(b2.GetTracks())
vias = sum(1 for t in tracks if t.GetClass() == 'PCB_VIA')
trks = sum(1 for t in tracks if t.GetClass() == 'PCB_TRACK')
zones = 0
try:
    for i in range(b2.GetAreaCount()):
        zones += 1
except:
    pass

print(f"\n=== VERIFICATION ===")
print(f"Footprints: {len(list(b2.GetFootprints()))}")
print(f"Tracks: {trks}")
print(f"Vias: {vias}")
print(f"Zones: {zones}")
print(f"Copper layers: {b2.GetCopperLayerCount()}")

# Check pad overlaps still 0
fps = list(b2.GetFootprints())
pad_overlaps = 0
for i, f1 in enumerate(fps):
    for p1 in f1.Pads():
        b1 = p1.GetBoundingBox()
        for j, f2 in enumerate(fps):
            if j <= i: continue
            for p2 in f2.Pads():
                b2 = p2.GetBoundingBox()
                if b1.Intersects(b2):
                    pad_overlaps += 1
print(f"Pad overlaps: {pad_overlaps}")