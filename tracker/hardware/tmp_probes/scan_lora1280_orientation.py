#!/usr/bin/env python3
"""Score every orientation of the LoRa1280 site on hub v10.

The operator's observation: the 9 lanes between U1 and the module cross each other, and
mirroring the part might untangle them. That is testable, so test it.

For each of 4 rotations x 2 board sides:
  * place the footprint at the same centre,
  * take the 9 required net connections as straight lines U1-pad -> module-pad,
  * count PAIRWISE CROSSINGS between those lines (lower is better),
  * measure the widest escape corridor available from each pad row.

Crossings are the metric the operator named; corridor is the constraint that decides whether
an escape is possible at all. A placement that is geometrically untangled but has no corridor
is still unusable, so both are reported and ranked together.
"""
from __future__ import annotations

import json
import math
import sys

import pcbnew

MM = 1_000_000
NETS = ["/SPI1_SCK", "/SPI1_MOSI", "/SPI1_MISO", "/E28_CS_N", "/E28_BUSY",
        "/E28_RESET_N", "/E28_DIO1", "/E28_DIO2", "/E28_DIO3"]
CLEARANCE = 0.20
STEP = 0.25
REACH = 16.0
HALF = 1.0


def seg_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / L2))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def segs_cross(a, b):
    (x1, y1, x2, y2), (x3, y3, x4, y4) = a, b

    def orient(ax, ay, bx, by, cx, cy):
        v = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
        return 0 if abs(v) < 1e-9 else (1 if v > 0 else -1)

    o1 = orient(x1, y1, x2, y2, x3, y3)
    o2 = orient(x1, y1, x2, y2, x4, y4)
    o3 = orient(x3, y3, x4, y4, x1, y1)
    o4 = orient(x3, y3, x4, y4, x2, y2)
    return o1 != o2 and o3 != o4


class Obs:
    def __init__(self, board, skip):
        self.seg = {pcbnew.F_Cu: [], pcbnew.B_Cu: []}
        self.cir = {pcbnew.F_Cu: [], pcbnew.B_Cu: []}
        for t in board.GetTracks():
            if isinstance(t, pcbnew.PCB_VIA):
                r = (t.GetWidth() / 2.0) / MM
                for lay in (pcbnew.F_Cu, pcbnew.B_Cu):
                    if t.IsOnLayer(lay):
                        self.cir[lay].append((t.GetPosition().x / MM, t.GetPosition().y / MM, r))
            elif t.GetLayer() in self.seg:
                lay = t.GetLayer()
                s, e = t.GetStart(), t.GetEnd()
                self.seg[lay].append((s.x / MM, s.y / MM, e.x / MM, e.y / MM,
                                      (t.GetWidth() / 2.0) / MM))
        for f in board.GetFootprints():
            if f.GetReference() == skip:
                continue
            for p in f.Pads():
                try:
                    if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                        continue
                    sz = p.GetSize()
                    r = max(sz.x, sz.y) / 2.0 / MM
                    c = p.GetPosition()
                    ls = p.GetLayerSet()
                    for lay in (pcbnew.F_Cu, pcbnew.B_Cu):
                        if ls.Contains(lay):
                            self.cir[lay].append((c.x / MM, c.y / MM, r))
                except Exception:
                    continue

    def blocked(self, lay, x, y):
        for x1, y1, x2, y2, w in self.seg[lay]:
            if seg_dist(x, y, x1, y1, x2, y2) <= w + CLEARANCE:
                return True
        for cx, cy, r in self.cir[lay]:
            if math.hypot(x - cx, y - cy) <= r + CLEARANCE:
                return True
        return False

    def corridor(self, lay, x, y, dx, dy):
        d = 0.0
        while d <= REACH:
            for off in (-HALF, 0.0, HALF):
                if self.blocked(lay, x + dx * d - dy * off, y + dy * d + dx * off):
                    return d
            d += STEP
        return REACH


def main() -> int:
    b0 = pcbnew.LoadBoard("tracker/hardware/hub_board_v10.kicad_pcb")
    u1 = next(f for f in b0.GetFootprints() if f.GetReference() == "U1")
    u1pads = {}
    for p in u1.Pads():
        n = p.GetNetname()
        if n in NETS and n not in u1pads:
            u1pads[n] = (p.GetPosition().x / MM, p.GetPosition().y / MM)
    oldpos = pcbnew.VECTOR2I(int(53.0e6), int(68.1e6))

    rows = []
    for side in ("B.Cu", "F.Cu"):
        for rot in (0, -90, 90, 180):
            b = pcbnew.LoadBoard("tracker/hardware/hub_board_v10.kicad_pcb")
            fp = pcbnew.FootprintLoad("tracker/hardware/footprints/lora1280", "LoRa1280")
            fp.SetPosition(oldpos)
            fp.SetOrientationDegrees(rot)
            b.Add(fp)
            if side == "B.Cu" and fp.GetLayer() != pcbnew.B_Cu:
                fp.Flip(oldpos, False)
            occ = Obs(b, "U_LORA1280")
            pads = {int(p.GetNumber()): (p.GetPosition().x / MM, p.GetPosition().y / MM,
                                         p.GetPinFunction()) for p in fp.Pads()}
            byfun = {v[2]: (v[0], v[1]) for v in pads.values()}
            funmap = {"/SPI1_SCK": "SCK", "/SPI1_MOSI": "MOSI", "/SPI1_MISO": "MISO",
                      "/E28_CS_N": "NSS", "/E28_BUSY": "BUSY", "/E28_RESET_N": "NRESET",
                      "/E28_DIO1": "DIO1", "/E28_DIO2": "DIO2", "/E28_DIO3": "DIO3"}
            lines = []
            for net in NETS:
                if net in u1pads and funmap[net] in byfun:
                    mx, my = byfun[funmap[net]]
                    ux, uy = u1pads[net]
                    lines.append((net, (ux, uy, mx, my)))
            cross = 0
            for i in range(len(lines)):
                for j in range(i + 1, len(lines)):
                    if segs_cross(lines[i][1], lines[j][1]):
                        cross += 1
            # corridor: best direction per row, per layer
            xs = sorted(v[0] for v in pads.values())
            cor = []
            for yv in sorted({round(v[1], 2) for v in pads.values()}):
                rowpads = [v for v in pads.values() if round(v[1], 2) == yv]
                mx = sum(p[0] for p in rowpads) / len(rowpads)
                best = max(
                    occ.corridor(lay, mx, yv, dx, dy)
                    for lay in (pcbnew.B_Cu, pcbnew.F_Cu)
                    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0))
                )
                cor.append(best)
            rows.append((side, rot, cross, min(cor), sum(cor) / len(cor), len(lines)))

    rows.sort(key=lambda r: (r[2], -r[3]))
    print(f"{'side':<6}{'rot':>6}{'crossings':>11}{'min corr':>10}{'mean corr':>11}{'nets':>6}")
    for side, rot, cross, mc, ac, n in rows:
        flag = "  <-- BEST" if (side, rot) == (rows[0][0], rows[0][1]) else ""
        print(f"{side:<6}{rot:>6}{cross:>11}{mc:>10.2f}{ac:>11.2f}{n:>6}{flag}")
    print(json.dumps({"best": [rows[0][0], rows[0][1], rows[0][2], rows[0][3]]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
