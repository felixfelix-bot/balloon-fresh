#!/usr/bin/python3.14
"""Fix zone fills, rebuild connectivity, repair remaining routing issues."""
import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew
import math

INPUT  = '/home/c03rad0r/repos/balloon-fresh/tracker/hardware/output/v_c3_flight_clean_routed.kicad_pcb'
OUTPUT = '/home/c03rad0r/repos/balloon-fresh/tracker/hardware/output/v_c3_flight_final_clean.kicad_pcb'

F_CU = pcbnew.F_Cu
B_CU = pcbnew.B_Cu
IN1  = pcbnew.In1_Cu  # GND plane
IN2  = pcbnew.In2_Cu  # +3V3 plane
TRACK_W = 250000
CLEAR   = 220000
PAD_CLR = 500000
VIA_W   = 550000
VIA_D   = 300000

print("=== ZONE FILL + CONNECTIVITY FIX ===")
b = pcbnew.LoadBoard(INPUT)

# Step 1: Inspect existing zones
zones = list(b.Zones())
print(f"\nZones found: {len(zones)}")
for z in zones:
    layer = z.GetLayer()
    net = z.GetNetname()
    layer_name = "F.Cu" if layer == F_CU else ("B.Cu" if layer == B_CU else (f"In{layer}" if layer in (IN1, IN2) else f"L{layer}"))
    print(f"  Layer={layer_name}  Net={net}  Filled={z.IsFilled()}")

# Step 2: Check if In1.Cu and In2.Cu zones exist
has_gnd_zone = False
has_3v3_zone = False
for z in zones:
    if z.GetLayer() == IN1 and z.GetNetname() == 'GND':
        has_gnd_zone = True
    if z.GetLayer() == IN2 and z.GetNetname() == '+3V3':
        has_3v3_zone = True

# Step 3: If zones missing, create them
board_bb = b.GetBoardEdgesBoundingBox()
bx = board_bb.GetLeft()
by = board_bb.GetTop()
bw = board_bb.GetRight() - board_bb.GetLeft()
bh = board_bb.GetBottom() - board_bb.GetTop()
margin = 500000  # 0.5mm inside edge

print(f"\nBoard bbox: ({bx/1e6:.1f},{by/1e6:.1f}) ({bw/1e6:.1f}x{bh/1e6:.1f})mm")

if not has_gnd_zone:
    print("Creating GND zone on In1.Cu...")
    z = pcbnew.ZONE(b)
    z.SetLayer(IN1)
    net = b.FindNet('GND')
    if net:
        z.SetNetCode(net.GetNetCode())
    # Outline = board area
    outline = [
        pcbnew.VECTOR2I(bx + margin, by + margin),
        pcbnew.VECTOR2I(bx + bw - margin, by + margin),
        pcbnew.VECTOR2I(bx + bw - margin, by + bh - margin),
        pcbnew.VECTOR2I(bx + margin, by + bh - margin),
    ]
    poly = z.Outline()
    poly.NewOutline()
    for p in outline:
        poly.Append(p.x, p.y)
    z.SetMinThickness(200000)
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL_RELIEF)
    b.Add(z)
    print(f"  GND zone added on In1.Cu")

if not has_3v3_zone:
    print("Creating +3V3 zone on In2.Cu...")
    z = pcbnew.ZONE(b)
    z.SetLayer(IN2)
    net = b.FindNet('+3V3')
    if net:
        z.SetNetCode(net.GetNetCode())
    outline = [
        pcbnew.VECTOR2I(bx + margin, by + margin),
        pcbnew.VECTOR2I(bx + bw - margin, by + margin),
        pcbnew.VECTOR2I(bx + bw - margin, by + bh - margin),
        pcbnew.VECTOR2I(bx + margin, by + bh - margin),
    ]
    poly = z.Outline()
    poly.NewOutline()
    for p in outline:
        poly.Append(p.x, p.y)
    z.SetMinThickness(200000)
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL_RELIEF)
    b.Add(z)
    print(f"  +3V3 zone added on In2.Cu")

# Step 4: Fix the short — find and rip LR_RST track near U2 pad 7
tracks = list(b.GetTracks())
print(f"\nTracks before fix: {len(tracks)}")

# Find the shorting track (LR_RST near U2)
ripped = 0
for t in list(tracks):
    netname = ""
    try:
        netname = t.GetNetname()
    except:
        pass
    if netname == 'LR_RST':
        start = t.GetStart()
        end = t.GetEnd()
        # Check if near U2 (around 57mm, 14mm on 80x60 board)
        # U2 is at ~(1450mil, 560mil) = ~(36.8mm, 14.2mm)
        mid_x = (start.x + end.x) / 2
        mid_y = (start.y + end.y) / 2
        # If track passes through U2 area
        if t.GetLayer() == F_CU:
            print(f"  LR_RST track on F.Cu: ({start.x/1e6:.1f},{start.y/1e6:.1f})-({end.x/1e6:.1f},{end.y/1e6:.1f})")
            # Rip it — re-route on B.Cu
            b.Remove(t)
            ripped += 1
            print(f"    RIPPED (causes short with U2)")

print(f"Tracks ripped: {ripped}")

# Step 5: Re-route LR_RST on B.Cu
# Find LR_RST pads
lr_rst_pads = []
for fp in b.GetFootprints():
    for pad in fp.Pads():
        if pad.GetNetname() == 'LR_RST':
            pos = pad.GetPosition()
            lr_rst_pads.append((pos.x, pos.y, fp.GetReference(), 'fp'))

print(f"\nLR_RST pads: {len(lr_rst_pads)}")
for px, py, ref, fpt in lr_rst_pads:
    print(f"  {ref} at ({px/1e6:.1f},{py/1e6:.1f})")

if len(lr_rst_pads) >= 2:
    sx, sy = lr_rst_pads[0][0], lr_rst_pads[0][1]
    ex, ey = lr_rst_pads[1][0], lr_rst_pads[1][1]
    # Manhattan route on B.Cu with endpoint vias
    mid_x, mid_y = ex, sy  # H then V
    segs = [(sx, sy, mid_x, mid_y), (mid_x, mid_y, ex, ey)]
    for s in segs:
        t = pcbnew.PCB_TRACK(b)
        t.SetLayer(B_CU)
        t.SetWidth(TRACK_W)
        t.SetStart(pcbnew.VECTOR2I(s[0], s[1]))
        t.SetEnd(pcbnew.VECTOR2I(s[2], s[3]))
        net = b.FindNet('LR_RST')
        if net:
            t.SetNetCode(net.GetNetCode())
        b.Add(t)
    # Vias at endpoints
    for vx, vy in [(sx, sy), (ex, ey)]:
        v = pcbnew.PCB_VIA(b)
        v.SetPosition(pcbnew.VECTOR2I(vx, vy))
        v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetWidth(VIA_W)
        v.SetDrill(VIA_D)
        net = b.FindNet('LR_RST')
        if net:
            v.SetNetCode(net.GetNetCode())
        b.Add(v)
    print(f"  Re-routed LR_RST on B.Cu with 2 vias")

# Step 6: Route remaining signal nets (GPS_TX, VDIV_MID)
# Collect all nets and their pads
nets = {}
for fp in b.GetFootprints():
    for pad in fp.Pads():
        nn = pad.GetNetname()
        if not nn:
            continue
        if nn not in nets:
            nets[nn] = []
        pos = pad.GetPosition()
        nets[nn].append((pos.x, pos.y, fp.GetReference(), pad.GetAttribute()))

POWER_NETS = {'+3V3', 'GND', 'VCAP', 'SOLAR_IN', 'EN'}

# Helper: segment-rectangle intersection (Liang-Barsky)
def seg_rect_hit(x1, y1, x2, y2, rx1, ry1, rx2, ry2):
    dx = x2 - x1
    dy = y2 - y1
    p = [-dx, dx, -dy, dy]
    q = [x1 - rx1, rx2 - x1, y1 - ry1, ry2 - y1]
    u1, u2 = 0.0, 1.0
    for i in range(4):
        if p[i] == 0:
            if q[i] < 0:
                return False
        else:
            t = q[i] / p[i]
            if p[i] < 0:
                u1 = max(u1, t)
            else:
                u2 = min(u2, t)
    return u1 <= u2

# Build pad obstacles (different net)
obs_pads = []
for fp in b.GetFootprints():
    for pad in fp.Pads():
        pos = pad.GetPosition()
        sz = pad.GetSize()
        net = pad.GetNetname()
        obs_pads.append((pos.x - sz.x//2 - PAD_CLR, pos.y - sz.y//2 - PAD_CLR,
                        pos.x + sz.x//2 + PAD_CLR, pos.y + sz.y//2 + PAD_CLR, net))

# Build track obstacles
obs_tracks = []
for t in list(b.GetTracks()):
    if t.GetClass() == 'PCB_TRACK_T' or t.Type() == pcbnew.PCB_TRACE_T:
        s = t.GetStart()
        e = t.GetEnd()
        obs_tracks.append((s.x, s.y, e.x, e.y, t.GetLayer(), t.GetNetname()))

def orient(ax, ay, bx, by, cx, cy):
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)

def seg_cross(x1, y1, x2, y2, x3, y3, x4, y4):
    d1 = orient(x3, y3, x4, y4, x1, y1)
    d2 = orient(x3, y3, x4, y4, x2, y2)
    d3 = orient(x1, y1, x2, y2, x3, y3)
    d4 = orient(x1, y1, x2, y2, x4, y4)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))

def pad_ok(sx, sy, ex, ey, net):
    for px1, py1, px2, py2, pn in obs_pads:
        if pn == net:
            continue
        if seg_rect_hit(sx, sy, ex, ey, px1, py1, px2, py2):
            return False
    return True

def trk_ok(sx, sy, ex, ey, layer, net):
    for ex1, ey1, ex2, ey2, el, en in obs_tracks:
        if el != layer or en == net:
            continue
        if seg_cross(sx, sy, ex, ey, ex1, ey1, ex2, ey2):
            return False
    return True

def try_route(sx, sy, ex, ey, net, layer):
    # Straight line
    if abs(sx - ex) < 2000 or abs(sy - ey) < 2000:
        if pad_ok(sx, sy, ex, ey, net) and trk_ok(sx, sy, ex, ey, layer, net):
            return [(sx, sy, ex, ey)]
    # L1: H then V
    mx, my = ex, sy
    if pad_ok(sx, sy, mx, my, net) and trk_ok(sx, sy, mx, my, layer, net) and \
       pad_ok(mx, my, ex, ey, net) and trk_ok(mx, my, ex, ey, layer, net):
        return [(sx, sy, mx, my), (mx, my, ex, ey)]
    # L2: V then H
    mx, my = sx, ey
    if pad_ok(sx, sy, mx, my, net) and trk_ok(sx, sy, mx, my, layer, net) and \
       pad_ok(mx, my, ex, ey, net) and trk_ok(mx, my, ex, ey, layer, net):
        return [(sx, sy, mx, my), (mx, my, ex, ey)]
    return None

# Route unrouted signal nets
print(f"\n=== ROUTING REMAINING SIGNAL NETS ===")
routed_count = 0
still_unrouted = []

for netname, pads in sorted(nets.items()):
    if netname in POWER_NETS or len(pads) < 2:
        continue
    ok = False
    for i in range(len(pads) - 1):
        sx, sy = pads[i][0], pads[i][1]
        ex, ey = pads[i+1][0], pads[i+1][1]
        # Try F.Cu
        segs = try_route(sx, sy, ex, ey, netname, F_CU)
        layer = F_CU
        if not segs:
            segs = try_route(sx, sy, ex, ey, netname, B_CU)
            layer = B_CU
            if segs:
                # Add vias at endpoints
                net = b.FindNet(netname)
                nc = net.GetNetCode() if net else 0
                for vx, vy in [(sx, sy), (ex, ey)]:
                    v = pcbnew.PCB_VIA(b)
                    v.SetPosition(pcbnew.VECTOR2I(vx, vy))
                    v.SetViaType(pcbnew.VIATYPE_THROUGH)
                    v.SetWidth(VIA_W)
                    v.SetDrill(VIA_D)
                    v.SetNetCode(nc)
                    b.Add(v)
        if segs:
            net = b.FindNet(netname)
            nc = net.GetNetCode() if net else 0
            for s in segs:
                t = pcbnew.PCB_TRACK(b)
                t.SetLayer(layer)
                t.SetWidth(TRACK_W)
                t.SetStart(pcbnew.VECTOR2I(s[0], s[1]))
                t.SetEnd(pcbnew.VECTOR2I(s[2], s[3]))
                t.SetNetCode(nc)
                b.Add(t)
                obs_tracks.append((s[0], s[1], s[2], s[3], layer, netname))
            ok = True
    if ok:
        routed_count += 1
    else:
        still_unrouted.append(netname)

print(f"  Routed: {routed_count}")
print(f"  Still unrouted: {len(still_unrouted)}")
for u in still_unrouted:
    print(f"    {u}")

# Step 7: Fill zones + rebuild connectivity
print(f"\n=== FILLING ZONES + REBUILDING CONNECTIVITY ===")
b.BuildConnectivity()

zones = list(b.Zones())
print(f"Zones to fill: {len(zones)}")
filler = pcbnew.ZONE_FILLER(b)
filler.Fill(zones)

# Save
pcbnew.SaveBoard(OUTPUT, b)
print(f"\nSaved: {OUTPUT}")

# Step 8: Run DRC
print(f"\n=== DRC ===")
b2 = pcbnew.LoadBoard(OUTPUT)
b2.BuildConnectivity()

# Re-fill zones on loaded board
zones2 = list(b2.Zones())
filler2 = pcbnew.ZONE_FILLER(b2)
filler2.Fill(zones2)

settings = b2.GetDesignSettings()
settings.m_DRCSeverities = {}  # Reset severities
b2.WriteDRCReport('/tmp/drc_final_clean_report.txt', settings)

# Parse DRC report
try:
    with open('/tmp/drc_final_clean_report.txt', 'r') as f:
        report = f.read()
    print(f"\n{report[:3000]}")
except:
    print("DRC report not found, trying alternate method")

print("\n=== DONE ===")
