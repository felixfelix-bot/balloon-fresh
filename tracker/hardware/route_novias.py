#!/usr/bin/env python3.14
"""Route all nets on clean placement. No vias. Signals on F.Cu, power on B.Cu."""
import pcbnew

BOARD_IN = "hub_board_v1_placed.kicad_pcb"
BOARD_OUT = "hub_board_v1_routed_clean.kicad_pcb"

F_CU = 0
B_CU = 2

def add_track(board, x1, y1, x2, y2, layer, width, net_code):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(pcbnew.VECTOR2I(int(x1), int(y1)))
    t.SetEnd(pcbnew.VECTOR2I(int(x2), int(y2)))
    t.SetLayer(layer)
    t.SetWidth(width)
    t.SetNetCode(net_code)
    board.Add(t)

b = pcbnew.LoadBoard(BOARD_IN)
print(f"Loaded {BOARD_IN}")

# Build net info
from collections import defaultdict
net_pads = defaultdict(list)
for fp in b.GetFootprints():
    ref = fp.GetReference()
    for p in fp.Pads():
        nn = p.GetNetname()
        if nn:
            pos = p.GetPosition()
            net_pads[nn].append((ref, p.GetPadName(), pos.x, pos.y))

# Get net codes
net_codes = {}
for i in range(b.GetNetCount()):
    n = b.GetNetInfo().GetNetItem(i)
    if n:
        net_codes[n.GetNetname()] = n.GetNetCode()

W_SIG = int(0.2 * 1e6)
W_PWR = int(0.4 * 1e6)

# Route each net: connect consecutive pads with L-route
# Power nets on B.Cu, signals on F.Cu
track_count = 0
for netname in sorted(net_pads.keys()):
    pads = net_pads[netname]
    nc = net_codes.get(netname, 0)
    width = W_PWR if netname in ("GND", "3V3", "VCAP", "SOLAR_IN") else W_SIG
    layer = B_CU if netname in ("GND", "3V3") else F_CU
    
    if len(pads) < 2:
        continue
    
    # Star topology: connect pad[0] to each other pad
    ref0, p0, x0, y0 = pads[0]
    for i in range(1, len(pads)):
        ref1, p1, x1, y1 = pads[i]
        # L-route: horizontal then vertical
        if x0 != x1:
            add_track(b, x0, y0, x1, y0, layer, width, nc)
            track_count += 1
        if y0 != y1:
            add_track(b, x1, y0, x1, y1, layer, width, nc)
            track_count += 1

pcbnew.SaveBoard(BOARD_OUT, b)
print(f"Routed {track_count} tracks (no vias)")
print(f"Saved to {BOARD_OUT}")

# Verify
b2 = pcbnew.LoadBoard(BOARD_OUT)
tracks = list(b2.GetTracks())
vias = sum(1 for t in tracks if t.GetClass() == 'PCB_VIA')
trks = sum(1 for t in tracks if t.GetClass() == 'PCB_TRACK')
print(f"\nTracks: {trks}, Vias: {vias}")
