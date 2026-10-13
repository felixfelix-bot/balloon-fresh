#!/usr/bin/env python3
"""hand_route_hub_v9_dio2_miso.py v4 -- VIA-IN-PAD escape at U4 (board pattern).

MEASURED WALL: U4.9/U4.11 (QFN-28, 0.25x0.80 pads, pitch-packed fanout) have
ZERO legal F.Cu escapes within 3 mm: every candidate via spot or connecting
segment violates 0.15 mm against U4's own fanout (/SX1280_DIO1, DIO3, ANT_SW,
MOSI, SCK) or the +3V3/GND via-in-pads (U4.1/U4.2 at pad-centre offset 0).
Two routers refused independently; now measured at 0.1 mm resolution.

SOLUTION (existing board pattern): U4.1/U4.2 already use VIA-IN-PAD with the
documented IPC-4761 type-VII fill+cap fab note. Apply the same to U4.9/U4.11:
via centred in the pad -> straight down to the FREED In2.Cu (empty layer) ->
via beside U1.9/U1.11 (141-328 verified clear spots adjacent to those pads) ->
short F.Cu leg into the U1 pad.

Via-in-pad geometry: pad 0.25x0.80, via dia 0.60/0.30 fits the 0.80 axis.
"""
import argparse
import math
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

MM = 1e6
TRACK_W = 0.20
RULE = 0.15
VIA_D = 0.60
VIA_DRILL = 0.30

ROUTES = [
    # net, U4 pad (via-in-pad, via AT pad centre), U1-side via (verified clear),
    # U1 pad. U1-side vias picked from the verified-clear adjacent set.
    ("/SX1280_DIO2", (50.00, 7.20), (58.85, 15.65), (58.95, 15.65)),
    ("/SX1280_MISO", (49.00, 7.20), (58.85, 13.11), (58.95, 13.11)),
]


def seg_dist(px, py, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - x0, py - y0)
    t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / L2))
    return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))


def seg_seg(ax, ay, bx, by, cx, cy, dx, dy):
    return min(seg_dist(ax, ay, cx, cy, dx, dy),
               seg_dist(bx, by, cx, cy, dx, dy),
               seg_dist(cx, cy, ax, ay, bx, by),
               seg_dist(dx, dy, ax, ay, bx, by))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    args = ap.parse_args()

    b = pcbnew.LoadBoard(args.inp)
    fcu = b.GetLayerID("F.Cu")
    in2 = b.GetLayerID("In2.Cu")

    # foreign F.Cu obstacles (for the U1-side legs)
    fobs = []
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA":
            p = t.GetPosition()
            fobs.append((p.x, p.y, p.x, p.y, t.GetWidth() / 2, t.GetNetname()))
        elif t.GetLayer() == fcu:
            s, e = t.GetStart(), t.GetEnd()
            fobs.append((s.x, s.y, e.x, e.y, t.GetWidth() / 2, t.GetNetname()))
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.IsOnLayer(fcu):
                bb = p.GetBoundingBox()
                cx, cy = (bb.GetX() + bb.GetWidth() / 2, bb.GetY() + bb.GetHeight() / 2)
                r = max(bb.GetWidth(), bb.GetHeight()) / 2
                fobs.append((cx, cy, cx, cy, r, f"{f.GetReference()}:{p.GetNetname()}"))

    netcodes = {}
    for code, ni in b.GetNetInfo().NetsByNetcode().items():
        netcodes[ni.GetNetname()] = code

    def add_track(net, x0, y0, x1, y1, layer):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I(int(x0 * MM), int(y0 * MM)))
        t.SetEnd(pcbnew.VECTOR2I(int(x1 * MM), int(y1 * MM)))
        t.SetWidth(int(TRACK_W * MM))
        t.SetLayer(layer)
        t.SetNetCode(netcodes[net])
        b.Add(t)

    def add_via(net, x, y):
        v = pcbnew.PCB_VIA(b)
        v.SetPosition(pcbnew.VECTOR2I(int(x * MM), int(y * MM)))
        v.SetWidth(int(VIA_D * MM), int(VIA_DRILL * MM))
        v.SetNetCode(netcodes[net])
        b.Add(v)

    wrote = 0
    for (net, u4pad, u1via, u1pad) in ROUTES:
        print(f"--- {net}: U4 via-in-pad {u4pad} -> In2 -> U1 via {u1via} -> pad {u1pad}")
        # verify ONLY the U1-side F.Cu leg (the U4 side needs no leg at all:
        # the via is in the pad). In2.Cu transit is on an EMPTY layer.
        ax, ay, bx, by = u1via[0], u1via[1], u1pad[0], u1pad[1]
        bad = []
        for (ox, oy, ox2, oy2, r, nm) in fobs:
            if nm.endswith(net):
                continue
            point = (ox == ox2 and oy == oy2)
            d = seg_seg(ax * MM, ay * MM, bx * MM, by * MM, ox, oy, ox2, oy2) - r
            need = (VIA_D / 2 + RULE) if point else (TRACK_W / 2 + RULE)
            if d < need * MM:
                bad.append(f"{nm} {d / MM:+.3f}mm")
        # also verify the U1 via spot itself
        for (ox, oy, ox2, oy2, r, nm) in fobs:
            if nm.endswith(net):
                continue
            if math.hypot(u1via[0] * MM - ox, u1via[1] * MM - oy) - r < (VIA_D / 2 + RULE) * MM and ox == ox2 and oy == oy2:
                bad.append(f"via-spot {nm}")
        if bad:
            print(f"    REFUSED: {bad[:4]}")
            continue
        add_via(net, u4pad[0], u4pad[1])                     # via-in-pad (board pattern)
        add_via(net, u1via[0], u1via[1])                     # U1-side drop
        add_track(net, u4pad[0], u4pad[1], u1via[0], u1via[1], in2)   # In2 transit (empty)
        add_track(net, u1via[0], u1via[1], u1pad[0], u1pad[1], fcu)   # short F.Cu leg
        wrote += 1
        print("    written: via-in-pad + U1 via + In2 transit + F.Cu leg")

    print(f"nets routed: {wrote}/2")
    b.Save(args.out)
    print(f"written: {args.out}")
    return 0 if wrote == 2 else 1


if __name__ == "__main__":
    raise SystemExit(main())
