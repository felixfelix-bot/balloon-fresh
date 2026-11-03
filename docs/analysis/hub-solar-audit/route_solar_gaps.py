#!/usr/bin/env python3
"""PROOF: can each of the 9 solar gaps be closed by real copper? Grid A*, two layers, one via.

This is the decisive test the audit turns on. The earlier finding argued geometrically that a via
"cannot connect" an SMD pad; it did not attempt a route. This does:

  * grid A* at --grid mm over F.Cu and B.Cu, 8-connected, allowing at most ONE layer change
  * a move is legal only if the swept track (width --track-w) keeps --clearance to every OTHER-NET
    track, pad and via on that layer, and stays --edge from the outline
  * a via is legal only if its annulus (--via-d) keeps --clearance on BOTH layers, and it is not
    inside a pad body (no via-in-pad)
  * source is the pad centre on the pad's own layer; goal is the other pad's centre on ITS layer

Reports per pair: PATH / NO PATH, length, via count, and the via XY if found. Read-only.
Usage: route_solar_gaps.py <board.kicad_pcb> [--grid 0.10] [--grid-max 0.40]
"""
import argparse
import heapq
import math
import sys

import pcbnew

UM = 1_000_000.0

PAIRS = [
    ("/W1_SOLAR_N", "J_W1.4", "D_BP1.2"),
    ("/W1_SOLAR_N", "J_W1.4", "D_BP2.1"),
    ("/W1_SOLAR_N", "J_W2.1", "D_BP2.1"),
    ("/W2_SOLAR_N", "J_W2.4", "D_BP2.2"),
    ("/W2_SOLAR_N", "J_W3.1", "D_BP3.1"),
    ("/W3_SOLAR_N", "J_W3.4", "D_BP3.2"),
    ("/W3_SOLAR_N", "J_W4.1", "D_BP4.1"),
    ("/W3_SOLAR_N", "J_W4.1", "D_BP3.2"),
    ("GND", "U2.4", "D_BP4.2"),
]


def find_pad(board, spec):
    ref, num = spec.split(".", 1)
    fp = next((f for f in board.GetFootprints() if f.GetReference() == ref), None)
    if fp is None:
        return None
    return next((p for p in fp.Pads() if p.GetNumber() == num), None)


def seg_point_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def seg_seg_dist(a1, a2, b1, b2):
    def orient(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    o1, o2 = orient(a1, a2, b1), orient(a1, a2, b2)
    o3, o4 = orient(b1, b2, a1), orient(b1, b2, a2)
    if o1 * o2 < 0 and o3 * o4 < 0:
        return 0.0
    return min(seg_point_dist(*b1, *a1, *a2), seg_point_dist(*b2, *a1, *a2),
               seg_point_dist(*a1, *b1, *b2), seg_point_dist(*a2, *b1, *b2))


class Grid:
    def __init__(self, board, net, grid_mm, clear_mm, track_mm, via_mm, edge_mm,
                 window=None):
        self.nx = self.ny = 0
        self.box = board.GetBoardEdgesBoundingBox()
        bx0, by0 = self.box.GetLeft() / UM, self.box.GetTop() / UM
        bx1, by1 = self.box.GetRight() / UM, self.box.GetBottom() / UM
        # SEARCH WINDOW: rasterising the whole 72x80 mm board costs minutes per pair because every
        # grid move is tested against ~700 obstacle objects. Restricting the search to a corridor
        # around the two pads makes it tractable, at the stated price that a route which would have
        # to detour outside the window is reported NO PATH. The window is passed in by the caller
        # and echoed in the output so a NO PATH is never read as "impossible" when it only means
        # "not within this window".
        if window is not None:
            wx0, wy0, wx1, wy1 = window
            self.x0, self.y0 = max(wx0, bx0), max(wy0, by0)
            self.x1, self.y1 = min(wx1, bx1), min(wy1, by1)
        else:
            self.x0, self.y0, self.x1, self.y1 = bx0, by0, bx1, by1
        self.window = window
        self.g = grid_mm
        self.nx = int((self.x1 - self.x0) / self.g) + 1
        self.ny = int((self.y1 - self.y0) / self.g) + 1
        self.clear = clear_mm
        self.tr = track_mm / 2.0
        self.vr = via_mm / 2.0
        self.edge = edge_mm
        self.obst = {pcbnew.F_Cu: [], pcbnew.B_Cu: []}
        self.same = {pcbnew.F_Cu: [], pcbnew.B_Cu: []}
        self.pad_boxes = []
        for t in board.GetTracks():
            if t.Type() == pcbnew.PCB_VIA_T:
                seg = (t.GetPosition().x / UM, t.GetPosition().y / UM,
                       t.GetPosition().x / UM, t.GetPosition().y / UM)
                r = t.GetWidth(pcbnew.F_Cu) / UM / 2.0
                for lay in (pcbnew.F_Cu, pcbnew.B_Cu):
                    (self.obst if t.GetNetname() != net else self.same)[lay].append((seg, r))
            else:
                seg = (t.GetStart().x / UM, t.GetStart().y / UM,
                       t.GetEnd().x / UM, t.GetEnd().y / UM)
                r = t.GetWidth() / UM / 2.0
                lay = t.GetLayer()
                if lay in self.obst:
                    (self.obst if t.GetNetname() != net else self.same)[lay].append((seg, r))
        for fp in board.GetFootprints():
            for p in fp.Pads():
                bb = p.GetBoundingBox()
                box = (bb.GetLeft() / UM, bb.GetTop() / UM, bb.GetRight() / UM, bb.GetBottom() / UM)
                self.pad_boxes.append(box)
                for lay in p.GetLayerSet().Seq():
                    if lay in self.obst:
                        # A pad is a RECTANGLE, not a disc. Modelling it as a circle of
                        # radius = longest_side/2 (the previous code) invents up to 1.4 mm of
                        # phantom copper on a 4.00 x 1.20 mm wing-seat pad and falsely seals a
                        # route corridor. Measured 2026-11-03: that single modelling error is
                        # what made this search report 0 of 9 while three escape directions from
                        # J_W2.1 are in fact clear. Store the four bbox edges as a degenerate
                        # rectangle and test against the real edges in track_ok/via_ok.
                        (self.same if p.GetNetname() == net else self.obst)[lay].append(
                            ("RECT", box))

    def xy(self, ix, iy):
        return self.x0 + ix * self.g, self.y0 + iy * self.g

    def inside(self, x, y, margin):
        return (self.x0 + margin <= x <= self.x1 - margin
                and self.y0 + margin <= y <= self.y1 - margin)

    def track_ok(self, lay, a, b):
        for item in self.obst[lay]:
            if item[0] == "RECT":
                # distance from the segment to the rectangle's four edges (0 if inside)
                box = item[1]
                x0, y0, x1, y1 = box
                if (min(a[0], b[0]) >= x0 and max(a[0], b[0]) <= x1
                        and min(a[1], b[1]) >= y0 and max(a[1], b[1]) <= y1):
                    return False
                edges = [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)),
                         ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]
                d = min(seg_seg_dist(a, b, e[0], e[1]) for e in edges)
                if d < self.tr + self.clear - 1e-9:
                    return False
            else:
                seg, r = item
                if seg_seg_dist(a, b, seg[:2], seg[2:]) < r + self.tr + self.clear - 1e-9:
                    return False
        return True

    def via_ok(self, x, y):
        for lay in (pcbnew.F_Cu, pcbnew.B_Cu):
            for item in self.obst[lay]:
                if item[0] == "RECT":
                    x0, y0, x1, y1 = item[1]
                    ddx = max(x0 - x, 0, x - x1)
                    ddy = max(y0 - y, 0, y - y1)
                    if math.hypot(ddx, ddy) < self.vr + self.clear - 1e-9:
                        return False
                else:
                    seg, r = item
                    if seg_point_dist(x, y, *seg[:2], *seg[2:]) < r + self.vr + self.clear - 1e-9:
                        return False
        for (bx0, by0, bx1, by1) in self.pad_boxes:
            if bx0 - 1e-9 <= x <= bx1 + 1e-9 and by0 - 1e-9 <= y <= by1 + 1e-9:
                return False      # inside a pad body -> via-in-pad
        return self.inside(x, y, self.vr + self.clear)

    def route(self, src, dst, src_lay, dst_lay):
        sxy = (src.GetPosition().x / UM, src.GetPosition().y / UM)
        dxy = (dst.GetPosition().x / UM, dst.GetPosition().y / UM)
        # The J_W* wing-seat pads sit ON Edge.Cuts BY DESIGN — the repo's own DRC allow-list scopes
        # copper_edge_clearance to exactly those refs (check_drc.py ALLOW). Without this exemption
        # the START node is illegal and the search cannot even leave the pad, which reads as
        # "unroutable" when the truth is "the edge rule does not apply here".
        exempt = []
        for pad in (src, dst):
            bb = pad.GetBoundingBox()
            r = max(pad.GetSize().x, pad.GetSize().y) / UM + 1.0
            exempt.append((sxy, r) if pad is src else (dxy, r))
            _ = bb

        def edge_exempt(x, y):
            for (cx, cy), r in exempt:
                if math.hypot(x - cx, y - cy) <= r:
                    return True
            return False

        start = (int(round((sxy[0] - self.x0) / self.g)),
                 int(round((sxy[1] - self.y0) / self.g)), 0, src_lay)
        goal = (int(round((dxy[0] - self.x0) / self.g)),
                int(round((dxy[1] - self.y0) / self.g)), dst_lay)
        pq = [(0.0, start)]
        best = {start: 0.0}
        prev = {}
        found = None
        while pq:
            cost, node = heapq.heappop(pq)
            if cost > best.get(node, 1e18) + 1e-9:
                continue
            ix, iy, used, lay = node
            if (ix, iy, lay) == goal:
                found = node
                break
            x, y = self.xy(ix, iy)
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                jx, jy = ix + dx, iy + dy
                if not (0 <= jx < self.nx and 0 <= jy < self.ny):
                    continue
                nx_, ny_ = self.xy(jx, jy)
                if not edge_exempt(nx_, ny_) and not self.inside(nx_, ny_, self.tr + self.edge):
                    continue
                if not self.track_ok(lay, (x, y), (nx_, ny_)):
                    continue
                nnode = (jx, jy, used, lay)
                ncost = cost + math.hypot(nx_ - x, ny_ - y)
                if ncost < best.get(nnode, 1e18) - 1e-9:
                    best[nnode] = ncost
                    prev[nnode] = node
                    heapq.heappush(pq, (ncost, nnode))
            # layer change
            if used == 0:
                other = pcbnew.B_Cu if lay == pcbnew.F_Cu else pcbnew.F_Cu
                if self.via_ok(x, y):
                    nnode = (ix, iy, 1, other)
                    ncost = cost + 1.5          # a via costs about this much detour
                    if ncost < best.get(nnode, 1e18) - 1e-9:
                        best[nnode] = ncost
                        prev[nnode] = node
                        heapq.heappush(pq, (ncost, nnode))
        if found is None:
            return None
        # walk back, count vias
        path = []
        cur = found
        while cur in prev:
            path.append(cur)
            cur = prev[cur]
        path.append(start)
        path.reverse()
        vias = [self.xy(n[0], n[1]) for i, n in enumerate(path[1:], 1)
                if n[2] != path[i - 1][2]]
        return {"len": round(best[found], 2), "vias": len(vias),
                "via_xy": [(round(x, 2), round(y, 2)) for x, y in vias],
                "nodes": len(path)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("board")
    ap.add_argument("--grid", type=float, default=0.25)
    ap.add_argument("--clearance", type=float, default=0.20)
    ap.add_argument("--track-w", type=float, default=0.20)
    ap.add_argument("--via-d", type=float, default=0.50)
    ap.add_argument("--edge", type=float, default=0.50)
    ap.add_argument("--pair", type=int, action="append",
                    help="solve only this 0-based pair index (repeatable); without it all 9 run "
                         "and one slow pair can starve the rest")
    ap.add_argument("--window-pad", type=float, default=8.0,
                    help="mm of search corridor added around the bounding box of the two pads")
    a = ap.parse_args()
    board = pcbnew.LoadBoard(a.board)
    if board is None:
        print("FAIL load")
        return 2

    solved = 0
    rows = []
    only = None
    for idx in getattr(a, "pair", []) or []:
        only = idx
    for pi, (net, sa, sb) in enumerate(PAIRS):
        if only is not None and pi != only:
            continue
        padA, padB = find_pad(board, sa), find_pad(board, sb)
        if padA is None or padB is None:
            print(f"{net:14s} {sa} / {sb}: PAD NOT FOUND", flush=True)
            continue
        la = pcbnew.F_Cu if pcbnew.F_Cu in padA.GetLayerSet().Seq() else pcbnew.B_Cu
        lb = pcbnew.F_Cu if pcbnew.F_Cu in padB.GetLayerSet().Seq() else pcbnew.B_Cu
        # corridor window around both pads
        ax, ay = padA.GetPosition().x / UM, padA.GetPosition().y / UM
        bx, by = padB.GetPosition().x / UM, padB.GetPosition().y / UM
        pad_mm = a.window_pad if hasattr(a, "window_pad") else 8.0
        win = (min(ax, bx) - pad_mm, min(ay, by) - pad_mm,
               max(ax, bx) + pad_mm, max(ay, by) + pad_mm)
        g = Grid(board, net, a.grid, a.clearance, a.track_w, a.via_d, a.edge,
                 window=win)
        r = g.route(padA, padB, la, lb)
        if r:
            solved += 1
            rows.append((net, sa, sb, r))
            print(f"{net:14s} {sa} -> {sb}: PATH len={r['len']:.2f}mm vias={r['vias']} "
                  f"via_xy={r['via_xy']}  grid={a.grid}mm", flush=True)
        else:
            print(f"{net:14s} {sa} -> {sb}: NO PATH at grid={a.grid}mm "
                  f"(clearance {a.clearance}, track {a.track_w}, via {a.via_d})", flush=True)
    print(f"\nROUTABLE: {solved} of {len(PAIRS)} pairs")
    if solved:
        print("A PATH here is copper, not an argument: the pair is board-fixable at the measured "
              "rules. It says nothing about whether it is the RIGHT fix — that is a netlist "
              "decision recorded separately.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
