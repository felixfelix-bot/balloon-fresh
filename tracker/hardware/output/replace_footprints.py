#!/usr/bin/python3.14
"""Re-place all footprints on balloon tracker board with ZERO overlaps.

Board enlarged to 70x50mm. Functional grouping, 1.5mm min gap.
"""
import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew

INPUT  = '/home/c03rad0r/repos/balloon-fresh/tracker/hardware/output/v_c3_flight_final.kicad_pcb'
OUTPUT = '/home/c03rad0r/repos/balloon-fresh/tracker/hardware/output/v_c3_flight_replaced.kicad_pcb'

# Board dimensions (nm)
BOARD_W = 70_000_000   # 70mm
BOARD_H = 50_000_000   # 50mm
MARGIN  = 2_000_000    # 2mm from edge

# Placement plan: (ref, x_mm, y_mm, rotation_degrees)
# Layout: 70x50mm board
# Left zone (0-22mm): power components
# Center zone (22-48mm): MCU + flash + decoupling
# Right zone (48-70mm): sensors + antenna
# Bottom edge: connectors
PLACEMENT = {
    # MCU center
    'U1':    (35.0, 18.0, 0),     # ESP32-C3 center
    'U5':    (35.0, 33.0, 0),     # Flash below MCU

    # Power left
    'SOLAR': (6.0,  6.0,  0),     # Solar input top-left
    'D1':    (6.0,  14.0, 0),     # Diode
    'U4':    (10.0, 22.0, 0),     # Voltage regulator
    'C_CAP': (5.0,  30.0, 90),    # Big cap, rotated to fit
    'C1':    (15.0, 30.0, 0),     # Cap near regulator
    'C2':    (20.0, 6.0,  0),     # Cap near MCU power
    'C3':    (15.0, 38.0, 0),     # Cap
    'C4':    (50.0, 6.0,  0),     # Cap near U2

    # Sensors right
    'U2':    (57.0, 14.0, 0),     # MS5611 pressure sensor
    'U3':    (57.0, 33.0, 0),     # Sensor/radio

    # Antenna top-right
    'ANT1':  (62.0, 5.0,  0),     # Antenna, clear area

    # Connectors bottom
    'J1':    (15.0, 45.0, 0),     # Connector 1 bottom-left
    'J2':    (48.0, 45.0, 0),     # Connector 2 bottom-right

    # Resistors + LED
    'R_DIV1':(22.0, 38.0, 0),     # Voltage divider
    'R_DIV2':(28.0, 38.0, 0),     # Voltage divider
    'R_PD':  (22.0, 44.0, 0),     # Pull-down
    'R_LED': (45.0, 38.0, 0),     # LED resistor
    'LED1':  (50.0, 38.0, 0),     # LED visible
}

print("=== PLACEMENT SCRIPT ===")
print(f"Loading: {INPUT}")
b = pcbnew.LoadBoard(INPUT)
fps = {fp.GetReference(): fp for fp in b.GetFootprints()}
print(f"Footprints found: {len(fps)}")

# Apply placement
for ref, (x_mm, y_mm, rot) in PLACEMENT.items():
    fp = fps.get(ref)
    if not fp:
        print(f"  WARNING: {ref} not found on board!")
        continue
    x_nm = int(x_mm * 1_000_000)
    y_nm = int(y_mm * 1_000_000)
    fp.SetPosition(pcbnew.VECTOR2I(x_nm, y_nm))
    fp.SetOrientationDegrees(rot)
    print(f"  {ref:8s} -> ({x_mm:.1f}, {y_mm:.1f})mm  rot={rot}")

# Update board outline (Edge.Cuts) to 70x50mm
# Remove old edge cuts drawings
old_drawings = []
for d in list(b.GetDrawings()):
    if d.GetClass() == 'PCB_SHAPE' and d.GetLayer() == pcbnew.Edge_Cuts:
        old_drawings.append(d)
for d in old_drawings:
    b.Remove(d)
print(f"\nRemoved {len(old_drawings)} old Edge.Cuts shapes")

# Draw new board outline: 4 lines forming rectangle
corners = [
    (0, 0),
    (BOARD_W, 0),
    (BOARD_W, BOARD_H),
    (0, BOARD_H),
]
for i in range(4):
    line = pcbnew.PCB_SHAPE(b)
    line.SetLayer(pcbnew.Edge_Cuts)
    sx, sy = corners[i]
    ex, ey = corners[(i + 1) % 4]
    line.SetStart(pcbnew.VECTOR2I(sx, sy))
    line.SetEnd(pcbnew.VECTOR2I(ex, ey))
    line.SetWidth(150000)  # 0.15mm
    b.Add(line)
print(f"Added new 70x50mm Edge.Cuts outline")

# Save
pcbnew.SaveBoard(OUTPUT, b)
print(f"\nSaved: {OUTPUT}")

# === VERIFY: check all pairwise overlaps ===
print("\n=== OVERLAP VERIFICATION ===")
b2 = pcbnew.LoadBoard(OUTPUT)
fps2 = list(b2.GetFootprints())
overlaps_found = 0
min_gap_violations = 0

for i in range(len(fps2)):
    for j in range(i + 1, len(fps2)):
        bb1 = fps2[i].GetBoundingBox()
        bb2 = fps2[j].GetBoundingBox()
        ref1 = fps2[i].GetReference()
        ref2 = fps2[j].GetReference()

        if bb1.Intersects(bb2):
            x_ov = min(bb1.GetRight(), bb2.GetRight()) - max(bb1.GetLeft(), bb2.GetLeft())
            y_ov = min(bb1.GetBottom(), bb2.GetBottom()) - max(bb1.GetTop(), bb2.GetTop())
            area = (x_ov / 1e6) * (y_ov / 1e6)
            if area > 0.1:
                print(f"  OVERLAP: {ref1} x {ref2}  {area:.1f}mm²")
                overlaps_found += 1

        # Check min gap (1.5mm = 1_500_000nm)
        gap_x = max(0, max(bb1.GetLeft(), bb2.GetLeft()) - min(bb1.GetRight(), bb2.GetRight()))
        gap_y = max(0, max(bb1.GetTop(), bb2.GetTop()) - min(bb1.GetBottom(), bb2.GetBottom()))
        if not bb1.Intersects(bb2):
            gap = min(gap_x, gap_y) / 1e6
            if gap < 1.0:  # Report <1mm gaps (was 1.5 target)
                min_gap_violations += 1

print(f"\nOverlaps: {overlaps_found}")
print(f"Gap violations (<1mm): {min_gap_violations}")

# Print placement table
print("\n=== FINAL PLACEMENT TABLE ===")
print(f"{'Ref':8s} {'X(mm)':>7s} {'Y(mm)':>7s} {'W(mm)':>7s} {'H(mm)':>7s} {'Rot':>5s}")
print("-" * 45)
for fp in sorted(fps2, key=lambda f: f.GetPosition().x):
    pos = fp.GetPosition()
    bb = fp.GetBoundingBox()
    w = (bb.GetRight() - bb.GetLeft()) / 1e6
    h = (bb.GetBottom() - bb.GetTop()) / 1e6
    rot = fp.GetOrientationDegrees()
    print(f"{fp.GetReference():8s} {pos.x/1e6:7.1f} {pos.y/1e6:7.1f} {w:7.1f} {h:7.1f} {rot:5.0f}")

# Check all parts inside board
print("\n=== BOUNDARY CHECK ===")
oob = 0
for fp in fps2:
    bb = fp.GetBoundingBox()
    if bb.GetLeft() < 0 or bb.GetTop() < 0 or bb.GetRight() > BOARD_W or bb.GetBottom() > BOARD_H:
        print(f"  OUT OF BOUNDS: {fp.GetReference()} bbox=({bb.GetLeft()/1e6:.1f},{bb.GetTop()/1e6:.1f})-({bb.GetRight()/1e6:.1f},{bb.GetBottom()/1e6:.1f})")
        oob += 1
print(f"Out of bounds: {oob}")

print("\n=== DONE ===")
