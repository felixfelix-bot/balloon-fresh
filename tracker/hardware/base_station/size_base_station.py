#!/usr/bin/env python3
"""Measure the base-station board's real area demand before choosing an outline.

Report each placed footprint's extent and the total, then try the packer at several outlines and
report where everything seats. No guessing at a size.
"""
import importlib.util
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

spec = importlib.util.spec_from_file_location("placer", os.path.join(HERE, "place_base_station.py"))
placer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(placer)

# 1. part extents at a generous outline so nothing is parked
board, placed, skipped, comps, nets = placer.load(120.0, 120.0)

print(f"{'ref':<12} {'w mm':>7} {'h mm':>7} {'area mm2':>9}  value")
print("-" * 74)
rows = []
for ref, fp in placed:
    bb = fp.GetBoundingBox()
    w = pcbnew.ToMM(bb.GetWidth())
    h = pcbnew.ToMM(bb.GetHeight())
    rows.append((w * h, ref, w, h, fp.GetValue()))
tot = 0.0
for area, ref, w, h, val in sorted(rows, reverse=True):
    tot += area
    print(f"{ref:<12} {w:>7.2f} {h:>7.2f} {area:>9.1f}  {str(val)[:30]}")
print("-" * 74)
print(f"{'TOTAL bbox area':<12} {tot:>25.1f} mm2   ({len(rows)} placed, {len(skipped)} unplaceable)")
print(f"packing efficiency ~60% -> need ~{tot/0.6:.0f} mm2 usable")
print(f"  square: {((tot/0.6) ** 0.5):.0f} x {((tot/0.6) ** 0.5):.0f} mm")
print()

# 2. try outlines
print("=== outline trials (does everything seat?) ===")
for outline in ("50x40", "60x45", "70x50", "80x60", "100x80"):
    w, h = (float(v) for v in outline.split("x"))
    b2, p2, s2, c2, n2 = placer.load(w, h)
    overflow = placer.hubgen.pack_rest(b2, p2, [], w, h)
    n_over = len(overflow) if overflow else 0
    print(f"  {outline:>8}: {len(p2)} placed, {n_over} overflow"
          f"{'  ' + str(overflow[:6]) if overflow else '  ALL SEATED'}")
