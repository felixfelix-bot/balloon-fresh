#!/usr/bin/python3.14
"""4-Layer PCB routing script (v3) for balloon tracker board.

Improvements over v2:
  - Per-segment via hopping: try_route_offset_mixed does 3-segment offset
    routing where EACH segment independently picks F.Cu or B.Cu (2^3 = 8 combos
    per offset value).  Vias placed at every layer transition.  This lets a
    net hop layers mid-route to dodge obstacles that block single-layer offset.
  - Pass 5 in route_connection: tries all offset × layer-combination combos.
  - Pass 6 (relaxed): if still unrouted after all strategies, accepts the
    minimum-collision route from any earlier pass (collision-tolerated).

Inherited from v2:
  - Liang-Barsky segment-rectangle intersection for accurate pad collision detection
  - Pad bbox from GetPosition() + GetSize() with proper rotation handling
  - Layer distribution: try BOTH F.Cu and B.Cu per net, pick the one with fewer collisions
  - Manhattan routing only (H-V or V-H), no diagonal fallback
  - Cleaner structure, better DRC summary
"""
import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew
import math
import os
import itertools

# ─── Paths ────────────────────────────────────────────────────────────────────
INPUT  = '/home/c03rad0r/repos/balloon-fresh/tracker/hardware/output/v_c3_flight_final.kicad_pcb'
OUTPUT = '/home/c03rad0r/repos/balloon-fresh/tracker/hardware/output/v_c3_flight_4layer_routed_v3.kicad_pcb'

# ─── Constants (all in nm) ─────────────────────────────────────────────────────
TRACK_WIDTH   = 250000   # 0.25mm
TRACK_CLEAR   = 220000   # 0.22mm track-to-track
PAD_CLEAR     = 500000   # 0.50mm pad-to-track
VIA_WIDTH     = 550000   # 0.55mm
VIA_DRILL     = 300000   # 0.30mm
VIA_RADIUS    = VIA_WIDTH // 2   # 275000nm
VIA_SPACING   = 800000   # 0.8mm min center-to-center (different nets)
ZONE_MARGIN   = 100000   # 0.1mm board edge margin for pours

# Layer constants
F_CU  = pcbnew.F_Cu     # 0
B_CU  = pcbnew.B_Cu     # 31 (or 2 depending on version)
IN1   = pcbnew.In1_Cu   # inner layer 1
IN2   = pcbnew.In2_Cu   # inner layer 2

POWER_NETS = {'+3V3', 'GND', 'VCAP', 'SOLAR_IN', 'EN'}

# ─── Geometry helpers ──────────────────────────────────────────────────────────

def dist2d(p1, p2):
    """Euclidean distance between two (x, y) tuples."""
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


def point_seg_dist(px, py, x1, y1, x2, y2):
    """Minimum distance from point (px, py) to segment (x1,y1)-(x2,y2)."""
    dx, dy = x2 - x1, y2 - y1
    l2 = dx * dx + dy * dy
    if l2 == 0:
        return math.sqrt((px - x1) ** 2 + (py - y1) ** 2)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / l2))
    cx = x1 + t * dx
    cy = y1 + t * dy
    return math.sqrt((px - cx) ** 2 + (py - cy) ** 2)


def ccw(A, B, C):
    """Cross product of AB x AC. >0 = counterclockwise, <0 = clockwise, 0 = colinear."""
    return (C[1] - A[1]) * (B[0] - A[0]) - (B[1] - A[1]) * (C[0] - A[0])


def seg_cross(p1, p2, p3, p4):
    """True if segments p1p2 and p3p4 properly cross."""
    d1 = ccw(p3, p4, p1)
    d2 = ccw(p3, p4, p2)
    d3 = ccw(p1, p2, p3)
    d4 = ccw(p1, p2, p4)
    return ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and \
           ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0))


def seg_collides(s1a, s1b, s2a, s2b, clearance):
    """True if segments are closer than `clearance` (including crossing and endpoint proximity)."""
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
    """True if two colinear segments overlap."""
    dx1 = s1b[0] - s1a[0]; dy1 = s1b[1] - s1a[1]
    dx2 = s2b[0] - s2a[0]; dy2 = s2b[1] - s2a[1]
    cross = dx1 * dy2 - dy1 * dx2
    if abs(cross) > 0:
        return False
    # Check colinearity
    cross2 = (s2a[0] - s1a[0]) * dy1 - (s2a[1] - s1a[1]) * dx1
    if abs(cross2) > 0:
        return False
    lo_x = max(min(s1a[0], s1b[0]), min(s2a[0], s2b[0]))
    hi_x = min(max(s1a[0], s1b[0]), max(s2a[0], s2b[0]))
    lo_y = max(min(s1a[1], s1b[1]), min(s2a[1], s2b[1]))
    hi_y = min(max(s1a[1], s1b[1]), max(s2a[1], s2b[1]))
    return (hi_x - lo_x >= 0) and (hi_y - lo_y >= 0)


def segments_share_endpoint(s1a, s1b, s2a, s2b):
    """True if any endpoint is shared between the two segments."""
    return any(p == q for p in (s1a, s1b) for q in (s2a, s2b))


def liang_barsky(x1, y1, x2, y2, xmin, ymin, xmax, ymax):
    """Liang-Barsky line clipping algorithm.
    Returns True if the segment (x1,y1)-(x2,y2) intersects the rectangle [xmin,ymin,xmax,ymax].
    """
    dx = x2 - x1
    dy = y2 - y1
    p = [-dx, dx, -dy, dy]
    q = [x1 - xmin, xmax - x1, y1 - ymin, ymax - y1]
    u1 = 0.0
    u2 = 1.0
    for i in range(4):
        if p[i] == 0:
            # Segment is parallel to this boundary
            if q[i] < 0:
                return False  # Outside this boundary
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


# ─── Board state (global, reset at start) ───────────────────────────────────────

# Each entry: (rxmin, rymin, rxmax, rymax, is_tht, pad_layer, netcode, netname)
pad_info = []

# Routed segments: (layer, (sx, sy), (ex, ey), netcode) — use list, NOT set (PCB_TRACK unhashable)
routed_segments = []

# Routed vias: (x, y, netcode)
routed_vias = []


# ─── Pad inspection ────────────────────────────────────────────────────────────

def is_pad_tht(pad):
    """Determine if a pad is a through-hole pad (THT).
    Checks pad.GetAttribute() first, then falls back to drill size.
    THT pads already connect through all layers — no thermal via needed.
    """
    try:
        attr = pad.GetAttribute()
        # KiCad 7/8: PAD_ATTRIB_THT
        if hasattr(pcbnew, 'PAD_ATTRIB_THT') and attr == pcbnew.PAD_ATTRIB_THT:
            return True
        if hasattr(pcbnew, 'PAD_ATTRIB_PTH') and attr == pcbnew.PAD_ATTRIB_PTH:
            return True
        # SMD and NPTH attributes
        if hasattr(pcbnew, 'PAD_ATTRIB_SMD') and attr == pcbnew.PAD_ATTRIB_SMD:
            return False
        if hasattr(pcbnew, 'PAD_ATTRIB_NPTH') and attr == pcbnew.PAD_ATTRIB_NPTH:
            return False
    except Exception:
        pass
    # Fallback: check drill size
    try:
        drill = pad.GetDrillSize()
        if drill.x > 0 and drill.y > 0:
            return True
    except Exception:
        pass
    return False


def get_pad_bbox(pad):
    """Get pad bounding box from GetPosition() + GetSize().
    Returns (rxmin, rymin, rxmax, rymax) in nm.
    Handles round pads by using the size as the bounding dimension.
    """
    pos = pad.GetPosition()
    size = pad.GetSize()
    rxmin = pos.x - size.x // 2
    rymin = pos.y - size.y // 2
    rxmax = pos.x + size.x // 2
    rymax = pos.y + size.y // 2
    return rxmin, rymin, rxmax, rymax


# ─── Collision checking ─────────────────────────────────────────────────────────

def count_pad_collisions(layer, seg_a, seg_b, netcode):
    """Count collisions between a segment and all pads (expanded by PAD_CLEARANCE).
    Uses Liang-Barsky segment-rectangle intersection.
    SMD pads only checked on their own layer; THT pads checked on all layers.
    """
    count = 0
    for rxmin, rymin, rxmax, rymax, is_tht, pad_layer, pad_net, _ in pad_info:
        if pad_net == netcode:
            continue  # Same net — no collision
        if not is_tht and pad_layer != layer:
            continue  # SMD pad on different layer — skip
        # Expand pad box by PAD_CLEARANCE
        if liang_barsky(seg_a[0], seg_a[1], seg_b[0], seg_b[1],
                        rxmin - PAD_CLEAR, rymin - PAD_CLEAR,
                        rxmax + PAD_CLEAR, rymax + PAD_CLEAR):
            count += 1
    return count


def count_via_collisions(layer, seg_a, seg_b, netcode):
    """Count collisions between a segment and existing vias (different nets)."""
    count = 0
    for vx, vy, via_net in routed_vias:
        if via_net == netcode:
            continue
        d = point_seg_dist(vx, vy, seg_a[0], seg_a[1], seg_b[0], seg_b[1])
        if d < TRACK_CLEAR + VIA_RADIUS:
            count += 1
    return count


def count_track_collisions(layer, seg_a, seg_b, netcode):
    """Count collisions between a segment and existing routed tracks (same layer, different net)."""
    count = 0
    for r_layer, r_a, r_b, r_net in routed_segments:
        if r_layer != layer:
            continue
        if r_net == netcode:
            continue
        # Skip shared endpoints (they connect at the same point)
        if segments_share_endpoint(seg_a, seg_b, r_a, r_b):
            if not colinear_overlap(seg_a, seg_b, r_a, r_b):
                continue
        if seg_collides(seg_a, seg_b, r_a, r_b, TRACK_CLEAR):
            count += 1
        elif colinear_overlap(seg_a, seg_b, r_a, r_b):
            count += 1
    return count


def count_all_collisions(layer, seg_a, seg_b, netcode):
    """Total collision count for a segment on a given layer."""
    return (count_pad_collisions(layer, seg_a, seg_b, netcode) +
            count_via_collisions(layer, seg_a, seg_b, netcode) +
            count_track_collisions(layer, seg_a, seg_b, netcode))


def has_collision(layer, seg_a, seg_b, netcode):
    """Quick boolean check — returns True if any collision exists."""
    return count_all_collisions(layer, seg_a, seg_b, netcode) > 0


def via_at_pos_ok(pos, netcode):
    """Check if a via at the given position is OK (no collision with other vias/pads)."""
    px, py = pos
    for vx, vy, vnet in routed_vias:
        d = dist2d((px, py), (vx, vy))
        if vnet == netcode:
            if d < 100000:  # 0.1mm — same net vias can be close
                return False
        else:
            if d < VIA_SPACING:
                return False
    # Check pad collisions
    for rxmin, rymin, rxmax, rymax, is_tht, pad_layer, pad_net, _ in pad_info:
        if pad_net == netcode:
            continue
        if (rxmin - TRACK_CLEAR <= px <= rxmax + TRACK_CLEAR and
            rymin - TRACK_CLEAR <= py <= rymax + TRACK_CLEAR):
            return False
    return True


# ─── Track/Via creation ────────────────────────────────────────────────────────

def make_track(board, layer, start, end, netcode):
    """Create and add a PCB track to the board."""
    t = pcbnew.PCB_TRACK(board)
    t.SetLayer(layer)
    t.SetWidth(TRACK_WIDTH)
    t.SetStart(pcbnew.VECTOR2I(int(start[0]), int(start[1])))
    t.SetEnd(pcbnew.VECTOR2I(int(end[0]), int(end[1])))
    t.SetNetCode(netcode)
    board.Add(t)
    return t


def make_via(board, pos, netcode):
    """Create and add a through-hole via to the board."""
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
    """Add segments and vias to the board and register them for collision tracking."""
    for layer, start, end in segments:
        make_track(board, layer, start, end, netcode)
        routed_segments.append((layer, start, end, netcode))
    for via_pos in vias:
        make_via(board, via_pos, netcode)
        routed_vias.append((via_pos[0], via_pos[1], netcode))


# ─── Routing engine ────────────────────────────────────────────────────────────

def gen_manhattan_segments(start, end, pattern):
    """Generate Manhattan routing segments.
    pattern='HV': horizontal first (start → (ex, sy) → end)
    pattern='VH': vertical first (start → (sx, ey) → end)
    Returns list of ((sx, sy), (ex, ey)) tuples.
    """
    sx, sy = start
    ex, ey = end
    if pattern == 'HV':
        mid = (ex, sy)
    else:
        mid = (sx, ey)
    segs = []
    if (sx, sy) != mid:
        segs.append(((sx, sy), mid))
    if mid != (ex, ey):
        segs.append((mid, (ex, ey)))
    return segs


def try_route_layer(layer, start, end, netcode, start_layers, end_layers, pattern):
    """Try to route on a single layer with given Manhattan pattern.
    Returns (segments, vias, collision_count) or (None, None, large) if infeasible.
    """
    sx, sy = start
    ex, ey = end
    if (sx, sy) == (ex, ey):
        return [], [], 0

    mid = (ex, sy) if pattern == 'HV' else (sx, ey)
    raw_segs = []
    if (sx, sy) != mid:
        raw_segs.append((layer, (sx, sy), mid))
    if mid != (ex, ey):
        raw_segs.append((layer, mid, (ex, ey)))

    # Determine if we need endpoint vias (pad is on a different layer)
    endpoint_vias = []
    if layer not in start_layers:
        endpoint_vias.append((sx, sy))
    if layer not in end_layers:
        endpoint_vias.append((ex, ey))

    # Check via positions
    for v in endpoint_vias:
        if not via_at_pos_ok(v, netcode):
            return None, None, 999999

    # Count collisions on all segments
    total_collisions = 0
    for _, sa, sb in raw_segs:
        total_collisions += count_all_collisions(layer, sa, sb, netcode)

    return raw_segs, endpoint_vias, total_collisions


def try_route_mixed_layer(start, end, netcode, start_layers, end_layers, pattern):
    """Try mixed-layer routing: one layer for first segment, via at corner, other layer for second.
    Returns (segments, vias, collision_count) or (None, None, large).
    """
    sx, sy = start
    ex, ey = end
    if (sx, sy) == (ex, ey):
        return [], [], 0

    mid = (ex, sy) if pattern == 'HV' else (sx, ey)
    if (sx, sy) == mid or mid == (ex, ey):
        return None, None, 999999  # Degenerate — would be single layer

    best = None
    best_collisions = 999999

    for l1, l2 in [(F_CU, B_CU), (B_CU, F_CU)]:
        if l1 not in start_layers or l2 not in end_layers:
            continue
        # Via at corner point
        if not via_at_pos_ok(mid, netcode):
            continue
        c1 = count_all_collisions(l1, (sx, sy), mid, netcode)
        c2 = count_all_collisions(l2, mid, (ex, ey), netcode)
        total = c1 + c2
        if total < best_collisions:
            segs = [(l1, (sx, sy), mid), (l2, mid, (ex, ey))]
            best = (segs, [mid], total)
            best_collisions = total

    if best:
        return best
    return None, None, 999999


def try_route_offset(layer, start, end, netcode, start_layers, end_layers, pattern):
    """Try routing with an offset to avoid obstacles (3-segment Manhattan).
    Returns (segments, vias, collision_count) or (None, None, large).
    """
    sx, sy = start
    ex, ey = end
    if (sx, sy) == (ex, ey):
        return [], [], 0

    best = None
    best_collisions = 999999

    for offset in (1500000, 2500000, 3500000, -1500000, -2500000, -3500000, 4500000, -4500000):
        if pattern == 'HV':
            mid1 = (ex, sy + offset)
            mid2 = (ex, ey)
        else:
            mid1 = (sx + offset, ey)
            mid2 = (sx, ey)

        # Check if any segment is degenerate
        segs = []
        if (sx, sy) != mid1:
            segs.append((layer, (sx, sy), mid1))
        if mid1 != mid2:
            segs.append((layer, mid1, mid2))
        if mid2 != (ex, ey):
            segs.append((layer, mid2, (ex, ey)))

        if not segs:
            continue

        endpoint_vias = []
        if layer not in start_layers:
            endpoint_vias.append((sx, sy))
        if layer not in end_layers:
            endpoint_vias.append((ex, ey))

        via_ok = all(via_at_pos_ok(v, netcode) for v in endpoint_vias)
        if not via_ok:
            continue

        total = sum(count_all_collisions(layer, sa, sb, netcode) for _, sa, sb in segs)
        if total < best_collisions:
            best = (segs, endpoint_vias, total)
            best_collisions = total

    return best if best else (None, None, 999999)


def try_route_offset_mixed(start, end, netcode, start_layers, end_layers, pattern):
    """Try 3-segment Manhattan offset routing with PER-SEGMENT layer choice.

    Each of the 3 segments independently picks F.Cu or B.Cu (2^n combos,
    where n is the number of non-degenerate segments).  Vias are placed at
    every layer transition between consecutive segments.

    Returns (segments, vias, collision_count) or (None, None, 999999).
    """
    sx, sy = start
    ex, ey = end
    if (sx, sy) == (ex, ey):
        return [], [], 0

    best = None
    best_collisions = 999999

    for offset in (1500000, 2500000, 3500000, -1500000, -2500000, -3500000, 4500000, -4500000):
        # Same geometry as try_route_offset
        if pattern == 'HV':
            mid1 = (ex, sy + offset)
            mid2 = (ex, ey)
        else:
            mid1 = (sx + offset, ey)
            mid2 = (sx, ey)

        # Build raw segment endpoints (filter degenerate zero-length segments)
        raw_points = [(sx, sy), mid1, mid2, (ex, ey)]
        raw_segs = []
        for i in range(3):
            a = raw_points[i]
            b = raw_points[i + 1]
            if a != b:
                raw_segs.append((a, b))

        if not raw_segs:
            continue

        num_segs = len(raw_segs)

        # Try every viable layer combination (each segment independently F.Cu/B.Cu)
        for combo in itertools.product((F_CU, B_CU), repeat=num_segs):
            # Respect endpoint layer constraints
            if combo[0] not in start_layers:
                continue
            if combo[-1] not in end_layers:
                continue

            # Determine via positions at layer transitions between consecutive segments
            via_positions = []
            for i in range(num_segs - 1):
                if combo[i] != combo[i + 1]:
                    via_positions.append(raw_segs[i][1])  # shared endpoint = transition point

            # Check all via positions are valid
            via_ok = all(via_at_pos_ok(v, netcode) for v in via_positions)
            if not via_ok:
                continue

            # Count collisions across all segments on their respective layers
            total = 0
            for i in range(num_segs):
                total += count_all_collisions(combo[i], raw_segs[i][0], raw_segs[i][1], netcode)

            if total < best_collisions:
                segs = [(combo[i], raw_segs[i][0], raw_segs[i][1]) for i in range(num_segs)]
                best = (segs, list(via_positions), total)
                best_collisions = total

    if best:
        return best
    return None, None, 999999


def route_connection(board, start, end, netcode, start_is_tht, end_is_tht,
                     start_layer, end_layer, preferred='HV'):
    """Route a single connection with layer distribution.
    Tries BOTH F.Cu and B.Cu, picks the layer with fewer collisions.

    Returns (segments, vias) or (None, None) if no collision-free route found.
    """
    sx, sy = start
    ex, ey = end
    if (sx, sy) == (ex, ey):
        return [], []

    # Determine available layers per endpoint
    start_layers = [F_CU, B_CU] if start_is_tht else [start_layer]
    end_layers = [F_CU, B_CU] if end_is_tht else [end_layer]

    patterns = [preferred, 'VH' if preferred == 'HV' else 'HV']

    # ── Pass 1: Single-layer Manhattan (both patterns, both layers) ──
    best = None
    best_collisions = 999999

    for pattern in patterns:
        for layer in (F_CU, B_CU):
            segs, vias, collisions = try_route_layer(
                layer, (sx, sy), (ex, ey), netcode, start_layers, end_layers, pattern)
            if segs is None:
                continue
            if collisions == 0:
                return segs, vias
            if collisions < best_collisions:
                best = (segs, vias)
                best_collisions = collisions

    # ── Pass 2: Mixed-layer (via at Manhattan corner) ──
    for pattern in patterns:
        segs, vias, collisions = try_route_mixed_layer(
            (sx, sy), (ex, ey), netcode, start_layers, end_layers, pattern)
        if segs is None:
            continue
        if collisions == 0:
            return segs, vias
        if collisions < best_collisions:
            best = (segs, vias)
            best_collisions = collisions

    # ── Pass 3: Offset routing on each layer ──
    for pattern in patterns:
        for layer in (F_CU, B_CU):
            segs, vias, collisions = try_route_offset(
                layer, (sx, sy), (ex, ey), netcode, start_layers, end_layers, pattern)
            if segs is None:
                continue
            if collisions == 0:
                return segs, vias
            if collisions < best_collisions:
                best = (segs, vias)
                best_collisions = collisions

    # ── Pass 4: Mixed-layer offset (3-segment with via at transition) ──
    for pattern in patterns:
        mid_corner = (ex, sy) if pattern == 'HV' else (sx, ey)
        for offset in (1500000, 2500000, -1500000, -2500000, 3500000, -3500000):
            if pattern == 'HV':
                mid1 = (ex, sy + offset)
            else:
                mid1 = (sx + offset, ey)
            mid2 = mid_corner

            if (sx, sy) == mid1 or mid1 == mid2 or mid2 == (ex, ey):
                continue

            for l1, l2 in [(F_CU, B_CU), (B_CU, F_CU)]:
                if l1 not in start_layers or l2 not in end_layers:
                    continue
                if not via_at_pos_ok(mid2, netcode):
                    continue
                c1 = count_all_collisions(l1, (sx, sy), mid1, netcode)
                c2 = count_all_collisions(l1, mid1, mid2, netcode)
                c3 = count_all_collisions(l2, mid2, (ex, ey), netcode)
                total = c1 + c2 + c3
                if total == 0:
                    segs = [(l1, (sx, sy), mid1), (l1, mid1, mid2), (l2, mid2, (ex, ey))]
                    return segs, [mid2]
                if total < best_collisions:
                    segs = [(l1, (sx, sy), mid1), (l1, mid1, mid2), (l2, mid2, (ex, ey))]
                    best = (segs, [mid2])
                    best_collisions = total

    # ── Pass 5: Per-segment via hopping (3-segment offset, independent layer per segment) ──
    for pattern in patterns:
        segs, vias, collisions = try_route_offset_mixed(
            (sx, sy), (ex, ey), netcode, start_layers, end_layers, pattern)
        if segs is None:
            continue
        if collisions == 0:
            return segs, vias
        if collisions < best_collisions:
            best = (segs, vias)
            best_collisions = collisions

    # ── Pass 6: Relaxed routing — accept minimum-collision route from any strategy ──
    # If we still haven't found a collision-free path, accept the least-bad option
    # rather than leaving the net unrouted.  These are logged as collision-tolerated.
    if best is not None and best_collisions < 999999:
        print(f'    COLLISION-TOLERATED: net={netcode} {start}->{end} '
              f'({best_collisions} collisions accepted)')
        return best

    # No route found at all
    return None, None


def route_net(board, netname, pad_list, pad_details, preferred='HV'):
    """Route all pads in a net using nearest-neighbor chain.
    pad_list: list of (x, y, netcode)
    pad_details: dict mapping (x, y) -> (is_tht, layer)
    Returns (track_count, via_count, fail_count).
    """
    if len(pad_list) < 2:
        return 0, 0, 0

    # Nearest-neighbor ordering
    remaining = list(pad_list)
    order = [remaining.pop(0)]
    while remaining:
        last = order[-1]
        nearest = min(remaining, key=lambda p: (p[0] - last[0]) ** 2 + (p[1] - last[1]) ** 2)
        order.append(nearest)
        remaining.remove(nearest)

    total_tracks = 0
    total_vias = 0
    total_failed = 0

    for i in range(len(order) - 1):
        start = (order[i][0], order[i][1])
        end = (order[i + 1][0], order[i + 1][1])
        netcode = order[i][2]

        s_info = pad_details.get(start, (True, F_CU))
        e_info = pad_details.get(end, (True, F_CU))
        s_is_tht, s_layer = s_info
        e_is_tht, e_layer = e_info

        segments, vias = route_connection(
            board, start, end, netcode, s_is_tht, e_is_tht, s_layer, e_layer, preferred)

        if segments is None:
            print(f'    SKIP: {netname} {start}->{end} (no collision-free route)')
            total_failed += 1
            continue

        commit_route(board, segments, vias, netcode)
        total_tracks += len(segments)
        total_vias += len(vias)

    return total_tracks, total_vias, total_failed


# ─── Zone creation ─────────────────────────────────────────────────────────────

def add_power_zone(board, netname, layer_id, layer_name, bx0, by0, bw, bh):
    """Add a copper pour zone on the specified layer for the specified net.
    Full board area with ZONE_MARGIN inset.
    """
    netcode = board.GetNetcodeFromNetname(netname)
    if netcode < 0:
        print(f'  WARNING: Net "{netname}" not found in board (netcode={netcode}), skipping zone')
        return None

    zone = pcbnew.ZONE(board)
    zone.SetLayer(layer_id)
    zone.SetNetCode(netcode)
    zone.SetAssignedPriority(0)

    corners = [
        pcbnew.VECTOR2I(bx0 + ZONE_MARGIN, by0 + ZONE_MARGIN),
        pcbnew.VECTOR2I(bx0 + bw - ZONE_MARGIN, by0 + ZONE_MARGIN),
        pcbnew.VECTOR2I(bx0 + bw - ZONE_MARGIN, by0 + bh - ZONE_MARGIN),
        pcbnew.VECTOR2I(bx0 + ZONE_MARGIN, by0 + bh - ZONE_MARGIN),
    ]
    for c in corners:
        zone.AppendCorner(c, -1)

    zone.SetFillMode(pcbnew.ZONE_FILL_MODE_POLYGONS)
    zone.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    zone.SetThermalReliefGap(250000)      # 0.25mm
    zone.SetThermalReliefSpokeWidth(500000)  # 0.50mm
    zone.SetMinThickness(200000)            # 0.20mm
    zone.SetIsFilled(False)
    try:
        zone.SetFillFlag(layer_id, True)
    except Exception:
        pass  # Some KiCad versions don't have SetFillFlag
    zone.SetLocalClearance(220000)          # 0.22mm
    board.Add(zone)
    print(f'  {netname} pour on {layer_name} (net={netcode})')
    return zone


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    print('=' * 72)
    print('4-Layer PCB Routing Script v3')
    print('Improvements: per-segment via hopping, relaxed collision-tolerated routing')
    print('=' * 72)

    # ── Step 1: Load board ─────────────────────────────────────────────────────
    board = pcbnew.LoadBoard(INPUT)
    print(f'\n[1] Loaded: {INPUT}')
    print(f'    Copper layers: {board.GetCopperLayerCount()}')

    # Reset global state
    global pad_info, routed_segments, routed_vias
    pad_info = []
    routed_segments = []
    routed_vias = []

    # ── Step 2: Rip all tracks and zones ────────────────────────────────────────
    print('\n[2] Ripping all existing tracks and zones')
    tracks = list(board.GetTracks())
    for t in tracks:
        board.Remove(t)
    print(f'    Removed {len(tracks)} tracks')

    zones = list(board.Zones())
    for z in zones:
        board.Remove(z)
    print(f'    Removed {len(zones)} zones')

    # ── Step 3: Add GND pour on In1.Cu, +3V3 pour on In2.Cu ──────────────────────
    print('\n[3] Adding power plane copper pours')
    bb = board.GetBoardEdgesBoundingBox()
    bx0, by0 = bb.GetX(), bb.GetY()
    bw, bh = bb.GetWidth(), bb.GetHeight()
    print(f'    Board bbox: ({bx0},{by0}) size ({bw},{bh}) = ({bw/1e6:.1f}x{bh/1e6:.1f}mm)')

    add_power_zone(board, 'GND',  IN1, 'In1.Cu', bx0, by0, bw, bh)
    add_power_zone(board, '+3V3', IN2, 'In2.Cu', bx0, by0, bw, bh)

    # ── Step 4: Thermal vias for SMD power pads only ───────────────────────────
    print('\n[4] Adding thermal vias at SMD power pads (skip THT)')
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
                continue  # THT pads already connect through all layers

            pos = pad.GetPosition()
            netcode = pad.GetNetCode()
            via_pos = (pos.x, pos.y)

            if not via_at_pos_ok(via_pos, netcode):
                spacing_skipped += 1
                continue

            make_via(board, via_pos, netcode)
            routed_vias.append((pos.x, pos.y, netcode))
            thermal_via_count += 1

    print(f'    Power pads found:       {power_pad_count}')
    print(f'    THT pads skipped:        {tht_skipped}')
    print(f'    Spacing conflicts skip:  {spacing_skipped}')
    print(f'    Thermal vias created:    {thermal_via_count}')

    # ── Step 5: Collect pad info for routing ─────────────────────────────────────
    print('\n[5] Collecting pad information')
    signal_nets = {}   # netname -> [(x, y, netcode), ...]
    pad_details = {}   # (x, y) -> (is_tht, layer)

    for fp in board.GetFootprints():
        for pad in fp.Pads():
            netname = pad.GetNetname()
            if not netname:
                continue
            pos = pad.GetPosition()
            layer = pad.GetLayer()
            netcode = pad.GetNetCode()
            is_tht = is_pad_tht(pad)
            rxmin, rymin, rxmax, rymax = get_pad_bbox(pad)

            pad_info.append((rxmin, rymin, rxmax, rymax, is_tht, layer, netcode, netname))

            pad_key = (pos.x, pos.y)
            pad_details[pad_key] = (is_tht, layer)

            if netname not in POWER_NETS:
                if netname not in signal_nets:
                    signal_nets[netname] = []
                signal_nets[netname].append((pos.x, pos.y, netcode))

    total_pads = len(pad_info)
    tht_pads = sum(1 for p in pad_info if p[4])
    print(f'    Total pads:              {total_pads}')
    print(f'    THT pads:                {tht_pads}')
    print(f'    SMD pads:                {total_pads - tht_pads}')
    print(f'    Signal nets to route:    {len(signal_nets)}')

    # ── Step 6: Route all signal nets ───────────────────────────────────────────
    print('\n[6] Routing signal nets (layer distribution: F.Cu vs B.Cu)')
    # Route shortest nets first (fewer pads = less complexity)
    net_order = sorted(signal_nets.keys(), key=lambda n: len(signal_nets[n]))

    grand_tracks = 0
    grand_vias = 0
    grand_failed = 0

    for idx, netname in enumerate(net_order):
        pads = signal_nets[netname]
        # Alternate preferred pattern per net for diversity
        preferred = 'HV' if idx % 2 == 0 else 'VH'
        tracks, vias, failed = route_net(board, netname, pads, pad_details, preferred)
        grand_tracks += tracks
        grand_vias += vias
        grand_failed += failed
        status = 'OK' if failed == 0 else f'{failed} FAILED'
        print(f'    {netname:30s}: {tracks:3d} tracks, {vias:2d} vias ({status})')

    print(f'\n    ─── Routing Summary ───')
    print(f'    Signal tracks created:   {grand_tracks}')
    print(f'    Signal vias created:     {grand_vias}')
    print(f'    Thermal vias created:    {thermal_via_count}')
    print(f'    Failed routes:           {grand_failed}')

    # ── Step 7: Fill zones and save ─────────────────────────────────────────────
    print('\n[7] Filling zones and saving board')
    filler = pcbnew.ZONE_FILLER(board)
    try:
        fill_result = filler.Fill(board.Zones())
        print(f'    Zone fill result: {fill_result}')
    except Exception as e:
        print(f'    Zone fill error: {e}')
        # Try alternative fill method
        try:
            for zone in board.Zones():
                zone.SetIsFilled(True)
            print(f'    Zones marked as filled (fallback)')
        except Exception as e2:
            print(f'    Fallback fill also failed: {e2}')

    pcbnew.SaveBoard(OUTPUT, board)
    print(f'    Saved: {OUTPUT}')

    if os.path.exists(OUTPUT):
        sz = os.path.getsize(OUTPUT)
        print(f'    File size: {sz:,} bytes ({sz/1024:.1f} KB)')
    else:
        print(f'    ERROR: Output file was not created!')

    # ── Step 8: DRC report ──────────────────────────────────────────────────────
    print('\n[8] Running DRC')
    drc_report_path = '/tmp/drc_4layer_v3_report.txt'
    try:
        board2 = pcbnew.LoadBoard(OUTPUT)
        result = pcbnew.WriteDRCReport(board2, drc_report_path, 0, True)
        print(f'    WriteDRCReport result: {result}')
    except Exception as e:
        print(f'    DRC error: {e}')

    # Parse and summarize DRC report
    tracks_crossing = 0
    unconnected_items = 0
    shorting_items = 0
    solder_mask_bridge = 0
    holes_co_located = 0
    clearance_violations = 0
    hole_clearance_violations = 0
    via_dangling = 0
    track_dangling = 0
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
            elif ll.startswith('[via_dangling]'):
                via_dangling += 1
            elif ll.startswith('[track_dangling]'):
                track_dangling += 1
            elif ll.startswith('[') and 'error' in ll:
                if not any(x in ll for x in [
                    'silk', 'courtyard', 'edge_clearance', 'silk_over',
                    'tracks_crossing', 'unconnected', 'unrouted',
                    'shorting', 'solder_mask', 'holes_co',
                    'clearance', 'hole_clearance', 'via_dangling',
                    'track_dangling'
                ]):
                    other_errors += 1

        print(f'\n    ─── DRC Summary (v3) ───')
        print(f'    tracks_crossing:           {tracks_crossing}')
        print(f'    unconnected_items:          {unconnected_items}')
        print(f'    shorting_items:             {shorting_items}')
        print(f'    solder_mask_bridge:         {solder_mask_bridge}')
        print(f'    holes_co_located:           {holes_co_located}')
        print(f'    clearance violations:       {clearance_violations}')
        print(f'    hole_clearance violations:  {hole_clearance_violations}')
        print(f'    via_dangling:               {via_dangling}')
        print(f'    track_dangling:             {track_dangling}')
        print(f'    other errors:               {other_errors}')
        print(f'\n    Full report: {drc_report_path}')
    else:
        print('    DRC report file not generated!')

    print('\n' + '=' * 72)
    print('Done.')
    print('=' * 72)


if __name__ == '__main__':
    main()