#!/usr/bin/env python3.14
"""Import Freerouting tracks + refill GND copper pour zone."""

import sys, re, math
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew

BOARD_PATH = '/home/c03rad0r/repos/balloon-fresh/tracker/hardware/hub_board_v1_clean.kicad_pcb'
DSN_PATH = '/tmp/routed_output.dsn'
OUTPUT_PATH = '/home/c03rad0r/repos/balloon-fresh/tracker/hardware/output/v1_freerouted_final.kicad_pcb'

print("Loading board...")
b = pcbnew.LoadBoard(BOARD_PATH)
print(f"Tracks: {len(b.GetTracks())}")

# Get nets from pads
nets = {}
for fp in b.GetFootprints():
    for pad in fp.Pads():
        net = pad.GetNet()
        if net:
            name = net.GetNetname()
            if name and name not in nets:
                nets[name] = net
print(f"Nets: {len(nets)}")

# Import Freerouting tracks (non-flipped Y)
print("Parsing Freerouting DSN...")
with open(DSN_PATH) as f:
    dsn = f.read()
wiring = dsn[dsn.find('(wiring'):]
wire_pattern = r'\(wire\s+\(polyline_path\s+(\S+)\s+([\d.]+)\s+([\d.\s\-]+?)\)\s*\(net\s+"?([^"\s\)]+)"?\s+\d+\)'
matches = re.findall(wire_pattern, wiring)
print(f"DSN wire segments: {len(matches)}")

layer_map = {'F.Cu': pcbnew.F_Cu, 'B.Cu': pcbnew.B_Cu}
track_count = 0
skipped = 0

for layer_str, width_str, coords_str, net_name in matches:
    if layer_str not in layer_map:
        continue
    coords = coords_str.split()
    if len(coords) < 4:
        continue
    points = []
    for i in range(0, len(coords), 2):
        try:
            x = int(float(coords[i]) * 1000)
            y = int(float(coords[i+1]) * 1000)
            points.append((x, y))
        except (ValueError, IndexError):
            break
    for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i+1]
        if abs(x2-x1) < 1000 and abs(y2-y1) < 1000:
            skipped += 1
            continue
        track = pcbnew.PCB_TRACK(b)
        track.SetStart(pcbnew.VECTOR2I(x1, y1))
        track.SetEnd(pcbnew.VECTOR2I(x2, y2))
        track.SetLayer(layer_map[layer_str])
        track.SetWidth(int(float(width_str) * 1000))
        clean_name = net_name.replace('"', '')
        if clean_name in nets:
            track.SetNet(nets[clean_name])
        b.Add(track)
        track_count += 1

print(f"Added {track_count} tracks (skipped {skipped} zero-length)")

# Refill GND copper pour zone
print("Refilling zones...")
zones = b.Zones()
print(f"Zones found: {len(zones)}")
for zone in zones:
    netname = zone.GetNetname() if hasattr(zone, 'GetNetname') else "?"
    layer = zone.GetLayerName()
    print(f"  Zone: layer={layer} net={netname}")
    zone.SetIsFilled(True)

# Use ZONE_FILLER to actually fill
filler = pcbnew.ZONE_FILLER(b)
filler.Fill(zones)

b.BuildConnectivity()

# Save
print(f"Saving to {OUTPUT_PATH}...")
pcbnew.SaveBoard(OUTPUT_PATH, b)
print("Done!")
print(f"Final tracks: {len(b.GetTracks())}, zones: {len(b.Zones())}")
