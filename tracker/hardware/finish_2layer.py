#!/usr/bin/env python3.14
"""One-shot: finish 2-layer board. Add outline, route power nets, fill zone, export gerbers."""
import sys, math
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew

BOARD_IN = '/home/c03rad0r/repos/balloon-fresh/tracker/hardware/output/v2_adc_fixed2.kicad_pcb'
BOARD_OUT = '/home/c03rad0r/repos/balloon-fresh/tracker/hardware/output/v2_2LAYER_FINAL.kicad_pcb'

b = pcbnew.LoadBoard(BOARD_IN)
fps = b.GetFootprints()
print(f"Loaded: {len(fps)} footprints, {len(b.GetTracks())} tracks")
assert len(fps) > 10, "BOARD EMPTY"

# 1. Add Edge.Cuts outline
edge = pcbnew.PCB_SHAPE(b)
edge.SetShape(pcbnew.SHAPE_T_RECT)
edge.SetLayer(pcbnew.Edge_Cuts)
edge.SetStart(pcbnew.VECTOR2I(0, 0))
edge.SetEnd(pcbnew.VECTOR2I(50000000, 40000000))
edge.SetWidth(150000)
b.Add(edge)

# 2. Fix thickness
ds = b.GetDesignSettings()
ds.SetBoardThickness(600000)  # 0.6mm

# 3. Route unconnected power nets using nearest-neighbor
# Get all pads grouped by net
from collections import defaultdict
net_pads = defaultdict(list)
for fp in fps:
    for pad in fp.Pads():
        net = pad.GetNetname()
        if net in ('3V3', 'GND', 'VCAP', 'SOLAR_IN'):
            pos = pad.GetPosition()
            net_pads[net].append({
                'ref': f"{fp.GetReference()}-{pad.GetNumber()}",
                'x': pos.x,
                'y': pos.y,
                'pad': pad
            })

def dist(a, b):
    return math.sqrt((a['x']-b['x'])**2 + (a['y']-b['y'])**2)

def route_net_chain(board, pads, net_name, width_nm=400000):
    """Connect pads via nearest-neighbor chain on F.Cu."""
    if len(pads) < 2:
        return 0
    visited = [pads[0]]
    unvisited = pads[1:]
    count = 0
    while unvisited:
        last = visited[-1]
        # Find nearest unvisited
        nearest = min(unvisited, key=lambda p: dist(last, p))
        # Create track
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(pcbnew.VECTOR2I(last['x'], last['y']))
        track.SetEnd(pcbnew.VECTOR2I(nearest['x'], nearest['y']))
        track.SetLayer(pcbnew.F_Cu)
        track.SetWidth(width_nm)
        net = last['pad'].GetNet()
        if net:
            track.SetNet(net)
        board.Add(track)
        count += 1
        visited.append(nearest)
        unvisited.remove(nearest)
    return count

POWER_NETS = {'3V3': 400000, 'GND': 400000, 'VCAP': 400000, 'SOLAR_IN': 400000}
total_routed = 0
for net_name, width in POWER_NETS.items():
    pads = net_pads.get(net_name, [])
    if len(pads) >= 2:
        n = route_net_chain(b, pads, net_name, width)
        print(f"  {net_name}: {len(pads)} pads, {n} tracks added")
        total_routed += n

# 4. Fill zones
zones = b.Zones()
if len(zones) > 0:
    filler = pcbnew.ZONE_FILLER(b)
    filler.Fill(zones)
    print(f"Filled {len(zones)} zones")

b.BuildConnectivity()
pcbnew.SaveBoard(BOARD_OUT, b)
print(f"\nSaved: {len(b.GetFootprints())} footprints, {len(b.GetTracks())} tracks")
print(f"Power tracks added: {total_routed}")
