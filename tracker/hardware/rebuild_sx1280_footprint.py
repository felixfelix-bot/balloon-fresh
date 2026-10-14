"""STEP 2: rebuild SX1280_QFN24.kicad_mod from Figure 17-3, the vendor land pattern.

MEASURED SPEC (Semtech SX1280/SX1281 Rev 3.2, Figure 17-3, page 153, read from the rendered drawing):
    X = 0.30 mm   pad WIDTH
    Y = 0.80 mm   pad LENGTH (radial, pointing outward)
    P = 0.50 mm   pad PITCH
    H = 2.70 mm   exposed-pad dimension
    K = 2.70 mm   exposed-pad dimension
    Z = 4.80 mm   pad-CENTRE span across the package
    6 pads per side, 24 peripheral + 1 exposed = 25

MEASURED DEFECTS IN THE EXISTING FOOTPRINT (verify_fp_fig173.py):
    pad size        0.80 x 0.25   vs spec 0.30 x 0.80   (both axes wrong; effectively transposed)
    exposed pad     2.60 x 2.60   vs spec 2.70 x 2.70
    pad-centre span 3.90          vs spec 4.80
    sides           6/6/6/6(+1)   vs spec 6/3/9/6 -- 12 pads on the wrong side, every one an exact
                                  REFLECTION across the X axis (7-12 TOP instead of BOTTOM/RIGHT,
                                  19-24 BOTTOM instead of TOP)

GENERATOR MATH
  Pad centres sit on a square of half-width Z/2 = 2.40 mm from the package centre.
  LEFT side, 6 pads: index 1..6 runs from BOTTOM to TOP (y = -1.25 .. +1.25, pitch 0.50).
  The side order follows datasheet Figure 2-1 (Table 2-1 sides), counter-clockwise from pad 1:
      pad 1  bottom-left corner, on the LEFT column at the bottom
      pads 1-6  LEFT      (6)
      pads 7-9  BOTTOM    (3)
      pads 10-18 RIGHT    (9)
      pads 19-24 TOP      (6)
  Counts 6/3/9/6 = 24. The BOTTOM row is 3 wide and the TOP row 6 wide, which is why a 6/6/6/6 ring
  cannot represent this part -- that was the original error.

A pad is drawn as a RECT whose long axis points radially outward, so on the LEFT/RIGHT sides the
footprint's (size w h) is (Y, X) = (0.80, 0.30) and on the BOTTOM/TOP sides it is (X, Y) = (0.30, 0.80).
"""
import sys

OUT = ("/home/c08r4d0r/worktrees/v9-route/tracker/hardware/schematics/flight_board/v9_lib/"
       "balloon_flight_v9.pretty/SX1280_QFN24.kicad_mod")

X, Y, P = 0.30, 0.80, 0.50      # pad width, pad length, pitch
H = K = 2.70                    # exposed pad
Z = 4.80                        # pad-centre span
OFF = Z / 2.0                   # 2.40 -- distance from centre to pad centre

# side -> pad numbers, in the datasheet's own order
SIDES = {
    "LEFT":   list(range(1, 7)),      # 1..6
    "BOTTOM": list(range(7, 10)),     # 7..9
    "RIGHT":  list(range(10, 19)),    # 10..18
    "TOP":    list(range(19, 25)),    # 19..24
}


def pad_centres(side, nums):
    """Return {num: (x, y, rot_degrees)} with the pad's long axis radial.

    rotation is the footprint's (at x y rot) for the pad RECT: 0 means size (w,h) is axis-aligned.
    For a LEFT/RIGHT pad the long axis is horizontal, so size=(Y,X) and rot=0 works with w=Y,h=X.
    For a BOTTOM/TOP pad the long axis is vertical: size=(X,Y), rot=0.
    """
    out = {}
    n = len(nums)
    # centre-to-centre index span, symmetric about 0
    span = (n - 1) * P / 2.0
    for i, num in enumerate(nums):
        t = -span + i * P
        if side == "LEFT":
            out[num] = (-OFF, t, 0)
        elif side == "RIGHT":
            out[num] = (OFF, -t, 0)          # reverse so 10 is at the top, running downward
        elif side == "BOTTOM":
            # 7..9: symmetric about the centre, pad 7 nearest the LEFT end (adjacent to pad 6)
            out[num] = (-span + i * P, -OFF, 0)
        else:  # TOP: 19..24, symmetric, pad 19 nearest the RIGHT end (adjacent to pad 18)
            out[num] = (span - i * P, OFF, 0)
    return out


coords = {}
for sd, nums in SIDES.items():
    coords.update(pad_centres(sd, nums))

# sanity: every number 1..24 exactly once
assert sorted(coords) == list(range(1, 25)), sorted(coords)

T = "\t"


def pad(num, x, y, w, h):
    return (
        f'{T}{T}(pad "{num}" smd rect (at {x:.2f} {y:.2f}) (size {w:.2f} {h:.2f})\n'
        f'{T}{T}{T}(layers "F.Cu" "F.Paste" "F.Mask")\n'
        f'{T}{T}{T}(roundrect_rratio 0.25)\n'
        f'{T}{T})\n'
    )


lines = []
lines.append("(footprint \"balloon_flight_v9:SX1280_QFN24\"")
lines.append(f"{T}(version 20240108)")
lines.append(f"{T}(generator \"sx1280_land_pattern_from_fig173\")")
lines.append(f"{T}(layer \"F.Cu\")")
lines.append(f"{T}(descr \"Semtech SX1280 QFN 4x4mm land pattern. REBUILT from the vendor drawing "
             f"Figure 17-3 (SX1280/SX1281 Data Sheet Rev 3.2, March 2020, p.153, vendored at "
             f"docs/sx1280/): X={X} pad width, Y={Y} pad length, P={P} pitch, H=K={H} exposed pad, "
             f"Z={Z} pad-centre span, 6/3/9/6 pads per side.\")")
lines.append(f"{T}(tags \"QFN QFN24 SX1280 4x4\")")
lines.append(f"{T}(attr smd)")

for num in range(1, 25):
    x, y, _r = coords[num]
    if abs(x) > abs(y):
        w, h = Y, X          # LEFT / RIGHT: long axis horizontal
    else:
        w, h = X, Y          # BOTTOM / TOP: long axis vertical
    lines.append(pad(num, x, y, w, h))

# exposed pad, pad 25 (the datasheet numbers it 0; the footprint numbers it 25 -- same physical pad)
lines.append(pad(25, 0.0, 0.0, H, K))

# courtyard: pad outer edge + 0.25 mm
ext = OFF + Y / 2.0 + 0.25
lines.append(f"{T}(fp_line (start {-ext:.2f} {-ext:.2f}) (end {ext:.2f} {-ext:.2f}) "
             f"(stroke (width 0.05) (type solid)) (layer \"F.CrtYd\"))")
lines.append(f"{T}(fp_line (start {ext:.2f} {-ext:.2f}) (end {ext:.2f} {ext:.2f}) "
             f"(stroke (width 0.05) (type solid)) (layer \"F.CrtYd\"))")
lines.append(f"{T}(fp_line (start {ext:.2f} {ext:.2f}) (end {-ext:.2f} {ext:.2f}) "
             f"(stroke (width 0.05) (type solid)) (layer \"F.CrtYd\"))")
lines.append(f"{T}(fp_line (start {-ext:.2f} {ext:.2f}) (end {-ext:.2f} {-ext:.2f}) "
             f"(stroke (width 0.05) (type solid)) (layer \"F.CrtYd\"))")
# silkscreen reference corner marker near pad 1
lines.append(f"{T}(fp_line (start {-OFF - 0.60:.2f} {-OFF - 0.60:.2f}) "
             f"(end {-OFF - 0.60:.2f} {-OFF:.2f}) "
             f"(stroke (width 0.12) (type solid)) (layer \"F.SilkS\"))")
lines.append(f"{T}(fp_text reference \"REF**\" (at 0 {-OFF - 1.2:.2f}) (layer \"F.SilkS\") "
             f"(effects (font (size 1 1) (thickness 0.15))))")
lines.append(f"{T}(fp_text value \"SX1280\" (at 0 {OFF + 1.2:.2f}) (layer \"F.Fab\") "
             f"(effects (font (size 1 1) (thickness 0.15))))")
lines.append(")")

text = "\n".join(lines) + "\n"

# ---- validation before writing (the rule learned the hard way) -----------------------------
inp = out = 0
for ch in text:
    if ch == "(":
        inp += 1
    elif ch == ")":
        out += 1
assert inp == out, f"REFUSING TO WRITE: unbalanced parens {inp} vs {out}"
assert text.count('"') % 2 == 0, "REFUSING TO WRITE: odd number of quotes"

if "--write" in sys.argv:
    open(OUT, "w", encoding="utf-8").write(text)
    print("WROTE", OUT)
else:
    print("DRY RUN")

print(f"pads: 24 peripheral + 1 exposed; sizes ({Y}x{X}) L/R, ({X}x{Y}) B/T; exposed {H}x{K}")
print(f"pad-centre span: {Z} ; outer edge: {Z + Y} ; courtyard: {2 * ext:.2f}")
for sd, nums in SIDES.items():
    print(f"  {sd:<6} {nums}")
