#!/usr/bin/python3.14
"""Analyze current board state: footprints, bounding boxes, overlaps."""
import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew

BOARD_PATH = 'hub_board_v1_4layer.kicad_pcb'
NM = 1000000  # 1mm in nm

b = pcbnew.LoadBoard(BOARD_PATH)
print(f"Copper layers: {b.GetCopperLayerCount()}")
fps = list(b.GetFootprints())
print(f"Footprints: {len(fps)}")

footprint_data = []
for fp in fps:
    pos = fp.GetPosition()
    # Get bounding box in board coordinates
    bbox = fp.GetBoundingBox()
    x0 = bbox.GetX() - bbox.GetWidth() // 2
    y0 = bbox.GetY() - bbox.GetHeight() // 2
    x1 = bbox.GetX() + bbox.GetWidth() // 2
    y1 = bbox.GetY() + bbox.GetHeight() // 2
    
    ref = fp.GetReference()
    val = fp.GetValue()
    orient = fp.GetOrientationDegrees()
    layer = fp.GetLayer()
    
    # Count pads and get nets
    pads = list(fp.Pads())
    pad_nets = set()
    for p in pads:
        nn = p.GetNetname()
        if nn:
            pad_nets.add(nn)
    
    w_mm = bbox.GetWidth() / NM
    h_mm = bbox.GetHeight() / NM
    cx_mm = pos.x / NM
    cy_mm = pos.y / NM
    
    footprint_data.append({
        'ref': ref,
        'value': val,
        'cx': cx_mm, 'cy': cy_mm,
        'orient': orient,
        'layer': layer,
        'w': w_mm, 'h': h_mm,
        'x0': x0 / NM, 'y0': y0 / NM,
        'x1': x1 / NM, 'y1': y1 / NM,
        'pad_count': len(pads),
        'nets': pad_nets,
    })
    print(f"  {ref:6s} val={val:20s} pos=({cx_mm:6.2f},{cy_mm:6.2f}) "
          f"size={w_mm:5.1f}x{h_mm:5.1f} orient={orient:6.1f} "
          f"pads={len(pads)} nets={','.join(sorted(pad_nets))}")

# Check bounding box overlaps
print(f"\n=== BOUNDING BOX OVERLAP CHECK ===")
overlap_count = 0
for i in range(len(footprint_data)):
    for j in range(i+1, len(footprint_data)):
        a = footprint_data[i]
        b_ = footprint_data[j]
        # Check overlap (with 1mm gap requirement, overlap means gap < 1mm)
        gap_x = max(a['x0'], b_['x0']) - min(a['x1'], b_['x1'])
        gap_y = max(a['y0'], b_['y0']) - min(a['y1'], b_['y1'])
        if gap_x < 0 and gap_y < 0:
            # Actual overlap
            overlap_count += 1
            ox = min(a['x1'], b_['x1']) - max(a['x0'], b_['x0'])
            oy = min(a['y1'], b_['y1']) - max(a['y0'], b_['y0'])
            print(f"  OVERLAP: {a['ref']} <-> {b_['ref']} overlap={ox:.2f}x{oy:.2f}mm")
        elif gap_x < 1.0 and gap_y < 0:
            overlap_count += 1
            print(f"  TOO CLOSE (x): {a['ref']} <-> {b_['ref']} gap_x={gap_x:.2f}mm")
        elif gap_y < 1.0 and gap_x < 0:
            overlap_count += 1
            print(f"  TOO CLOSE (y): {a['ref']} <-> {b_['ref']} gap_y={gap_y:.2f}mm")

print(f"\nTotal overlap/too-close pairs: {overlap_count}")

# Check pad-to-pad overlaps between different footprints
print(f"\n=== PAD-TO-PAD OVERLAP CHECK (different footprints) ===")
pad_overlap_count = 0
all_pads = []
for fp in fps:
    for pad in fp.Pads():
        pos = pad.GetPosition()
        sz = pad.GetSize()
        all_pads.append({
            'ref': fp.GetReference(),
            'pad': pad.GetPadName(),
            'x': pos.x / NM,
            'y': pos.y / NM,
            'w': sz.x / NM,
            'h': sz.y / NM,
            'net': pad.GetNetname(),
        })

for i in range(len(all_pads)):
    for j in range(i+1, len(all_pads)):
        if all_pads[i]['ref'] == all_pads[j]['ref']:
            continue
        a, b_ = all_pads[i], all_pads[j]
        dx = abs(a['x'] - b_['x'])
        dy = abs(a['y'] - b_['y'])
        min_gap_x = (a['w'] + b_['w']) / 2
        min_gap_y = (a['h'] + b_['h']) / 2
        if dx < min_gap_x and dy < min_gap_y:
            pad_overlap_count += 1
            if pad_overlap_count <= 20:
                print(f"  PAD OVERLAP: {a['ref']}.{a['pad']} <-> {b_['ref']}.{b_['pad']} "
                      f"at ({a['x']:.2f},{a['y']:.2f})/({b_['x']:.2f},{b_['y']:.2f})")

print(f"Total pad overlaps between different footprints: {pad_overlap_count}")

# Check current tracks/vias
tracks = list(b.GetTracks())
vias = [t for t in tracks if t.GetClass() == 'PCB_VIA']
real_tracks = [t for t in tracks if t.GetClass() != 'PCB_VIA']
zones = list(b.Zones())
print(f"\n=== CURRENT STATE ===")
print(f"  Tracks: {len(real_tracks)}")
print(f"  Vias: {len(vias)}")
print(f"  Zones: {len(zones)}")
for z in zones:
    print(f"    Zone: layer={z.GetLayer()}, net={z.GetNetname()}")

# Print nets
print(f"\n=== NETS ===")
for net in b.GetNetInfo().NetsByName().items():
    name = str(net[0])
    code = net[1].GetNetCode()
    if code > 0:
        print(f"  Net {code}: {name}")
