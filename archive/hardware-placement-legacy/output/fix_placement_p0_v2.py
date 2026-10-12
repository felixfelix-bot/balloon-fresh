#!/usr/bin/python3.14
"""Phase 0 placement fix v2: pad-aware cap placement outside IC courtyards."""
import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew
import math

INPUT  = 'v_c3_flight_v5.kicad_pcb'
OUTPUT = 'v_c3_flight_p0fixed.kicad_pcb'

b = pcbnew.LoadBoard(INPUT)

# Get all footprint bboxes for overlap checking
def get_fp_bboxes(board):
    result = {}
    for fp in board.GetFootprints():
        bb = fp.GetBoundingBox()
        result[fp.GetReference()] = (bb.GetX(), bb.GetY(), bb.GetWidth(), bb.GetHeight())
    return result

def overlaps_any(pos_x, pos_y, ref, bboxes, cap_w=5_000_000, cap_h=5_000_000, margin=500_000):
    """Check if a cap at pos overlaps any existing footprint."""
    cx1 = pos_x - cap_w//2 - margin
    cy1 = pos_y - cap_h//2 - margin
    cx2 = pos_x + cap_w//2 + margin
    cy2 = pos_y + cap_h//2 + margin
    for r, (x, y, w, h) in bboxes.items():
        if r == ref:
            continue
        ox1 = x - w//2; oy1 = y - h//2
        ox2 = x + w//2; oy2 = y + h//2
        if cx2 > ox1 and cx1 < ox2 and cy2 > oy1 and cy1 < oy2:
            return True, r
    return False, None

def find_clear_spot(target_x, target_y, ref, bboxes, board_w=80_000_000, board_h=60_000_000):
    """Spiral search from target for a non-overlapping position."""
    if target_x < 3_000_000: target_x = 3_000_000
    if target_x > board_w - 3_000_000: target_x = board_w - 3_000_000
    if target_y < 3_000_000: target_y = 3_000_000
    if target_y > board_h - 3_000_000: target_y = board_h - 3_000_000
    
    ov, other = overlaps_any(target_x, target_y, ref, bboxes)
    if not ov:
        return target_x, target_y
    
    # Spiral search: try offsets in expanding rings
    for radius in range(1, 30):
        for angle_deg in range(0, 360, 15):
            angle = math.radians(angle_deg)
            tx = int(target_x + radius * 2_000_000 * math.cos(angle))
            ty = int(target_y + radius * 2_000_000 * math.sin(angle))
            tx = max(3_000_000, min(board_w - 3_000_000, tx))
            ty = max(3_000_000, min(board_h - 3_000_000, ty))
            ov, other = overlaps_any(tx, ty, ref, bboxes)
            if not ov:
                return tx, ty
    return None, None

# VCC pad positions (from probe):
# U1 VCC pad at (31.2,19.0)mm → bbox bottom at y=20.2
# U2 VCC pad at (73.5,13.0)mm → outside bbox (pad beyond courtyard)  
# U3 VCC pad at (60.2,42.2)mm → below bbox (bbox max y=40.1)
# U5 VCC pad at (37.7,49.0)mm → near bbox edge

# Desired positions (just outside IC bbox, near VCC pad)
TARGETS = {
    'C4': (33_000_000, 23_000_000),   # Below U1 bbox, near VCC pad (31.2,19)
    'C2': (28_000_000, 23_000_000),   # Also below U1, second cap
    'C3': (73_500_000, 18_000_000),   # Below U2 VCC pad (73.5,13)
    'C1': (42_000_000, 49_000_000),   # Right of U5 VCC pad (37.7,49)
    'J2': (48_000_000, 53_000_000),   # Closer to bottom edge
}

print("=== PHASE 0 PLACEMENT FIX v2 ===")

# First, snapshot current bboxes (before moves)
bboxes = get_fp_bboxes(b)
# Remove the caps we're about to move from the bbox check
for ref in ['C1', 'C2', 'C3', 'C4']:
    if ref in bboxes:
        del bboxes[ref]

moves_made = {}
for fp in b.GetFootprints():
    ref = fp.GetReference()
    if ref in TARGETS:
        old = fp.GetPosition()
        tx, ty = TARGETS[ref]
        
        # For J2, remove from bboxes for its own check
        check_bboxes = {k: v for k, v in bboxes.items() if k != ref}
        
        fx, fy = find_clear_spot(tx, ty, ref, check_bboxes)
        if fx is not None:
            fp.SetPosition(pcbnew.VECTOR2I(fx, fy))
            moves_made[ref] = (fx, fy)
            print(f"  {ref}: ({old.x/1e6:.1f},{old.y/1e6:.1f}) → ({fx/1e6:.1f},{fy/1e6:.1f})mm")
        else:
            print(f"  {ref}: NO CLEAR SPOT FOUND near ({tx/1e6:.1f},{ty/1e6:.1f})mm")
        # Update bboxes with new position
        bb = fp.GetBoundingBox()
        bboxes[ref] = (bb.GetX(), bb.GetY(), bb.GetWidth(), bb.GetHeight())

pcbnew.SaveBoard(OUTPUT, b)
print(f"\nSaved: {OUTPUT}")

# === VERIFY ===
print("\n=== VERIFICATION ===")
b2 = pcbnew.LoadBoard(OUTPUT)

# 1. Bbox overlaps (exclude self)
fps = list(b2.GetFootprints())
fp_bbs = []
for fp in fps:
    bb = fp.GetBoundingBox()
    fp_bbs.append((fp.GetReference(), bb.GetX(), bb.GetY(), bb.GetWidth(), bb.GetHeight()))

overlaps = 0
for i in range(len(fp_bbs)):
    for j in range(i+1, len(fp_bbs)):
        r1, x1, y1, w1, h1 = fp_bbs[i]
        r2, x2, y2, w2, h2 = fp_bbs[j]
        ix1 = max(x1-w1//2, x2-w2//2); iy1 = max(y1-h1//2, y2-h2//2)
        ix2 = min(x1+w1//2, x2+w2//2); iy2 = min(y1+h1//2, y2+h2//2)
        if ix2 > ix1 and iy2 > iy1:
            area = (ix2-ix1)*(iy2-iy1)/1e12
            if area > 0.1:
                print(f"  OVERLAP: {r1} x {r2} {area:.1f}mm²")
                overlaps += 1
print(f"Bbox overlaps: {overlaps}")

# 2. Cap proximity to VCC pads (pad-to-pad distance, not center-to-center)
VCC_PADS = {
    'U1': (31_200_000, 19_000_000),
    'U2': (73_500_000, 13_000_000),
    'U3': (60_200_000, 42_200_000),
    'U5': (37_700_000, 49_000_000),
}

print("\nDecoupling cap proximity (pad-to-pad):")
all_pass = True
cap_positions = {}
for fp in b2.GetFootprints():
    ref = fp.GetReference()
    if ref in ['C1','C2','C3','C4']:
        pos = fp.GetPosition()
        cap_positions[ref] = (pos.x, pos.y)

for ic, (vx, vy) in VCC_PADS.items():
    min_d = float('inf')
    nearest = None
    for cap, (cx, cy) in cap_positions.items():
        d = math.sqrt((vx-cx)**2 + (vy-cy)**2) / 1e6
        if d < min_d:
            min_d = d
            nearest = cap
    status = "PASS" if min_d <= 5.0 else "FAIL"
    if min_d > 5.0:
        all_pass = False
    print(f"  {ic}: nearest cap {nearest} at {min_d:.1f}mm [{status}]")

# 3. J2 edge check
for fp in b2.GetFootprints():
    if fp.GetReference() == 'J2':
        pos = fp.GetPosition()
        dist = (60_000_000 - pos.y) / 1e6
        status = "PASS" if abs(dist) <= 5.0 else "FAIL"
        print(f"\nJ2 to bottom edge: {dist:.1f}mm [{status}]")

print(f"\n{'PHASE 0 PASS' if overlaps == 0 and all_pass else 'PHASE 0 FAIL — REVIEW ABOVE'}")
print("=== DONE ===")
