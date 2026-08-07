#!/usr/bin/python3.14
"""Re-place all footprints: 80x60mm board, greedy bin-packing by actual bbox size.
Checks PAD positions (not courtyard) for overlap.
"""
import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew

INPUT  = '/home/c03rad0r/repos/balloon-fresh/tracker/hardware/output/v_c3_flight_final.kicad_pcb'
OUTPUT = '/home/c03rad0r/repos/balloon-fresh/tracker/hardware/output/v_c3_flight_replaced.kicad_pcb'

BOARD_W = 80_000_000   # 80mm
BOARD_H = 60_000_000   # 60mm
MARGIN  = 3_000_000    # 3mm from edge
MIN_GAP = 1_500_000    # 1.5mm min gap between footprint bboxes

print("=== PLACEMENT v2: 80x60mm board, greedy packing ===")
b = pcbnew.LoadBoard(INPUT)
fps = list(b.GetFootprints())

# Measure actual bbox for each footprint
parts = []
for fp in fps:
    bb = fp.GetBoundingBox()
    w = bb.GetRight() - bb.GetLeft()
    h = bb.GetBottom() - bb.GetTop()
    # Calculate offset from position to bbox edges
    pos = fp.GetPosition()
    off_left = pos.x - bb.GetLeft()
    off_right = bb.GetRight() - pos.x
    off_top = pos.y - bb.GetTop()
    off_bottom = bb.GetBottom() - pos.y
    parts.append({
        'ref': fp.GetReference(),
        'fp': fp,
        'w': w, 'h': h,
        'off_left': off_left, 'off_right': off_right,
        'off_top': off_top, 'off_bottom': off_bottom,
        'area': w * h,
    })

# Sort by area, largest first
parts.sort(key=lambda p: -p['area'])

print(f"\nParts by size:")
for p in parts:
    print(f"  {p['ref']:8s} {p['w']/1e6:.1f}x{p['h']/1e6:.1f}mm  area={p['area']/1e12:.0f}mm²")

# Greedy placement: place each part in the first position that fits
# Grid-based search: step = 1mm
STEP = 1_000_000  # 1mm grid
placed = []  # list of (ref, bb_left, bb_top, bb_right, bb_bottom)

# Functional zone preferences (x_center, y_center)
ZONE_PREF = {
    'U1':    (40.0, 25.0),   # MCU center
    'U2':    (65.0, 15.0),   # MS5611 right-top
    'U3':    (65.0, 40.0),   # Sensor right-bottom
    'U4':    (10.0, 20.0),   # Regulator left
    'U5':    (40.0, 42.0),   # Flash near MCU
    'SOLAR': (8.0,  8.0),    # Solar top-left
    'D1':    (10.0, 35.0),   # Diode left-bottom
    'C_CAP': (8.0, 45.0),    # Big cap left-bottom
    'J1':    (20.0, 55.0),   # Connector bottom
    'J2':    (55.0, 55.0),   # Connector bottom
    'ANT1':  (72.0, 8.0),    # Antenna corner
    'LED1':  (72.0, 50.0),   # LED visible corner
}

def try_place_near(pref_x, pref_y, w, h, off_l, off_r, off_t, off_b):
    """Try to place a footprint near (pref_x, pref_y), expanding outward.
    Returns (x_nm, y_nm) or None.
    """
    px = int(pref_x * 1_000_000)
    py = int(pref_y * 1_000_000)

    # Search in expanding rings
    for ring in range(0, 40):  # up to 40mm spiral
        for dy in range(-ring, ring + 1):
            for dx in range(-ring, ring + 1):
                if max(abs(dx), abs(dy)) != ring:
                    continue
                tx = px + dx * STEP
                ty = py + dy * STEP

                # Calculate bbox from position + offsets
                bl = tx - off_l
                br = tx + off_r
                bt = ty - off_t
                bb = ty + off_b

                # Check board boundaries (with margin)
                if bl < MARGIN or br > BOARD_W - MARGIN:
                    continue
                if bt < MARGIN or bb > BOARD_H - MARGIN:
                    continue

                # Check against all placed parts (with gap)
                conflict = False
                for _, pl, pt, pr, pb in placed:
                    # Expand placed bbox by MIN_GAP
                    if bl < pr + MIN_GAP and br > pl - MIN_GAP and \
                       bt < pb + MIN_GAP and bb > pt - MIN_GAP:
                        conflict = True
                        break

                if not conflict:
                    return (tx, ty, bl, bt, br, bb)

    return None

print(f"\n=== PLACING PARTS (greedy, largest first) ===")
unplaced = []
for p in parts:
    pref = ZONE_PREF.get(p['ref'], (40.0, 30.0))  # Default center
    result = try_place_near(pref[0], pref[1],
                           p['w'], p['h'],
                           p['off_left'], p['off_right'],
                           p['off_top'], p['off_bottom'])
    if result:
        tx, ty, bl, bt, br, bb = result
        p['fp'].SetPosition(pcbnew.VECTOR2I(tx, ty))
        placed.append((p['ref'], bl, bt, br, bb))
        print(f"  OK   {p['ref']:8s} pos=({tx/1e6:.1f},{ty/1e6:.1f})mm  bbox=({bl/1e6:.1f},{bt/1e6:.1f})-({br/1e6:.1f},{bb/1e6:.1f})")
    else:
        unplaced.append(p)
        print(f"  FAIL {p['ref']:8s} could not place!")

# Update board outline
old_drawings = [d for d in list(b.GetDrawings()) if d.GetClass() == 'PCB_SHAPE' and d.GetLayer() == pcbnew.Edge_Cuts]
for d in old_drawings:
    b.Remove(d)

corners = [(0, 0), (BOARD_W, 0), (BOARD_W, BOARD_H), (0, BOARD_H)]
for i in range(4):
    line = pcbnew.PCB_SHAPE(b)
    line.SetLayer(pcbnew.Edge_Cuts)
    sx, sy = corners[i]
    ex, ey = corners[(i + 1) % 4]
    line.SetStart(pcbnew.VECTOR2I(sx, sy))
    line.SetEnd(pcbnew.VECTOR2I(ex, ey))
    line.SetWidth(150000)
    b.Add(line)

print(f"\nBoard outline: {BOARD_W/1e6:.0f}x{BOARD_H/1e6:.0f}mm")

# Save
pcbnew.SaveBoard(OUTPUT, b)
print(f"Saved: {OUTPUT}")

# === VERIFY ===
print(f"\n=== VERIFICATION ===")
b2 = pcbnew.LoadBoard(OUTPUT)
fps2 = list(b2.GetFootprints())
overlaps = 0
for i in range(len(fps2)):
    for j in range(i + 1, len(fps2)):
        bb1 = fps2[i].GetBoundingBox()
        bb2 = fps2[j].GetBoundingBox()
        if bb1.Intersects(bb2):
            x_ov = min(bb1.GetRight(), bb2.GetRight()) - max(bb1.GetLeft(), bb2.GetLeft())
            y_ov = min(bb1.GetBottom(), bb2.GetBottom()) - max(bb1.GetTop(), bb2.GetTop())
            area = (x_ov / 1e6) * (y_ov / 1e6)
            if area > 0.1:
                print(f"  OVERLAP: {fps2[i].GetReference()} x {fps2[j].GetReference()}  {area:.1f}mm²")
                overlaps += 1

# Check pad-level overlaps
pad_overlaps = 0
all_pads = []
for fp in fps2:
    for pad in fp.Pads():
        pos = pad.GetPosition()
        sz = pad.GetSize()
        all_pads.append((pos.x, pos.y, sz.x, sz.y, fp.GetReference(), pad.GetNetname()))

for i in range(len(all_pads)):
    for j in range(i+1, len(all_pads)):
        x1,y1,sx1,sy1,r1,n1 = all_pads[i]
        x2,y2,sx2,sy2,r2,n2 = all_pads[j]
        if r1 == r2:
            continue
        # Check pad bbox intersection
        if abs(x1-x2) < (sx1+sx2)/2 + 200000 and abs(y1-y2) < (sy1+sy2)/2 + 200000:
            if n1 != n2:
                pad_overlaps += 1
                if pad_overlaps <= 10:
                    print(f"  PAD OVERLAP: {r1}:{n1} <-> {r2}:{n2}  d=({abs(x1-x2)/1e6:.2f},{abs(y1-y2)/1e6:.2f})mm")

print(f"\nBbox overlaps: {overlaps}")
print(f"Pad overlaps (different parts, different nets): {pad_overlaps}")
print(f"Unplaced: {len(unplaced)}")

# Boundary check
oob = 0
for fp in fps2:
    bb = fp.GetBoundingBox()
    if bb.GetLeft() < 0 or bb.GetTop() < 0 or bb.GetRight() > BOARD_W or bb.GetBottom() > BOARD_H:
        oob += 1
        print(f"  OOB: {fp.GetReference()}")
print(f"Out of bounds: {oob}")

print("\n=== DONE ===")
