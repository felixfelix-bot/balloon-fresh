#!/usr/bin/env python3
"""Locate the ACTUAL closest-approach point of each clearance violation.

Why this exists: `kicad-cli pcb drc --format json` reports an item `pos` that is
the object's own origin/reference point, NOT the point where the two pieces of
copper come closest. Plotting `pos` puts the marker on the wrong piece of
copper -- measured 2026-10-29, the first version of the clearance figure drew
its circles ~3 mm away from the real gap, and a vision review of the figure
correctly rejected it while the underlying numbers were right.

So: resolve each violation's items by uuid, build the copper outline of each
(track = rectangle along its centreline at its width; pad = its rectangle),
sample both outlines densely, and take the minimum-distance point pair. That
pair IS the gap, and it is what the human needs to see.

Runs under /usr/bin/python3 (distro python, where pcbnew lives), NOT the venv.

Output: JSON on stdout (or --out) with, per violation, the closest points, the
edge-to-edge gap, and a small geometry window for plotting.

Usage:
  /usr/bin/python3 tracker/hardware/tmp_probes/plot_clearance_violations.py \
      --board <board.kicad_pcb> --drc <drc.json> --out /tmp/clear.json
"""
import argparse
import json
import sys

import pcbnew

MM = 1e6
SAMPLES = 400


def rect_points(cx, cy, w, h):
    """Perimeter samples of an axis-aligned-ish rectangle (pad)."""
    hw, hh = w / 2.0, h / 2.0
    pts = []
    n = max(4, SAMPLES // 4)
    for i in range(n):
        t = i / (n - 1)
        pts.append((cx - hw + t * w, cy - hh))
        pts.append((cx - hw + t * w, cy + hh))
        pts.append((cx - hw, cy - hh + t * h))
        pts.append((cx + hw, cy - hh + t * h))
    return pts


def track_points(p1, p2, width):
    """Perimeter of the copper a track occupies (rectangle along the segment)."""
    x1, y1 = p1
    x2, y2 = p2
    dx, dy = x2 - x1, y2 - y1
    length = (dx * dx + dy * dy) ** 0.5
    if length < 1e-9:
        return rect_points(x1, y1, width, width)
    nx, ny = -dy / length * width / 2.0, dx / length * width / 2.0
    corners = [(x1 + nx, y1 + ny), (x2 + nx, y2 + ny), (x2 - nx, y2 - ny), (x1 - nx, y1 - ny)]
    pts = []
    n = max(8, SAMPLES // 4)
    for i in range(4):
        ax, ay = corners[i]
        bx, by = corners[(i + 1) % 4]
        for j in range(n):
            t = j / (n - 1)
            pts.append((ax + t * (bx - ax), ay + t * (by - ay)))
    return pts


def item_points(obj):
    """Copper outline samples for a board item, or None if unsupported."""
    if isinstance(obj, pcbnew.PCB_VIA):
        p = obj.GetPosition()
        d = obj.GetWidth() / MM
        return rect_points(p.x / MM, p.y / MM, d, d)
    if isinstance(obj, pcbnew.PCB_TRACK):
        s, e = obj.GetStart(), obj.GetEnd()
        return track_points((s.x / MM, s.y / MM), (e.x / MM, e.y / MM), obj.GetWidth() / MM)
    if isinstance(obj, pcbnew.PAD):
        p = obj.GetPosition()
        sz = obj.GetSize()
        return rect_points(p.x / MM, p.y / MM, sz.x / MM, sz.y / MM)
    if isinstance(obj, pcbnew.ZONE):
        return None  # zones are filled polygons; not handled here
    return None


def describe(obj, board):
    if isinstance(obj, pcbnew.PCB_VIA):
        return f"via {obj.GetNetname()}"
    if isinstance(obj, pcbnew.PCB_TRACK):
        return f"track {obj.GetNetname()} {board.GetLayerName(obj.GetLayer())}"
    if isinstance(obj, pcbnew.PAD):
        fp = obj.GetParent()
        ref = fp.GetReference() if hasattr(fp, "GetReference") else "?"
        return f"pad {obj.GetNumber()} of {ref} {obj.GetNetname()}"
    return type(obj).__name__


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", required=True)
    ap.add_argument("--drc", required=True)
    ap.add_argument("--out", default="-")
    args = ap.parse_args()

    board = pcbnew.LoadBoard(args.board)
    drc = json.load(open(args.drc))

    by_uuid = {}
    for t in board.GetTracks():
        by_uuid[t.m_Uuid.AsString()] = t
    for f in board.GetFootprints():
        for p in f.Pads():
            by_uuid[p.m_Uuid.AsString()] = p
    for z in board.Zones():
        by_uuid[z.m_Uuid.AsString()] = z

    results = []
    for v in drc["violations"]:
        if v["type"] != "clearance":
            continue
        items = []
        for raw in v["items"]:
            obj = by_uuid.get(raw.get("uuid", ""))
            pts = item_points(obj) if obj is not None else None
            items.append({"obj": obj, "pts": pts, "desc": raw["description"], "raw": raw})
        if len(items) != 2 or any(i["pts"] is None for i in items):
            results.append({"desc": v["description"], "error": "unresolved item"})
            continue
        best = None
        for a in items[0]["pts"]:
            for b in items[1]["pts"]:
                d = ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
                if best is None or d < best[0]:
                    best = (d, a, b)
        gap, pa, pb = best
        cx, cy = (pa[0] + pb[0]) / 2.0, (pa[1] + pb[1]) / 2.0
        results.append({
            "desc": v["description"],
            "gap_mm": round(gap, 4),
            "a": list(pa), "b": list(pb), "centre": [cx, cy],
            "a_desc": describe(items[0]["obj"], board),
            "b_desc": describe(items[1]["obj"], board),
            "a_net": items[0]["obj"].GetNetname(),
            "b_net": items[1]["obj"].GetNetname(),
        })

    payload = json.dumps(results, indent=1)
    if args.out == "-":
        sys.stdout.write(payload + "\n")
    else:
        open(args.out, "w").write(payload + "\n")
        for r in results:
            if "error" in r:
                print("unresolved:", r["desc"][:70], file=sys.stderr)
            else:
                print(f"{r['gap_mm']:.4f} mm  {r['a_desc'][:34]:34s} <-gap->  {r['b_desc'][:34]}",
                      file=sys.stderr)


if __name__ == "__main__":
    main()
