#!/usr/bin/python3.14
"""Phase 0 placement fix: move decoupling caps near ICs, move J2 to edge."""
import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew

INPUT  = 'v_c3_flight_v5.kicad_pcb'
OUTPUT = 'v_c3_flight_p0fixed.kicad_pcb'

b = pcbnew.LoadBoard(INPUT)

# Target positions (mm → nm)
MOVES = {
    # C3 → near U2 (MS5611 at ~57,14)
    'C3':   (53_000_000, 11_000_000),
    # C4 → near U1 (ESP32 at ~35,18)  
    'C4':   (30_000_000, 11_000_000),
    # C2 → near U1 as second decoupling
    'C2':   (30_000_000, 25_000_000),
    # C1 → near U5 (flash at ~38,50)
    'C1':   (33_000_000, 46_000_000),
    # J2 → closer to bottom edge (from 48,45 to 48,49)
    'J2':   (48_000_000, 49_000_000),
}

print("=== PHASE 0 PLACEMENT FIX ===")
for fp in b.GetFootprints():
    ref = fp.GetReference()
    if ref in MOVES:
        old = fp.GetPosition()
        new_x, new_y = MOVES[ref]
        fp.SetPosition(pcbnew.VECTOR2I(new_x, new_y))
        print(f"  {ref}: ({old.x/1e6:.1f},{old.y/1e6:.1f}) → ({new_x/1e6:.1f},{new_y/1e6:.1f})mm")

pcbnew.SaveBoard(OUTPUT, b)
print(f"\nSaved: {OUTPUT}")

# === VERIFY ===
print("\n=== VERIFICATION ===")
b2 = pcbnew.LoadBoard(OUTPUT)

# 1. Check bbox overlaps
fps = list(b2.GetFootprints())
fp_info = []
for fp in fps:
    bb = fp.GetBoundingBox()
    fp_info.append((fp.GetReference(), bb.GetX(), bb.GetY(), bb.GetWidth(), bb.GetHeight()))

overlaps = 0
for i in range(len(fp_info)):
    for j in range(i+1, len(fp_info)):
        r1, x1, y1, w1, h1 = fp_info[i]
        r2, x2, y2, w2, h2 = fp_info[j]
        # Bbox intersection
        ix1 = max(x1 - w1//2, x2 - w2//2)
        iy1 = max(y1 - h1//2, y2 - h2//2)
        ix2 = min(x1 + w1//2, x2 + w2//2)
        iy2 = min(y1 + h1//2, y2 + h2//2)
        if ix2 > ix1 and iy2 > iy1:
            area = (ix2 - ix1) * (iy2 - iy1) / 1e12  # mm²
            if area > 0.1:
                print(f"  OVERLAP: {r1} x {r2} {area:.1f}mm²")
                overlaps += 1
print(f"Bbox overlaps: {overlaps}")

# 2. Check decoupling cap proximity
ICs = {'U1': None, 'U2': None, 'U3': None, 'U5': None}
CAPS = {}
for fp in b2.GetFootprints():
    ref = fp.GetReference()
    pos = fp.GetPosition()
    if ref in ICs:
        ICs[ref] = (pos.x, pos.y)
    if ref.startswith('C') and ref != 'C_CAP':
        # Check cap net
        for pad in fp.Pads():
            net = pad.GetNetname()
            CAPS[ref] = (pos.x, pos.y, net)
            break

print("\nDecoupling cap proximity:")
import math
all_pass = True
for ic, (ix, iy) in ICs.items():
    min_d = float('inf')
    nearest = None
    for cap, (cx, cy, cnet) in CAPS.items():
        d = math.sqrt((ix-cx)**2 + (iy-cy)**2) / 1e6
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
        bb = fp.GetBoundingBox()
        bottom = (bb.GetY() + bb.GetHeight()//2) / 1e6
        dist = 60.0 - bottom
        status = "PASS" if dist <= 5.0 else "FAIL"
        print(f"\nJ2 bottom edge distance: {dist:.1f}mm [{status}]")

print(f"\n{'ALL CHECKS PASS' if overlaps == 0 and all_pass else 'FAILURES FOUND'}")
print("=== DONE ===")
