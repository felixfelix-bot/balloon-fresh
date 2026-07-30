#!/usr/bin/env python3
"""DRC shorting fix: detour traces around conflict points.

For each shorting_item/tracks_crossing in DRC report, replace the 
conflicting trace segment with a detour path that goes around the 
obstacle by 0.7mm perpendicular offset.

Strategy: parse DRC report for exact conflict coordinates, find the 
trace segment in PCB that matches, split it into a U-shaped detour.
"""
import re, sys, uuid, os, math

def gen_uuid():
    return str(uuid.uuid4())

def parse_drc_shorts(drc_path):
    """Parse shorting_items from DRC report."""
    with open(drc_path) as f:
        text = f.read()
    
    shorts = []
    blocks = re.split(r'\[shorting_items\]', text)
    for block in blocks[1:]:
        lines = [l.strip() for l in block.strip().split('\n') if l.strip()]
        # Extract nets from header line: "Items shorting two nets (nets A and B)"
        net_match = re.search(r'nets (\S+) and (\S+)', lines[0]) if lines else None
        net_a = net_match.group(1) if net_match else '?'
        net_b = net_match.group(2) if net_match else '?'
        
        # Find the two @(x,y) endpoints
        endpoints = [l for l in lines if l.startswith('@')]
        if len(endpoints) < 2:
            continue
        
        coords = []
        for ep in endpoints[:2]:
            m = re.search(r'@\(([\d.]+)\s*mm,\s*([\d.]+)\s*mm\)', ep)
            if m:
                coords.append((float(m.group(1)), float(m.group(2)), ep))
        
        if len(coords) >= 2:
            shorts.append({
                'net_a': net_a, 'net_b': net_b,
                'ax': coords[0][0], 'ay': coords[0][1], 'desc_a': coords[0][2],
                'bx': coords[1][0], 'by': coords[1][1], 'desc_b': coords[1][2],
            })
    return shorts

def find_segment_to_detour(pcb_text, conflict_x, conflict_y, net_num=None):
    """Find the trace segment that passes through the conflict point."""
    best_match = None
    best_dist = float('inf')
    
    for m in re.finditer(
        r'\(segment\s+\(start\s+([\d.]+)\s+([\d.]+)\)\s+\(end\s+([\d.]+)\s+([\d.]+)\)'
        r'\s+\(width\s+([\d.]+)\)\s+\(layer\s+"([^"]+)"\)\s+\(net\s+(\d+)\)\s+\(uuid\s+"([^"]+)"\)',
        pcb_text
    ):
        x1, y1 = float(m.group(1)), float(m.group(2))
        x2, y2 = float(m.group(3)), float(m.group(4))
        net = int(m.group(7))
        
        if net_num and net != net_num:
            continue
        
        # Distance from conflict point to this segment
        d = point_to_seg_dist(conflict_x, conflict_y, x1, y1, x2, y2)
        if d < best_dist:
            best_dist = d
            best_match = {
                'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2,
                'width': float(m.group(5)),
                'layer': m.group(6),
                'net': net,
                'uuid': m.group(8),
                'full_match': m.group(0),
                'dist': d,
            }
    
    return best_match

def point_to_seg_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.sqrt((px - x1)**2 + (py - y1)**2)
    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx*dx + dy*dy)))
    cx, cy = x1 + t * dx, y1 + t * dy
    return math.sqrt((px - cx)**2 + (py - cy)**2)

def detour_segment(seg, conflict_x, conflict_y, offset=0.7):
    """Replace a straight segment with a U-shaped detour around conflict point.
    
    Returns list of replacement segment text lines.
    """
    x1, y1, x2, y2 = seg['x1'], seg['y1'], seg['x2'], seg['y2']
    width = seg['width']
    layer = seg['layer']
    net = seg['net']
    
    # Determine trace direction
    is_vertical = abs(x2 - x1) < abs(y2 - y1)
    
    if is_vertical:
        # Trace runs vertically (x ≈ const), conflict at (cx, cy)
        # Detour horizontally: offset_x = x ± offset
        trace_x = (x1 + x2) / 2
        if conflict_x >= trace_x:
            offset_x = trace_x - offset  # detour left
        else:
            offset_x = trace_x + offset  # detour right
        
        # U-shaped: stay on trace → move sideways → parallel → back to trace
        # Only detour the portion near the conflict (±1.5mm)
        detour_start = min(conflict_y - 1.5, y1)
        detour_end = max(conflict_y + 1.5, y2)
        
        if detour_start <= y1 or detour_end >= y2:
            # Conflict near endpoints — detour entire segment
            detour_start = y1
            detour_end = y2
        
        segs = []
        # Part 1: trace to detour start
        segs.append((x1, y1, trace_x, detour_start))
        # Part 2: move sideways
        segs.append((trace_x, detour_start, offset_x, detour_start))
        # Part 3: parallel run
        segs.append((offset_x, detour_start, offset_x, detour_end))
        # Part 4: move back
        segs.append((offset_x, detour_end, trace_x, detour_end))
        # Part 5: continue to end
        segs.append((trace_x, detour_end, x2, y2))
    else:
        # Trace runs horizontally (y ≈ const), conflict at (cx, cy)
        trace_y = (y1 + y2) / 2
        if conflict_y >= trace_y:
            offset_y = trace_y - offset  # detour down
        else:
            offset_y = trace_y + offset  # detour up
        
        detour_start = min(conflict_x - 1.5, x1)
        detour_end = max(conflict_x + 1.5, x2)
        
        if detour_start <= x1 or detour_end >= x2:
            detour_start = x1
            detour_end = x2
        
        segs = []
        segs.append((x1, y1, detour_start, trace_y))
        segs.append((detour_start, trace_y, detour_start, offset_y))
        segs.append((detour_start, offset_y, detour_end, offset_y))
        segs.append((detour_end, offset_y, detour_end, trace_y))
        segs.append((detour_end, trace_y, x2, y2))
    
    # Generate text
    result = []
    for sx1, sy1, sx2, sy2 in segs:
        # Skip zero-length segments
        if abs(sx2 - sx1) < 0.01 and abs(sy2 - sy1) < 0.01:
            continue
        result.append(
            f'  (segment (start {sx1:.4f} {sy1:.4f}) (end {sx2:.4f} {sy2:.4f}) '
            f'(width {width}) (layer "{layer}") (net {net}) (uuid "{gen_uuid()}"))'
        )
    return result

def get_net_names(pcb_text):
    net_names = {}
    for m in re.finditer(r'\(net\s+(\d+)\s+"([^"]+)"\)', pcb_text):
        net_names[m.group(2)] = int(m.group(1))
    return net_names

def fix_board(pcb_path, drc_path, board_name):
    print(f"\n{'='*60}")
    print(f"FIXING {board_name}")
    print(f"{'='*60}")
    
    with open(pcb_path) as f:
        pcb = f.read()
    
    net_name_to_id = get_net_names(pcb)
    shorts = parse_drc_shorts(drc_path)
    print(f"  Found {len(shorts)} shorting items in DRC report")
    
    # Also parse tracks_crossing
    with open(drc_path) as f:
        drc_text = f.read()
    
    crossings = []
    for block in re.split(r'\[tracks_crossing\]', drc_text)[1:]:
        lines = [l.strip() for l in block.strip().split('\n') if l.strip()]
        endpoints = [l for l in lines if l.startswith('@')]
        if len(endpoints) >= 2:
            coords = []
            for ep in endpoints[:2]:
                m = re.search(r'@\(([\d.]+)\s*mm,\s*([\d.]+)\s*mm\)', ep)
                if m:
                    coords.append((float(m.group(1)), float(m.group(2))))
            if len(coords) >= 2:
                crossings.append((coords[0][0], coords[0][1], coords[1][0], coords[1][1]))
    
    print(f"  Found {len(crossings)} tracks_crossing in DRC report")
    
    # Process shorts
    detoured_uuids = set()
    fixes_applied = 0
    
    for short in shorts:
        # Try to detour the trace (not the via/pad)
        # Use net_b (the second item) as the trace to move
        net_b_id = net_name_to_id.get(short['net_b'])
        
        seg = find_segment_to_detour(pcb, short['bx'], short['by'], net_b_id)
        if not seg:
            # Try net_a
            net_a_id = net_name_to_id.get(short['net_a'])
            seg = find_segment_to_detour(pcb, short['ax'], short['ay'], net_a_id)
            if seg:
                conflict_x, conflict_y = short['bx'], short['by']
            else:
                continue
        else:
            conflict_x, conflict_y = short['ax'], short['ay']
        
        if seg['uuid'] in detoured_uuids:
            continue  # Already detoured
        
        # Detour this segment
        new_segs = detour_segment(seg, conflict_x, conflict_y)
        if new_segs:
            # Replace old segment with detour segments
            replacement = '\n'.join(new_segs)
            pcb = pcb.replace(seg['full_match'], replacement, 1)
            detoured_uuids.add(seg['uuid'])
            fixes_applied += 1
    
    # Process crossings
    for cx1, cy1, cx2, cy2 in crossings:
        # Find segment near first endpoint
        seg = find_segment_to_detour(pcb, cx1, cy1)
        if seg and seg['uuid'] not in detoured_uuids:
            new_segs = detour_segment(seg, cx2, cy2)
            if new_segs:
                replacement = '\n'.join(new_segs)
                pcb = pcb.replace(seg['full_match'], replacement, 1)
                detoured_uuids.add(seg['uuid'])
                fixes_applied += 1
    
    print(f"  Detours applied: {fixes_applied}")
    
    # Write fixed PCB
    with open(pcb_path, 'w') as f:
        f.write(pcb)
    
    print(f"  PCB written to {pcb_path}")
    return fixes_applied

# Main
hw_dir = os.path.dirname(os.path.abspath(__file__))

v1_fixes = fix_board(
    os.path.join(hw_dir, 'hub_board_v1.kicad_pcb'),
    os.path.join(hw_dir, 'drc_v1_check.txt'),
    'hub_board_v1'
)

f33_fixes = fix_board(
    os.path.join(hw_dir, 'hub_board_f33.kicad_pcb'),
    os.path.join(hw_dir, 'drc_f33_check.txt'),
    'hub_board_f33'
)

print(f"\nDONE: V1={v1_fixes} detours, F33={f33_fixes} detours")
print(f"Run DRC: kicad-cli pcb drc --output drc_v1_check2.txt hub_board_v1.kicad_pcb")
