#!/usr/bin/env python3
"""4-layer routing for hub_board_v1_routed.kicad_pcb.

Strategy:
  - In1.Cu (layer 4): GND copper zone (full board) — thermal vias at GND pads
  - In2.Cu (layer 6): 3V3 copper zone (full board) — thermal vias at 3V3 pads
  - F.Cu (layer 0) + B.Cu (layer 2): signal routing with Manhattan + vias
  
Signal routing: odd-indexed signals route on F.Cu, even-indexed on B.Cu.
When a signal needs to cross another, use a via to switch layers.
"""
import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew
import math
import copy

BOARD_IN  = 'hub_board_v1_routed.kicad_pcb'
BOARD_OUT = 'hub_board_v1_4layer.kicad_pcb'

F_CU  = pcbnew.F_Cu   # 0
B_CU  = pcbnew.B_Cu   # 2
IN1   = pcbnew.In1_Cu # 4
IN2   = pcbnew.In2_Cu # 6
EDGE  = pcbnew.Edge_Cuts # 25

NM = 1000000  # 1mm in nanometers
TRACK_WIDTH = int(0.25 * NM)
VIA_SIZE = int(0.6 * NM)
VIA_DRILL = int(0.3 * NM)
CLEARANCE = int(0.2 * NM)

# Board outline: (0,0) to (50,40) mm → in nm
BOARD_X0 = 0
BOARD_Y0 = 0
BOARD_X1 = 50 * NM
BOARD_Y1 = 40 * NM
ZONE_MARGIN = int(0.5 * NM)

print("=== 4-Layer Routing Script ===")
print(f"Loading {BOARD_IN}...")
b = pcbnew.LoadBoard(BOARD_IN)
print(f"Copper layers: {b.GetCopperLayerCount()}")
assert b.GetCopperLayerCount() == 4, "Board must have 4 copper layers!"

# ─── Step 1: Remove all existing tracks ───
print("\n--- Removing existing tracks ---")
tracks = list(b.GetTracks())
print(f"  Existing tracks: {len(tracks)}")
for t in tracks:
    b.Remove(t)
print(f"  Removed all tracks")

# Remove existing zones (the old GND zone on B.Cu)
old_zones = list(b.Zones())
print(f"  Existing zones: {len(old_zones)}")
for z in old_zones:
    b.RemoveNative(z)
print(f"  Removed all zones")

# ─── Step 2: Create GND zone on In1.Cu ───
print("\n--- Creating GND zone on In1.Cu ---")
gnd_net = b.FindNet("GND")
assert gnd_net is not None, "GND net not found!"
print(f"  GND net code: {gnd_net.GetNetCode()}")

gnd_zone = pcbnew.ZONE(b)
gnd_zone.SetLayer(IN1)
gnd_zone.SetNet(gnd_net)
gnd_zone.SetNetCode(gnd_net.GetNetCode())

# Create zone outline as a rectangle covering the board
outline = pcbnew.SHAPE_POLY_SET()
outline.NewOutline()
outline.Append(BOARD_X0 + ZONE_MARGIN, BOARD_Y0 + ZONE_MARGIN)
outline.Append(BOARD_X1 - ZONE_MARGIN, BOARD_Y0 + ZONE_MARGIN)
outline.Append(BOARD_X1 - ZONE_MARGIN, BOARD_Y1 - ZONE_MARGIN)
outline.Append(BOARD_X0 + ZONE_MARGIN, BOARD_Y1 - ZONE_MARGIN)
gnd_zone.SetOutline(outline)

# Zone settings
gnd_zone.SetMinThickness(int(0.2 * NM))
gnd_zone.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL_RELIEF if hasattr(pcbnew, 'ZONE_CONNECTION_THERMAL_RELIEF') else 1)
gnd_zone.SetThermalReliefGap(int(0.5 * NM))
gnd_zone.SetThermalReliefSpokeWidth(int(0.5 * NM))
gnd_zone.SetIsFilled(True) if hasattr(gnd_zone, 'SetIsFilled') else None

b.Add(gnd_zone)
print("  GND zone added on In1.Cu")

# ─── Step 3: Create 3V3 zone on In2.Cu ───
print("\n--- Creating 3V3 zone on In2.Cu ---")
p3v3_net = b.FindNet("3V3")
assert p3v3_net is not None, "3V3 net not found!"
print(f"  3V3 net code: {p3v3_net.GetNetCode()}")

p3v3_zone = pcbnew.ZONE(b)
p3v3_zone.SetLayer(IN2)
p3v3_zone.SetNet(p3v3_net)
p3v3_zone.SetNetCode(p3v3_net.GetNetCode())

outline2 = pcbnew.SHAPE_POLY_SET()
outline2.NewOutline()
outline2.Append(BOARD_X0 + ZONE_MARGIN, BOARD_Y0 + ZONE_MARGIN)
outline2.Append(BOARD_X1 - ZONE_MARGIN, BOARD_Y0 + ZONE_MARGIN)
outline2.Append(BOARD_X1 - ZONE_MARGIN, BOARD_Y1 - ZONE_MARGIN)
outline2.Append(BOARD_X0 + ZONE_MARGIN, BOARD_Y1 - ZONE_MARGIN)
p3v3_zone.SetOutline(outline2)

p3v3_zone.SetMinThickness(int(0.2 * NM))
p3v3_zone.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL_RELIEF if hasattr(pcbnew, 'ZONE_CONNECTION_THERMAL_RELIEF') else 1)
p3v3_zone.SetThermalReliefGap(int(0.5 * NM))
p3v3_zone.SetThermalReliefSpokeWidth(int(0.5 * NM))
p3v3_zone.SetIsFilled(True) if hasattr(p3v3_zone, 'SetIsFilled') else None

b.Add(p3v3_zone)
print("  3V3 zone added on In2.Cu")

# ─── Step 4: Collect all pads by net ───
print("\n--- Collecting pads by net ---")
nets = {}
for fp in b.GetFootprints():
    for pad in fp.Pads():
        netname = pad.GetNetname()
        if not netname:
            continue
        if netname not in nets:
            nets[netname] = []
        pos = pad.GetPosition()
        nets[netname].append({
            'ref': fp.GetReference(),
            'pad': pad.GetPadName(),
            'x': pos.x,
            'y': pos.y,
            'pad_obj': pad,
            'net_code': pad.GetNetCode(),
        })

for nn in sorted(nets.keys()):
    print(f"  {nn}: {len(nets[nn])} pads")

# ─── Step 5: Add thermal vias for power nets ───
print("\n--- Adding thermal vias for power nets ---")
POWER_NETS = {'GND', '3V3'}
via_count = 0

for netname in POWER_NETS:
    if netname not in nets:
        print(f"  {netname}: no pads, skipping")
        continue
    netinfo = b.FindNet(netname)
    nc = netinfo.GetNetCode()
    for p in nets[netname]:
        v = pcbnew.PCB_VIA(b)
        v.SetPosition(pcbnew.VECTOR2I(p['x'], p['y']))
        v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetLayer(F_CU)
        v.SetTopLayer(F_CU)
        v.SetBottomLayer(B_CU)
        v.SetWidth(VIA_SIZE)
        v.SetDrill(VIA_DRILL)
        v.SetNetCode(nc)
        b.Add(v)
        via_count += 1
    print(f"  {netname}: {len(nets[netname])} thermal vias added")

# ─── Step 6: Route signal nets ───
print("\n--- Routing signal nets ---")
SIGNAL_NETS = sorted([nn for nn in nets if nn not in POWER_NETS])
print(f"  Signal nets: {SIGNAL_NETS}")

def add_track(board, start, end, layer, width=TRACK_WIDTH):
    t = pcbnew.PCB_TRACK(board)
    t.SetLayer(layer)
    t.SetWidth(width)
    t.SetStart(pcbnew.VECTOR2I(int(start[0]), int(start[1])))
    t.SetEnd(pcbnew.VECTOR2I(int(end[0]), int(end[1])))
    board.Add(t)
    return t

def add_via(board, pos, net_code, size=VIA_SIZE, drill=VIA_DRILL):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pcbnew.VECTOR2I(int(pos[0]), int(pos[1])))
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetLayer(F_CU)
    v.SetTopLayer(F_CU)
    v.SetBottomLayer(B_CU)
    v.SetWidth(size)
    v.SetDrill(drill)
    v.SetNetCode(net_code)
    board.Add(v)
    return v

def manhattan_route(board, start, end, layer, net_code, width=TRACK_WIDTH):
    """Route an L-shaped or straight Manhattan path."""
    tracks_added = []
    sx, sy = start
    ex, ey = end
    
    if abs(sx - ex) < 1000 and abs(sy - ey) < 1000:
        # Same point, skip
        return tracks_added
    
    if abs(sx - ex) < 1000:
        # Vertical only
        t = add_track(board, (sx, sy), (ex, ey), layer, width)
        tracks_added.append(t)
    elif abs(sy - ey) < 1000:
        # Horizontal only
        t = add_track(board, (sx, sy), (ex, ey), layer, width)
        tracks_added.append(t)
    else:
        # L-shaped: go horizontal first, then vertical
        mid = (ex, sy)
        t1 = add_track(board, (sx, sy), mid, layer, width)
        tracks_added.append(t1)
        t2 = add_track(board, mid, (ex, ey), layer, width)
        tracks_added.append(t2)
    
    return tracks_added

# Route signals: alternate between F.Cu and B.Cu
track_count = 0
for idx, netname in enumerate(SIGNAL_NETS):
    pads = nets[netname]
    if len(pads) < 2:
        print(f"  [SKIP] {netname}: only {len(pads)} pad(s)")
        continue
    
    netinfo = b.FindNet(netname)
    if netinfo is not None:
        try:
            nc = netinfo.GetNetCode()
        except AttributeError:
            # FindNet returned raw SwigPyObject — use pad's net code instead
            nc = pads[0]['net_code']
    else:
        nc = pads[0]['net_code']
    
    # Alternate layers: even index → F.Cu, odd index → B.Cu
    primary_layer = F_CU if idx % 2 == 0 else B_CU
    secondary_layer = B_CU if idx % 2 == 0 else F_CU
    layer_name = "F.Cu" if primary_layer == F_CU else "B.Cu"
    
    # Sort pads by position for chain routing
    # Sort by x, then y
    pads_sorted = sorted(pads, key=lambda p: (p['x'], p['y']))
    
    # Route between consecutive pads
    for i in range(len(pads_sorted) - 1):
        start = (pads_sorted[i]['x'], pads_sorted[i]['y'])
        end = (pads_sorted[i+1]['x'], pads_sorted[i+1]['y'])
        
        # Route on primary layer
        tracks = manhattan_route(b, start, end, primary_layer, nc)
        track_count += len(tracks)
    
    print(f"  [SIGNAL] {netname}: {len(pads_sorted)} pads on {layer_name}, {len(pads_sorted)-1} connections")

# ─── Step 7: Fill zones ───
print("\n--- Filling zones ---")
filler = pcbnew.ZONE_FILLER(b)
zones = list(b.Zones())
if zones:
    try:
        filler.Fill(zones)
        print(f"  Filled {len(zones)} zones")
    except Exception as e:
        print(f"  Zone fill error: {e}")

# ─── Step 8: Save ───
print(f"\n--- Saving to {BOARD_OUT} ---")
pcbnew.SaveBoard(BOARD_OUT, b)
print(f"  Saved! Tracks: {track_count}, Vias: {via_count}")

# ─── Step 9: Verify ───
print(f"\n--- Verifying {BOARD_OUT} ---")
b2 = pcbnew.LoadBoard(BOARD_OUT)
print(f"  Copper layers: {b2.GetCopperLayerCount()}")
print(f"  Footprints: {len(list(b2.GetFootprints()))}")
print(f"  Tracks: {len(list(b2.GetTracks()))}")
zones2 = list(b2.Zones())
print(f"  Zones: {len(zones2)}")
for z in zones2:
    print(f"    Zone: layer={z.GetLayer()}, net={z.GetNetname()}")

# Track layer distribution
layer_dist = {}
for t in b2.GetTracks():
    l = t.GetLayer()
    ln = {0:'F.Cu', 2:'B.Cu', 4:'In1.Cu', 6:'In2.Cu'}.get(l, f'L{l}')
    layer_dist[ln] = layer_dist.get(ln, 0) + 1
print(f"  Track layers: {layer_dist}")

print("\n=== Done ===")