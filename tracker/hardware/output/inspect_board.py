#!/usr/bin/env python3.14
"""Inspect current footprint positions and bounding boxes on the PCB."""
import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew

BOARD = "/home/c03rad0r/repos/balloon-fresh/tracker/hardware/output/v_c3_flight_v5.kicad_pcb"

b = pcbnew.LoadBoard(BOARD)

def mm(nm):
    return nm / 1_000_000.0

print("=" * 90)
print("FOOTPRINT INVENTORY")
print("=" * 90)
print(f"{'Ref':<10} {'X(mm)':>8} {'Y(mm)':>8}  {'BBox X0':>8} {'Y0':>8} {'X1':>8} {'Y1':>8}  {'W(mm)':>6} {'H(mm)':>6}")
print("-" * 90)

fps = []
for fp in b.GetFootprints():
    pos = fp.GetPosition()
    ref = fp.GetReference()
    # Get board bounding box (footprint area on board)
    bb = fp.GetBoundingBox()
    origin = bb.GetOrigin()
    end = bb.GetEnd()
    x0, y0 = origin.x, origin.y
    x1, y1 = end.x, end.y
    w = bb.GetWidth()
    h = bb.GetHeight()
    fps.append((ref, pos, bb))
    print(f"{ref:<10} {mm(pos.x):>8.2f} {mm(pos.y):>8.2f}  {mm(x0):>8.2f} {mm(y0):>8.2f} {mm(x1):>8.2f} {mm(y1):>8.2f}  {mm(w):>6.2f} {mm(h):>6.2f}")

print()
print("Board outline dimensions:")
outline = b.GetBoardEdgesBoundingBox()
print(f"  Outline bbox: X=[{mm(outline.GetX0()):.2f}, {mm(outline.GetX1()):.2f}]  Y=[{mm(outline.GetY0()):.2f}, {mm(outline.GetY1()):.2f}]")
print(f"  Board size: {mm(outline.GetWidth()):.2f} x {mm(outline.GetHeight()):.2f} mm")

# Also get the actual board outline from DRAWINGS for full clarity
print()
print("Board edge segments (DRAWSEGMENTS on Edge.Cuts):")
edge_count = 0
for item in b.GetDrawings():
    if item.IsOnLayer(pcbnew.Edge_Cuts):
        edge_count += 1
        if edge_count <= 10:
            seg = item.GetStart(), item.GetEnd()
            print(f"  ({mm(seg[0].x):.2f},{mm(seg[0].y):.2f}) -> ({mm(seg[1].x):.2f},{mm(seg[1].y):.2f})")
print(f"  Total Edge.Cuts items: {edge_count}")
