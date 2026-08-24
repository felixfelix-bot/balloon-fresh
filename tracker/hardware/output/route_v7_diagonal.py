#!/usr/bin/python3.14
"""Diagonal (45°) signal router for balloon PCB v7.

Extends route_v7_signals.py with diagonal routing patterns.
Loads the v7-routed board (9/16 nets already routed) and routes
remaining unconnected nets using 45° diagonal patterns.

Patterns tried (in order):
  a. Single 45° diagonal (both slopes)
  b. Diagonal + orthogonal (45° then H/V, or H/V then 45°)
  c. Z-shaped: diagonal 45°, horizontal, diagonal -45° (and mirror, and vertical-middle variants)
  d. 2-segment diagonal: two 45° segments meeting at computed midpoint
  e. Mixed-layer: diagonal on F.Cu, via, diagonal on B.Cu, via back

Falls back to Manhattan patterns from route_v7_signals.py if all diagonal patterns fail.

Uses the SAME collision detection (seg_cross, seg_hits_pad, route_clear) as the original.
"""
import sys
sys.path.insert(0, '/usr/lib/python3/dist_packages'.replace('_dist_packages', '/dist_packages'))
import pcbnew
import math

INPUT  = '/home/c03rad0r/repos/balloon-fresh/tracker/hardware/output/v_c3_flight_v7_routed.kicad_pcb'
OUTPUT = '/home/c03rad0r/repos/balloon-fresh/tracker/hardware/output/v_c3_flight_v7_diagonal.kicad_pcb'

F_CU = pcbnew.F_Cu
B_CU = pcbnew.B_Cu
TRACK_W = 200000      # 0.2mm
VIA_W   = 550000      # 0.55mm
VIA_D   = 300000      # 0.3mm drill
PAD_CLR = 500000      # 0.5mm pad clearance
VIA_CLR = 600000      # 0.6mm via clearance

BOARD_W = 80000000   # 80mm
BOARD_H = 60000000   # 60mm
MARGIN   = 2000000    # 2mm board edge margin

SIGNAL_NETS = [
    'SPI_SCK', 'SPI_MISO', 'SPI_MOSI', 'SPI_NSS',
    'I2C_SCL', 'I2C_SDA',
    'GPS_TX', 'GPS_RX',
    'UART0_TX', 'UART0_RX',
    'LED_A', 'LED_DRIVE',
    'LR_RST', 'LR_BUSY', 'LR_DIO0',
    'VDIV_MID',
]

DIAG_TOL = 2000000   # 2mm tolerance for "approximately 45°"
MIN_SEG  = 1000000   # 1mm minimum segment length

print("=== Diagonal Signal Router v7 ===")
b = pcbnew.LoadBoard(INPUT)

# Precompute net codes
NET_CODES = {}
for net in b.GetNetsByNetcode().values():
    try:
        NET_CODES[net.GetNetname()] = net.GetNetCode()
    except Exception:
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
    except Exception:
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

# Obstacle list — updated as we add new tracks
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

# === Collision detection (identical to route_v7_signals.py) ===

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
    if point_in_bbox(sx, sy, x1, y1, x2, y2):
        return True
    if point_in_bbox(ex, ey, x1, y1, x2, y2):
        return True
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

# === Helper functions ===

def sign(x):
    if x > 0: return 1
    if x < 0: return -1
    return 0

def in_board(x, y, margin=MARGIN):
    return margin < x < BOARD_W - margin and margin < y < BOARD_H - margin

def is_diagonal(x1, y1, x2, y2, tol=DIAG_TOL):
    """Check if segment is approximately 45° (|dx| ≈ |dy|)."""
    return abs(abs(x2 - x1) - abs(y2 - y1)) < tol

# === Diagonal routing patterns ===

def try_route_diagonal(sx, sy, ex, ey, net, layer, use_vias=False):
    """Try diagonal (45°) routing patterns. Returns list of segments or None.

    Each segment is (x1, y1, x2, y2, layer).
    Via markers are ('via', x, y).
    """
    dx = ex - sx
    dy = ey - sy
    sdx = sign(dx)
    sdy = sign(dy)
    adx = abs(dx)
    ady = abs(dy)

    # --- 1. Straight line (if nearly horizontal or vertical) ---
    if adx < 2000 or ady < 2000:
        if route_clear(sx, sy, ex, ey, layer, net):
            return [(sx, sy, ex, ey, layer)]

    # --- 2. Single 45° diagonal (both slopes) ---
    if is_diagonal(sx, sy, ex, ey):
        if route_clear(sx, sy, ex, ey, layer, net):
            return [(sx, sy, ex, ey, layer)]

    # --- 3. Diagonal + orthogonal ---
    # 3a. Diagonal first (45°), then orthogonal (H or V) to target
    d = min(adx, ady)
    if d >= MIN_SEG:
        diag_end_x = sx + sdx * d
        diag_end_y = sy + sdy * d
        if route_clear(sx, sy, diag_end_x, diag_end_y, layer, net) and \
           route_clear(diag_end_x, diag_end_y, ex, ey, layer, net):
            return [(sx, sy, diag_end_x, diag_end_y, layer),
                    (diag_end_x, diag_end_y, ex, ey, layer)]

    # 3b. Orthogonal first, then diagonal
    if adx > ady and ady >= MIN_SEG:
        # Horizontal first for (adx - ady), then diagonal for ady
        ortho_end_x = ex - sdx * ady
        ortho_end_y = sy
        if route_clear(sx, sy, ortho_end_x, ortho_end_y, layer, net) and \
           route_clear(ortho_end_x, ortho_end_y, ex, ey, layer, net):
            return [(sx, sy, ortho_end_x, ortho_end_y, layer),
                    (ortho_end_x, ortho_end_y, ex, ey, layer)]
    elif ady > adx and adx >= MIN_SEG:
        # Vertical first for (ady - adx), then diagonal for adx
        ortho_end_x = sx
        ortho_end_y = ey - sdy * adx
        if route_clear(sx, sy, ortho_end_x, ortho_end_y, layer, net) and \
           route_clear(ortho_end_x, ortho_end_y, ex, ey, layer, net):
            return [(sx, sy, ortho_end_x, ortho_end_y, layer),
                    (ortho_end_x, ortho_end_y, ex, ey, layer)]

    # --- 4. Z-shaped: diagonal, horizontal, diagonal ---
    # Two slope variants (ds = ±1 = y-direction of first diagonal)
    for ds in [1, -1]:
        # Constraints: d1 > max(0, dy*ds), d1 <= (adx + dy*ds) / 2
        lo = max(MIN_SEG, dy * ds + MIN_SEG)
        hi = (adx + dy * ds) // 2
        if lo >= hi or hi < MIN_SEG:
            continue
        for frac in [0.15, 0.3, 0.5, 0.7, 0.85]:
            d1 = int(lo + frac * (hi - lo))
            if d1 < MIN_SEG:
                continue
            d2 = d1 - dy * ds
            h = adx - 2 * d1 + dy * ds
            if d2 < MIN_SEG or h < 0:
                continue
            mid1_x = sx + sdx * d1
            mid1_y = sy + ds * d1
            mid2_x = sx + sdx * (d1 + h)
            mid2_y = sy + ds * d1  # same y as mid1 (horizontal middle)
            if not in_board(mid1_x, mid1_y) or not in_board(mid2_x, mid2_y):
                continue
            if route_clear(sx, sy, mid1_x, mid1_y, layer, net) and \
               route_clear(mid1_x, mid1_y, mid2_x, mid2_y, layer, net) and \
               route_clear(mid2_x, mid2_y, ex, ey, layer, net):
                return [(sx, sy, mid1_x, mid1_y, layer),
                        (mid1_x, mid1_y, mid2_x, mid2_y, layer),
                        (mid2_x, mid2_y, ex, ey, layer)]

    # --- 4b. Z-shaped: diagonal, vertical, diagonal ---
    for ds in [1, -1]:
        # ds = x-direction of first diagonal
        # d2 = d1 - dx*ds, v = ady - 2*d1 + dx*ds
        lo = max(MIN_SEG, dx * ds + MIN_SEG)
        hi = (ady + dx * ds) // 2
        if lo >= hi or hi < MIN_SEG:
            continue
        for frac in [0.15, 0.3, 0.5, 0.7, 0.85]:
            d1 = int(lo + frac * (hi - lo))
            if d1 < MIN_SEG:
                continue
            d2 = d1 - dx * ds
            v = ady - 2 * d1 + dx * ds
            if d2 < MIN_SEG or v < 0:
                continue
            mid1_x = sx + ds * d1
            mid1_y = sy + sdy * d1
            mid2_x = sx + ds * d1  # same x as mid1 (vertical middle)
            mid2_y = sy + sdy * (d1 + v)
            if not in_board(mid1_x, mid1_y) or not in_board(mid2_x, mid2_y):
                continue
            if route_clear(sx, sy, mid1_x, mid1_y, layer, net) and \
               route_clear(mid1_x, mid1_y, mid2_x, mid2_y, layer, net) and \
               route_clear(mid2_x, mid2_y, ex, ey, layer, net):
                return [(sx, sy, mid1_x, mid1_y, layer),
                        (mid1_x, mid1_y, mid2_x, mid2_y, layer),
                        (mid2_x, mid2_y, ex, ey, layer)]

    # --- 5. 2-segment diagonal: two 45° segments meeting at computed point ---
    # Variant A: first diagonal in x-direction (sdx), y-direction ds1
    #   ds1 = -1: d1 = (adx - dy) / 2, need adx > dy (signed)
    #   ds1 = +1: d1 = (adx + dy) / 2, need adx + dy > 0
    for ds1 in [-1, 1]:
        if ds1 == -1:
            if adx - dy <= 0:
                continue
            d1 = (adx - dy) // 2
        else:
            if adx + dy <= 0:
                continue
            d1 = (adx + dy) // 2
        if d1 < MIN_SEG:
            continue
        # Verify second segment is 45°
        d2_x = adx - d1
        d2_y = dy - ds1 * d1
        if d2_x < MIN_SEG or abs(abs(d2_y) - d2_x) > DIAG_TOL:
            continue
        mid_x = sx + sdx * d1
        mid_y = sy + ds1 * d1
        if not in_board(mid_x, mid_y):
            continue
        if route_clear(sx, sy, mid_x, mid_y, layer, net) and \
           route_clear(mid_x, mid_y, ex, ey, layer, net):
            return [(sx, sy, mid_x, mid_y, layer),
                    (mid_x, mid_y, ex, ey, layer)]

    # Variant B: first diagonal in y-direction (sdy), x-direction ds1
    #   ds1 = -1: d1 = (ady - dx) / 2, need ady > dx (signed)
    #   ds1 = +1: d1 = (ady + dx) / 2, need ady + dx > 0
    for ds1 in [-1, 1]:
        if ds1 == -1:
            if ady - dx <= 0:
                continue
            d1 = (ady - dx) // 2
        else:
            if ady + dx <= 0:
                continue
            d1 = (ady + dx) // 2
        if d1 < MIN_SEG:
            continue
        d2_y = ady - d1
        d2_x = dx - ds1 * d1
        if d2_y < MIN_SEG or abs(abs(d2_x) - d2_y) > DIAG_TOL:
            continue
        mid_x = sx + ds1 * d1
        mid_y = sy + sdy * d1
        if not in_board(mid_x, mid_y):
            continue
        if route_clear(sx, sy, mid_x, mid_y, layer, net) and \
           route_clear(mid_x, mid_y, ex, ey, layer, net):
            return [(sx, sy, mid_x, mid_y, layer),
                    (mid_x, mid_y, ex, ey, layer)]

    # --- 6. Manhattan L-shaped fallback ---
    if route_clear(sx, sy, ex, sy, layer, net) and route_clear(ex, sy, ex, ey, layer, net):
        return [(sx, sy, ex, sy, layer), (ex, sy, ex, ey, layer)]
    if route_clear(sx, sy, sx, ey, layer, net) and route_clear(sx, ey, ex, ey, layer, net):
        return [(sx, sy, sx, ey, layer), (sx, ey, ex, ey, layer)]

    # --- 7. Manhattan 3-segment fallback ---
    for off in [2000000, -2000000, 4000000, -4000000, 6000000, -6000000,
                8000000, -8000000, 10000000, -10000000]:
        # H-offset-V
        mx = ex + off
        if MARGIN < mx < BOARD_W - MARGIN:
            if route_clear(sx, sy, mx, sy, layer, net) and \
               route_clear(mx, sy, mx, ey, layer, net) and \
               route_clear(mx, ey, ex, ey, layer, net):
                return [(sx, sy, mx, sy, layer), (mx, sy, mx, ey, layer),
                        (mx, ey, ex, ey, layer)]
        # V-offset-H
        my = ey + off
        if MARGIN < my < BOARD_H - MARGIN:
            if route_clear(sx, sy, sx, my, layer, net) and \
               route_clear(sx, my, ex, my, layer, net) and \
               route_clear(ex, my, ex, ey, layer, net):
                return [(sx, sy, sx, my, layer), (sx, my, ex, my, layer),
                        (ex, my, ex, ey, layer)]

    # --- 8. Mixed-layer: diagonal on F.Cu, via, diagonal on B.Cu, via back ---
    if not use_vias:
        return None
    other_layer = B_CU if layer == F_CU else F_CU

    # 8a. Diagonal to midpoint on layer, via, diagonal to end on other_layer
    for off_x in [3000000, -3000000, 6000000, -6000000, 9000000, -9000000]:
        for off_y in [3000000, -3000000, 6000000, -6000000, 0]:
            mx = (sx + ex) // 2 + off_x
            my = (sy + ey) // 2 + off_y
            if not in_board(mx, my):
                continue

            # Build first-leg segments (start → midpoint on `layer`)
            segs1 = _try_diag_or_ortho(sx, sy, mx, my, net, layer)
            if segs1 is None:
                continue

            # Build second-leg segments (midpoint → end on `other_layer`)
            segs2 = _try_diag_or_ortho(mx, my, ex, ey, net, other_layer)
            if segs2 is None:
                continue

            # Combine with vias
            result = list(segs1)
            result.append(('via', mx, my))
            result.extend(segs2)
            result.append(('via', ex, ey))
            return result

    # 8b. Manhattan mixed-layer (from original route_v7_signals.py)
    for off in [5000000, -5000000, 10000000, -10000000]:
        mx = (sx + ex) // 2 + off
        if mx < MARGIN or mx > BOARD_W - MARGIN:
            continue
        if route_clear(sx, sy, mx, sy, layer, net) and \
           route_clear(mx, sy, mx, ey, other_layer, net) and \
           route_clear(mx, ey, ex, ey, layer, net):
            return [('via', mx, sy),
                    (sx, sy, mx, sy, layer),
                    (mx, sy, mx, ey, other_layer),
                    ('via', mx, ey),
                    (mx, ey, ex, ey, layer)]

    return None


def _try_diag_or_ortho(sx, sy, ex, ey, net, layer):
    """Try a single 45° diagonal, or diagonal+ortho, or Manhattan L.
    Returns list of (x1,y1,x2,y2,layer) segments or None.
    Does NOT use vias — single layer only.
    """
    dx = ex - sx
    dy = ey - sy
    sdx = sign(dx)
    sdy = sign(dy)
    adx = abs(dx)
    ady = abs(dy)

    # Direct line
    if adx < 2000 or ady < 2000:
        if route_clear(sx, sy, ex, ey, layer, net):
            return [(sx, sy, ex, ey, layer)]

    # Single 45° diagonal
    if is_diagonal(sx, sy, ex, ey):
        if route_clear(sx, sy, ex, ey, layer, net):
            return [(sx, sy, ex, ey, layer)]

    # Diagonal first, then orthogonal
    d = min(adx, ady)
    if d >= MIN_SEG:
        dx2 = sx + sdx * d
        dy2 = sy + sdy * d
        if route_clear(sx, sy, dx2, dy2, layer, net) and \
           route_clear(dx2, dy2, ex, ey, layer, net):
            return [(sx, sy, dx2, dy2, layer), (dx2, dy2, ex, ey, layer)]

    # Orthogonal first, then diagonal
    if adx > ady and ady >= MIN_SEG:
        ox = ex - sdx * ady
        oy = sy
        if route_clear(sx, sy, ox, oy, layer, net) and \
           route_clear(ox, oy, ex, ey, layer, net):
            return [(sx, sy, ox, oy, layer), (ox, oy, ex, ey, layer)]
    elif ady > adx and adx >= MIN_SEG:
        ox = sx
        oy = ey - sdy * adx
        if route_clear(sx, sy, ox, oy, layer, net) and \
           route_clear(ox, oy, ex, ey, layer, net):
            return [(sx, sy, ox, oy, layer), (ox, oy, ex, ey, layer)]

    # Manhattan L-shaped
    if route_clear(sx, sy, ex, sy, layer, net) and route_clear(ex, sy, ex, ey, layer, net):
        return [(sx, sy, ex, sy, layer), (ex, sy, ex, ey, layer)]
    if route_clear(sx, sy, sx, ey, layer, net) and route_clear(sx, ey, ex, ey, layer, net):
        return [(sx, sy, sx, ey, layer), (sx, ey, ex, ey, layer)]

    return None


# === Connectivity check ===

def is_net_routed(net):
    """Check if a net already has tracks (already routed by v7 router)."""
    if net not in net_pads or len(net_pads[net]) < 2:
        return True  # Nothing to route
    track_count = 0
    for ot in existing_tracks:
        if ot[0] == 'track':
            tn = ot[7]
            if tn == net:
                track_count += 1
        elif ot[0] == 'via':
            vn = ot[4]
            if vn == net:
                track_count += 1
    return track_count > 0


def route_net_diagonal(net):
    """Route a single signal net with diagonal patterns. Returns True if all pads connected."""
    if net not in net_pads or len(net_pads[net]) < 2:
        print(f"  SKIP {net}: {len(net_pads.get(net, []))} pads")
        return False

    pads = net_pads[net]
    if len(pads) > 2:
        # Multi-pad: nearest-neighbor chain
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
        segs = try_route_diagonal(sx, sy, ex, ey, net, F_CU, use_vias=True)
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
        segs = try_route_diagonal(sx, sy, ex, ey, net, B_CU, use_vias=True)
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


# === Identify unconnected nets ===
print(f"\nChecking {len(SIGNAL_NETS)} signal nets...")
already_routed = []
to_route = []
for net in SIGNAL_NETS:
    if is_net_routed(net):
        already_routed.append(net)
        print(f"  ALREADY ROUTED: {net}")
    else:
        to_route.append(net)
        print(f"  NEEDS ROUTING: {net}")

print(f"\nAlready routed (preserved): {len(already_routed)}/{len(SIGNAL_NETS)}")
print(f"To route: {len(to_route)}")

# === Route unconnected nets with diagonal patterns ===
print(f"\nRouting {len(to_route)} nets with diagonal patterns...")
routed = 0
failed = []

for net in to_route:
    if route_net_diagonal(net):
        routed += 1
        print(f"  ROUTED: {net}")
    else:
        failed.append(net)
        print(f"  FAILED: {net}")

print(f"\n=== ROUTING SUMMARY ===")
print(f"Already routed (preserved): {len(already_routed)}")
print(f"Newly routed: {routed}/{len(to_route)}")
print(f"Still failed: {len(failed)}")
for f in failed:
    print(f"  {f}")
print(f"Total connected: {len(already_routed) + routed}/{len(SIGNAL_NETS)}")

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