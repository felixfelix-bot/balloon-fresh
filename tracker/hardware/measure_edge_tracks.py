#!/usr/bin/env python3
"""What are the 26 edge-clearance TRACK items, and are they real defects?

The operator-approved scope covers the WING-SOCKET interface (by design on the edge).
These tracks are NOT that: +3V3, F33_VCC, GNSS_VCC are ordinary power nets. If a router
turned a power track along the board edge inside the 0.5mm keepout, that is a REAL
manufacturing risk, not an interface exemption.

Measure each: actual clearance vs required, and where it sits.
"""
import sys
import pcbnew

BOARD = sys.argv[1]
b = pcbnew.LoadBoard(BOARD)

# board outline bbox, to reason about "near the edge"
bds = b.GetBoardEdgesBoundingBox()
x0, y0 = bds.GetX() / 1e6, bds.GetY() / 1e6
x1, y1 = x0 + bds.GetWidth() / 1e6, y0 + bds.GetHeight() / 1e6
print(f"board bbox: ({x0:.2f},{y0:.2f}) - ({x1:.2f},{y1:.2f})")
print()

names = ("+3V3", "/F33_VCC", "/GNSS_VCC", "/W1_SOLAR_N", "/CUT_SENSE_W")
for t in b.GetTracks():
    if t.GetClass() != "PCB_TRACK":
        continue
    net = t.GetNetname()
    if not any(n in net for n in names):
        continue
    p = t.GetStart()
    q = t.GetEnd()
    xs, ys = p.x / 1e6, p.y / 1e6
    xe, ye = q.x / 1e6, q.y / 1e6
    # min distance of either endpoint to the bbox edge
    def edge_dist(x, y):
        return min(x - x0, x1 - x, y - y0, y1 - y)
    d = min(edge_dist(xs, ys), edge_dist(xe, ye))
    if d < 0.6:
        layer = b.GetLayerName(t.GetLayer())
        print(f"{net:18s} {layer:8s} ({xs:7.2f},{ys:7.2f})->({xe:7.2f},{ye:7.2f}) "
              f"len={t.GetLength()/1e6:5.2f} minedge={d:.3f}")
