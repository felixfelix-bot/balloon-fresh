#!/usr/bin/env python3
"""Route C3 flight PCB using Manhattan routing on F.Cu/B.Cu.
Power nets (3V3, GND) go through In1/In2 planes (just need thermal vias).
Signal nets get Manhattan routed."""
import sys; sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew, math

BOARD_PATH = '/home/c03rad0r/repos/balloon-fresh/tracker/hardware/output/v_c3_flight_final.kicad_pcb'
b = pcbnew.LoadBoard(BOARD_PATH)

F_CU = pcbnew.F_Cu
B_CU = pcbnew.B_Cu
IN1 = pcbnew.In1_Cu
IN2 = pcbnew.In2_Cu
EDGE = pcbnew.Edge_Cuts

# --- Board outline ---
# Check if outline exists
outline_exists = False
for d in b.GetDrawings():
    if d.GetLayer() == EDGE:
        outline_exists = True
        break

if not outline_exists:
    print("Adding board outline (0,0) to (45,35)")
    outline = pcbnew.PCB_SHAPE(b)
    outline.SetShape(pcbnew.SHAPE_T_RECT)
    outline.SetLayer(EDGE)
    outline.SetStart(pcbnew.VECTOR2I(0, 0))
    outline.SetEnd(pcbnew.VECTOR2I(int(45e6), int(35e6)))
    outline.SetWidth(int(0.15e6))
    b.Add(outline)

# --- Collect pads by net ---
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
            'pad': pad,
            'x': pos.x,
            'y': pos.y,
        })

print(f"Nets: {len(nets)}")

# --- Helper: add track segment ---
def add_track(board, start, end, layer, width_nm=250000):
    t = pcbnew.PCB_TRACK(board)
    t.SetLayer(layer)
    t.SetWidth(width_nm)
    t.SetStart(pcbnew.VECTOR2I(int(start[0]), int(start[1])))
    t.SetEnd(pcbnew.VECTOR2I(int(end[0]), int(end[1])))
    board.Add(t)
    return t

def add_via(board, pos, net_code, size=600000, drill=300000):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pcbnew.VECTOR2I(int(pos[0]), int(pos[1])))
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetWidth(size)
    v.SetDrill(drill)
    v.SetNetCode(net_code)
    board.Add(v)
    return v

# --- Route signal nets with Manhattan routing ---
POWER_NETS = {'+3V3', 'GND', 'VCAP', 'SOLAR_IN', 'EN'}
track_count = 0
via_count = 0
unrouted = []

for netname, pads in sorted(nets.items()):
    if netname in POWER_NETS:
        # Power: add a single via near each pad to connect to plane
        for p in pads:
            # Get net code
            netinfo = b.FindNet(netname)
            if netinfo:
                add_via(b, (p['x'], p['y']), netinfo.GetNetCode())
                via_count += 1
        print(f"  [POWER] {netname}: {len(pads)} thermal vias")
        continue

    # Signal: Manhattan route between pads
    # Sort by position for chain routing
    if len(pads) < 2:
        continue

    # Simple: connect pads in order (pad[0]→pad[1]→pad[2]...)
    for i in range(len(pads) - 1):
        start = (pads[i]['x'], pads[i]['y'])
        end = (pads[i+1]['x'], pads[i+1]['y'])

        # Manhattan L-route on F.Cu
        mid = (end[0], start[1])

        # Check if same x or y (straight line)
        if abs(start[0] - end[0]) < 10000 or abs(start[1] - end[1]) < 10000:
            add_track(b, start, end, F_CU, 250000)
            track_count += 1
        else:
            # L-shaped route
            add_track(b, start, mid, F_CU, 250000)
            track_count += 1
            add_track(b, mid, end, F_CU, 250000)
            track_count += 1

    print(f"  [SIGNAL] {netname}: {len(pads)} pads, {len(pads)-1} segments")

# --- Fill zones ---
print("Filling zones...")
filler = pcbnew.ZONE_FILLER(b)
zones = b.GetZones()
if zones:
    filler.Fill(zones)
    print(f"Filled {len(zones)} zones")

# --- Set thickness ---
b.GetDesignSettings().SetBoardThickness(600000)  # 0.6mm

# --- Save ---
b.Save(BOARD_PATH)
print(f"\nSaved: {track_count} tracks, {via_count} vias")

# --- Verify ---
b2 = pcbnew.LoadBoard(BOARD_PATH)
fps = list(b2.GetFootprints())
tracks = list(b2.GetTracks())
print(f"Verified: {len(fps)} footprints, {len(tracks)} tracks")
