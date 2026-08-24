#!/usr/bin/env python3.14
"""Convert v_c3_flight_final.kicad_pcb to 4-layer with power planes + re-route all signal nets.
Iteration 3: Fixed pad collision (bbox), THT thermal via skip, layer distribution,
  0.5mm pad clearance, no collision fallback, thermal via spacing,
  via-aware routing: F.Cu stub→via→B.Cu→via→F.Cu stub for SMD pads."""
import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew
import math
import os

INPUT  = '/home/c03rad0r/repos/balloon-fresh/tracker/hardware/output/v_c3_flight_final.kicad_pcb'
OUTPUT = '/home/c03rad0r/repos/balloon-fresh/tracker/hardware/output/v_c3_flight_4layer_routed.kicad_pcb'

# Constants
TRACK_WIDTH   = 250000   # 0.25mm
CLEARANCE      = 220000   # 0.22mm track-to-track
PAD_CLEARANCE  = 500000   # 0.50mm pad-to-track (as specified)
VIA_WIDTH      = 550000   # 0.55mm
VIA_DRILL      = 300000   # 0.30mm
VIA_RADIUS     = VIA_WIDTH // 2  # 275000nm
VIA_SPACING    = 800000   # 0.8mm min center-to-center for different-net vias
VIA_PAD_OFFSET = 2000000  # 2.0mm offset from pad center for routing vias
F_CU  = pcbnew.F_Cu    # 0
B_CU  = pcbnew.B_Cu    # 2
IN1   = pcbnew.In1_Cu  # 4
IN2   = pcbnew.In2_Cu  # 6

POWER_NETS = {'+3V3', 'GND', 'VCAP', 'SOLAR_IN', 'EN'}

# ─── Geometry helpers ─────────────────────────────────────────────────────────

def ccw(A, B, C):
    return (C[1]-A[1])*(B[0]-A[0]) - (B[1]-A[1])*(C[0]-A[0])

def seg_cross(p1, p2, p3, p4):
    d1 = ccw(p3, p4, p1)
    d2 = ccw(p3, p4, p2)
    d3 = ccw(p1, p2, p3)
    d4 = ccw(p1, p2, p4)
    return ((d1>0 and d2<0) or (d1<0 and d2>0)) and ((d3>0 and d4<0) or (d3<0 and d4>0))

def point_seg_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2-x1, y2-y1
    l2 = dx*dx + dy*dy
    if l2 == 0:
        return math.sqrt((px-x1)**2 + (py-y1)**2)
    t = max(0, min(1, ((px-x1)*dx + (py-y1)*dy)/l2))
    return math.sqrt((px-(x1+t*dx))**2 + (py-(y1+t*dy))**2)

def seg_collides(s1a, s1b, s2a, s2b, clearance):
    if seg_cross(s1a, s1b, s2a, s2b):
        return True
    min_d = min(
        point_seg_dist(s1a[0], s1a[1], s2a[0], s2a[1], s2b[0], s2b[1]),
        point_seg_dist(s1b[0], s1b[1], s2a[0], s2a[1], s2b[0], s2b[1]),
        point_seg_dist(s2a[0], s2a[1], s1a[0], s1a[1], s1b[0], s1b[1]),
        point_seg_dist(s2b[0], s2b[1], s1a[0], s1a[1], s1b[0], s1b[1]),
    )
    return min_d < clearance

def colinear_overlap(s1a, s1b, s2a, s2b):
    def cross2d(ax, ay, bx, by): return ax*by - ay*bx
    dx1 = s1b[0]-s1a[0]; dy1 = s1b[1]-s1a[1]
    dx2 = s2b[0]-s2a[0]; dy2 = s2b[1]-s2a[1]
    cross = cross2d(dx1, dy1, dx2, dy2)
    if abs(cross) > 0:
        return False
    if s1a != s2a and s1a != s2b:
        cross2 = cross2d(s2a[0]-s1a[0], s2a[1]-s1a[1], dx1, dy1)
        if abs(cross2) > 0:
            return False
    lo_x = max(min(s1a[0],s1b[0]), min(s2a[0],s2b[0]))
    hi_x = min(max(s1a[0],s1b[0]), max(s2a[0],s2b[0]))
    lo_y = max(min(s1a[1],s1b[1]), min(s2a[1],s2b[1]))
    hi_y = min(max(s1a[1],s1b[1]), max(s2a[1],s2b[1]))
    return (hi_x - lo_x >= 0) and (hi_y - lo_y >= 0)

def segments_share_endpoint(s1a, s1b, s2a, s2b):
    return any(p == q for p in [s1a, s1b] for q in [s2a, s2b])

def seg_rect_intersect(x1, y1, x2, y2, rxmin, rymin, rxmax, rymax):
    """Liang-Barsky segment-rectangle intersection."""
    dx = x2 - x1
    dy = y2 - y1
    p = [-dx, dx, -dy, dy]
    q = [x1 - rxmin, rxmax - x1, y1 - rymin, rymax - y1]
    u1 = 0.0
    u2 = 1.0
    for i in range(4):
        if p[i] == 0:
            if q[i] < 0:
                return False
        else:
            t = q[i] / p[i]
            if p[i] < 0:
                if t > u2:
                    return False
                if t > u1:
                    u1 = t
            else:
                if t < u1:
                    return False
                if t < u2:
                    u2 = t
    return u1 <= u2

def dist2d(p1, p2):
    return math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)

# ─── Board state ──────────────────────────────────────────────────────────────

routed_segments = []
routed_vias     = []
pad_info        = []  # (rxmin, rymin, rxmax, rymax, is_tht, pad_layer, netcode, netname, pos_x, pos_y)
pad_pos_to_info = {}  # (x, y) -> (is_tht, pad_layer) for routing
footprint_info  = {}  # ref -> (bbox_xmin, bbox_ymin, bbox_xmax, bbox_ymax) for via offset calc

def is_pad_tht(pad):
    try:
        attr = pad.GetAttribute()
        if hasattr(pcbnew, 'PAD_ATTRIB_THT') and attr == pcbnew.PAD_ATTRIB_THT:
            return True
        if hasattr(pcbnew, 'PAD_ATTRIB_PTH') and attr == pcbnew.PAD_ATTRIB_PTH:
            return True
    except:
        pass
    try:
        drill = pad.GetDrillSize()
        if drill.x > 0 and drill.y > 0:
            return True
    except:
        pass
    return False

def get_pad_bbox(pad):
    try:
        bbox = pad.GetBoundingBox()
        return bbox.GetX(), bbox.GetY(), bbox.GetX() + bbox.GetWidth(), bbox.GetY() + bbox.GetHeight()
    except:
        pos = pad.GetPosition()
        size = pad.GetSize()
        return pos.x - size.x // 2, pos.y - size.y // 2, pos.x + size.x // 2, pos.y + size.y // 2

def check_collision(layer, seg_a, seg_b, netcode):
    """Check if a proposed segment collides with existing tracks/vias/pads on same layer."""
    for rxmin, rymin, rxmax, rymax, is_tht, pad_layer, pad_net, pad_netname, _, _ in pad_info:
        if pad_net == netcode:
            continue
        if not is_tht and pad_layer != layer:
            continue
        if seg_rect_intersect(seg_a[0], seg_a[1], seg_b[0], seg_b[1],
                              rxmin - PAD_CLEARANCE, rymin - PAD_CLEARANCE,
                              rxmax + PAD_CLEARANCE, rymax + PAD_CLEARANCE):
            return True

    for vx, vy, via_net in routed_vias:
        if via_net == netcode:
            continue
        d = point_seg_dist(vx, vy, seg_a[0], seg_a[1], seg_b[0], seg_b[1])
        if d < CLEARANCE + VIA_RADIUS:
            return True

    for r_layer, r_a, r_b, r_net in routed_segments:
        if r_layer != layer:
            continue
        if r_net == netcode:
            continue
        if segments_share_endpoint(seg_a, seg_b, r_a, r_b):
            if not colinear_overlap(seg_a, seg_b, r_a, r_b):
                continue
        if seg_collides(seg_a, seg_b, r_a, r_b, CLEARANCE):
            return True
        if colinear_overlap(seg_a, seg_b, r_a, r_b):
            return True
    return False

def count_collisions(layer, seg_a, seg_b, netcode):
    count = 0
    for rxmin, rymin, rxmax, rymax, is_tht, pad_layer, pad_net, pad_netname, _, _ in pad_info:
        if pad_net == netcode:
            continue
        if not is_tht and pad_layer != layer:
            continue
        if seg_rect_intersect(seg_a[0], seg_a[1], seg_b[0], seg_b[1],
                              rxmin - PAD_CLEARANCE, rymin - PAD_CLEARANCE,
                              rxmax + PAD_CLEARANCE, rymax + PAD_CLEARANCE):
            count += 1
    for vx, vy, via_net in routed_vias:
        if via_net == netcode:
            continue
        d = point_seg_dist(vx, vy, seg_a[0], seg_a[1], seg_b[0], seg_b[1])
        if d < CLEARANCE + VIA_RADIUS:
            count += 1
    for r_layer, r_a, r_b, r_net in routed_segments:
        if r_layer != layer:
            continue
        if r_net == netcode:
            continue
        if segments_share_endpoint(seg_a, seg_b, r_a, r_b):
            if not colinear_overlap(seg_a, seg_b, r_a, r_b):
                continue
        if seg_collides(seg_a, seg_b, r_a, r_b, CLEARANCE):
            count += 1
        elif colinear_overlap(seg_a, seg_b, r_a, r_b):
            count += 1
    return count

def via_at_pos_ok(pos, netcode):
    """Check if a via at pos is OK (no collision with other vias/pads)."""
    px, py = pos
    for vx, vy, vnet in routed_vias:
        d = dist2d((px, py), (vx, vy))
        if vnet == netcode:
            if d < 100000:
                return False
        else:
            if d < VIA_SPACING:
                return False
    # Check pad collisions
    for rxmin, rymin, rxmax, rymax, is_tht, pad_layer, pad_net, pad_netname, _, _ in pad_info:
        if pad_net == netcode:
            continue
        if (rxmin - CLEARANCE <= px <= rxmax + CLEARANCE and
            rymin - CLEARANCE <= py <= rymax + CLEARANCE):
            return False
    return True

# ─── Via offset calculation ────────────────────────────────────────────────────

def calc_via_offset(pad_pos, pad_ref):
    """Calculate the best direction to offset a via from a pad.
    Tries to place the via away from the IC body (outside the footprint)."""
    px, py = pad_pos
    
    if pad_ref in footprint_info:
        fxmin, fymin, fxmax, fymax = footprint_info[pad_ref]
        fcx = (fxmin + fxmax) / 2
        fcy = (fymin + fymax) / 2
        
        # Offset away from footprint center
        dx = px - fcx
        dy = py - fcy
        
        # Normalize and scale
        if abs(dx) > abs(dy):
            # Pad is on left/right side of footprint — offset horizontally
            offset_x = VIA_PAD_OFFSET if dx > 0 else -VIA_PAD_OFFSET
            offset_y = 0
        else:
            # Pad is on top/bottom — offset vertically
            offset_x = 0
            offset_y = VIA_PAD_OFFSET if dy > 0 else -VIA_PAD_OFFSET
        
        return (px + offset_x, py + offset_y)
    else:
        # No footprint info — offset rightward
        return (px + VIA_PAD_OFFSET, py)

def try_via_offsets(pad_pos, pad_ref, netcode):
    """Try multiple via positions near a pad. Returns best (x, y) or None."""
    # Try calculated offset first
    candidates = []
    
    base_offset = calc_via_offset(pad_pos, pad_ref)
    candidates.append(base_offset)
    
    px, py = pad_pos
    # Try all 4 cardinal directions at various distances
    for dist in [VIA_PAD_OFFSET, 1500000, 2500000, 3000000]:
        for dx, dy in [(dist, 0), (-dist, 0), (0, dist), (0, -dist),
                       (dist, dist), (-dist, dist), (dist, -dist), (-dist, -dist)]:
            candidates.append((px + dx, py + dy))
    
    # Try diagonal offsets at 45 degrees
    diag_dist = int(VIA_PAD_OFFSET * 0.707)
    for dx, dy in [(diag_dist, diag_dist), (-diag_dist, diag_dist), 
                   (diag_dist, -diag_dist), (-diag_dist, -diag_dist)]:
        candidates.append((px + dx, py + dy))
    
    for pos in candidates:
        if via_at_pos_ok(pos, netcode):
            return pos
    return None

# ─── Track/Via creation ────────────────────────────────────────────────────────

def make_track(board, layer, start, end, netcode):
    t = pcbnew.PCB_TRACK(board)
    t.SetLayer(layer)
    t.SetWidth(TRACK_WIDTH)
    t.SetStart(pcbnew.VECTOR2I(int(start[0]), int(start[1])))
    t.SetEnd(pcbnew.VECTOR2I(int(end[0]), int(end[1])))
    t.SetNetCode(netcode)
    board.Add(t)
    return t

def make_via(board, pos, netcode):
    v = pcbnew.PCB_VIA(board)
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetPosition(pcbnew.VECTOR2I(int(pos[0]), int(pos[1])))
    v.SetNetCode(netcode)
    v.SetWidth(VIA_WIDTH)
    v.SetDrill(VIA_DRILL)
    v.SetLayer(F_CU)
    board.Add(v)
    return v

def commit_route(board, segments, vias, netcode):
    for layer, start, end in segments:
        make_track(board, layer, start, end, netcode)
        routed_segments.append((layer, start, end, netcode))
    for via_pos in vias:
        make_via(board, via_pos, netcode)
        routed_vias.append((via_pos[0], via_pos[1], netcode))

# ─── Routing engine ────────────────────────────────────────────────────────────

def route_direct(start, end, netcode, start_layers, end_layers, preferred='HV'):
    """Try to route directly (same layer or single via at midpoint).
    Returns (segments, vias) or (None, None) if no collision-free route."""
    sx, sy = start
    ex, ey = end
    if sx == ex and sy == ey:
        return [], []

    # Pass 1: Single-layer Manhattan (both patterns, both layers)
    for pattern in [preferred, 'VH' if preferred == 'HV' else 'HV']:
        for layer in [F_CU, B_CU]:
            mid = (ex, sy) if pattern == 'HV' else (sx, ey)
            segments = []
            if start != mid:
                segments.append((layer, start, mid))
            if mid != end:
                segments.append((layer, mid, end))
            
            # Check endpoint layer compatibility
            endpoint_vias = []
            if layer not in start_layers:
                endpoint_vias.append(start)
            if layer not in end_layers:
                endpoint_vias.append(end)
            
            # Check via collisions at endpoints
            via_ok = all(via_at_pos_ok(v, netcode) for v in endpoint_vias)
            if not via_ok:
                continue
            
            collisions = sum(count_collisions(l, a, b, netcode) for l, a, b in segments)
            if collisions == 0:
                return segments, endpoint_vias

    # Pass 2: Mixed-layer with via at midpoint
    for pattern in ['HV', 'VH']:
        mid = (ex, sy) if pattern == 'HV' else (sx, ey)
        for l1, l2 in [(F_CU, B_CU), (B_CU, F_CU)]:
            if l1 not in start_layers or l2 not in end_layers:
                continue
            seg1 = (l1, start, mid) if start != mid else None
            seg2 = (l2, mid, end) if mid != end else None
            if not seg1 or not seg2:
                continue
            c1 = count_collisions(l1, start, mid, netcode)
            c2 = count_collisions(l2, mid, end, netcode)
            via_ok = via_at_pos_ok(mid, netcode)
            if c1 + c2 == 0 and via_ok:
                return [seg1, seg2], [mid]

    # Pass 3: Offset single-layer routing
    for offset in [1500000, 2500000, 3500000, -1500000, -2500000, 4000000, -4000000]:
        for pattern in ['HV', 'VH']:
            if pattern == 'HV':
                mid1 = (ex, sy + offset) if sy + offset != sy else (ex, sy)
                mid2 = (ex, sy)
            else:
                mid1 = (sx + offset, ey) if sx + offset != sx else (sx, ey)
                mid2 = (sx, ey)
            for layer in [F_CU, B_CU]:
                segs = []
                if start != mid1:
                    segs.append((layer, start, mid1))
                if mid1 != mid2:
                    segs.append((layer, mid1, mid2))
                if mid2 != end:
                    segs.append((layer, mid2, end))
                
                endpoint_vias = []
                if layer not in start_layers:
                    endpoint_vias.append(start)
                if layer not in end_layers:
                    endpoint_vias.append(end)
                via_ok = all(via_at_pos_ok(v, netcode) for v in endpoint_vias)
                if not via_ok:
                    continue
                
                collisions = sum(count_collisions(l, a, b, netcode) for l, a, b in segs)
                if collisions == 0:
                    return segs, endpoint_vias

    # Pass 4: Mixed-layer offset routing (3 segments, via at transition)
    for offset in [1500000, 2500000, -1500000, -2500000, 3500000, -3500000]:
        for pattern in ['HV', 'VH']:
            if pattern == 'HV':
                mid1 = (ex, sy + offset) if sy + offset != sy else (ex, sy)
                mid2 = (ex, sy)
            else:
                mid1 = (sx + offset, ey) if sx + offset != sx else (sx, ey)
                mid2 = (sx, ey)
            for l1, l2 in [(F_CU, B_CU), (B_CU, F_CU)]:
                if l1 not in start_layers or l2 not in end_layers:
                    continue
                segs = []
                if start != mid1:
                    segs.append((l1, start, mid1))
                if mid1 != mid2:
                    segs.append((l1, mid1, mid2))
                if mid2 != end:
                    segs.append((l2, mid2, end))
                
                via_ok = via_at_pos_ok(mid2, netcode)
                collisions = sum(count_collisions(l, a, b, netcode) for l, a, b in segs)
                if collisions == 0 and via_ok:
                    return segs, [mid2]

    return None, None

def route_with_routing_vias(board, start, end, netcode, start_pad_ref, end_pad_ref, preferred='HV'):
    """Route using dedicated routing vias near SMD pads.
    F.Cu stub → via1 → B.Cu track → via2 → F.Cu stub.
    Only for SMD pads that can't connect on B.Cu."""
    
    sx, sy = start
    ex, ey = end
    if sx == ex and sy == ey:
        return [], []

    # Try to place routing vias near each pad
    via1_pos = try_via_offsets(start, start_pad_ref, netcode)
    via2_pos = try_via_offsets(end, end_pad_ref, netcode)
    
    if not via1_pos or not via2_pos:
        return None, None
    
    # Build route: start → via1 (F.Cu) → via2 (B.Cu) → end (F.Cu)
    segments = []
    vias = [via1_pos, via2_pos]
    
    # F.Cu stub from pad to via1
    if start != via1_pos:
        segments.append((F_CU, start, via1_pos))
    
    # B.Cu track from via1 to via2
    if via1_pos != via2_pos:
        segments.append((B_CU, via1_pos, via2_pos))
    
    # F.Cu stub from via2 to end
    if via2_pos != end:
        segments.append((F_CU, via2_pos, end))
    
    # Check all collisions
    # Temporarily add vias to check segment collisions
    # (vias are checked separately via via_at_pos_ok which already passed)
    
    # Check F.Cu stubs for pad collisions (these are on F.Cu where all SMD pads live)
    all_collisions = 0
    for layer, s, e in segments:
        # For F.Cu segments, the pad check is strict
        # For B.Cu segments, only THT pads matter
        c = count_collisions(layer, s, e, netcode)
        all_collisions += c
    
    # Also check that the B.Cu track doesn't hit any THT pads
    # and that F.Cu stubs don't hit other SMD pads
    
    # Check via-to-segment collisions (existing segments vs new vias)
    for vx, vy in [via1_pos, via2_pos]:
        for r_layer, r_a, r_b, r_net in routed_segments:
            if r_net == netcode:
                continue
            d = point_seg_dist(vx, vy, r_a[0], r_a[1], r_b[0], r_b[1])
            if d < CLEARANCE + VIA_RADIUS:
                all_collisions += 1
    
    if all_collisions == 0:
        return segments, vias
    
    # Try with offset routing on B.Cu (route via1→waypoint→via2)
    for offset in [1500000, 2500000, -1500000, -2500000, 3500000, -3500000, 5000000, -5000000]:
        for pattern in ['HV', 'VH']:
            if pattern == 'HV':
                wp = (via2_pos[0], via1_pos[1] + offset)
                wp2 = (via2_pos[0], via1_pos[1])
            else:
                wp = (via1_pos[0] + offset, via2_pos[1])
                wp2 = (via1_pos[0], via2_pos[1])
            
            segs = []
            if start != via1_pos:
                segs.append((F_CU, start, via1_pos))
            if via1_pos != wp:
                segs.append((B_CU, via1_pos, wp))
            if wp != wp2:
                segs.append((B_CU, wp, wp2))
            if wp2 != via2_pos:
                segs.append((B_CU, wp2, via2_pos))
            if via2_pos != end:
                segs.append((F_CU, via2_pos, end))
            
            collisions = sum(count_collisions(l, a, b, netcode) for l, a, b in segs)
            if collisions == 0:
                return segs, [via1_pos, via2_pos]
    
    # Try different via positions
    for v1_alt in [via1_pos]:
        for v2_alt in [via2_pos]:
            # Try routing on B.Cu with different Manhattan patterns
            for pattern in ['HV', 'VH']:
                if pattern == 'HV':
                    mid = (v2_alt[0], v1_alt[1])
                else:
                    mid = (v1_alt[0], v2_alt[1])
                
                segs = []
                if start != v1_alt:
                    segs.append((F_CU, start, v1_alt))
                if v1_alt != mid:
                    segs.append((B_CU, v1_alt, mid))
                if mid != v2_alt:
                    segs.append((B_CU, mid, v2_alt))
                if v2_alt != end:
                    segs.append((F_CU, v2_alt, end))
                
                collisions = sum(count_collisions(l, a, b, netcode) for l, a, b in segs)
                if collisions == 0:
                    return segs, [v1_alt, v2_alt]
    
    return None, None

def route_connection(board, start, end, netcode, start_info, end_info, start_ref, end_ref, preferred='HV'):
    """Route a single connection. Tries direct first, then via-aware routing."""
    start_is_tht, start_layer = start_info
    end_is_tht, end_layer = end_info
    
    start_layers = [F_CU, B_CU] if start_is_tht else [start_layer]
    end_layers = [F_CU, B_CU] if end_is_tht else [end_layer]
    
    # Try direct routing first
    segments, vias = route_direct(start, end, netcode, start_layers, end_layers, preferred)
    if segments is not None:
        return segments, vias
    
    # If either pad is SMD on F.Cu, try via-aware routing
    # (route on B.Cu with vias at each pad)
    if not start_is_tht or not end_is_tht:
        segments, vias = route_with_routing_vias(
            board, start, end, netcode, start_ref, end_ref, preferred)
        if segments is not None:
            return segments, vias
    
    # Try one-sided via: if start is THT (can connect on B.Cu) and end is SMD (F.Cu only)
    if start_is_tht and not end_is_tht:
        # Route on B.Cu from start to a via near end, then F.Cu stub
        via_pos = try_via_offsets(end, end_ref, netcode)
        if via_pos:
            for pattern in ['HV', 'VH']:
                mid = (via_pos[0], start[1]) if pattern == 'HV' else (start[0], via_pos[1])
                segs = []
                if start != mid:
                    segs.append((B_CU, start, mid))
                if mid != via_pos:
                    segs.append((B_CU, mid, via_pos))
                if via_pos != end:
                    segs.append((F_CU, via_pos, end))
                collisions = sum(count_collisions(l, a, b, netcode) for l, a, b in segs)
                if collisions == 0 and via_at_pos_ok(via_pos, netcode):
                    return segs, [via_pos]
    
    # Try one-sided via: start is SMD, end is THT
    if not start_is_tht and end_is_tht:
        via_pos = try_via_offsets(start, start_ref, netcode)
        if via_pos:
            for pattern in ['HV', 'VH']:
                mid = (end[0], via_pos[1]) if pattern == 'HV' else (via_pos[0], end[1])
                segs = []
                if start != via_pos:
                    segs.append((F_CU, start, via_pos))
                if via_pos != mid:
                    segs.append((B_CU, via_pos, mid))
                if mid != end:
                    segs.append((B_CU, mid, end))
                collisions = sum(count_collisions(l, a, b, netcode) for l, a, b in segs)
                if collisions == 0 and via_at_pos_ok(via_pos, netcode):
                    return segs, [via_pos]
    
    return None, None

def route_net(board, netname, pad_list, pad_details, pad_refs, preferred='HV'):
    """Route all pads in a net using nearest-neighbor chain."""
    if len(pad_list) < 2:
        return 0, 0, 0

    remaining = list(pad_list)
    order = [remaining.pop(0)]
    while remaining:
        last = order[-1]
        nearest = min(remaining, key=lambda p: (p[0]-last[0])**2 + (p[1]-last[1])**2)
        order.append(nearest)
        remaining.remove(nearest)

    total_tracks = 0
    total_vias = 0
    total_failed = 0

    for i in range(len(order)-1):
        start = (order[i][0], order[i][1])
        end = (order[i+1][0], order[i+1][1])
        netcode = order[i][2]

        s_info = pad_details.get(start, (True, F_CU))
        e_info = pad_details.get(end, (True, F_CU))
        s_ref = pad_refs.get(start, '')
        e_ref = pad_refs.get(end, '')

        segments, vias = route_connection(board, start, end, netcode,
                                           s_info, e_info, s_ref, e_ref, preferred)
        if segments is None:
            print(f'    SKIP: {netname} {start}->{end} (no collision-free route)')
            total_failed += 1
            continue

        commit_route(board, segments, vias, netcode)
        total_tracks += len(segments)
        total_vias += len(vias)

    return total_tracks, total_vias, total_failed

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print('=== 4-Layer Conversion + Re-Route (Iteration 3) ===')
    print('Fixes: bbox pad collision, THT via skip, layer distribution,')
    print('       0.5mm pad clearance, no collision fallback, thermal via spacing,')
    print('       via-aware routing (F.Cu stub -> via -> B.Cu -> via -> F.Cu stub)')
    board = pcbnew.LoadBoard(INPUT)
    print(f'Loaded: {INPUT}')
    print(f'Copper layers: {board.GetCopperLayerCount()}')

    # ── Step 1: Rip all tracks and zones ────────────────────────────────────
    print('\n--- Step 1: Rip all tracks and zones ---')
    tracks = list(board.GetTracks())
    for t in tracks:
        board.Remove(t)
    print(f'Removed {len(tracks)} tracks')
    zones = list(board.Zones())
    for z in zones:
        board.Remove(z)
    print(f'Removed {len(zones)} zones')

    # ── Step 2: Add power planes on inner layers ────────────────────────────
    print('\n--- Step 2: Add GND on In1.Cu, +3V3 on In2.Cu ---')
    bb = board.GetBoardEdgesBoundingBox()
    bx0, by0 = bb.GetX(), bb.GetY()
    bw,  bh  = bb.GetWidth(), bb.GetHeight()
    print(f'Board: ({bx0},{by0}) size ({bw},{bh})')

    def add_power_zone(board, netname, layer_id, layer_name):
        netcode = board.GetNetcodeFromNetname(netname)
        zone = pcbnew.ZONE(board)
        zone.SetLayer(layer_id)
        zone.SetNetCode(netcode)
        zone.SetAssignedPriority(0)
        margin = 100000
        corners = [
            pcbnew.VECTOR2I(bx0 + margin, by0 + margin),
            pcbnew.VECTOR2I(bx0 + bw - margin, by0 + margin),
            pcbnew.VECTOR2I(bx0 + bw - margin, by0 + bh - margin),
            pcbnew.VECTOR2I(bx0 + margin, by0 + bh - margin),
        ]
        for c in corners:
            zone.AppendCorner(c, -1)
        zone.SetFillMode(pcbnew.ZONE_FILL_MODE_POLYGONS)
        zone.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        zone.SetThermalReliefGap(250000)
        zone.SetThermalReliefSpokeWidth(500000)
        zone.SetMinThickness(200000)
        zone.SetIsFilled(False)
        zone.SetFillFlag(layer_id, True)
        zone.SetLocalClearance(220000)
        board.Add(zone)
        print(f'  {netname} zone on {layer_name} (net={netcode})')
        return zone

    add_power_zone(board, 'GND',  IN1, 'In1.Cu')
    add_power_zone(board, '+3V3', IN2, 'In2.Cu')

    # ── Step 3: Collect footprint info for via offset calculation ─────────────
    print('\n--- Step 3: Collect footprint info ---')
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        bb = fp.GetBoundingBox()
        footprint_info[ref] = (bb.GetX(), bb.GetY(), bb.GetX() + bb.GetWidth(), bb.GetY() + bb.GetHeight())
    print(f'  Footprints: {len(footprint_info)}')

    # ── Step 4: Thermal vias for SMD power pads only ──────────────────────────
    print('\n--- Step 4: Thermal vias for SMD power pads (skip THT, check spacing) ---')
    thermal_via_count = 0
    tht_skipped = 0
    spacing_skipped = 0
    power_pad_count = 0

    for fp in board.GetFootprints():
        for pad in fp.Pads():
            netname = pad.GetNetname()
            if netname not in POWER_NETS:
                continue
            power_pad_count += 1
            if is_pad_tht(pad):
                tht_skipped += 1
                continue
            pos = pad.GetPosition()
            netcode = pad.GetNetCode()
            via_pos = (pos.x, pos.y)
            if not via_at_pos_ok(via_pos, netcode):
                spacing_skipped += 1
                continue
            make_via(board, via_pos, netcode)
            routed_vias.append((pos.x, pos.y, netcode))
            thermal_via_count += 1

    print(f'  Power pads: {power_pad_count}, THT skipped: {tht_skipped}')
    print(f'  Spacing skipped: {spacing_skipped}, Thermal vias created: {thermal_via_count}')

    # ── Step 5: Collect pad info ──────────────────────────────────────────────
    print('\n--- Step 5: Collect pad info ---')
    signal_nets = {}
    pad_details = {}
    pad_refs = {}

    for fp in board.GetFootprints():
        ref = fp.GetReference()
        for pad in fp.Pads():
            netname = pad.GetNetname()
            if not netname:
                continue
            pos = pad.GetPosition()
            layer = pad.GetLayer()
            netcode = pad.GetNetCode()
            is_tht = is_pad_tht(pad)
            rxmin, rymin, rxmax, rymax = get_pad_bbox(pad)
            pad_info.append((rxmin, rymin, rxmax, rymax, is_tht, layer, netcode, netname, pos.x, pos.y))
            pad_key = (pos.x, pos.y)
            pad_details[pad_key] = (is_tht, layer)
            pad_refs[pad_key] = ref
            if netname not in POWER_NETS:
                if netname not in signal_nets:
                    signal_nets[netname] = []
                signal_nets[netname].append((pos.x, pos.y, netcode))

    print(f'  Total pads: {len(pad_info)}, THT: {sum(1 for p in pad_info if p[4])}')
    print(f'  Signal nets: {len(signal_nets)}')
    for n, pads in sorted(signal_nets.items()):
        print(f'    {n}: {len(pads)} pads')

    # ── Step 6: Route all signal nets ─────────────────────────────────────────
    print('\n--- Step 6: Route signal nets (via-aware layer distribution) ---')
    net_order = sorted(signal_nets.keys(), key=lambda n: len(signal_nets[n]))

    total_tracks = 0
    total_vias = 0
    total_failed = 0
    for idx, netname in enumerate(net_order):
        pads = signal_nets[netname]
        preferred = 'HV' if idx % 2 == 0 else 'VH'
        tracks, vias, failed = route_net(board, netname, pads, pad_details, pad_refs, preferred)
        total_tracks += tracks
        total_vias += vias
        total_failed += failed
        status = 'OK' if failed == 0 else f'{failed} FAILED'
        print(f'  {netname}: {tracks} tracks, {vias} vias ({status})')

    print(f'\nTotal: {total_tracks} signal tracks, {total_vias} signal vias, {thermal_via_count} thermal vias')
    print(f'Failed routes (unconnected): {total_failed}')

    # ── Step 7: Fill zones + save ─────────────────────────────────────────────
    print('\n--- Step 7: Fill zones + save ---')
    filler = pcbnew.ZONE_FILLER(board)
    fill_result = filler.Fill(board.Zones())
    print(f'Zone fill result: {fill_result}')
    pcbnew.SaveBoard(OUTPUT, board)
    print(f'Saved: {OUTPUT}')

    # ── Step 8: DRC ───────────────────────────────────────────────────────────
    print('\n--- Step 8: DRC ---')
    board2 = pcbnew.LoadBoard(OUTPUT)
    drc_report_path = '/tmp/drc_4layer_report.txt'
    result = pcbnew.WriteDRCReport(board2, drc_report_path, 0, True)
    print(f'WriteDRCReport: {result}')

    tracks_crossing = 0
    unconnected_items = 0
    shorting_items = 0
    solder_mask_bridge = 0
    holes_co_located = 0
    clearance_violations = 0
    hole_clearance_violations = 0
    other_errors = 0

    if os.path.exists(drc_report_path):
        with open(drc_report_path) as f:
            report = f.read()
        for line in report.split('\n'):
            ll = line.lower().strip()
            if ll.startswith('[tracks_crossing]'):
                tracks_crossing += 1
            elif ll.startswith('[unconnected_items]') or ll.startswith('[unrouted_items]'):
                unconnected_items += 1
            elif ll.startswith('[shorting_items]'):
                shorting_items += 1
            elif ll.startswith('[solder_mask_bridge]'):
                solder_mask_bridge += 1
            elif ll.startswith('[holes_co_located]'):
                holes_co_located += 1
            elif ll.startswith('[clearance]') and 'hole' not in ll:
                clearance_violations += 1
            elif ll.startswith('[hole_clearance]'):
                hole_clearance_violations += 1
            elif ll.startswith('[') and 'error' in ll:
                if not any(x in ll for x in ['silk', 'courtyard', 'edge_clearance', 'silk_over',
                                             'tracks_crossing', 'unconnected', 'unrouted',
                                             'shorting', 'solder_mask', 'holes_co',
                                             'clearance', 'hole_clearance', 'via_dangling',
                                             'track_dangling']):
                    other_errors += 1
        print(f'\n=== DRC Summary (Iteration 3) ===')
        print(f'  tracks_crossing:          {tracks_crossing}')
        print(f'  unconnected_items:        {unconnected_items}')
        print(f'  shorting_items:           {shorting_items}')
        print(f'  solder_mask_bridge:       {solder_mask_bridge}')
        print(f'  holes_co_located:         {holes_co_located}')
        print(f'  clearance violations:     {clearance_violations}')
        print(f'  hole_clearance violations: {hole_clearance_violations}')
        print(f'  other errors:             {other_errors}')
        print(f'\nFull report: {drc_report_path}')
    else:
        print('DRC report not generated!')

    if os.path.exists(OUTPUT):
        sz = os.path.getsize(OUTPUT)
        print(f'\nOutput: {OUTPUT} ({sz} bytes)')
    else:
        print(f'\nERROR: Output file not created!')
    print('\n=== Done ===')

if __name__ == '__main__':
    main()