#!/usr/bin/env python3
"""FIND FREE AREA and place the long-net partners there -- measured, not guessed.

My first attempt GUESSED coordinates (22,6) and (30,24) and introduced 4 new bounding-box overlaps.
That is the guess-and-hope pattern this campaign keeps punishing. This version MEASURES.

Approach: rasterise the board into a coarse occupancy grid from the EXISTING footprint outlines,
then pick the free cell nearest to U_MCU that fits the part's real extent. Report the chosen site's
clearance to its nearest neighbour so the choice is auditable.
"""
import os
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

HERE = "/home/c08r4d0r/worktrees/v9-route/tracker/hardware/base_station"
SRC = os.path.join(HERE, "base_station_v1_placed.kicad_pcb")
DST = os.path.join(HERE, "base_station_v1_placed_v2.kicad_pcb")

CELL = 1.0                      # mm raster
EDGE_MARGIN = 1.0

board = pcbnew.LoadBoard(SRC)
bb = board.GetBoardEdgesBoundingBox()
X0, Y0 = pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop())
W, H = pcbnew.ToMM(bb.GetWidth()), pcbnew.ToMM(bb.GetHeight())
print(f"board {W:.2f} x {H:.2f} mm at ({X0:.2f},{Y0:.2f})")


def extent(fp):
    b = fp.GetBoundingBox()
    return (pcbnew.ToMM(b.GetLeft()), pcbnew.ToMM(b.GetTop()),
            pcbnew.ToMM(b.GetRight()), pcbnew.ToMM(b.GetBottom()))


# ---- occupancy grid from every footprint EXCEPT the ones we intend to move --------------------
movers = {"U_FLASH", "U_VGA"}
occ = {}
for fp in board.GetFootprints():
    if fp.GetReference() in movers:
        continue
    l, t, r, b = extent(fp)
    ix0, iy0 = int((l - X0) / CELL), int((t - Y0) / CELL)
    ix1, iy1 = int((r - X0) / CELL) + 1, int((b - Y0) / CELL) + 1
    for ix in range(max(0, ix0), min(int(W / CELL) + 1, ix1)):
        for iy in range(max(0, iy0), min(int(H / CELL) + 1, iy1)):
            occ[(ix, iy)] = fp.GetReference()

print(f"occupied cells: {len(occ)} of {int(W / CELL) * int(H / CELL)}")

# ---- the microstrip-free idea: put each mover in the free cell closest to U_MCU ---------------
mcu = board.FindFootprintByReference("U_MCU")
mp = mcu.GetPosition()
mx, my = pcbnew.ToMM(mp.x), pcbnew.ToMM(mp.y)

KEEPOUT = 2.0   # extra mm around the chosen site


def find_site(fp, prefer_x_range):
    l, t, r, b = extent(fp)
    w, h = r - l, b - t
    cw, ch = int(w / CELL) + 1, int(h / CELL) + 1
    best = None
    nx = int(W / CELL) - cw
    for ix in range(int(EDGE_MARGIN / CELL), nx):
        if not (prefer_x_range[0] <= X0 + ix * CELL <= prefer_x_range[1]):
            continue
        for iy in range(int(EDGE_MARGIN / CELL), int(H / CELL) - ch):
            blocked = False
            for dx in range(-1, cw + 1):
                for dy in range(-1, ch + 1):
                    if (ix + dx, iy + dy) in occ:
                        blocked = True
                        break
                if blocked:
                    break
            if blocked:
                continue
            cx = X0 + (ix + cw / 2) * CELL
            cy = Y0 + (iy + ch / 2) * CELL
            d = ((cx - mx) ** 2 + (cy - my) ** 2) ** 0.5
            if best is None or d < best[0]:
                best = (d, ix, iy, cx, cy, w, h)
    return best


# U_FLASH is a QSPI partner -> keep it in the TOP band near U_MCU. U_VGA in the middle band.
PLANS = {
    "U_FLASH": (12.0, 34.0),
    "U_VGA": (20.0, 40.0),
}

print()
chosen = {}
for ref, xr in PLANS.items():
    fp = board.FindFootprintByReference(ref)
    if fp is None:
        print(f"  {ref}: NOT FOUND")
        continue
    s = find_site(fp, xr)
    if s is None:
        print(f"  {ref}: NO FREE SITE in x range {xr}")
        continue
    d, ix, iy, cx, cy, w, h = s
    old = fp.GetPosition()
    print(f"  {ref:9s} extent {w:.1f}x{h:.1f}  "
          f"({pcbnew.ToMM(old.x):.2f},{pcbnew.ToMM(old.y):.2f}) -> ({cx:.2f},{cy:.2f})  "
          f"dist to U_MCU {d:.1f} mm")
    chosen[ref] = (cx, cy, ix, iy, w, h)

# ---- apply, reserving each chosen site so they cannot collide with each other -----------------
for ref, (cx, cy, ix, iy, w, h) in chosen.items():
    fp = board.FindFootprintByReference(ref)
    fp.SetPosition(pcbnew.VECTOR2I(int(round(cx * 1e6)), int(round(cy * 1e6))))
    cw, ch = int(w / CELL) + 1, int(h / CELL) + 1
    for dx in range(-1, cw + 1):
        for dy in range(-1, ch + 1):
            occ[(ix + dx, iy + dy)] = ref

pcbnew.SaveBoard(DST, board)
print(f"\nsaved {os.path.relpath(DST, HERE)}")

# ---- verify: no new overlaps, all inside -------------------------------------------------------
b2 = pcbnew.LoadBoard(DST)
fps = list(b2.GetFootprints())
boxes = []
for fp in fps:
    l, t, r, b = extent(fp)
    boxes.append((fp.GetReference(), l, t, r, b))
ov = []
for i in range(len(boxes)):
    for j in range(i + 1, len(boxes)):
        a, c = boxes[i], boxes[j]
        if a[1] < c[3] and c[1] < a[3] and a[2] < c[4] and c[2] < a[4]:
            ov.append((a[0], c[0]))
print(f"\nfootprints {len(fps)}   bbox overlaps {len(ov)}")
for o in ov[:10]:
    print(f"   overlap {o}")
inside = all(EDGE_MARGIN - X0 - 0.01 <= b[1] and b[3] <= X0 + W - EDGE_MARGIN + 0.01
             and EDGE_MARGIN - Y0 - 0.01 <= b[2] and b[4] <= Y0 + H - EDGE_MARGIN + 0.01
             for b in boxes)
print(f"all inside the outline with {EDGE_MARGIN} mm margin: {inside}")
sys.exit(1 if ov else 0)
