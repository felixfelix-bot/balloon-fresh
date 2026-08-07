#!/usr/bin/env python3.14
"""Convert v_c3_flight_final.kicad_pcb to 4-layer with power planes + re-route all signal nets."""
import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew
import math
import os

INPUT  = '/home/c03rad0r/repos/balloon-fresh/tracker/hardware/output/v_c3_flight_final.kicad_pcb'
OUTPUT = '/home/c03rad0r/repos/balloon-fresh/tracker/hardware/output/v_c3_flight_4layer_routed.kicad_pcb'

# Constants
TRACK_WIDTH = 250000   # 0.25mm
CLEARANCE   = 220000   # 0.22mm
VIA_WIDTH   = 550000   # 0.55mm
VIA_DRILL   = 300000   # 0.30mm
F_CU  = pcbnew.F_Cu    # 0
B_CU  = pcbnew.B_Cu    # 2
IN1   = pcbnew.In1_Cu  # 4
IN2   = pcbnew.In2_Cu  # 6

POWER_NETS = {'+3V3', 'GND', 'VCAP', 'SOLAR_IN', 'EN'}

# ─── Geometry helpers ─────────────────────────────────────────────────────────

def ccw(A, B, C):
    return (C[1]-A[1])*(B[0]-A[0]) - (B[1]-A[1])*(C[0]-A[0])

def seg_cross(p1, p2, p3, p4):
    """True if segment p1-p2 properly crosses segment p3-p4."""
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
    """True if two segments come within clearance of each other (or cross)."""
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
    """True if two segments are colinear and overlap."""
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

# ─── Board state ──────────────────────────────────────────────────────────────

routed_segments = []   # list of (layer_id, (x1,y1), (x2,y2), netcode)
routed_vias     = []   # list of (x, y, netcode)
pad_positions   = []   # list of (x, y, layer, netcode, netname)

def check_collision(layer, seg_a, seg_b, netcode):
    """Check if a proposed segment collides with existing tracks/vias/pads on same layer."""
    # Check pads (all pads are on F_Cu; THT pads visible from both layers)
    for px, py, pad_layer, pad_net, pad_netname in pad_positions:
        if pad_net == netcode:
            continue
        # Pads on F_Cu are only visible from F_Cu
        # Pads on B_Cu are only visible from B_Cu
        # But THT pads (through-hole) are visible from both
        # In this board, pad layer=0 means F_Cu. Most are SMD on F_Cu.
        # For collision: check if pad is on this layer
        if pad_layer != layer:
            continue
        d = point_seg_dist(px, py, seg_a[0], seg_a[1], seg_b[0], seg_b[1])
        if d < CLEARANCE + 300000:  # pad radius ~500000, so 300000 + clearance
            return True

    # Check vias
    for vx, vy, via_net in routed_vias:
        if via_net == netcode:
            continue
        d = point_seg_dist(vx, vy, seg_a[0], seg_a[1], seg_b[0], seg_b[1])
        if d < CLEARANCE + VIA_WIDTH//2:
            return True

    # Check routed segments
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

# ─── Routing ─────────────────────────────────────────────────────────────────

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

def route_manhattan(start, end, netcode, preferred='HV'):
    """Route from start to end using Manhattan style.  Returns (segments, vias) or (None, None)."""
    sx, sy = start
    ex, ey = end

    if sx == ex and sy == ey:
        return [], []

    # Try 4 variants: HV/F, VH/F, HV/B, VH/B
    for pattern in [preferred, 'VH' if preferred=='HV' else 'HV', 'HV', 'VH']:
        for layer in [F_CU, B_CU]:
            if pattern == 'HV':
                mid = (ex, sy)
            else:
                mid = (sx, ey)

            segments = []
            if start != mid:
                segments.append((layer, start, mid))
            if mid != end:
                segments.append((layer, mid, end))

            collisions = sum(1 for l, a, b in segments if check_collision(l, a, b, netcode))
            if collisions == 0:
                return segments, []

    # Try mixed-layer: first segment on F_Cu, second on B_Cu (with via at mid)
    for pattern in ['HV', 'VH']:
        if pattern == 'HV':
            mid = (ex, sy)
        else:
            mid = (sx, ey)

        # F first, B second
        seg1 = (F_CU, start, mid) if start != mid else None
        seg2 = (B_CU, mid, end) if mid != end else None
        if seg1 and seg2:
            c1 = check_collision(F_CU, start, mid, netcode)
            c2 = check_collision(B_CU, mid, end, netcode)
            if not c1 and not c2:
                return [seg1, seg2], [mid]

        # B first, F second
        seg1b = (B_CU, start, mid) if start != mid else None
        seg2b = (F_CU, mid, end) if mid != end else None
        if seg1b and seg2b:
            c1 = check_collision(B_CU, start, mid, netcode)
            c2 = check_collision(F_CU, mid, end, netcode)
            if not c1 and not c2:
                return [seg1b, seg2b], [mid]

    # Try offset routing: add intermediate waypoint to avoid collisions
    for offset in [1500000, 2500000, 3500000, -1500000, -2500000]:
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

                collisions = sum(1 for l, a, b in segs if check_collision(l, a, b, netcode))
                if collisions == 0:
                    return segs, []

    # Last resort: try F_Cu only with larger offset
    for offset in [5000000, -5000000]:
        for pattern in ['HV', 'VH']:
            if pattern == 'HV':
                mid1 = (ex + offset, sy)
            else:
                mid1 = (sx, ey + offset)

            for layer in [F_CU, B_CU]:
                segs = []
                if start != mid1:
                    segs.append((layer, start, mid1))
                if mid1 != end:
                    segs.append((layer, mid1, end))

                collisions = sum(1 for l, a, b in segs if check_collision(l, a, b, netcode))
                if collisions == 0:
                    return segs, []

    # If nothing works, return best single-layer attempt
    if preferred == 'HV':
        mid = (ex, sy)
    else:
        mid = (sx, ey)
    return [(F_CU, start, mid), (F_CU, mid, end)], []

def commit_route(board, segments, vias, netcode):
    for layer, start, end in segments:
        make_track(board, layer, start, end, netcode)
        routed_segments.append((layer, start, end, netcode))
    for via_pos in vias:
        make_via(board, via_pos, netcode)
        routed_vias.append((via_pos[0], via_pos[1], netcode))

def route_net(board, netname, pad_list, preferred='HV'):
    if len(pad_list) < 2:
        return 0, 0

    # Sort pads: nearest-neighbor chain
    remaining = list(pad_list)
    order = [remaining.pop(0)]
    while remaining:
        last = order[-1]
        nearest = min(remaining, key=lambda p: (p[0]-last[0])**2 + (p[1]-last[1])**2)
        order.append(nearest)
        remaining.remove(nearest)

    total_tracks = 0
    total_vias = 0

    for i in range(len(order)-1):
        start = (order[i][0], order[i][1])
        end = (order[i+1][0], order[i+1][1])
        netcode = order[i][2]

        segments, vias = route_manhattan(start, end, netcode, preferred=preferred)
        if segments is None:
            print(f'  WARN: No route for {netname} {start}->{end}')
            continue

        commit_route(board, segments, vias, netcode)
        total_tracks += len(segments)
        total_vias += len(vias)

    return total_tracks, total_vias

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print('=== 4-Layer Conversion + Re-Route ===')
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

        margin = 100000  # 0.1mm inset
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

    # ── Step 3: Thermal vias for power pads ─────────────────────────────────
    print('\n--- Step 3: Thermal vias for power nets ---')

    thermal_via_count = 0
    power_pad_count = 0
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            netname = pad.GetNetname()
            if netname in POWER_NETS:
                power_pad_count += 1
                pos = pad.GetPosition()
                netcode = pad.GetNetCode()
                make_via(board, (pos.x, pos.y), netcode)
                routed_vias.append((pos.x, pos.y, netcode))
                thermal_via_count += 1
    print(f'  Power pads: {power_pad_count}, thermal vias: {thermal_via_count}')

    # ── Step 4: Collect pad positions ───────────────────────────────────────
    print('\n--- Step 4: Collect pad positions ---')

    signal_nets = {}
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            netname = pad.GetNetname()
            if not netname:
                continue
            pos = pad.GetPosition()
            layer = pad.GetLayer()
            netcode = pad.GetNetCode()
            pad_positions.append((pos.x, pos.y, layer, netcode, netname))
            if netname not in POWER_NETS:
                if netname not in signal_nets:
                    signal_nets[netname] = []
                signal_nets[netname].append((pos.x, pos.y, netcode))

    print(f'  Signal nets: {len(signal_nets)}')
    for n, pads in sorted(signal_nets.items()):
        print(f'    {n}: {len(pads)} pads')

    # ── Step 5: Route all signal nets ────────────────────────────────────────
    print('\n--- Step 5: Route signal nets ---')

    # Route short nets first (2-pad), then multi-pad
    net_order = sorted(signal_nets.keys(), key=lambda n: len(signal_nets[n]))

    total_tracks = 0
    total_vias = 0
    for idx, netname in enumerate(net_order):
        pads = signal_nets[netname]
        preferred = 'HV' if idx % 2 == 0 else 'VH'
        tracks, vias = route_net(board, netname, pads, preferred=preferred)
        total_tracks += tracks
        total_vias += vias
        print(f'  {netname}: {tracks} tracks, {vias} vias (pref={preferred})')

    print(f'\nTotal: {total_tracks} signal tracks, {total_vias} signal vias, {thermal_via_count} thermal vias')

    # ── Step 6: Fill zones + save ────────────────────────────────────────────
    print('\n--- Step 6: Fill zones + save ---')
    filler = pcbnew.ZONE_FILLER(board)
    fill_result = filler.Fill(board.Zones())
    print(f'Zone fill result: {fill_result}')

    pcbnew.SaveBoard(OUTPUT, board)
    print(f'Saved: {OUTPUT}')

    # ── Step 7: DRC ─────────────────────────────────────────────────────────
    print('\n--- Step 7: DRC ---')

    # Re-load for clean DRC
    board2 = pcbnew.LoadBoard(OUTPUT)

    drc_report_path = '/tmp/drc_4layer_report.txt'
    result = pcbnew.WriteDRCReport(board2, drc_report_path, 0, True)
    print(f'WriteDRCReport: {result}')

    tracks_crossing = 0
    unconnected_items = 0
    shorting_items = 0
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
            elif ll.startswith('[shorting_items]') or ('short' in ll and 'error' in ll):
                shorting_items += 1
            elif ll.startswith('[') and 'error' in ll:
                if not any(x in ll for x in ['silk', 'courtyard', 'edge_clearance', 'silk_over']):
                    other_errors += 1

        print(f'\n=== DRC Summary ===')
        print(f'  tracks_crossing:   {tracks_crossing}')
        print(f'  unconnected_items:  {unconnected_items}')
        print(f'  shorting_items:     {shorting_items}')
        print(f'  other errors:       {other_errors}')
        print(f'\nFull report: {drc_report_path}')
    else:
        print('DRC report not generated!')

    # Verify output
    if os.path.exists(OUTPUT):
        sz = os.path.getsize(OUTPUT)
        print(f'\nOutput: {OUTPUT} ({sz} bytes)')
    else:
        print(f'\nERROR: Output file not created!')

    print('\n=== Done ===')

if __name__ == '__main__':
    main()