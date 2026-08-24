#!/usr/bin/python3.14
"""Route 16 signal nets on balloon PCB with collision detection.
Preserves existing tracks/vias from Phase 1A. Routes only missing signal nets.
"""
import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew
import math

INPUT  = '/home/c03rad0r/repos/balloon-fresh/tracker/hardware/output/v_c3_flight_rf_power.kicad_pcb'
OUTPUT = '/home/c03rad0r/repos/balloon-fresh/tracker/hardware/output/v_c3_flight_v7_routed.kicad_pcb'

F_CU = pcbnew.F_Cu
B_CU = pcbnew.B_Cu
TRACK_W = 200000      # 0.2mm
VIA_W   = 550000      # 0.55mm
VIA_D   = 300000      # 0.3mm drill
PAD_CLR = 500000      # 0.5mm pad clearance
VIA_CLR = 600000      # 0.6mm via clearance

SIGNAL_NETS = [
    'SPI_SCK', 'SPI_MISO', 'SPI_MOSI', 'SPI_NSS',
    'I2C_SCL', 'I2C_SDA',
    'GPS_TX', 'GPS_RX',
    'UART0_TX', 'UART0_RX',
    'LED_A', 'LED_DRIVE',
    'LR_RST', 'LR_BUSY', 'LR_DIO0',
    'VDIV_MID',
]

print("=== Signal Router v7 ===")
b = pcbnew.LoadBoard(INPUT)

# Precompute net codes
NET_CODES = {}
for net in b.GetNetsByNetcode().values():
    try:
        NET_CODES[net.GetNetname()] = net.GetNetCode()
    except:
        pass

# Snapshot ALL existing tracks/vias BEFORE any modification
existing_tracks = []
for t in b.Tracks():
    try:
        if t.GetClass() == 'PCB_VIA':
            pos = t.GetPosition()
            existing_tracks.append(('via', t, pos.x, pos.y, t.GetNetname()))
        else:
            s = t.GetStart(); e = t.GetEnd()
            existing_tracks.append(('track', t, s.x, s.y, e.x, e.y, t.GetLayer(), t.GetNetname()))
    except:
        pass
print(f"Existing tracks/vias snapshot: {len(existing_tracks)}")

# Collect pads by net
net_pads = {}
all_pads = []  # (x, y, w, h, netname, ref)
for fp in b.GetFootprints():
    ref = fp.GetReference()
    for pad in fp.Pads():
        nn = pad.GetNetname()
        if not nn:
            continue
        pos = pad.GetPosition()
        sz = pad.GetSize()
        px, py = pos.x, pos.y
        pw, ph = sz.x // 2, sz.y // 2
        all_pads.append((px, py, pw, ph, nn, ref))
        if nn not in net_pads:
            net_pads[nn] = []
        net_pads[nn].append((px, py, ref))

print(f"Total pads: {len(all_pads)}")
print(f"Nets with pads: {len(net_pads)}")

# Obstacle list (tracks) — updated as we add new tracks
new_obstacles = []

def add_track(x1, y1, x2, y2, layer, netname):
    t = pcbnew.PCB_TRACK(b)
    t.SetLayer(layer)
    t.SetWidth(TRACK_W)
    t.SetStart(pcbnew.VECTOR2I(int(x1), int(y1)))
    t.SetEnd(pcbnew.VECTOR2I(int(x2), int(y2)))
    t.SetNetCode(NET_CODES.get(netname, 0))
    b.Add(t)
    new_obstacles.append(('track', x1, y1, x2, y2, layer, netname))
    return t

def add_via(x, y, netname):
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(pcbnew.VECTOR2I(int(x), int(y)))
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetWidth(VIA_W)
    v.SetDrill(VIA_D)
    v.SetNetCode(NET_CODES.get(netname, 0))
    b.Add(v)
    new_obstacles.append(('via', x, y, netname))
    return v

# === Collision detection ===

def seg_cross(x1, y1, x2, y2, x3, y3, x4, y4):
    """Segment-segment intersection test (orientation method)."""
    def orient(ax, ay, bx, by, cx, cy):
        return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
    d1 = orient(x3, y3, x4, y4, x1, y1)
    d2 = orient(x3, y3, x4, y4, x2, y2)
    d3 = orient(x1, y1, x2, y2, x3, y3)
    d4 = orient(x1, y1, x2, y2, x4, y4)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))

def point_in_bbox(px, py, x1, y1, x2, y2):
    return x1 <= px <= x2 and y1 <= py <= y2

def seg_hits_pad(sx, sy, ex, ey, px, py, pw, ph, clr):
    """Check if segment passes through expanded pad bbox."""
    x1 = px - pw - clr
    y1 = py - ph - clr
    x2 = px + pw + clr
    y2 = py + ph + clr
    # If either endpoint inside expanded bbox → collision
    if point_in_bbox(sx, sy, x1, y1, x2, y2):
        return True
    if point_in_bbox(ex, ey, x1, y1, x2, y2):
        return True
    # Check segment vs 4 bbox edges
    if seg_cross(sx, sy, ex, ey, x1, y1, x2, y1): return True
    if seg_cross(sx, sy, ex, ey, x2, y1, x2, y2): return True
    if seg_cross(sx, sy, ex, ey, x2, y2, x1, y2): return True
    if seg_cross(sx, sy, ex, ey, x1, y2, x1, y1): return True
    return False

def route_clear(sx, sy, ex, ey, layer, net):
    """Check if a track segment from (sx,sy) to (ex,ey) on layer is collision-free."""
    # Check pad obstacles
    for px, py, pw, ph, pn, ref in all_pads:
        if pn == net:
            continue
        if seg_hits_pad(sx, sy, ex, ey, px, py, pw, ph, PAD_CLR):
            return False
    # Check existing track obstacles
    for ot in existing_tracks:
        if ot[0] == 'track':
            _, t, tx1, ty1, tx2, ty2, tl, tn = ot
            if tl != layer or tn == net:
                continue
            if seg_cross(sx, sy, ex, ey, tx1, ty1, tx2, ty2):
                return False
        elif ot[0] == 'via':
            _, t, vx, vy, vn = ot
            if vn == net:
                continue
            # Via clearance: check if either endpoint is too close
            if math.sqrt((sx - vx)**2 + (sy - vy)**2) < VIA_CLR:
                return False
            if math.sqrt((ex - vx)**2 + (ey - vy)**2) < VIA_CLR:
                return False
    # Check new obstacles (tracks we just added)
    for ot in new_obstacles:
        if ot[0] == 'track':
            _, tx1, ty1, tx2, ty2, tl, tn = ot
            if tl != layer or tn == net:
                continue
            if seg_cross(sx, sy, ex, ey, tx1, ty1, tx2, ty2):
                return False
        elif ot[0] == 'via':
            _, vx, vy, vn = ot
            if vn == net:
                continue
            if math.sqrt((sx - vx)**2 + (sy - vy)**2) < VIA_CLR:
                return False
            if math.sqrt((ex - vx)**2 + (ey - vy)**2) < VIA_CLR:
                return False
    return True

def try_route(sx, sy, ex, ey, net, layer, use_vias=False):
    """Try Manhattan routing patterns. Returns list of (x1,y1,x2,y2) segments or None."""
    segments = None

    # 1. Straight line
    if abs(sx - ex) < 2000 or abs(sy - ey) < 2000:
        if route_clear(sx, sy, ex, ey, layer, net):
            return [(sx, sy, ex, ey)]

    # 2. L-shaped H-V: horizontal then vertical
    if route_clear(sx, sy, ex, sy, layer, net) and route_clear(ex, sy, ex, ey, layer, net):
        return [(sx, sy, ex, sy), (ex, sy, ex, ey)]

    # 3. L-shaped V-H: vertical then horizontal
    if route_clear(sx, sy, sx, ey, layer, net) and route_clear(sx, ey, ex, ey, layer, net):
        return [(sx, sy, sx, ey), (sx, ey, ex, ey)]

    # 4. 3-segment offset: H-offset-V or V-offset-H
    for off in [2000000, -2000000, 4000000, -4000000, 6000000, -6000000, 8000000, -8000000, 10000000, -10000000]:
        # H-offset-V: horizontal to offset X, vertical to target Y, horizontal to end
        mx = ex + off
        if mx > 2000000 and mx < 78000000:  # stay in board
            if route_clear(sx, sy, mx, sy, layer, net) and \
               route_clear(mx, sy, mx, ey, layer, net) and \
               route_clear(mx, ey, ex, ey, layer, net):
                return [(sx, sy, mx, sy), (mx, sy, mx, ey), (mx, ey, ex, ey)]
        # V-offset-H: vertical to offset Y, horizontal to target X, vertical to end
        my = ey + off
        if my > 2000000 and my < 58000000:  # stay in board
            if route_clear(sx, sy, sx, my, layer, net) and \
               route_clear(sx, my, ex, my, layer, net) and \
               route_clear(ex, my, ex, ey, layer, net):
                return [(sx, sy, sx, my), (sx, my, ex, my), (ex, my, ex, ey)]

    # 5. Mixed-layer: F.Cu segment + via + B.Cu segment + via + F.Cu segment
    if not use_vias:
        return None
    other_layer = B_CU if layer == F_CU else F_CU
    for off in [5000000, -5000000, 10000000, -10000000]:
        mx = (sx + ex) // 2 + off
        if mx < 2000000 or mx > 78000000:
            continue
        # F.Cu to midpoint, via, B.Cu to endpoint area, via back
        if route_clear(sx, sy, mx, sy, layer, net) and \
           route_clear(mx, sy, mx, ey, other_layer, net) and \
           route_clear(mx, ey, ex, ey, layer, net):
            # Return as 3 segments with via markers
            return [('via', mx, sy), (sx, sy, mx, sy, layer), (mx, sy, mx, ey, other_layer), ('via', mx, ey), (mx, ey, ex, ey, layer)]

def route_net(net):
    """Route a single signal net. Returns True if all pads connected."""
    if net not in net_pads or len(net_pads[net]) < 2:
        print(f"  SKIP {net}: {len(net_pads.get(net, []))} pads")
        return False

    pads = net_pads[net]
    if len(pads) > 2:
        # Multi-pad: sort by proximity chain (nearest neighbor)
        chain = [pads[0]]
        remaining = list(pads[1:])
        while remaining:
            last = chain[-1]
            nearest = min(remaining, key=lambda p: (p[0]-last[0])**2 + (p[1]-last[1])**2)
            chain.append(nearest)
            remaining.remove(nearest)
        pads = chain

    all_ok = True
    for i in range(len(pads) - 1):
        sx, sy = pads[i][0], pads[i][1]
        ex, ey = pads[i+1][0], pads[i+1][1]

        # Try F.Cu first
        segs = try_route(sx, sy, ex, ey, net, F_CU, use_vias=True)
        if segs:
            for s in segs:
                if isinstance(s, tuple) and s[0] == 'via':
                    add_via(s[1], s[2], net)
                elif len(s) == 5:
                    add_track(s[0], s[1], s[2], s[3], s[4], net)
                else:
                    add_track(s[0], s[1], s[2], s[3], F_CU, net)
            continue

        # Try B.Cu with vias at endpoints
        segs = try_route(sx, sy, ex, ey, net, B_CU, use_vias=True)
        if segs:
            add_via(sx, sy, net)
            add_via(ex, ey, net)
            for s in segs:
                if isinstance(s, tuple) and s[0] == 'via':
                    add_via(s[1], s[2], net)
                elif len(s) == 5:
                    add_track(s[0], s[1], s[2], s[3], s[4], net)
                else:
                    add_track(s[0], s[1], s[2], s[3], B_CU, net)
            continue

        all_ok = False
        print(f"    Failed segment: ({sx/1e6:.1f},{sy/1e6:.1f}) -> ({ex/1e6:.1f},{ey/1e6:.1f})")

    return all_ok

# === Route all signal nets ===
print(f"\nRouting {len(SIGNAL_NETS)} signal nets...")
routed = 0
failed = []

for net in SIGNAL_NETS:
    if route_net(net):
        routed += 1
        print(f"  ROUTED: {net}")
    else:
        failed.append(net)
        print(f"  FAILED: {net}")

print(f"\n=== ROUTING SUMMARY ===")
print(f"Routed: {routed}/{len(SIGNAL_NETS)}")
print(f"Failed: {len(failed)}")
for f in failed:
    print(f"  {f}")

# === Fill zones + connectivity ===
print("\nFilling zones...")
b.BuildConnectivity()
zones = list(b.Zones())
filler = pcbnew.ZONE_FILLER(b)
filler.Fill(zones)
print(f"Filled {len(zones)} zones")

# === Save ===
pcbnew.SaveBoard(OUTPUT, b)
print(f"\nSaved: {OUTPUT}")
print("\n=== DONE ===")