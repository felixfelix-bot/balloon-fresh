"""STEP 2: verify SX1280_QFN24.kicad_mod against Figure 17-3 (QFN 4x4mm Land Pattern).

Figure 17-3, read from the rendered drawing (Semtech SX1280/SX1281 Rev 3.2, page 153):
    X = 0.30 mm   pad WIDTH
    Y = 0.80 mm   pad LENGTH (radial)
    P = 0.50 mm   pad PITCH
    H = 2.70 mm   exposed-pad dimension
    K = 2.70 mm   exposed-pad dimension
    Z = 4.80 mm   overall land-pattern span
    6 pads per side

Note the earlier finding: the footprint's pads 10, 11, 12 sit on the BOTTOM where the datasheet's
Figure 2-1 puts 10-18 on the RIGHT. This script measures BOTH claims so the fix is scoped by numbers:
  1. per-pad size and pitch, versus X / Y / P
  2. the exposed pad, versus H x K
  3. the rotation index each pad sits at, versus the datasheet's side assignment
  4. the overall span, versus Z
"""
import math
import re
import sys

FP = ("/home/c08r4d0r/worktrees/v9-route/tracker/hardware/schematics/flight_board/v9_lib/"
      "balloon_flight_v9.pretty/SX1280_QFN24.kicad_mod")

SPEC = {"X": 0.30, "Y": 0.80, "P": 0.50, "H": 2.70, "K": 2.70, "Z": 4.80}
TOL = 0.03

s = open(FP, encoding="utf-8").read()

# pads: (pad "N" smd rect (at X Y [rot]) (size W H) ...)
pads = []
for m in re.finditer(
        r'\(pad "([^"]+)"\s+(\w+)\s+(\w+)\s+\(at ([-\d.]+) ([-\d.]+)(?:\s+([-\d.]+))?\)\s*'
        r'\(size ([-\d.]+) ([-\d.]+)\)', s):
    num, ptype, shape, x, y, rot, w, h = m.groups()
    pads.append({
        "num": num, "type": ptype, "shape": shape,
        "x": float(x), "y": float(y), "rot": float(rot or 0),
        "w": float(w), "h": float(h),
    })

print(f"=== footprint has {len(pads)} pads ===")
nums = [p["num"] for p in pads]
print(f"pad numbers: {nums}")

# sizes
from collections import Counter
sizes = Counter((p["w"], p["h"]) for p in pads)
print()
print("=== pad size distribution (want X=0.30, Y=0.80) ===")
for (w, h), c in sizes.most_common():
    ok = (abs(w - SPEC["X"]) <= TOL or abs(w - SPEC["Y"]) <= TOL) and \
         (abs(h - SPEC["Y"]) <= TOL or abs(h - SPEC["X"]) <= TOL)
    print(f"   {w:.2f} x {h:.2f} mm  x{c}   {'OK (X/Y)' if ok else '** NOT X x Y **'}")

# exposed pad
ep = [p for p in pads if p["num"] in ("0", "25") or p["shape"] == "circle" and p["w"] > 2]
print()
print("=== candidate exposed pad ===")
for p in ep:
    print(f"   pad {p['num']}: {p['shape']} {p['w']:.2f} x {p['h']:.2f} at "
          f"({p['x']:.2f}, {p['y']:.2f})  spec H/K={SPEC['H']:.2f}")
if not ep:
    big = [p for p in pads if p["w"] >= 2.0]
    for p in big:
        print(f"   pad {p['num']}: {p['shape']} {p['w']:.2f} x {p['h']:.2f}  (large)")

# initial rotation -> side, and compare against the datasheet assignment
DATA_SIDE = {}
for n in range(1, 7):
    DATA_SIDE[n] = "LEFT"
for n in (7, 8, 9):
    DATA_SIDE[n] = "BOTTOM"
for n in range(10, 19):
    DATA_SIDE[n] = "RIGHT"
for n in range(19, 25):
    DATA_SIDE[n] = "TOP"


def geom_side(p):
    """side from position. The exposed pad sits at the centre and has NO side, so return None."""
    x, y = p["x"], p["y"]
    if abs(x) < 0.01 and abs(y) < 0.01:
        return None
    if abs(x) > abs(y):
        return "RIGHT" if x > 0 else "LEFT"
    return "BOTTOM" if y < 0 else "TOP"


print()
print("=== SIDE ASSIGNMENT: footprint vs datasheet Figure 2-1 ===")
mismatch = []
for p in sorted(pads, key=lambda q: int(q["num"]) if q["num"].isdigit() else 999):
    if not p["num"].isdigit() or int(p["num"]) == 0:
        continue
    n = int(p["num"])
    if n > 24:
        continue
    got, want = geom_side(p), DATA_SIDE[n]
    flag = "" if got == want else "  ** MISMATCH **"
    if got != want:
        mismatch.append(n)
    print(f"   pad {n:>2}  at ({p['x']:>6.2f},{p['y']:>6.2f})  footprint={got:<6} datasheet={want:<6}{flag}")

print()
print(f"pads on the WRONG side: {mismatch}")

# pitch within each side
print()
print("=== pitch within each side (want P=0.50) ===")
for side in ("LEFT", "BOTTOM", "RIGHT", "TOP"):
    pts = sorted([p for p in pads
                  if p["num"].isdigit() and int(p["num"]) > 0 and geom_side(p) == side],
                 key=lambda q: (q["y"] if side in ("LEFT", "RIGHT") else q["x"]))
    if len(pts) < 2:
        print(f"   {side:<6} n={len(pts)}  (cannot measure pitch)")
        continue
    key = (lambda q: q["y"]) if side in ("LEFT", "RIGHT") else (lambda q: q["x"])
    ds = [round(abs(key(pts[i + 1]) - key(pts[i])), 3) for i in range(len(pts) - 1)]
    okall = all(abs(d - SPEC["P"]) <= TOL for d in ds)
    print(f"   {side:<6} n={len(pts)}  spacings={ds}  {'OK' if okall else '** OFF **'}")

# overall span
xs = [p["x"] for p in pads]
ys = [p["y"] for p in pads]
print()
print(f"=== span: x {min(xs):.2f}..{max(xs):.2f}  y {min(ys):.2f}..{max(ys):.2f}")
print(f"    outer span = {max(max(xs) - min(xs), max(ys) - min(ys)):.2f} mm "
      f"(Z={SPEC['Z']:.2f} is the pad-centre span; Z+2*Y/2={SPEC['Z'] + SPEC['Y']:.2f} = pad outer edge)")
