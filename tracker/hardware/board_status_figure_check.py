#!/usr/bin/env python3
"""board_status_figure_check.py — verify the status figure against the census.

Reads the SVG produced by `board_status_figure.py` and the census JSON, then
asserts — from the SVG TEXT, not from a rendered image and not by eye:

  1. the SVG is well-formed XML;
  2. every board in the census is present, with matching verdict, DRC
     unconnected count and copper-layer count;
  3. every layer's encoded segments / zones / track length equal the census;
  4. every drawn segments-bar height equals the scale the figure declares
     (segments / max_segments * BAR_MAX_H), within 0.5 px;
  5. every pad-side bar value equals the census, and its width is proportional
     to that value;
  6. the required text labels are present (board names, verdict words, layer
     names) — nothing silently dropped;
  7. no two text labels collide (bbox intersection > 35% of the smaller box);
  8. the census numbers are internally consistent (segments == sum over layers).

Exits non-zero and prints every failure.  A green run means the figure is a
faithful, complete rendering of the census — the only unverified part is
aesthetics.
"""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SVG_NS = "{http://www.w3.org/2000/svg}"
BAR_MAX_H = 78.0
TOL_PX = 0.5
TOL_REL = 0.005


class Check:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.checks = 0

    def ok(self, cond: bool, msg: str) -> bool:
        self.checks += 1
        if not cond:
            self.failures.append(msg)
        return cond

    def close(self, a: float, b: float, tol: float, msg: str) -> bool:
        return self.ok(abs(a - b) <= tol, f"{msg}: {a} vs {b} (tol {tol})")


def parse(svg_path: Path):
    tree = ET.parse(svg_path)
    return tree.getroot()


def text_of(el) -> str:
    return "".join(el.itertext())


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    svg_path, census_path = Path(argv[0]), Path(argv[1])
    c = Check()

    census = json.loads(census_path.read_text())
    by_name = {b["name"]: b for b in census}

    try:
        root = parse(svg_path)
    except ET.ParseError as exc:
        print(f"FAIL: SVG is not well-formed XML: {exc}")
        return 1
    c.ok(True, "svg parses")

    groups = [g for g in root.iter(f"{SVG_NS}g") if g.get("data-board")]
    c.ok(len(groups) == len(census),
         f"board group count: {len(groups)} vs census {len(census)}")

    max_seg = max((b["totals"]["segments"] for b in census), default=1) or 1

    # ---- per board -------------------------------------------------------
    for g in groups:
        name = g.get("data-board")
        c.ok(name in by_name, f"board {name!r} present in census")
        if name not in by_name:
            continue
        b = by_name[name]
        c.ok(g.get("data-verdict") == b["verdict"],
             f"{name}: verdict {g.get('data-verdict')} != {b['verdict']}")
        c.ok(g.get("data-unconnected") == str(b["drc_unconnected"]),
             f"{name}: unconnected {g.get('data-unconnected')} != {b['drc_unconnected']}")
        c.ok(g.get("data-copper-layers") == str(b["copper_layers"]),
             f"{name}: copper layers {g.get('data-copper-layers')} != {b['copper_layers']}")

        # ---- layers ----
        seen_layers = set()
        for lg in g.iter(f"{SVG_NS}g"):
            lname = lg.get("data-layer")
            if not lname:
                continue
            seen_layers.add(lname)
            lv = b["layers"].get(lname)
            c.ok(lv is not None, f"{name}/{lname}: layer missing from census")
            if lv is None:
                continue
            c.ok(lg.get("data-segments") == str(lv["segments"]),
                 f"{name}/{lname}: segments {lg.get('data-segments')} != {lv['segments']}")
            c.ok(lg.get("data-zones") == str(lv["zones"]),
                 f"{name}/{lname}: zones {lg.get('data-zones')} != {lv['zones']}")
            c.close(float(lg.get("data-length-mm", "nan")), lv["length_mm"], 0.01,
                    f"{name}/{lname}: length {lg.get('data-length-mm')} != {lv['length_mm']:.2f}")
            # drawn bar height must match the declared scale
            bars = [r for r in lg.iter(f"{SVG_NS}rect")
                    if r.get("data-role") == "segments-bar"]
            expect_h = BAR_MAX_H * lv["segments"] / max_seg
            if lv["segments"] == 0:
                c.ok(not bars, f"{name}/{lname}: 0 segments but a bar was drawn")
            else:
                c.ok(len(bars) == 1,
                     f"{name}/{lname}: expected 1 segments bar, got {len(bars)}")
                if bars:
                    c.close(float(bars[0].get("height")), expect_h, TOL_PX,
                            f"{name}/{lname}: bar height {bars[0].get('height')} != scaled {expect_h:.2f}")
            # zone overlay present iff zones > 0
            ov = [r for r in lg.iter(f"{SVG_NS}rect")
                  if r.get("data-role") == "zone-overlay"]
            c.ok(bool(ov) == (lv["zones"] > 0),
                 f"{name}/{lname}: zone overlay presence {bool(ov)} != zones={lv['zones']}")
        c.ok(seen_layers == set(b["layers"]),
             f"{name}: layer groups {sorted(seen_layers)} != census {sorted(b['layers'])}")

        # ---- pads ----
        ptot = sum(b["pads"].get(k, 0) for k in ("front", "back", "through")) or 1
        seen_sides = set()
        for pg in g.iter(f"{SVG_NS}g"):
            side = pg.get("data-pad-side")
            if not side:
                continue
            seen_sides.add(side)
            val = b["pads"].get(side, 0)
            c.ok(pg.get("data-value") == str(val),
                 f"{name}/{side}: pad value {pg.get('data-value')} != {val}")
            bars = [r for r in pg.iter(f"{SVG_NS}rect") if r.get("data-role") == "pad-bar"]
            expect_w = 210 * val / ptot
            if val == 0:
                c.ok(not bars, f"{name}/{side}: 0 pads but a bar was drawn")
            else:
                c.ok(len(bars) == 1, f"{name}/{side}: expected 1 pad bar, got {len(bars)}")
                if bars:
                    c.close(float(bars[0].get("width")), expect_w, 0.05,
                            f"{name}/{side}: pad bar width {bars[0].get('width')} != scaled {expect_w:.2f}")
        c.ok(seen_sides == {"front", "back", "through"},
             f"{name}: pad sides {sorted(seen_sides)} incomplete")

    # ---- labels present --------------------------------------------------
    all_text = [text_of(t) for t in root.iter(f"{SVG_NS}text")]
    blob = "\n".join(all_text)
    for b in census:
        c.ok(b["name"] in blob, f"label missing: board name {b['name']!r}")
        c.ok(b["verdict"] in blob, f"label missing: verdict {b['verdict']!r}")
    for lname in ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu"):
        c.ok(lname in blob, f"label missing: layer {lname!r}")
    for side in ("front", "back", "through"):
        c.ok(side in blob, f"label missing: pad side {side!r}")

    # ---- no label collisions --------------------------------------------
    def bbox(t):
        try:
            x = float(t.get("x")); y = float(t.get("y"))
        except (TypeError, ValueError):
            return None
        raw = text_of(t)
        size = float(t.get("font-size", "12"))
        w = 0.62 * size * len(raw)
        h = size
        anchor = t.get("text-anchor", "start")
        if anchor == "middle":
            x -= w / 2
        elif anchor == "end":
            x -= w
        return (x, y - h, x + w, y)

    boxes = [bb for bb in (bbox(t) for t in root.iter(f"{SVG_NS}text")) if bb]
    overlaps = 0
    examples: list[str] = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            ax0, ay0, ax1, ay1 = boxes[i]
            bx0, by0, bx1, by1 = boxes[j]
            ix = max(0.0, min(ax1, bx1) - max(ax0, bx0))
            iy = max(0.0, min(ay1, by1) - max(ay0, by0))
            inter = ix * iy
            if inter <= 0:
                continue
            smaller = min((ax1 - ax0) * (ay1 - ay0), (bx1 - bx0) * (by1 - by0))
            frac = inter / smaller if smaller else 0.0
            if frac > 0.35:
                overlaps += 1
                if len(examples) < 5:
                    examples.append(f"{frac:.0%}: {all_text[i]!r} vs {all_text[j]!r}")
    c.ok(overlaps == 0, f"label collisions: {overlaps} ({'; '.join(examples)})")

    # ---- census internal consistency ------------------------------------
    for b in census:
        c.ok(b["totals"]["segments"] == sum(v["segments"] for v in b["layers"].values()),
             f"{b['name']}: totals.segments != sum over layers")
        c.ok(b["totals"]["vias"] == sum(v["vias"] for v in b["layers"].values()),
             f"{b['name']}: totals.vias != sum over layers")

    print(f"checks run: {c.checks}")
    if c.failures:
        print(f"FAILURES: {len(c.failures)}")
        for f in c.failures:
            print(f"  FAIL {f}")
        return 1
    print("PASS — figure is a faithful rendering of the census "
          "(boards, verdicts, layers, bar geometry, pad bars, labels, no collisions)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
