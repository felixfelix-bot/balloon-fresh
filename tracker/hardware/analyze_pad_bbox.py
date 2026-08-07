#!/usr/bin/python3.14
"""Get pad-only bounding boxes — what actually matters for DRC clearance."""
import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew

BOARD_PATH = 'hub_board_v1_4layer.kicad_pcb'
NM = 1000000

b = pcbnew.LoadBoard(BOARD_PATH)

print(f"{'Ref':6s} {'Value':20s} {'PadBBox(mm)':20s} {'Courtyard(mm)':20s} {'Orient':>8s}  Pads")
for fp in b.GetFootprints():
    ref = fp.GetReference()
    val = fp.GetValue()
    orient = fp.GetOrientationDegrees()
    pads = list(fp.Pads())
    
    # Pad-only bounding box
    if pads:
        minx = min(p.GetPosition().x - p.GetSize().x//2 for p in pads)
        maxx = max(p.GetPosition().x + p.GetSize().x//2 for p in pads)
        miny = min(p.GetPosition().y - p.GetSize().y//2 for p in pads)
        maxy = max(p.GetPosition().y + p.GetSize().y//2 for p in pads)
        pw = (maxx - minx) / NM
        ph = (maxy - miny) / NM
    else:
        pw = ph = 0
    
    # Full bounding box
    bbox = fp.GetBoundingBox()
    bw = bbox.GetWidth() / NM
    bh = bbox.GetHeight() / NM
    
    print(f"{ref:6s} {val:20s} {pw:6.1f}x{ph:5.1f}     {bw:6.1f}x{bh:5.1f}     {orient:7.1f}f  {len(pads)}")

# Also print footprint library names
print("\n=== Footprint library names ===")
for fp in b.GetFootprints():
    fp_id = fp.GetFPID()
    lib_id = fp_id.GetUniStringLibId() if hasattr(fp_id, 'GetUniStringLibId') else str(fp_id)
    print(f"  {fp.GetReference():6s} -> {lib_id}")
