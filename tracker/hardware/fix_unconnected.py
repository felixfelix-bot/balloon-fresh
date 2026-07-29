#!/usr/bin/env python3
"""Parse DRC unconnected items and generate fix traces for gen_pcb.py output.

Reads DRC reports, extracts unconnected pairs, generates KiCad segment/via
text to bridge each gap. Outputs patch text that gets appended to the .kicad_pcb
files BEFORE the closing paren.
"""
import re, sys, uuid, os

def gen_uuid():
    return str(uuid.uuid4())

def parse_coords(text):
    """Extract X,Y coordinates from a DRC line like @(36.5000 mm, 7.6100 mm)"""
    m = re.search(r'@\(([\d.]+)\s*mm,\s*([\d.]+)\s*mm\)', text)
    if m:
        return float(m.group(1)), float(m.group(2))
    return None, None

def parse_net(text):
    """Extract net name from [NET_NAME] in brackets"""
    m = re.search(r'\[([^\]]+)\]', text)
    if m:
        return m.group(1)
    return None

def parse_layer(text):
    """Extract layer from 'on F.Cu' or 'on B.Cu'"""
    if 'B.Cu' in text:
        return 'B.Cu'
    return 'F.Cu'  # default

def parse_drc(filepath):
    with open(filepath) as f:
        text = f.read()
    
    blocks = text.split('[unconnected_items]')
    items = []
    for block in blocks[1:]:
        lines = [l.strip() for l in block.strip().split('\n') if l.strip()]
        if len(lines) < 3:
            continue
        # Format: lines[0]="Missing connection between items"
        #         lines[1]="Local override; error"  (sometimes)
        #         next two @ lines are the endpoints
        # Find the two @(x,y) lines
        endpoints = [l for l in lines if l.startswith('@')]
        if len(endpoints) < 2:
            continue
        ep_a = endpoints[0]
        ep_b = endpoints[1]
        
        ax, ay = parse_coords(ep_a)
        bx, by = parse_coords(ep_b)
        net = parse_net(ep_a) or parse_net(ep_b)
        
        if ax is None or bx is None or net is None:
            continue
            
        items.append({
            'ax': ax, 'ay': ay, 'bx': bx, 'by': by,
            'net': net,
            'layer_a': parse_layer(ep_a),
            'layer_b': parse_layer(ep_b),
            'desc_a': ep_a,
            'desc_b': ep_b,
        })
    return items

def gen_segment(x1, y1, x2, y2, net_name, net_id, width=0.25, layer="F.Cu"):
    return f'  (segment (start {x1:.4f} {y1:.4f}) (end {x2:.4f} {y2:.4f}) (width {width}) (layer "{layer}") (net {net_id}) (uuid "{gen_uuid()}"))\n'

def gen_via(x, y, net_name, net_id):
    return f'  (via (at {x:.4f} {y:.4f}) (size 0.6) (drill 0.3) (layers "F.Cu" "B.Cu") (net {net_id}) (uuid "{gen_uuid()}"))\n'

def fix_board(drc_file, pcb_file, board_name):
    items = parse_drc(drc_file)
    print(f"\n{'='*60}")
    print(f"FIXING {board_name}: {len(items)} unconnected items")
    print(f"{'='*60}")
    
    # Read current PCB file
    with open(pcb_file) as f:
        pcb = f.read()
    
    # Build a net ID lookup from the existing PCB
    net_ids = {}
    for m in re.finditer(r'\(net (\d+) "([^"]+)"\)', pcb):
        net_ids[m.group(2)] = int(m.group(1))
    
    # Generate fix segments
    fix_text = "\n"
    fixes = 0
    
    for item in items:
        net = item['net']
        nid = net_ids.get(net, 0)
        
        ax, ay = item['ax'], item['ay']
        bx, by = item['bx'], item['by']
        
        # If endpoints are on same layer, direct connect
        if item['layer_a'] == item['layer_b']:
            fix_text += gen_segment(ax, ay, bx, by, net, nid, layer=item['layer_a'])
            fixes += 1
        else:
            # Different layers: add via at midpoint
            mx = (ax + bx) / 2
            my = (ay + by) / 2
            fix_text += gen_segment(ax, ay, mx, my, net, nid, layer=item['layer_a'])
            fix_text += gen_via(mx, my, net, nid)
            fix_text += gen_segment(mx, my, bx, by, net, nid, layer=item['layer_b'])
            fixes += 3
    
    # Insert fix traces before the closing paren of the PCB file
    # Find last ')' at top level
    last_paren = pcb.rstrip().rfind(')')
    if last_paren < 0:
        print(f"ERROR: Could not find closing paren in {pcb_file}")
        return False
    
    new_pcb = pcb[:last_paren] + fix_text + pcb[last_paren:]
    
    # Write fixed PCB
    with open(pcb_file, 'w') as f:
        f.write(new_pcb)
    
    print(f"  Added {fixes} fix primitives ({len(items)} connections)")
    print(f"  Written to {pcb_file}")
    return True

# Main
hw_dir = os.path.dirname(os.path.abspath(__file__))

# Fix V1
v1_ok = fix_board(
    os.path.join(hw_dir, 'drc_v1_baseline.txt'),
    os.path.join(hw_dir, 'hub_board_v1.kicad_pcb'),
    'V1'
)

# Fix F33
f33_ok = fix_board(
    os.path.join(hw_dir, 'drc_f33_baseline.txt'),
    os.path.join(hw_dir, 'hub_board_f33.kicad_pcb'),
    'F33'
)

if v1_ok and f33_ok:
    print("\n✓ Both boards patched. Run DRC to verify.")
else:
    print("\n✗ Some boards failed to patch!")
    sys.exit(1)
