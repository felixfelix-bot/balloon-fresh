#!/usr/bin/env python3
"""
Fix hub_board_v1.kicad_pcb:
1. Strip all (segment ...), (via ...), (arc ...) S-expressions (rip up all tracks)
2. Fix GPIO: LED net → GPIO9 (pad 9), remove STATUS_LED from pad 10
3. Remove FEM_TX net (net 22)
4. Remove I2C_SCL net (net 11) from ESP32 pad 8, MS5611 pad 4, and R2
5. Save cleaned .kicad_pcb
6. Export to DSN using kicad-cli
7. Strip wires from DSN (if kicad-cli still includes them)
8. Run Freerouting
9. Verify 0 unrouted nets
"""

import sexpdata
import subprocess
import sys
import os
import re

HARDWARE_DIR = os.path.expanduser("~/repos/balloon-fresh/tracker/hardware")
PCB_FILE = os.path.join(HARDWARE_DIR, "hub_board_v1.kicad_pcb")
PCB_CLEAN = os.path.join(HARDWARE_DIR, "hub_board_v1_clean.kicad_pcb")
DSN_CLEAN = "/tmp/clean_export.dsn"
DSN_ROUTED = "/tmp/routed.dsn"
FREEROUTING_JAR = "/tmp/freerouting.jar"
JAVA_HOME = "/usr/lib/jvm/java-1.25.0-openjdk-amd64"

def is_symbol(obj, name):
    """Check if sexpdata object is a list starting with symbol `name`."""
    if not isinstance(obj, list):
        return False
    if len(obj) == 0:
        return False
    first = obj[0]
    if isinstance(first, sexpdata.Symbol):
        return first.value() == name
    return False

def get_symbol_name(obj):
    """Get the symbol name of a list's first element."""
    if isinstance(obj, list) and len(obj) > 0:
        first = obj[0]
        if isinstance(first, sexpdata.Symbol):
            return first.value()
    return None

def find_net_in_pad(pad):
    """Find the (net N "name") element in a pad definition. Returns the net list or None."""
    for elem in pad:
        if is_symbol(elem, "net"):
            return elem
    return None

def get_pad_number(pad):
    """Get the pad number (as string) from a pad definition."""
    for i, elem in enumerate(pad):
        if is_symbol(pad[0], "pad") and i == 1:
            return str(elem)
    return None

def fix_pcb():
    """Parse, fix, and save the PCB file."""
    print(f"=== Parsing {PCB_FILE} ===")
    with open(PCB_FILE, 'r') as f:
        pcb = sexpdata.load(f)
    
    # The top-level element is (kicad_pcb ...)
    # We need to filter out (segment ...), (via ...), (arc ...) elements
    # These are direct children of the top-level list
    
    removed_segments = 0
    removed_vias = 0
    removed_arcs = 0
    
    new_children = []
    for child in pcb:
        name = get_symbol_name(child)
        if name == "segment":
            removed_segments += 1
            continue
        elif name == "via":
            removed_vias += 1
            continue
        elif name == "arc":
            removed_arcs += 1
            continue
        new_children.append(child)
    
    pcb[:] = new_children
    print(f"  Removed {removed_segments} segments, {removed_vias} vias, {removed_arcs} arcs")
    
    # Now fix GPIO assignments in footprints
    # We need to find the ESP32-C3 footprint and modify its pads
    # Also fix the MS5611, R2 (I2C_SCL pullup), and net definitions
    
    for child in pcb:
        name = get_symbol_name(child)
        if name != "footprint":
            continue
        
        # Get footprint name (first string argument)
        fp_name = None
        for elem in child:
            if isinstance(elem, str):
                fp_name = elem
                break
        
        if fp_name and "ESP32-C3_Mini_V1_Header" in fp_name:
            # Fix ESP32-C3 pads:
            # Pad 9: currently no net → assign STATUS_LED (net 18)
            # Pad 10: currently STATUS_LED → remove net
            # Pad 8: currently I2C_SCL (net 11) → remove net
            for elem in child:
                if is_symbol(elem, "pad"):
                    pad_num = str(elem[1]) if len(elem) > 1 else None
                    if pad_num == "9":
                        # Add STATUS_LED net
                        if not find_net_in_pad(elem):
                            elem.append(sexpdata.Symbol("net"))
                            # Actually, net is (net 18 "STATUS_LED")
                            # Need to insert it as a list
                            elem.pop()  # remove the symbol we just added
                            elem.append([sexpdata.Symbol("net"), 18, "STATUS_LED"])
                            print(f"  ESP32 pad 9: added net 18 STATUS_LED")
                    elif pad_num == "10":
                        # Remove STATUS_LED net
                        for i in range(len(elem)-1, -1, -1):
                            if is_symbol(elem[i], "net"):
                                elem.pop(i)
                                print(f"  ESP32 pad 10: removed STATUS_LED net")
                                break
                    elif pad_num == "8":
                        # Remove I2C_SCL net
                        for i in range(len(elem)-1, -1, -1):
                            if is_symbol(elem[i], "net"):
                                elem.pop(i)
                                print(f"  ESP32 pad 8: removed I2C_SCL net")
                                break
        
        elif fp_name and "PinHeader_1x04" in fp_name:
            # Check if this is MS5611 (U4) by looking at Value property
            is_ms5611 = False
            for elem in child:
                if is_symbol(elem, "property"):
                    if len(elem) > 2 and elem[1] == sexpdata.Symbol("Value"):
                        val = elem[2]
                        if isinstance(val, str) and "MS5611" in val:
                            is_ms5611 = True
            
            if is_ms5611:
                # MS5611 pad 4: remove I2C_SCL net
                for elem in child:
                    if is_symbol(elem, "pad"):
                        pad_num = str(elem[1]) if len(elem) > 1 else None
                        if pad_num == "4":
                            for i in range(len(elem)-1, -1, -1):
                                if is_symbol(elem[i], "net"):
                                    elem.pop(i)
                                    print(f"  MS5611 (U4) pad 4: removed I2C_SCL net")
                                    break
    
    # Fix net definitions: remove I2C_SCL (net 11) and FEM_TX (net 22)
    # Also update the class definition
    nets_to_remove = {11: "I2C_SCL", 22: "FEM_TX"}
    
    new_children = []
    for child in pcb:
        name = get_symbol_name(child)
        if name == "net":
            # (net N "name")
            net_num = child[1] if len(child) > 1 else None
            if net_num in nets_to_remove:
                print(f"  Removed net {net_num} ({nets_to_remove[net_num]})")
                continue
        elif name == "net_class":
            # Remove I2C_SCL and FEM_TX from class member lists
            for elem in child:
                if isinstance(elem, str):
                    if elem == "I2C_SCL":
                        # Replace with empty or skip
                        pass
                    if elem == "FEM_TX":
                        pass
            # Filter out I2C_SCL and FEM_TX from the class
            filtered = []
            for elem in child:
                if isinstance(elem, str) and elem in ("I2C_SCL", "FEM_TX"):
                    print(f"  Removed '{elem}' from net_class")
                    continue
                filtered.append(elem)
            child[:] = filtered
        new_children.append(child)
    pcb[:] = new_children
    
    # Also remove R2 (I2C_SCL pullup resistor) since I2C_SCL is removed
    # And remove TP6 (FEM_TX test point) since FEM_TX is removed
    new_children = []
    for child in pcb:
        name = get_symbol_name(child)
        if name != "footprint":
            new_children.append(child)
            continue
        
        # Check for R2 or TP6
        ref = None
        for elem in child:
            if is_symbol(elem, "property"):
                if len(elem) > 1 and elem[1] == sexpdata.Symbol("Reference"):
                    ref = elem[2] if len(elem) > 2 else None
        
        if ref and ref == "R2":
            print(f"  Removed R2 (I2C_SCL pullup)")
            continue
        if ref and ref == "TP6":
            print(f"  Removed TP6 (FEM_TX test point)")
            continue
        
        new_children.append(child)
    pcb[:] = new_children
    
    # Update silkscreen text
    for child in pcb:
        name = get_symbol_name(child)
        if name == "gr_text":
            for elem in child:
                if isinstance(elem, str) and "GPIO" in elem:
                    # Replace with new text
                    idx = child.index(elem)
                    child[idx] = "Balloon Hub V1 — Auto-route (GPIO9 LED)"
                    print(f"  Updated silkscreen text")
    
    # Save
    print(f"\n=== Saving cleaned PCB to {PCB_CLEAN} ===")
    with open(PCB_CLEAN, 'w') as f:
        sexpdata.dump(pcb, f)
    print(f"  Saved successfully")
    
    # Verify: count segments, vias in saved file
    with open(PCB_CLEAN, 'r') as f:
        content = f.read()
    seg_count = content.count("(segment")
    via_count = content.count("(via ")
    arc_count = content.count("(arc ")
    print(f"  Verification: {seg_count} segments, {via_count} vias, {arc_count} arcs in cleaned file")
    
    return True


def export_dsn():
    """Export cleaned PCB to DSN using kicad-cli."""
    print(f"\n=== Exporting DSN from {PCB_CLEAN} ===")
    # kicad-cli pcb export dsn --output <output> <input>
    cmd = [
        "kicad-cli", "pcb", "export", "dsn",
        "--output", DSN_CLEAN,
        PCB_CLEAN
    ]
    print(f"  Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ERROR: kicad-cli failed: {result.stderr}")
        return False
    print(f"  DSN exported to {DSN_CLEAN}")
    print(f"  stdout: {result.stdout[:200]}")
    return True


def strip_wires_from_dsn():
    """Remove all (wire ...) and (via ...) lines from the DSN file's network section."""
    print(f"\n=== Stripping wires from DSN ===")
    with open(DSN_CLEAN, 'r') as f:
        lines = f.readlines()
    
    new_lines = []
    in_network = False
    removed_wires = 0
    removed_vias = 0
    
    for line in lines:
        stripped = line.strip()
        if stripped == "(network":
            in_network = True
        elif stripped == ")" and in_network:
            in_network = False
        
        if in_network:
            if stripped.startswith("(wire "):
                removed_wires += 1
                continue
            if stripped.startswith("(via "):
                removed_vias += 1
                continue
        
        new_lines.append(line)
    
    with open(DSN_CLEAN, 'w') as f:
        f.writelines(new_lines)
    
    print(f"  Removed {removed_wires} wires, {removed_vias} vias from DSN")
    return True


def run_freerouting():
    """Run Freerouting auto-router."""
    print(f"\n=== Running Freerouting ===")
    env = os.environ.copy()
    env["JAVA_HOME"] = JAVA_HOME
    
    cmd = [
        "xvfb-run", "-a",
        f"{JAVA_HOME}/bin/java", "-jar", FREEROUTING_JAR,
        "-de", DSN_CLEAN,
        "-do", DSN_ROUTED,
        "-mp", "20"
    ]
    print(f"  Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=300)
    
    print(f"  Exit code: {result.returncode}")
    print(f"  stdout (last 500): {result.stdout[-500:]}")
    print(f"  stderr (last 500): {result.stderr[-500:]}")
    
    if not os.path.exists(DSN_ROUTED):
        print(f"  ERROR: Output file {DSN_ROUTED} not created!")
        return False
    
    return True


def verify_routed():
    """Verify the routed DSN has 0 unrouted nets."""
    print(f"\n=== Verifying routed DSN ===")
    if not os.path.exists(DSN_ROUTED):
        print(f"  ERROR: {DSN_ROUTED} does not exist")
        return False
    
    with open(DSN_ROUTED, 'r') as f:
        content = f.read()
    
    # Count unrouted nets
    unrouted = re.findall(r'\(unrouted\s+(\w+)', content)
    # Also check for "unrouted" in net names
    unrouted_nets = re.findall(r'\(net\s+(\S+)\s*\n\s*\(type\s+unrouted\)', content)
    # Check for any "(type unrouted)" entries
    type_unrouted = re.findall(r'\(type\s+unrouted\)', content)
    
    # Count wires (routed connections)
    wire_count = content.count("(wire ")
    via_count = content.count("(via ")
    
    print(f"  Wires in routed DSN: {wire_count}")
    print(f"  Vias in routed DSN: {via_count}")
    print(f"  Unrouted net references: {len(unrouted)}")
    print(f"  Type unrouted entries: {len(type_unrouted)}")
    
    if type_unrouted:
        # Find which nets are unrouted
        # Look for patterns like: (net NETNAME ... (type unrouted))
        net_section = re.findall(r'\(net\s+(\S+)\s*\n\s*\((?:pins|wire|via).*?\n.*?\(type\s+unrouted\)', content, re.DOTALL)
        print(f"  Unrouted nets found: {net_section}")
    
    if len(type_unrouted) == 0:
        print(f"  ✓ All nets routed!")
        return True
    else:
        print(f"  ✗ {len(type_unrouted)} unrouted entries found")
        return False


def main():
    print("=" * 60)
    print("Freerouting Auto-Router Pipeline Fix")
    print("=" * 60)
    
    # Step 1-4: Fix PCB
    if not fix_pcb():
        print("FAILED: Could not fix PCB")
        sys.exit(1)
    
    # Step 5: Export DSN
    if not export_dsn():
        print("FAILED: Could not export DSN")
        sys.exit(1)
    
    # Step 5b: Strip wires from DSN (in case kicad-cli includes them)
    if not strip_wires_from_dsn():
        print("FAILED: Could not strip wires from DSN")
        sys.exit(1)
    
    # Step 6: Run Freerouting
    if not run_freerouting():
        print("FAILED: Freerouting did not produce output")
        sys.exit(1)
    
    # Step 7: Verify routed DSN
    if not verify_routed():
        print("WARNING: Some nets may be unrouted")
    
    print("\n" + "=" * 60)
    print("Pipeline complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()