#!/usr/bin/python3.14
"""
Phase 1-4: Placement-first redesign of hub_board_v1_4layer.kicad_pcb

PHASE 1: Re-place all 30 footprints with zero pad-bbox overlaps
PHASE 2: Place thermal vias properly (not on pads, not near THT holes)
PHASE 3: Route signals with layer switching
PHASE 4: Verify DRC, save, git commit+push
"""
import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew
import math
import os

BOARD_DIR = os.path.dirname(os.path.abspath(__file__))
BOARD_PATH = os.path.join(BOARD_DIR, 'hub_board_v1_4layer.kicad_pcb')

NM = 1000000  # 1mm in nm
F_CU  = pcbnew.F_Cu    # 0
B_CU  = pcbnew.B_Cu    # 2
IN1   = pcbnew.In1_Cu  # 4 (GND)
IN2   = pcbnew.In2_Cu  # 6 (3V3)

BOARD_W = 50.0
BOARD_H = 40.0
MIN_GAP = 1.0  # mm — minimum gap between pad bounding boxes

def mm(x):
    """Convert mm to internal units (nm)."""
    return int(x * NM)

def to_mm(x):
    return x / NM

# ─── Load board ───
print("=== PHASE 1: PLACEMENT ===")
b = pcbnew.LoadBoard(BOARD_PATH)
print(f"Loaded: {BOARD_PATH}")
print(f"Copper layers: {b.GetCopperLayerCount()}")

# ─── Compute pad bbox for a footprint at a given position/rotation ───
def get_fp_pad_bbox(fp):
    """Return (x0, y0, x1, y1) in mm of the pad bounding box (absolute)."""
    pads = list(fp.Pads())
    if not pads:
        pos = fp.GetPosition()
        return (to_mm(pos.x), to_mm(pos.y), to_mm(pos.x), to_mm(pos.y))
    minx = min(p.GetPosition().x - p.GetSize().x//2 for p in pads)
    maxx = max(p.GetPosition().x + p.GetSize().x//2 for p in pads)
    miny = min(p.GetPosition().y - p.GetSize().y//2 for p in pads)
    maxy = max(p.GetPosition().y + p.GetSize().y//2 for p in pads)
    return (to_mm(minx), to_mm(miny), to_mm(maxx), to_mm(maxy))

def get_fp_pad_centers(fp):
    """Return list of (ref, pad_name, x_mm, y_mm, w_mm, h_mm, net, is_tht, drill_mm)."""
    result = []
    for pad in fp.Pads():
        pos = pad.GetPosition()
        sz = pad.GetSize()
        is_tht = (pad.GetAttribute() == 3)  # PAD_ATTRIB_THROUGH_HOLE
        drill = pad.GetDrillSize()
        drill_mm = to_mm(drill.x) if drill.x > 0 else 0
        result.append({
            'pad': pad.GetPadName(),
            'x': to_mm(pos.x),
            'y': to_mm(pos.y),
            'w': to_mm(sz.x),
            'h': to_mm(sz.y),
            'net': pad.GetNetname(),
            'net_code': pad.GetNetCode(),
            'is_tht': is_tht,
            'drill': drill_mm,
        })
    return result

# ─── Placement plan ───
# Board: 50 x 40 mm. Origin top-left, Y increases downward.
#
# LAYOUT MAP:
#   ┌──────────────────────────────────────────────────────┐
#   │ [LED D2][R5]    [LoRa U2 (21.8x11)]  [AE1][AE2]      │ Y 1-12
#   │                                                    │
#   │ [PWR]  [ESP32 U]   [C3 C4]  [RP2040 U1]  [Sensors] │ Y 12-32
#   │ [D1 U5]    (6.8x19.5)            (1.7x19.7)         │
#   │ [SC]                                               │
#   │                                                    │
#   │ [J SOLAR] [TP1 TP2 TP3 TP4 TP5 TP6]  [U3 GPS][U4]  │ Y 32-39
#   └──────────────────────────────────────────────────────┘
#
# Function groups:
# Power (left): J, D1, U5, SC, C7, C5, R3, R4
# ESP32: U, C1, D2, R5
# LoRa: U2, C3, C4
# RP2040: U1, C2
# GPS: U3
# Sensor: U4, C6, R1, R2
# RF: AE1, AE2
# Test: TP1-TP6

# Each entry: (ref, center_x_mm, center_y_mm, rotation_degrees)
PLACEMENT = {
    # ─── Top band: LoRa module (horizontal, center-top) ───
    'U2':  (26.0,  6.5,  0),    # LoRa2021: pad bbox 21.8x11.0, spans X:15.1-36.9 Y:1.0-12.0
    
    # ─── Top-left: LED section ───
    'D2':  (14.0,  3.5,  0),    # Status LED: pad bbox 2.4x0.8, spans X:12.8-15.2 Y:3.1-3.9
    'R5':  (17.5,  3.5,  0),    # LED resistor: pad bbox 1.5x0.5, spans X:16.75-18.25 Y:3.25-3.75
    
    # ─── Top-right: Antennas ───
    'AE1': (47.0,  4.0,  0),    # 868MHz antenna: THT 2.0x2.0
    'AE2': (47.0,  7.5,  0),    # 2.4GHz antenna: THT 2.0x2.0
    
    # ─── Middle-left: Power section ───
    'D1':  (3.0,  20.0,  0),    # BAT54: pad bbox 4.0x0.8, X:1.0-5.0 Y:19.6-20.4
    'U5':  (3.0,  24.0,  0),    # TPS7A02: pad bbox 2.5x2.5, X:1.75-4.25 Y:22.75-25.25
    'C5':  (3.0,  16.0,  0),    # 100nF power decoupling: 1.5x0.5, X:2.25-3.75 Y:15.75-16.25
    'C7':  (3.0,  28.0,  0),    # 10uF power: 2.1x0.8, X:1.95-4.05 Y:27.6-28.4
    'R3':  (6.0,  16.0, 90),    # 1M VCAP->VDIV: rotated 90° → 0.5x1.5, X:5.75-6.25 Y:15.25-16.75
    'R4':  (8.0,  16.0, 90),    # 1M VDIV->GND: rotated 90° → 0.5x1.5, X:7.75-8.25 Y:15.25-16.75
    'SC':  (3.0,  31.0,  0),    # Supercap: 5.0x1.5, X:0.5-5.5 Y:30.25-31.75
    
    # ─── Middle-center-left: ESP32-C3 (vertical) ───
    'U':   (10.5, 22.0,  0),    # ESP32: pad bbox 6.8x19.5, X:7.1-13.9 Y:12.25-31.75
    'C1':  (10.5, 33.5,  0),    # 100nF ESP decoupling: 1.5x0.5, X:9.75-11.25 Y:33.25-33.75
    
    # ─── Middle-center: LoRa decoupling ───
    'C3':  (38.0,  6.5,  0),    # 100nF LoRa: 1.5x0.5, X:37.25-38.75 Y:6.25-6.75
    'C4':  (40.0,  6.5,  0),    # 10uF LoRa: 2.1x0.8, X:38.95-41.05 Y:6.1-6.9
    
    # ─── Middle-right: RP2040-Zero (vertical) ───
    'U1':  (43.0, 22.0,  0),    # RP2040: pad bbox 1.7x19.7, X:42.15-43.85 Y:12.15-31.85
    'C2':  (43.0, 33.5,  0),    # 100nF RP2040 decoupling: 1.5x0.5, X:42.25-43.75 Y:33.25-33.75
    
    # ─── Right side: MS5611 sensor + pull-ups ───
    'U4':  (46.0, 22.0,  0),    # MS5611: pad bbox 1.7x9.3, X:45.15-46.85 Y:17.35-26.65
    'C6':  (46.0, 29.0,  0),    # 100nF MS5611: 1.5x0.5, X:45.25-46.75 Y:28.75-29.25
    'R1':  (49.0, 22.0, 90),    # 4.7k I2C pull-up: rotated 90° → 0.5x1.5, X:48.75-49.25 Y:21.25-22.75
    'R2':  (49.0, 25.0, 90),    # 4.7k I2C pull-up: rotated 90° → 0.5x1.5, X:48.75-49.25 Y:24.25-25.75
    
    # ─── Bottom band: Connectors + GPS + Test points ───
    'J':   (3.0,  37.5,  0),    # Solar connector: pad bbox 1.7x4.2, X:2.15-3.85 Y:35.4-39.6
    'U3':  (7.0,  36.0,  0),    # GPS MAX-M10S: pad bbox 1.7x9.3, X:6.15-7.85 Y:31.35-40.65
    # Test points along bottom
    'TP1': (12.0, 37.5,  0),    # SPI0_SCK: D1.0mm pad
    'TP2': (16.0, 37.5,  0),    # SPI0_MOSI
    'TP3': (20.0, 37.5,  0),    # 3V3
    'TP4': (24.0, 37.5,  0),    # GND
    'TP5': (28.0, 37.5,  0),    # LED_GPIO18
    'TP6': (32.0, 37.5,  0),    # FEM_TX_GPIO19
}

# ─── Apply placement ───
print("\nApplying placement...")
fp_map = {}
for fp in b.GetFootprints():
    ref = fp.GetReference()
    fp_map[ref] = fp

missing = [k for k in PLACEMENT if k not in fp_map]
if missing:
    print(f"ERROR: Missing footprints: {missing}")
    sys.exit(1)

for ref, (cx, cy, rot) in PLACEMENT.items():
    fp = fp_map[ref]
    fp.SetPosition(pcbnew.VECTOR2I(mm(cx), mm(cy)))
    if rot != 0:
        fp.SetOrientationDegrees(rot)
    else:
        fp.SetOrientationDegrees(0)

print(f"  Placed {len(PLACEMENT)} footprints")

# ─── Verify: zero pad-bbox overlaps ───
print("\n--- Verifying pad bounding box overlaps ---")

all_bboxes = {}
for ref in PLACEMENT:
    fp = fp_map[ref]
    bbox = get_fp_pad_bbox(fp)
    all_bboxes[ref] = bbox

overlap_count = 0
pad_overlap_count = 0
refs_list = sorted(PLACEMENT.keys())
for i, ref_a in enumerate(refs_list):
    for ref_b in refs_list[i+1:]:
        a = all_bboxes[ref_a]
        b_ = all_bboxes[ref_b]
        # Check gap in X and Y
        gap_x = max(a[0], b_[0]) - min(a[2], b_[2])
        gap_y = max(a[1], b_[1]) - min(a[3], b_[3])
        if gap_x < MIN_GAP and gap_y < MIN_GAP:
            overlap_count += 1
            actual_overlap = (gap_x < 0 and gap_y < 0)
            status = "OVERLAP" if actual_overlap else f"GAP({max(gap_x,gap_y):.2f}mm)"
            print(f"  CONFLICT: {ref_a}({a[0]:.1f},{a[1]:.1f},{a[2]:.1f},{a[3]:.1f}) <-> "
                  f"{ref_b}({b_[0]:.1f},{b_[1]:.1f},{b_[2]:.1f},{b_[3]:.1f}) {status}")

# Also check pad-to-pad overlaps
print("\n--- Verifying pad-to-pad overlaps (different footprints) ---")
all_pad_info = {}
for ref in PLACEMENT:
    fp = fp_map[ref]
    all_pad_info[ref] = get_fp_pad_centers(fp)

for i, ref_a in enumerate(refs_list):
    for ref_b in refs_list[i+1:]:
        for pa in all_pad_info[ref_a]:
            for pb in all_pad_info[ref_b]:
                dx = abs(pa['x'] - pb['x'])
                dy = abs(pa['y'] - pb['y'])
                min_dx = (pa['w'] + pb['w']) / 2
                min_dy = (pa['h'] + pb['h']) / 2
                if dx < min_dx and dy < min_dy:
                    pad_overlap_count += 1
                    if pad_overlap_count <= 20:
                        print(f"  PAD OVERLAP: {ref_a}.{pa['pad']} <-> {ref_b}.{pb['pad']} "
                              f"at ({pa['x']:.2f},{pa['y']:.2f})/({pb['x']:.2f},{pb['y']:.2f})")

# Check all parts are within board bounds
print("\n--- Checking board bounds ---")
oob_count = 0
for ref, bbox in all_bboxes.items():
    if bbox[0] < 0 or bbox[1] < 0 or bbox[2] > BOARD_W or bbox[3] > BOARD_H:
        oob_count += 1
        print(f"  OUT OF BOUNDS: {ref} bbox=({bbox[0]:.1f},{bbox[1]:.1f})-({bbox[2]:.1f},{bbox[3]:.1f})")

print(f"\n=== PLACEMENT SUMMARY ===")
print(f"  Footprint bbox conflicts (< {MIN_GAP}mm gap): {overlap_count}")
print(f"  Pad-to-pad overlaps: {pad_overlap_count}")
print(f"  Out of bounds: {oob_count}")

if overlap_count > 0:
    print("\n  WARNING: Conflicts remain — adjusting positions...")
