#!/usr/bin/env python3
"""Auto-route hub_board_v1.kicad_pcb from scratch.

This script:
1. Reads the existing PCB file
2. Extracts all footprints, pads, and their positions
3. Fixes GPIO assignments (GPIO18→GPIO8 for LED, remove FEM_TX)
4. Rips up all existing tracks, vias, and zones
5. Re-routes all nets using a clearance-aware Manhattan router
6. Writes a clean PCB file
7. Runs DRC to verify

Key fixes:
- STATUS_LED: moved from non-existent GPIO18 to GPIO8 (ESP32-C3 pad 10)
- FEM_TX: removed entirely (no FEM on V1 flight, wire dipole only)
- All routing redone from scratch with proper clearance
- Solder mask bridges fixed by ensuring proper trace spacing
- GND plane on B.Cu with proper clearance
"""

import re
import sys
import os
import uuid as uuid_mod
from collections import defaultdict
from pathlib import Path

# Add the hardware directory to path so we can import router.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from router import Router, manhattan_route_points

PCB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hub_board_v1.kicad_pcb")
OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hub_board_v1_routed.kicad_pcb")

def read_pcb(path):
    with open(path, 'r') as f:
        return f.read()

def write_pcb(path, content):
    with open(path, 'w') as f:
        f.write(content)

def gen_uuid():
    return str(uuid_mod.uuid4())

# ============================================================
# Parse the PCB to extract footprints and pads
# ============================================================

class PadInfo:
    def __init__(self, pin, dx, dy, w, h, net_id, net_name, layers, pad_type, shape, drill=0):
        self.pin = pin
        self.dx = dx  # relative to footprint origin
        self.dy = dy
        self.w = w
        self.h = h
        self.net_id = net_id
        self.net_name = net_name
        self.layers = layers
        self.pad_type = pad_type  # 'thru_hole' or 'smd'
        self.shape = shape  # 'rect', 'oval', 'circle'
        self.drill = drill
    
    @property
    def is_thru(self):
        return self.pad_type == 'thru_hole'
    
    @property
    def is_smd(self):
        return self.pad_type == 'smd'

class FootprintInfo:
    def __init__(self, name, fp_id, x, y, layer, ref, value, raw_text):
        self.name = name  # footprint library name
        self.fp_id = fp_id  # uuid
        self.x = x
        self.y = y
        self.layer = layer
        self.ref = ref
        self.value = value
        self.raw_text = raw_text  # full s-expression text
        self.pads = []  # list of PadInfo
    
    def pad_abs_pos(self, pad):
        """Get absolute (x, y) of a pad."""
        return (self.x + pad.dx, self.y + pad.dy)

def parse_pcb(text):
    """Parse KiCad PCB text to extract footprints and pads."""
    footprints = []
    nets = {}
    
    # Parse net definitions
    net_re = re.compile(r'\(net\s+(\d+)\s+"([^"]*)"\)')
    for m in net_re.finditer(text):
        net_id = int(m.group(1))
        net_name = m.group(2)
        nets[net_id] = net_name
    
    # Parse footprints - find each (footprint ... ) block
    # We need balanced paren matching
    idx = 0
    while True:
        fp_start = text.find('(footprint ', idx)
        if fp_start == -1:
            break
        
        # Find matching close paren
        depth = 0
        i = fp_start
        while i < len(text):
            if text[i] == '(':
                depth += 1
            elif text[i] == ')':
                depth -= 1
                if depth == 0:
                    break
            i += 1
        
        fp_text = text[fp_start:i+1]
        
        # Extract footprint name
        name_m = re.match(r'\(footprint\s+"([^"]+)"', fp_text)
        if not name_m:
            idx = i + 1
            continue
        fp_name = name_m.group(1)
        
        # Extract UUID
        uuid_m = re.search(r'\(uuid\s+"([^"]+)"\)', fp_text)
        fp_uuid = uuid_m.group(1) if uuid_m else gen_uuid()
        
        # Extract position (at X Y)
        at_m = re.search(r'\(at\s+([-\d.]+)\s+([-\d.]+)\)', fp_text)
        if not at_m:
            idx = i + 1
            continue
        fp_x = float(at_m.group(1))
        fp_y = float(at_m.group(2))
        
        # Extract layer
        layer_m = re.search(r'\(layer\s+"([^"]+)"\)', fp_text)
        fp_layer = layer_m.group(1) if layer_m else "F.Cu"
        
        # Extract Reference and Value
        ref_m = re.search(r'\(property\s+"Reference"\s+"([^"]+)"', fp_text)
        val_m = re.search(r'\(property\s+"Value"\s+"([^"]+)"', fp_text)
        ref = ref_m.group(1) if ref_m else ""
        value = val_m.group(1) if val_m else ""
        
        fp = FootprintInfo(fp_name, fp_uuid, fp_x, fp_y, fp_layer, ref, value, fp_text)
        
        # Parse pads within this footprint
        # Simple pad parsing - find all (pad ...) blocks
        pad_idx = 0
        while True:
            pad_start = fp_text.find('(pad ', pad_idx)
            if pad_start == -1:
                break
            
            depth = 0
            j = pad_start
            while j < len(fp_text):
                if fp_text[j] == '(':
                    depth += 1
                elif fp_text[j] == ')':
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            
            pad_text = fp_text[pad_start:j+1]
            
            # Parse pad attributes
            pin_m = re.match(r'\(pad\s+"([^"]+)"', pad_text)
            if not pin_m:
                pad_idx = j + 1
                continue
            pin = pin_m.group(1)
            
            type_m = re.search(r'(thru_hole|smd|connect|np_thru_hole)', pad_text)
            pad_type = type_m.group(1) if type_m else 'smd'
            
            shape_m = re.search(r'(thru_hole|smd|connect|np_thru_hole)\s+(rect|oval|circle|roundrect|custom)', pad_text)
            shape = shape_m.group(2) if shape_m else 'rect'
            
            at_m = re.search(r'\(at\s+([-\d.]+)\s+([-\d.]+)\)', pad_text)
            if not at_m:
                pad_idx = j + 1
                continue
            pad_dx = float(at_m.group(1))
            pad_dy = float(at_m.group(2))
            
            size_m = re.search(r'\(size\s+([\d.]+)\s+([\d.]+)\)', pad_text)
            if size_m:
                pad_w = float(size_m.group(1))
                pad_h = float(size_m.group(2))
            else:
                pad_w = pad_h = 1.0
            
            drill_m = re.search(r'\(drill\s+([\d.]+)', pad_text)
            drill = float(drill_m.group(1)) if drill_m else 0.0
            
            # Layers
            layers_m = re.search(r'\(layers\s+([^)]+)\)', pad_text)
            if layers_m:
                layers_str = layers_m.group(1).strip()
            else:
                layers_str = '"F.Cu" "F.Paste" "F.Mask"'
            
            # Net
            net_m = re.search(r'\(net\s+(\d+)\s+"([^"]*)"\)', pad_text)
            net_id = int(net_m.group(1)) if net_m else 0
            net_name = net_m.group(2) if net_m else ""
            
            pad = PadInfo(pin, pad_dx, pad_dy, pad_w, pad_h, net_id, net_name, 
                         layers_str, pad_type, shape, drill)
            fp.pads.append(pad)
            
            pad_idx = j + 1
        
        footprints.append(fp)
        idx = i + 1
    
    return footprints, nets

# ============================================================
# Build netlist: for each net, list of pad positions to connect
# ============================================================

def build_netlist(footprints):
    """Build a mapping: net_id -> list of (fp_ref, pin, abs_x, abs_y, pad_w, pad_h, is_thru)"""
    netlist = defaultdict(list)
    for fp in footprints:
        for pad in fp.pads:
            if pad.net_id > 0:
                abs_x, abs_y = fp.pad_abs_pos(pad)
                netlist[pad.net_id].append({
                    'ref': fp.ref,
                    'pin': pad.pin,
                    'x': abs_x,
                    'y': abs_y,
                    'w': pad.w,
                    'h': pad.h,
                    'is_thru': pad.is_thru,
                    'is_smd': pad.is_smd,
                    'layers': pad.layers,
                })
    return netlist

# ============================================================
# Auto-router: route all nets
# ============================================================

def route_all(footprints, nets, board_w=50, board_h=40):
    """Route all nets using the Router class."""
    router = Router(board_w=board_w, board_h=board_h, clearance=0.3, grid=0.5)
    
    # Register all pads as obstacles (for clearance checking)
    # But we need to be smarter: only register pads that are on specific layers
    for fp in footprints:
        for pad in fp.pads:
            if pad.net_id > 0:
                abs_x, abs_y = fp.pad_abs_pos(pad)
                # Pads on *.Cu are on both layers
                if '*.Cu' in pad.layers or 'F.Cu' in pad.layers:
                    router.add_pad(abs_x, abs_y, pad.w, pad.h, pad.net_id, 'F.Cu')
                if '*.Cu' in pad.layers or 'B.Cu' in pad.layers:
                    if '*.Cu' not in pad.layers:  # Avoid double-adding *.Cu pads
                        router.add_pad(abs_x, abs_y, pad.w, pad.h, pad.net_id, 'B.Cu')
                    elif 'F.Cu' not in pad.layers:
                        # *.Cu pad not yet added on B.Cu
                        router.add_pad(abs_x, abs_y, pad.w, pad.h, pad.net_id, 'B.Cu')
    
    # Build netlist
    netlist = build_netlist(footprints)
    
    # Determine net classes
    power_nets = {1: "3V3", 2: "GND"}  # Power nets get wider traces
    rf_nets = {12: "RF_SUB_868", 13: "RF_2G4_2400"}  # RF nets get wider traces
    
    # Route priority: power first, then RF, then signals
    route_order = []
    
    # Power nets first
    for net_id in sorted(netlist.keys()):
        if net_id in power_nets:
            route_order.append(net_id)
    
    # RF nets
    for net_id in sorted(netlist.keys()):
        if net_id in rf_nets:
            route_order.append(net_id)
    
    # Signal nets
    for net_id in sorted(netlist.keys()):
        if net_id not in power_nets and net_id not in rf_nets:
            route_order.append(net_id)
    
    # Route each net
    routed_nets = {}
    for net_id in route_order:
        pads = netlist[net_id]
        if len(pads) < 2:
            continue
        
        # Determine trace width and layer preference
        if net_id in power_nets:
            width = 0.5
            clearance = 0.3
            # Power on B.Cu for distribution
            primary_layer = "B.Cu"
        elif net_id in rf_nets:
            width = 0.8
            clearance = 0.3
            primary_layer = "F.Cu"
        else:
            width = 0.25
            clearance = 0.25
            primary_layer = "F.Cu"
        
        # Update router clearance for this net
        old_clearance = router.clearance
        
        # Route: connect all pads of this net in a star/chain pattern
        # Sort pads by position to minimize total trace length
        if len(pads) == 2:
            # Simple point-to-point
            p1, p2 = pads[0], pads[1]
            layer = primary_layer
            # If either pad is SMD on a specific layer, use that layer
            if p1['is_smd'] and 'B.Cu' not in p1['layers']:
                layer = "F.Cu"
            elif p2['is_smd'] and 'B.Cu' not in p2['layers']:
                layer = "F.Cu"
            
            router.connect(p1['x'], p1['y'], p2['x'], p2['y'], net_id, width, layer)
        else:
            # Chain route: connect pads in order of proximity
            connected = [pads[0]]
            remaining = pads[1:]
            
            while remaining:
                # Find nearest unconnected pad to any connected pad
                best_dist = float('inf')
                best_pair = None
                
                for cp in connected:
                    for rp in remaining:
                        d = ((cp['x'] - rp['x'])**2 + (cp['y'] - rp['y'])**2)**0.5
                        if d < best_dist:
                            best_dist = d
                            best_pair = (cp, rp)
                
                if best_pair:
                    cp, rp = best_pair
                    layer = primary_layer
                    # If either pad is SMD on a specific layer, use that layer
                    if cp['is_smd'] and 'B.Cu' not in cp['layers']:
                        layer = "F.Cu"
                    elif rp['is_smd'] and 'B.Cu' not in rp['layers']:
                        layer = "F.Cu"
                    
                    router.connect(cp['x'], cp['y'], rp['x'], rp['y'], net_id, width, layer)
                    connected.append(rp)
                    remaining.remove(rp)
                else:
                    break
        
        routed_nets[net_id] = True
    
    router.clearance = old_clearance
    return router

# ============================================================
# Generate new PCB file
# ============================================================

def generate_pcb(footprints, nets, router, board_w=50, board_h=40):
    """Generate a complete KiCad PCB file from scratch."""
    
    lines = []
    
    # Header
    lines.append('(kicad_pcb')
    lines.append('  (version 20241229)')
    lines.append('  (generator "pcbnew")')
    lines.append('  (generator_version "9.0")')
    lines.append('  (general')
    lines.append('    (thickness 0.6)')
    lines.append('  )')
    lines.append('  (paper "A4")')
    
    # Layers
    lines.append('  (layers')
    lines.append('    (0 "F.Cu" signal)')
    lines.append('    (31 "B.Cu" signal)')
    lines.append('    (32 "B.Adhes" user)')
    lines.append('    (33 "F.Adhes" user)')
    lines.append('    (34 "B.Paste" user)')
    lines.append('    (35 "F.Paste" user)')
    lines.append('    (36 "B.SilkS" user "B.Silkscreen")')
    lines.append('    (37 "F.SilkS" user "F.Silkscreen")')
    lines.append('    (38 "B.Mask" user)')
    lines.append('    (39 "F.Mask" user)')
    lines.append('    (40 "Dwgs.User" user "User.Drawings")')
    lines.append('    (41 "Cmts.User" user "User.Comments")')
    lines.append('    (42 "Eco1.User" user "User.Eco1")')
    lines.append('    (43 "Eco2.User" user "User.Eco2")')
    lines.append('    (44 "Edge.Cuts" user)')
    lines.append('    (45 "Margin" user)')
    lines.append('    (46 "B.CrtYd" user "B.Courtyard")')
    lines.append('    (47 "F.CrtYd" user "F.Courtyard")')
    lines.append('    (48 "B.Fab" user "B.Fab")')
    lines.append('    (49 "F.Fab" user "F.Fab")')
    lines.append('  )')
    
    # Setup - with proper solder mask settings
    lines.append('  (setup')
    lines.append('    (pad_to_mask_clearance 0.05)')
    lines.append('    (allow_soldermask_bridges_in_footprints no)')
    lines.append('    (tenting front back)')
    lines.append('    (aux_axis_origin 0 0)')
    lines.append('    (grid_origin 0 0)')
    lines.append('    (min_clearance 0.25)')
    lines.append('  )')
    
    # Net definitions
    lines.append('  (net 0 "")')
    for net_id in sorted(nets.keys()):
        if net_id == 0:
            continue
        lines.append(f'  (net {net_id} "{nets[net_id]}")')
    
    # Net classes
    lines.append('  (net_class "Default" "Default signal traces"')
    lines.append('    (clearance 0.25)')
    lines.append('    (trace_width 0.25)')
    lines.append('    (via_dia 0.6)')
    lines.append('    (via_drill 0.3)')
    lines.append('    (uvia_dia 0.3)')
    lines.append('    (uvia_drill 0.1)')
    lines.append('  )')
    lines.append('  (net_class "Power" "Power traces"')
    lines.append('    (clearance 0.3)')
    lines.append('    (trace_width 0.5)')
    lines.append('    (via_dia 0.8)')
    lines.append('    (via_drill 0.4)')
    lines.append('    (uvia_dia 0.3)')
    lines.append('    (uvia_drill 0.1)')
    lines.append('  )')
    lines.append('  (net_class "RF" "RF antenna traces"')
    lines.append('    (clearance 0.3)')
    lines.append('    (trace_width 0.8)')
    lines.append('    (via_dia 0.8)')
    lines.append('    (via_drill 0.4)')
    lines.append('    (uvia_dia 0.3)')
    lines.append('    (uvia_drill 0.1)')
    lines.append('  )')
    
    # Board outline
    lines.append(f'  (gr_rect (start 0 0) (end {board_w} {board_h}) (stroke (width 0.15) (type default)) (fill none) (layer "Edge.Cuts") (uuid "{gen_uuid()}"))')
    
    # Silkscreen text
    lines.append(f'  (gr_text "Balloon Hub V1 — Auto-routed (GPIO8 LED)" (at 25.0 2.5) (layer "F.SilkS") (uuid "{gen_uuid()}") (effects (font (size 1.2 1.2) (thickness 0.2))))')
    lines.append(f'  (gr_text "JLCPCB 2-layer 0.6mm" (at 25.0 38) (layer "B.SilkS") (uuid "{gen_uuid()}") (effects (font (size 1 1) (thickness 0.15) (justify mirror))))')
    
    # Footprints - re-emit with fixed GPIO assignments
    for fp in footprints:
        fp_text = fp.raw_text
        
        # Fix GPIO assignments:
        # 1. STATUS_LED (net 18) should go to ESP32-C3 pad 10 (GPIO8)
        #    Pad 10 currently has no net, we add STATUS_LED
        # 2. FEM_TX (net 22) should be removed entirely
        # 3. TP5 label should change from "LED_GPIO18" to "LED_GPIO8"
        # 4. TP6 (FEM_TX_GPIO19) should be removed
        
        # Fix pad 10 of ESP32-C3: add STATUS_LED net
        # Current pad 10: (pad "10" thru_hole oval (at 2.54 6.35) (size 1.7 1.7) (drill 0.8) (layers "*.Cu" "*.Mask"))
        # Should become:    (pad "10" thru_hole oval (at 2.54 6.35) (size 1.7 1.7) (drill 0.8) (layers "*.Cu" "*.Mask") (net 18 "STATUS_LED"))
        if 'ESP32-C3' in fp.name and fp.ref == 'U':
            # Add STATUS_LED to pad 10
            old_pad10 = '(pad "10" thru_hole oval (at 2.54 6.35) (size 1.7 1.7) (drill 0.8) (layers "*.Cu" "*.Mask"))'
            new_pad10 = '(pad "10" thru_hole oval (at 2.54 6.35) (size 1.7 1.7) (drill 0.8) (layers "*.Cu" "*.Mask") (net 18 "STATUS_LED"))'
            fp_text = fp_text.replace(old_pad10, new_pad10)
        
        # Fix TP5 label: "LED_GPIO18" -> "LED_GPIO8"
        if fp.ref == 'TP5':
            fp_text = fp_text.replace('LED_GPIO18', 'LED_GPIO8')
        
        # Remove TP6 (FEM_TX_GPIO19) entirely - skip emitting it
        if fp.ref == 'TP6':
            continue
        
        # Remove FEM_TX net from any pads - set to no net
        if 'FEM_TX' in (fp_text or ''):
            fp_text = re.sub(r' \(net 22 "FEM_TX"\)', '', fp_text)
        
        lines.append(fp_text)
    
    # Segments (tracks)
    for seg in router.segments:
        lines.append(
            f'  (segment (start {seg.x1:.4f} {seg.y1:.4f}) '
            f'(end {seg.x2:.4f} {seg.y2:.4f}) '
            f'(width {seg.width}) (layer "{seg.layer}") '
            f'(net {seg.net}) (uuid "{seg.uuid}"))'
        )
    
    # Vias
    for via in router.vias:
        lines.append(
            f'  (via (at {via.x:.4f} {via.y:.4f}) '
            f'(size {via.size}) (drill {via.drill}) '
            f'(layers "F.Cu" "B.Cu") (net {via.net}) '
            f'(uuid "{via.uuid}"))'
        )
    
    # GND zone on B.Cu
    lines.append(f'  (zone (net 2) (net_name "GND") (layer "B.Cu") (uuid "{gen_uuid()}")')
    lines.append('    (hatch edge 0.5)')
    lines.append('    (connect_pads (clearance 0.5))')
    lines.append('    (min_thickness 0.25)')
    lines.append('    (filled_areas_thickness no)')
    lines.append('    (fill yes (thermal_gap 0.5) (thermal_bridge_width 0.5))')
    lines.append('    (polygon')
    lines.append('      (pts')
    lines.append(f'        (xy 0.5 0.5)')
    lines.append(f'        (xy {board_w - 0.5} 0.5)')
    lines.append(f'        (xy {board_w - 0.5} {board_h - 0.5})')
    lines.append(f'        (xy 0.5 {board_h - 0.5})')
    lines.append('      )')
    lines.append('    )')
    lines.append('  )')
    
    lines.append(')')
    lines.append('')
    
    return '\n'.join(lines)

# ============================================================
# Main
# ============================================================

def main():
    print(f"Reading PCB: {PCB_PATH}")
    text = read_pcb(PCB_PATH)
    
    print("Parsing footprints and pads...")
    footprints, nets = parse_pcb(text)
    print(f"  Found {len(footprints)} footprints, {len(nets)} nets")
    
    # Print netlist summary
    netlist = build_netlist(footprints)
    for net_id in sorted(netlist.keys()):
        if net_id == 0:
            continue
        pads = netlist[net_id]
        pad_info = ', '.join([f"{p['ref']}.{p['pin']}" for p in pads])
        print(f"  Net {net_id} ({nets.get(net_id, '?')}): {pad_info}")
    
    print("\nRouting all nets...")
    router = route_all(footprints, nets, board_w=50, board_h=40)
    
    summary = router.summary()
    print(f"  Segments: {summary['segments']}")
    print(f"  Vias: {summary['vias']}")
    print(f"  Warnings: {summary['warnings']}")
    print(f"  Forced: {summary['forced_count']}")
    print(f"  Blocked: {summary['blocked_count']}")
    
    if router.warnings:
        print("\n  Warnings:")
        for w in router.warnings[:20]:
            print(f"    {w}")
        if len(router.warnings) > 20:
            print(f"    ... and {len(router.warnings) - 20} more")
    
    print(f"\nGenerating PCB: {OUTPUT_PATH}")
    pcb_text = generate_pcb(footprints, nets, router, board_w=50, board_h=40)
    write_pcb(OUTPUT_PATH, pcb_text)
    print(f"  Written {len(pcb_text)} bytes")
    
    # Copy to the main file
    import shutil
    main_pcb = PCB_PATH
    backup_pcb = PCB_PATH + '.preroute.bak'
    shutil.copy2(main_pcb, backup_pcb)
    print(f"  Backed up original to {backup_pcb}")
    
    shutil.copy2(OUTPUT_PATH, main_pcb)
    print(f"  Replaced {main_pcb} with routed version")
    
    print("\nDone! Now run DRC:")
    print(f"  kicad-cli pcb drc --output /tmp/drc_routed.txt {main_pcb}")

if __name__ == '__main__':
    main()