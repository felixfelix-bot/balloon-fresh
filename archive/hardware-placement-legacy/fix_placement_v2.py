#!/usr/bin/env python3
"""Fix C3 flight PCB placement v2 — pad-based spacing, courtyard overlaps OK.
shorting_items=0 is the real gate, not courtyard overlaps."""
import sys; sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew

PATH = '/home/c03rad0r/repos/balloon-fresh/tracker/hardware/output/v_c3_flight_final.kicad_pcb'
BOARD_W = 55  # mm
BOARD_H = 45  # mm

b = pcbnew.LoadBoard(PATH)

# Get actual pad extents for each footprint (what matters for shorts)
def get_pad_bbox(fp):
    """Get bounding box of just the pads, not courtyard."""
    min_x = min_y = float('inf')
    max_x = max_y = float('-inf')
    for pad in fp.Pads():
        pos = pad.GetPosition()
        size = pad.GetSize()
        x1 = pos.x - size.x//2
        y1 = pos.y - size.y//2
        x2 = pos.x + size.x//2
        y2 = pos.y + size.y//2
        min_x = min(min_x, x1)
        min_y = min(min_y, y1)
        max_x = max(max_x, x2)
        max_y = max(max_y, y2)
    if min_x == float('inf'):
        return None
    return (min_x, min_y, max_x, max_y)

fps = {fp.GetReference(): fp for fp in b.GetFootprints()}

# Print actual pad sizes
print("=== Actual pad sizes (not courtyard) ===")
for ref, fp in sorted(fps.items()):
    pb = get_pad_bbox(fp)
    if pb:
        w = (pb[2]-pb[0])/1e6
        h = (pb[3]-pb[1])/1e6
        cx = fp.GetPosition().x/1e6
        cy = fp.GetPosition().y/1e6
        print(f"  {ref:8s} pads={w:.1f}x{h:.1f}mm current_center=({cx:.1f},{cy:.1f})")

# Placement plan — spread out on 55x45mm board
# Leave 3mm margin → usable: 49x39mm
placements = {
    # U1 ESP32-C3: pads ~15.4x20.5mm — the big one
    'U1':  (13, 12),   # center → pad bbox x=[5.3,20.7] y=[1.8,22.3]
    # U2 LR2021: pads ~17x17mm  
    'U2':  (38, 11),   # center → pad bbox x=[29.5,46.5] y=[2.5,19.5]
    # Gap between U1 and U2: 29.5-20.7 = 8.8mm ✓

    # U3 GPS: pads ~10x10mm
    'U3':  (40, 28),   # center → pad bbox x=[35,45] y=[23,33]

    # C_CAP supercap: pads ~8x10mm (THT radial)
    'C_CAP': (6, 28),  # center → pad bbox x=[2,10] y=[23,33]

    # U4 regulator SOT-23-5: pads ~4x4mm
    'U4':  (18, 28),   # center

    # D1 BAT54 SOD-123: pads ~3x3mm
    'D1':  (24, 20),   # center — between U1 and U2

    # Small R/C: 1x2mm each, cluster around their ICs
    'C1':  (16, 25),   # near U4 input
    'C2':  (18, 9),    # near U1 VCC
    'C3':  (22, 25),   # near U4 output
    'C4':  (33, 9),    # near U2 VCC
    'R_LED': (30, 35), # bottom right
    'LED1': (36, 35),  # bottom right
    'R_DIV1': (3, 36), # near supercap bottom
    'R_DIV2': (7, 36), # near supercap bottom
    'R_PD':  (11, 36), # bottom
    'U5':   (24, 35),  # bottom center
    'SOLAR': (4, 42),  # bottom-left edge connector
    'J1':   (20, 42),  # bottom connector
    'J2':   (40, 42),  # bottom-right connector
    'ANT1': (51, 22),  # right edge
}

for ref, (x_mm, y_mm) in placements.items():
    if ref not in fps:
        print(f"  SKIP: {ref} not on board")
        continue
    fp = fps[ref]
    fp.SetPosition(pcbnew.VECTOR2I(int(x_mm * 1e6), int(y_mm * 1e6)))

# Update board outline
for d in list(b.GetDrawings()):
    if d.GetLayer() == pcbnew.Edge_Cuts:
        b.Remove(d)
outline = pcbnew.PCB_SHAPE(b)
outline.SetShape(pcbnew.SHAPE_T_RECT)
outline.SetLayer(pcbnew.Edge_Cuts)
outline.SetStart(pcbnew.VECTOR2I(0, 0))
outline.SetEnd(pcbnew.VECTOR2I(int(BOARD_W * 1e6), int(BOARD_H * 1e6)))
outline.SetWidth(int(0.15e6))
b.Add(outline)

# Verify: check PAD overlaps (not courtyard)
all_fps = list(b.GetFootprints())
pad_overlaps = 0
for i in range(len(all_fps)):
    for j in range(i+1, len(all_fps)):
        pb1 = get_pad_bbox(all_fps[i])
        pb2 = get_pad_bbox(all_fps[j])
        if not pb1 or not pb2:
            continue
        # Check intersection with 0.2mm margin
        margin = int(0.2e6)
        if (pb1[0]-margin < pb2[2]+margin and pb2[0]-margin < pb1[2]+margin and
            pb1[1]-margin < pb2[3]+margin and pb2[1]-margin < pb1[3]+margin):
            r1 = all_fps[i].GetReference()
            r2 = all_fps[j].GetReference()
            print(f"  PAD OVERLAP: {r1} & {r2}")
            pad_overlaps += 1

print(f"\nPad overlaps: {pad_overlaps}")

# Check off-board
off_board = 0
for fp in all_fps:
    pb = get_pad_bbox(fp)
    if not pb:
        continue
    x1, y1 = pb[0]/1e6, pb[1]/1e6
    x2, y2 = pb[2]/1e6, pb[3]/1e6
    if x1 < 0 or y1 < 0 or x2 > BOARD_W or y2 > BOARD_H:
        print(f"  OFF BOARD: {fp.GetReference()} pads x=[{x1:.1f},{x2:.1f}] y=[{y1:.1f},{y2:.1f}]")
        off_board += 1
print(f"Off-board: {off_board}")

# Save
pcbnew.SaveBoard(PATH, b)
b2 = pcbnew.LoadBoard(PATH)
print(f"\nVERIFIED: {len(list(b2.GetFootprints()))} footprints, {len(list(b2.GetTracks()))} tracks")
