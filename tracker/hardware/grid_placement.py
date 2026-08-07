#!/usr/bin/env python3.14
"""Grid placement: move all 30 footprints to non-overlapping positions on 50x40mm board."""
import pcbnew
import sys

BOARD = "hub_board_v1_4layer.kicad_pcb"
OUT = "hub_board_v1_placed.kicad_pcb"

# Placement map: ref -> (x_mm, y_mm, rotation_degrees)
# Board: 50x40mm. Big parts first, small parts fill gaps.
PLACEMENT = {
    # --- BIG PARTS ---
    # ESP32-C3: 18x25mm — left-center, moved down for U1 clearance
    "U":     (12.0, 18.0, 0),
    # Radio module: 11x43mm — MUST rotate 90°, moved up slightly
    "U1":    (17.0,  6.0, 90),
    # U2 (sensor/LR2021): 22x20mm — right-center, moved left to avoid U4
    "U2":    (34.0, 22.0, 0),
    # USB-C: 7x15mm — left edge connector
    "U3":    ( 3.5, 18.0, 0),
    # U4: 5x15mm — right edge, pushed out to avoid U2 pad overlap
    "U4":    (47.0, 22.0, 0),

    # --- CONNECTORS ---
    # Solar connector: 5x12mm — bottom-left, moved up to stay in bounds
    "SC":    ( 5.0, 33.5, 0),
    # J: 3x9mm — top-left edge
    "J":     ( 3.0,  8.0, 0),

    # --- LED + DIODES ---
    "U5":    (12.0, 35.0, 0),  # LED near power input
    "D1":    ( 8.0, 30.0, 0),  # Solar diode
    "D2":    (18.0, 34.0, 0),  # LED diode

    # --- ANTENNAS (top edge, right side, away from copper) ---
    "AE1":   (47.0,  3.0, 0),
    "AE2":   (47.0,  8.0, 0),  # will check overlap, may need reposition

    # --- CAPS (near ICs) ---
    # C1 near U (ESP32) power pins
    "C1":    ( 6.0,  4.0, 0),
    # C2 near U1 (radio)
    "C2":    (38.0,  4.0, 0),
    # C3, C4 near U2
    "C3":    (30.0, 30.0, 0),
    "C4":    (33.0, 33.0, 0),
    # C5 bottom strip, away from all ICs
    "C5":    (20.0, 38.0, 0),
    # C6 near U4
    "C6":    (42.0, 30.0, 0),
    # C7 bottom strip, away from all ICs
    "C7":    (16.0, 38.0, 0),

    # --- RESISTORS ---
    "R1":    (42.0, 14.0, 0),  # I2C pullup near U4
    "R2":    (42.0, 17.0, 0),  # near U4
    "R3":    (20.0, 30.0, 0),  # VCAP divider
    "R4":    (23.0, 30.0, 0),  # GND side of divider
    "R5":    (22.0, 34.0, 0),  # LED resistor

    # --- TEST POINTS (bottom edge row) ---
    "TP1":   (25.0, 38.0, 0),
    "TP2":   (29.0, 38.0, 0),
    "TP3":   (33.0, 38.0, 0),
    "TP4":   (37.0, 38.0, 0),
    "TP5":   (40.0, 38.0, 0),
    "TP6":   (45.0, 38.0, 0),
}

b = pcbnew.LoadBoard(BOARD)
fps = {fp.GetReference(): fp for fp in b.GetFootprints()}

print(f"Loaded {len(fps)} footprints")
missing = set(PLACEMENT) - set(fps)
extra = set(fps) - set(PLACEMENT)
if missing:
    print(f"WARNING: placement defined but not on board: {missing}")
if extra:
    print(f"WARNING: on board but no placement defined: {extra}")

# Apply positions
for ref, (x, y, rot) in PLACEMENT.items():
    if ref not in fps:
        continue
    fp = fps[ref]
    pos = pcbnew.VECTOR2I(int(x * 1e6), int(y * 1e6))
    fp.SetPosition(pos)
    if rot:
        fp.SetOrientationDegrees(rot)

# Remove ALL tracks and vias — clean slate for routing
tracks = list(b.GetTracks())
print(f"Removing {len(tracks)} tracks/vias")
for t in tracks:
    b.Remove(t)

# Skip zone removal — KiCad 9 API for zones is finicky
# Zones will be handled in the routing step
print("Skipping zone removal (handled later)")

# Save
pcbnew.SaveBoard(OUT, b)
print(f"Saved to {OUT}")

# ===== VERIFY =====
b2 = pcbnew.LoadBoard(OUT)
fps2 = list(b2.GetFootprints())
print(f"\n=== VERIFICATION ===")
print(f"Footprints: {len(fps2)}")

# Check bounding box overlaps
overlaps = 0
for i, f1 in enumerate(fps2):
    r1 = f1.GetBoundingBox()
    for j, f2 in enumerate(fps2):
        if j <= i:
            continue
        r2 = f2.GetBoundingBox()
        if r1.Intersects(r2):
            overlaps += 1
            p1 = f1.GetPosition()
            p2 = f2.GetPosition()
            print(f"  OVERLAP: {f1.GetReference()}({p1.x/1e6:.1f},{p1.y/1e6:.1f}) x {f2.GetReference()}({p2.x/1e6:.1f},{p2.y/1e6:.1f})")
print(f"Bbox overlaps: {overlaps}")

# Check pad overlaps between footprints
pad_overlaps = 0
for i, f1 in enumerate(fps2):
    for p1 in f1.Pads():
        b1 = p1.GetBoundingBox()
        for j, f2 in enumerate(fps2):
            if j <= i:
                continue
            for p2 in f2.Pads():
                b2 = p2.GetBoundingBox()
                if b1.Intersects(b2):
                    pad_overlaps += 1
print(f"Pad overlaps between footprints: {pad_overlaps}")

# Check all within bounds
oob = 0
for fp in fps2:
    bb = fp.GetBoundingBox()
    if bb.GetLeft() < 0 or bb.GetTop() < 0 or bb.GetRight() > 50e6 or bb.GetBottom() > 40e6:
        oob += 1
        p = fp.GetPosition()
        print(f"  OUT OF BOUNDS: {fp.GetReference()}({p.x/1e6:.1f},{p.y/1e6:.1f}) bb=({bb.GetLeft()/1e6:.1f},{bb.GetTop()/1e6:.1f})-({bb.GetRight()/1e6:.1f},{bb.GetBottom()/1e6:.1f})")
print(f"Out of bounds: {oob}")

print(f"\nCopper layers: {b2.GetCopperLayerCount()}")
print(f"Tracks: {len(list(b2.GetTracks()))}")
print(f"Zones: {len(list(b2.GetZones()))}")
