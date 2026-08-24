#!/usr/bin/env python3.14
"""P2V: Place thermal vias for GND/3V3 SMD pads. Edge-to-edge clearance rules.
Skips THT pads. Tries 8 directions. Skips if no clear position."""
import pcbnew
import math

BOARD_IN = "output/v5_zones.kicad_pcb"
BOARD_OUT = "output/v5_vias.kicad_pcb"

F_CU = 0
IN1_CU = 4
IN2_CU = 6

VIA_DRILL = int(0.3 * 1e6)
VIA_SIZE = int(0.6 * 1e6)
# Edge-to-edge clearance minimums (mm)
MIN_PAD_EDGE = 0.25   # via edge to pad edge
MIN_HOLE_EDGE = 0.25  # via edge to THT hole edge
MIN_VIA_EDGE = 0.25   # via edge to via edge

def via_radius():
    return VIA_SIZE / 2

def edge_dist(vx, vy, px, py, pradius):
    """Edge-to-edge distance between via center and a circle (pad/hole/via)."""
    center_dist = math.sqrt((vx - px)**2 + (vy - py)**2)
    return center_dist - pradius - via_radius()

# Load board
b = pcbnew.LoadBoard(BOARD_IN)
print(f"Loaded {BOARD_IN}")

# Build pad info: (x_nm, y_nm, radius_nm, is_tht, drill_radius_nm, netname, ref)
pad_info = []
for fp in b.GetFootprints():
    ref = fp.GetReference()
    for p in fp.Pads():
        pos = p.GetPosition()
        sz = p.GetSize()
        radius = max(sz.x, sz.y) / 2
        drill = p.GetDrillSize()
        is_tht = drill.x > 0
        drill_r = max(drill.x, drill.y) / 2 if is_tht else 0
        pad_info.append((pos.x, pos.y, radius, is_tht, drill_r, p.GetNetname(), ref, p.GetPadName()))

print(f"Pads found: {len(pad_info)}")

# For each SMD pad on GND or 3V3, place a thermal via
via_positions = []  # track for via-via collision
vias_placed = 0
vias_skipped = 0
power_nets = {"GND": IN1_CU, "3V3": IN2_CU}

for px, py, pradius, is_tht, drill_r, netname, ref, padname in pad_info:
    if netname not in power_nets:
        continue
    if is_tht:
        continue  # THT pads connect through plating
    
    target_layer = power_nets[netname]
    
    # Try 8 directions at 1.0mm offset from pad center
    best = None
    for angle_deg in range(0, 360, 45):
        angle = math.radians(angle_deg)
        vx = px + int(1.0 * 1e6 * math.cos(angle))
        vy = py + int(1.0 * 1e6 * math.sin(angle))
        
        # Check clearance to all pads
        ok = True
        for opx, opy, oradius, otht, odrill, onet, oref, opad in pad_info:
            # Edge distance to pad
            de = edge_dist(vx, vy, opx, opy, oradius)
            if de < MIN_PAD_EDGE * 1e6:
                ok = False
                break
            # Edge distance to THT hole (if applicable)
            if otht and odrill > 0:
                he = edge_dist(vx, vy, opx, opy, odrill)
                if he < MIN_HOLE_EDGE * 1e6:
                    ok = False
                    break
        
        if not ok:
            continue
        
        # Check clearance to existing vias
        for evx, evy in via_positions:
            ve = edge_dist(vx, vy, evx, evy, via_radius())
            if ve < MIN_VIA_EDGE * 1e6:
                ok = False
                break
        
        if ok:
            best = (vx, vy, target_layer)
            break
    
    if best:
        vx, vy, layer = best
        via = pcbnew.PCB_VIA(b)
        via.SetPosition(pcbnew.VECTOR2I(vx, vy))
        via.SetViaType(pcbnew.VIATYPE_THROUGH)
        via.SetDrill(VIA_DRILL)
        via.SetWidth(VIA_SIZE)
        net = b.FindNet(netname)
        if net:
            via.SetNetCode(net.GetNetCode())
        via.SetLayerPair(F_CU, layer)
        b.Add(via)
        via_positions.append((vx, vy))
        vias_placed += 1
    else:
        vias_skipped += 1
        print(f"  SKIP: {ref}.{padname} ({netname}) — no clear via position")

print(f"\nVias placed: {vias_placed}")
print(f"Vias skipped: {vias_skipped}")

pcbnew.SaveBoard(BOARD_OUT, b)
print(f"Saved {BOARD_OUT}")

# Verify
b2 = pcbnew.LoadBoard(BOARD_OUT)
tracks = list(b2.GetTracks())
vias = sum(1 for t in tracks if t.GetClass() == 'PCB_VIA')
print(f"Total vias: {vias}")
print(f"Zones: {len(list(b2.Zones()))}")
print(f"Footprints: {len(list(b2.GetFootprints()))}")
