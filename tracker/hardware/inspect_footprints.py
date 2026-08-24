#!/usr/bin/env python3
"""Step 1: Inspect all footprints in the PCB."""
import pcbnew

b = pcbnew.LoadBoard("/home/c03rad0r/repos/balloon-fresh/tracker/hardware/hub_board_v1_4layer.kicad_pcb")

print(f"Board loaded: {b.GetFileName()}")
fps_all = list(b.GetFootprints())
print(f"Footprints: {len(fps_all)}")
print(f"Tracks: {len(list(b.GetTracks()))}")
print()

# Sort by reference
fps = sorted(b.GetFootprints(), key=lambda f: f.GetReference())

print(f"{'Ref':<8} {'Value':<20} {'X(mm)':>8} {'Y(mm)':>8} {'W(mm)':>7} {'H(mm)':>7} {'Pads':>4}")
print("-" * 80)

for fp in fps:
    ref = fp.GetReference()
    val = fp.GetValue()
    pos = fp.GetPosition()
    x_mm = pos.x / 1e6
    y_mm = pos.y / 1e6
    # Bounding box including pads
    bbox = fp.GetBoundingBox()
    w_mm = bbox.GetWidth() / 1e6
    h_mm = bbox.GetHeight() / 1e6
    n_pads = len(list(fp.Pads()))
    print(f"{ref:<8} {val:<20} {x_mm:>8.2f} {y_mm:>8.2f} {w_mm:>7.2f} {h_mm:>7.2f} {n_pads:>4}")

print()
print("=== NET ASSIGNMENTS PER FOOTPRINT ===")
for fp in fps:
    ref = fp.GetReference()
    nets = set()
    for pad in fp.Pads():
        if pad.GetNetname():
            nets.add(pad.GetNetname())
    if nets:
        print(f"{ref}: {', '.join(sorted(nets))}")
    else:
        print(f"{ref}: (no nets)")

# Board bounds
print()
print("=== BOARD BOUNDS ===")
rect = b.GetBoardEdgesBoundingBox()
print(f"Bounds: x={rect.GetLeft()/1e6:.2f}-{rect.GetRight()/1e6:.2f}mm  y={rect.GetTop()/1e6:.2f}-{rect.GetBottom()/1e6:.2f}mm")
print(f"W={rect.GetWidth()/1e6:.2f}mm H={rect.GetHeight()/1e6:.2f}mm")
