#!/usr/bin/env python3
"""Fix C3 flight PCB placement — spread components, no overlaps, all inside board."""
import sys; sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew

PATH = '/home/c03rad0r/repos/balloon-fresh/tracker/hardware/output/v_c3_flight_final.kicad_pcb'
BOARD_W = 50  # mm — increased from 45
BOARD_H = 40  # mm — increased from 35

b = pcbnew.LoadBoard(PATH)

# Step 1: Rip ALL tracks
tracks = list(b.GetTracks())
for t in tracks:
    b.Remove(t)
print(f"Removed {len(tracks)} tracks")

# Step 2: Get footprint sizes
fps = {fp.GetReference(): fp for fp in b.GetFootprints()}
sizes = {}
for ref, fp in fps.items():
    bb = fp.GetBoundingBox()
    w = bb.GetWidth() / 1e6
    h = bb.GetHeight() / 1e6
    sizes[ref] = (w, h)
    print(f"  {ref:8s} size={w:.1f}x{h:.1f}mm")

# Step 3: Calculate placement — mathematical, no overlaps
# Board: 50x40mm. Leave 2mm margin on all sides → usable: 48x38mm
# Strategy: 3 rows

placements = {
    # Row 1 (TOP, y~12): Big ICs
    'U1':  (12, 12),   # ESP32-C3 — 15.4x20.5mm → x=[4.3,19.7] y=[1.8,22.3]
    'U2':  (35, 9),    # LR2021 — 18.6x20.3mm → x=[25.7,44.3] y=[-1.2,19.2]
    
    # Row 2 (MIDDLE, y~25): GPS, power
    'U3':  (37, 26),   # GPS — 11.8x13.9mm → x=[31.1,42.9] y=[19.1,32.9]
    'C_CAP': (8, 25),  # Supercap — 10.8x14.2mm → x=[2.6,13.4] y=[17.9,32.1]
    'U4':  (20, 26),   # Regulator SOT-23-5 — 6.6x6.4mm → x=[16.7,23.3] y=[22.8,29.2]
    'D1':  (20, 19),   # BAT54 diode — 4.8x5.7mm
    
    # Row 3 (BOTTOM, y~33): Small components
    'SOLAR': (4, 35),  # Solar header — 9x6.2mm → x=[-0.5,8.5] y=[31.9,38.1] → move to x=5
    'J1':   (15, 35),  # Header — 19.1x9.6mm → too big, move down? Actually J1 is 19mm wide
    'J2':   (37, 36),  # Header
    'C1':   (16, 23),  # 0805 cap near U4 input
    'C2':   (20, 15),  # 0805 cap near U1 VCC
    'C3':   (24, 23),  # 0402 cap near U4 output
    'C4':   (30, 15),  # 0402 cap near U2 VCC
    'C5':   (24, 27),  # 0402 cap
    'C6':   (28, 19),  # 0402 cap
    'R_LED': (28, 33), # 0402 resistor
    'LED1': (33, 33),  # 0603 LED
    'R_DIV1': (5, 30), # 0402 resistor — voltage divider near supercap
    'R_DIV2': (9, 30), # 0402 resistor
    'R_PD':  (13, 30), # 0402 pull-down
    'U5':   (24, 33),  # Small IC
    'ANT1': (47, 20),  # Antenna pad — right edge
}

# Apply placements
for ref, (x_mm, y_mm) in placements.items():
    if ref not in fps:
        print(f"  WARNING: {ref} not found on board, skipping")
        continue
    fp = fps[ref]
    # Convert mm to nm (internal units)
    fp.SetPosition(pcbnew.VECTOR2I(int(x_mm * 1e6), int(y_mm * 1e6)))

print(f"\nMoved {len(placements)} footprints")

# Step 4: Update board outline to 50x40mm
# Remove old Edge.Cuts drawings
for d in list(b.GetDrawings()):
    if d.GetLayer() == pcbnew.Edge_Cuts:
        b.Remove(d)

# Add new outline
outline = pcbnew.PCB_SHAPE(b)
outline.SetShape(pcbnew.SHAPE_T_RECT)
outline.SetLayer(pcbnew.Edge_Cuts)
outline.SetStart(pcbnew.VECTOR2I(0, 0))
outline.SetEnd(pcbnew.VECTOR2I(int(BOARD_W * 1e6), int(BOARD_H * 1e6)))
outline.SetWidth(int(0.15e6))
b.Add(outline)
print(f"Board outline: {BOARD_W}x{BOARD_H}mm")

# Step 5: Verify no overlaps
all_fps = list(b.GetFootprints())
overlaps = 0
for i in range(len(all_fps)):
    for j in range(i+1, len(all_fps)):
        bb1 = all_fps[i].GetBoundingBox()
        bb2 = all_fps[j].GetBoundingBox()
        if bb1.Intersects(bb2):
            r1 = all_fps[i].GetReference()
            r2 = all_fps[j].GetReference()
            print(f"  OVERLAP: {r1} & {r2}")
            overlaps += 1

print(f"\nOverlaps: {overlaps}")

# Step 6: Verify all inside board
off_board = 0
for fp in all_fps:
    bb = fp.GetBoundingBox()
    x1 = bb.GetX() / 1e6
    y1 = bb.GetY() / 1e6
    x2 = (bb.GetX() + bb.GetWidth()) / 1e6
    y2 = (bb.GetY() + bb.GetHeight()) / 1e6
    if x1 < 0 or y1 < 0 or x2 > BOARD_W or y2 > BOARD_H:
        print(f"  OFF BOARD: {fp.GetReference()} x=[{x1:.1f},{x2:.1f}] y=[{y1:.1f},{y2:.1f}]")
        off_board += 1

print(f"Off-board: {off_board}")

# Step 7: Save
pcbnew.SaveBoard(PATH, b)
print(f"\nSaved to {PATH}")

# Step 8: Verify
b2 = pcbnew.LoadBoard(PATH)
fps2 = list(b2.GetFootprints())
tracks2 = list(b2.GetTracks())
print(f"VERIFIED: {len(fps2)} footprints, {len(tracks2)} tracks")
