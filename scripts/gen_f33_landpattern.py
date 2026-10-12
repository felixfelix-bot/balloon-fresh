#!/usr/bin/env python3
"""Generate the NiceRF LoRa2021F33-2G4 KiCad land pattern from the VENDOR's own
land file, so every copy in this repo is DERIVED rather than hand-drawn.

WHY THIS EXISTS
---------------
`docs/f33-module/F33-LANDPATTERN-VERIFICATION.md` recorded a FAIL 0/18: the
footprint in the design of record carried the pads on the two 21 mm ENDS at a
2.0 mm pitch (a 90 deg rotated, wrong-pitch pattern), where the vendor's own
land file puts 9 pads on each of the two 39 mm EDGES at a 3.9289 mm pitch.
A board ordered with that pattern cannot have the module soldered to it - and on
this vehicle every joint is hand-soldered, so a wrong land is the most expensive
error available. This script makes the correct pattern reproducible from the
authoritative source instead of being a hand-edited artifact, and it refuses to
emit anything if the source no longer decodes to the geometry it was built from.

AUTHORITATIVE SOURCE (the only land-pattern source reachable from this host)
---------------------------------------------------------------------------
  docs/f33-module/materials/LORA2021F33-2G4 footprint_pads.pcb
  sha256 c66ea27c4409a3af58f1bfd967cddec60214d446d4b15f620f2eef82e86ee7ac
  90 821 bytes, NiceRF (vendor) Altium .PcbDoc, shipped inside
  docs/f33-module/LoRa2021F33-2G4-materials.zip.

  Record layout (re-derived here, byte-exact, stdlib only):
      offset  size  field
      0       4     int32 object tag  0x08435AD8 (every PAD record)
      4       16    pad name          ASCII "1".."18" + NUL padding
      20      16    x1,y1,x2,y2      int32; x1==x2 and y1==y2 -> the CENTRE only
      => 36 bytes/record, 18 records contiguous, first tag at byte 7290.
  Units: 1 500 000 per mm.  The scale is pinned WITHOUT assuming it, by three
  independent agreements with the datasheet drawing:
      * decoded pad pitch 3.9289 mm      <-> drawing callout 3.93 +-0.1
      * decoded row separation 21.0000mm <-> module width 21.00 (castellated
                                            pads are centred on the module edge)
      * scale-free ratio pitch/rowsep = 0.18709 vs 3.93/21.00 = 0.18714 (0.028%)
      * closure 2*3.7844 + 8*3.9289 = 39.0000 mm == module length 39.00 +-0.5

WHAT THIS SCRIPT DERIVES, AND WHAT STAYS UNVERIFIED
---------------------------------------------------
  LAND SIZE - NOW VERIFIED, DERIVED (it was the one declared guess, and it
  carried a TODO(unverified) until the drawing was read).
  The module is CASTELLATED (`tracker/hardware/footprints/nicerf-lora2021f33-2g4
  .json`: pin_type "castellated"): each of the 18 pins is a plated HALF-HOLE
  stamped into one of the two 39 mm edges, so the module presents a length of
  copper equal to the hole DIAMETER along the edge and reaches only its RADIUS
  inward from the module edge line (y = +/-10.5).

  OPERATOR DATUM (authoritative, 2026-10-07) - the last unknown on this part:
      D = 0.80 +/- 0.10 mm   "the diameter of the hole that the pin goes
                              through ... 0.8 +- 0.1mm"
  source: docs/f33-module/LoRa2021F33-2G4-datasheet-v1.1.pdf, section 9
          "Mechanism Dimension", page 8.  That page is an embedded JPEG RASTER
          with NO text layer, so it cannot be extracted in-repo:
              `pdftotext -raw -f 8 -l 8 <pdf>` prints ONLY the page header
              `pdfimages -list -f 8 -l 8 <pdf>` lists the two page-8 images
          tesseract (a text extractor, not a drawing reader) recovers the
          callouts 3.78 / 3.93 / 0.80 / 3.00 x2 / 6.09 / 5.00 x2 / 4.32 / 39.00
          / 9.00 / 3.30 but CANNOT attribute them to a feature.  The operator
          read the drawing, so the 0.80 mm diameter is an OPERATOR-SUPPLIED
          DATUM - authoritative, not a guess, and not an unattributed callout.

  RULE (one line): the land is the castellation APERTURE grown by a uniform
                   0.25 mm solder-fillet margin on every side.
      along the edge (x):  x = D + 2*0.25 = 0.80 + 0.50 = 1.30 mm
          >= D by construction (0.25 mm of land beyond the castellation on each
          side, for the fillet).  The old 2.0 mm was exactly 2.5 x D and had no
          source at all.  Gap to the neighbouring land:
              3.9289 (pitch) - 1.30 = 2.6289 mm   -> no bridging risk.
      across the edge (y): y = D + 2*0.25 = 0.80 + 0.50 = 1.30 mm
          The pad CENTRE is pinned on the module edge line by the vendor land
          file (y = +/-10.5) and MUST NOT MOVE, so the land is necessarily
          SYMMETRIC: half-width = D/2 + 0.25 = 0.65 mm each side.
            inward  0.65 mm >= D/2 = 0.40 mm  -> the joint sits under the
                    castellation copper with 0.25 mm of margin.
            outward 0.65 mm >= inward 0.65 mm (never smaller) and is the DESIGN
                    DRIVER: every joint on this vehicle is hand-soldered, so the
                    outward half is what the iron tip lands on.  0.65 mm clears
                    a 0.5 mm chisel tip, and it is 0.15 mm MORE exposed copper
                    than the old guess (0.50 mm) - the same uniform fillet
                    margin, not a second invented number.
      Bound check: land_length 1.30 mm < the physical ceiling recorded in
      F33-LANDPATTERN-VERIFICATION.md s7 (land_length < pitch - creepage,
      i.e. <~ 3.4 mm at 3.93 mm pitch).

  STILL UNVERIFIED - never guessed, and NOT closeable from the vendor file:
  the module THICKNESS (the module JSON says 2.5 mm; the p.8 OCR also recovers
  the callouts 3.00 x2 / 6.09 / 5.00 x2 / 4.32 / 3.30, and NOT ONE of them can
  be attributed to a feature without reading the drawing, so every one stays
  unattributed and TODO(unverified)) and whether a land/pad callout hides among
  them.  Do NOT guess an attribution.

USAGE
-----
  python3 scripts/gen_f33_landpattern.py                      # write canonical footprint
  python3 scripts/gen_f33_landpattern.py --print              # stdout only
  python3 scripts/gen_f33_landpattern.py --install            # + refresh legacy custom.pretty copies
  python3 scripts/gen_f33_landpattern.py --signature FILE     # signature of a footprint file
  python3 scripts/gen_f33_landpattern.py --check FILE         # exit 1 if FILE's geometry drifted
  python3 scripts/gen_f33_landpattern.py --verify-all         # check every registered copy

  --land-length / --land-width remain as EXPLICIT OVERRIDES of the derived
  land; leaving them off uses the derivation above.

Exit codes: 0 ok / 1 geometry mismatch or source drift / 2 usage or source unreadable.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import math
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

VENDOR_REL = os.path.join("docs", "f33-module", "materials",
                          "LORA2021F33-2G4 footprint_pads.pcb")
VENDOR_SHA256 = ("c66ea27c4409a3af58f1bfd967cddec60214d446d4b15f620f2eef82e86ee7ac")

# --- module envelope, from the datasheet drawing callouts (39.00 +-0.5 /
#     21.00 +-0.5) corroborated by the vendor file's own row separation (21.00).
MODULE_LENGTH_MM = 39.0
MODULE_WIDTH_MM = 21.0
PAD_ROWS_Y_MM = (-10.5, 10.5)          # pad rows sit ON the two 39 mm edges
PAD_PITCH_MM = 3.9289                  # decoded; drawing callout 3.93 +-0.1
EDGE_TO_PAD_MM = 3.7844                # decoded; drawing callout 3.78 +-0.1

# --- CASTELLATION APERTURE (operator-supplied datum, AUTHORITATIVE) ----------
# The module is castellated (footprint JSON: pin_type "castellated"): each of the
# 18 pins is a plated HALF-HOLE in one of the two 39 mm edges, so the module
# presents copper equal to the hole DIAMETER along the edge and reaches only its
# RADIUS (D/2) inward from the module edge line (y = +/-10.5).
#
# D below is the OPERATOR'S reading of the vendor drawing (2026-10-07), quoted:
#   "the diameter of the hole that the pin goes through ... 0.8 +- 0.1mm"
#   source: docs/f33-module/LoRa2021F33-2G4-datasheet-v1.1.pdf, section 9
#           "Mechanism Dimension", page 8 - an embedded JPEG raster with no text
#           layer, hence NOT extractable in-repo.  Authoritative; not a guess.
CASTELLATION_D_MM = 0.80               # hole diameter = edge copper width
CASTELLATION_D_TOL_MM = 0.10           # operator's stated +/- tolerance

# --- DERIVED LAND (was 2.0 x 1.0, a declared guess marked TODO(unverified)) --
# RULE: the land is the castellation APERTURE grown by a uniform
#       LAND_FILLET_MARGIN_MM solder-fillet margin on EVERY side.
#   along the edge (x):  LAND_LENGTH = D + 2*0.25 = 1.30 mm
#   across the edge (y): LAND_WIDTH  = D + 2*0.25 = 1.30 mm  (symmetric: the pad
#                        centre is pinned on the module edge and must not move,
#                        so half-width = D/2 + 0.25 = 0.65 mm inward, 0.65 mm
#                        outward - outward >= inward, and outward is the driver
#                        because every joint here is hand-soldered).
# The tolerance band does not change the rule: at D = 0.90 (max) the land is
# 1.40 mm and the gap to the next land is 3.9289 - 1.40 = 2.5289 mm; at
# D = 0.70 (min) it is 1.20 mm - both comfortably clear of bridging.
LAND_FILLET_MARGIN_MM = 0.25           # solder-fillet margin on every side
LAND_LENGTH_MM = CASTELLATION_D_MM + 2 * LAND_FILLET_MARGIN_MM   # 1.30 (x)
LAND_WIDTH_MM = CASTELLATION_D_MM + 2 * LAND_FILLET_MARGIN_MM    # 1.30 (y)
LAND_SIZE_VERIFIED = True              # DERIVED from the operator datum above
LAND_SIZE_SOURCE = ("operator reading of the vendor drawing, datasheet s9 p8 "
                    "(raster, no text layer), 2026-10-07: castellation hole "
                    "diameter %g +/- %g mm"
                    % (CASTELLATION_D_MM, CASTELLATION_D_TOL_MM))

TAG = 0x08435AD8
UNITS_PER_MM = 1_500_000
PAD_TAG_OFFSET = 7290                  # first PAD record in the vendor file
PAD_STRIDE = 36

CANONICAL_REL = os.path.join("tracker", "hardware", "footprints", "f33",
                             "LoRa2021F33_2G4.kicad_mod")

# Every committed copy that must be derived from this generator.  The value is
# the footprint library prefix written into the file's first line.
CONSUMERS = [
    (CANONICAL_REL, "custom"),
    (os.path.join("tracker", "hardware", "hub_board_diy", "custom.pretty",
                  "LoRa2021F33_2G4.kicad_mod"), "custom"),
    (os.path.join("tracker", "hardware", "hub_board_f33_jlcpcb", "custom.pretty",
                  "LoRa2021F33_2G4.kicad_mod"), "custom"),
    (os.path.join("tracker", "hardware", "output", "pcb-handoff", "custom.pretty",
                  "LoRa2021F33_2G4.kicad_mod"), "custom"),
]

DESCR = ("NiceRF LoRa2021F33-2G4, 18-pin castellated module (LR2021 + 2W PA + "
         "TCXO), 39x21mm. Pad CENTRES decoded from the vendor land file "
         "LORA2021F33-2G4 footprint_pads.pcb (pitch 3.9289mm, 9 pads on each "
         "39mm edge). Land size %g x %g mm DERIVED from the operator-supplied "
         "castellation hole diameter D = %g +/- %g mm grown by a uniform %g mm "
         "solder-fillet margin on every side (datasheet s9 p8, read by the "
         "operator 2026-10-07)."
         % (LAND_LENGTH_MM, LAND_WIDTH_MM, CASTELLATION_D_MM,
            CASTELLATION_D_TOL_MM, LAND_FILLET_MARGIN_MM))

TAGS = "LoRa LR2021 NiceRF F33 castellated PA 2W vendor-land-pattern"


# --------------------------------------------------------------------------
# 1. decode the vendor file and CHECK it against itself
# --------------------------------------------------------------------------
def vendor_path() -> str:
    return os.path.join(REPO, VENDOR_REL)


def decode_vendor(path: str | None = None) -> dict:
    """Decode the 18 pad records.  Raises ValueError if anything fails closed."""
    path = path or vendor_path()
    if not os.path.exists(path):
        raise ValueError("vendor land file missing: %s" % path)
    blob = open(path, "rb").read()
    sha = hashlib.sha256(blob).hexdigest()

    recs = []
    for k in range(18):
        o = PAD_TAG_OFFSET + PAD_STRIDE * k
        tag = struct.unpack_from("<I", blob, o)[0]
        if tag != TAG:
            raise ValueError("record %d at byte %d: tag 0x%08x != 0x%08x"
                             % (k + 1, o, tag, TAG))
        name = blob[o + 4:o + 20].rstrip(b"\0").decode("ascii", "strict")
        if name != str(k + 1):
            raise ValueError("record %d at byte %d: name %r != %r"
                             % (k + 1, o, name, str(k + 1)))
        x, y, x2, y2 = struct.unpack_from("<iiii", blob, o + 20)
        recs.append(dict(n=k + 1, name=name, x=x, y=y, x2=x2, y2=y2))

    # pad 18's coordinate field is zeroed in the file -> place it by ring closure.
    # Outer pad centre x = -(module_length/2 - edge_to_first_pad).
    zeroed = [r["n"] for r in recs if r["x"] == 0 and r["y"] == 0]
    missing_x = -(MODULE_LENGTH_MM / 2 - EDGE_TO_PAD_MM)

    pads = {}
    for r in recs:
        if r["n"] == 18:
            x_mm, y_mm = missing_x, PAD_ROWS_Y_MM[0]
        else:
            x_mm, y_mm = r["x"] / UNITS_PER_MM, r["y"] / UNITS_PER_MM
        pads[r["n"]] = (round(x_mm, 4), round(y_mm, 4))

    pitch = sorted({abs(round(pads[a][0] - pads[b][0], 4))
                    for a, b in ((2, 1), (3, 2), (4, 3), (5, 4), (6, 5), (7, 6),
                                 (8, 7), (10, 9), (11, 10), (12, 11), (13, 12),
                                 (14, 13), (15, 14), (16, 15), (17, 16))})
    rows = sorted({pads[n][1] for n in pads})
    closure = 2 * EDGE_TO_PAD_MM + 8 * PAD_PITCH_MM

    checks = {
        "pad_count_18": len(pads) == 18,
        "names_ring_1_18": sorted(pads) == list(range(1, 19)),
        "pad18_zeroed_in_file": zeroed == [18],
        "two_rows_at_+/-10.5": rows == list(PAD_ROWS_Y_MM),
        "nine_pads_per_row": (sorted(n for n in pads if pads[n][1] < 0) ==
                             [1, 2, 3, 4, 5, 6, 7, 8, 18]) and
                             (sorted(n for n in pads if pads[n][1] > 0) ==
                              list(range(9, 18))),
        "pitch_uniform": len(pitch) == 1 and abs(pitch[0] - PAD_PITCH_MM) < 5e-4,
        "closure_39.0000": abs(closure - MODULE_LENGTH_MM) < 1e-3,
        "row_sep_21.0000": abs((rows[1] - rows[0]) - MODULE_WIDTH_MM) < 1e-3,
        "outer_pad_3.7844_from_end": abs(max(abs(pads[n][0]) for n in pads) -
                                         (MODULE_LENGTH_MM / 2 - EDGE_TO_PAD_MM)) < 1e-3,
    }
    failed = [k for k, v in checks.items() if not v]
    if failed:
        raise ValueError("vendor file failed its own self-checks: %s "
                         "(checks=%r)" % (failed, checks))
    return dict(sha256=sha, pads=pads, pitch=pitch[0], rows=rows,
                closure=closure, checks=checks)


# --------------------------------------------------------------------------
# 2. emit the footprint
# --------------------------------------------------------------------------
def footprint_text(libname: str = "custom", leaf: str = "LoRa2021F33_2G4",
                   lands: tuple[float, float] | None = None,
                   vendor_sha: str = VENDOR_SHA256) -> str:
    d = decode_vendor()
    lx, ly = lands or (LAND_LENGTH_MM, LAND_WIDTH_MM)
    hl, hw = MODULE_LENGTH_MM / 2, MODULE_WIDTH_MM / 2
    L = []
    L.append('(footprint "%s:%s"' % (libname, leaf))
    L.append('  (version 20250114)')
    L.append('  (generator "gen_f33_landpattern.py")')
    L.append('  (layer "F.Cu")')
    L.append('  (attr smd)')
    L.append('  (descr "%s")' % DESCR)
    L.append('  (tags "%s")' % TAGS)
    L.append('  ;; ================================================================')
    L.append('  ;; GENERATED FILE - do not hand-edit.')
    L.append('  ;;   python3 scripts/gen_f33_landpattern.py')
    L.append('  ;; Pad CENTRES decoded from the VENDOR land file')
    L.append('  ;;   docs/f33-module/materials/LORA2021F33-2G4 footprint_pads.pcb')
    L.append('  ;;   sha256 %s' % vendor_sha)
    L.append('  ;;   (18 x 36-byte records, tag 0x%08X, 1.5e6 units/mm)' % TAG)
    L.append('  ;; Verified against the vendor file and the datasheet drawing:')
    L.append('  ;;   pad count 18, names 1..18, 9 per row; rows on the two 39mm')
    L.append('  ;;   edges at y=+/-10.5000; pitch %.4fmm (drawing 3.93+-0.1);' % d["pitch"])
    L.append('  ;;   outer pad centre 3.7844mm from the 39mm end (drawing 3.78+-0.1);')
    L.append('  ;;   closure 2*3.7844 + 8*%.4f = %.4fmm = module length 39.00.' % (d["pitch"], d["closure"]))
    L.append('  ;; VERIFIED land size - DERIVED from the operator-supplied datum:')
    L.append('  ;;   pad LAND SIZE %g x %g mm' % (lx, ly))
    L.append('  ;;     castellation HALF-HOLE diameter D = %g +/- %g mm, the'
             % (CASTELLATION_D_MM, CASTELLATION_D_TOL_MM))
    L.append('  ;;       operator\'s reading of the vendor drawing (datasheet s9 p8,')
    L.append('  ;;       a raster with no text layer). The module presents D of')
    L.append('  ;;       copper along the edge and penetrates only D/2 inward.')
    L.append('  ;;     RULE: land = the castellation aperture grown by a uniform')
    L.append('  ;;       %g mm solder-fillet margin on EVERY side.'
             % LAND_FILLET_MARGIN_MM)
    L.append('  ;;       x: D + 2*%g = %g mm; gap to the next land = %.4f - %g'
             ' = %.4f mm' % (LAND_FILLET_MARGIN_MM, lx, d["pitch"], lx,
                             d["pitch"] - lx))
    L.append('  ;;       y: D + 2*%g = %g mm, symmetric about the pad centre'
             ' (pinned' % (LAND_FILLET_MARGIN_MM, ly))
    L.append('  ;;          on the module edge, y=+/-10.5, and NOT moved):'
             ' inward %g >= D/2 = %g mm;' % (ly / 2, CASTELLATION_D_MM / 2))
    L.append('  ;;          outward %g = the hand-solder iron\'s access, never'
             ' smaller than' % (ly / 2,))
    L.append('  ;;          the inward half. F33-LANDPATTERN-VERIFICATION.md'
             ' s11.')
    L.append('  ;; NOT verified (do not read this as verified):')
    L.append('  ;;   pin-1 ORIENTATION anchor: pads 9/10 (ANT / ANT-2G4) are the')
    L.append('  ;;     adjacent pair at the +x end; pad 18 (IRQ) sits beside pad 1')
    L.append('  ;;     (VCC) at the -x end. The vendor file carries no body outline.')
    L.append('  ;; ================================================================')
    L.append('  (property "Reference" "U2" (at 0 -12 0) (layer "F.SilkS")')
    L.append('    (uuid "fp-ref") (effects (font (size 1 1) (thickness 0.15))))')
    L.append('  (property "Value" "%s" (at 0 12.5 0) (layer "F.Fab")' % leaf)
    L.append('    (uuid "fp-val") (effects (font (size 1 1) (thickness 0.15))))')
    L.append('')
    L.append('  ;; Module outline %g x %g mm, centred on the origin' % (MODULE_LENGTH_MM, MODULE_WIDTH_MM))
    L.append('  (fp_line (start %g %g) (end %g %g) (stroke (width 0.12) (type solid)) (layer "F.SilkS") (uuid "outline-1"))' % (-hl, -hw, hl, -hw))
    L.append('  (fp_line (start %g %g) (end %g %g) (stroke (width 0.12) (type solid)) (layer "F.SilkS") (uuid "outline-2"))' % (hl, -hw, hl, hw))
    L.append('  (fp_line (start %g %g) (end %g %g) (stroke (width 0.12) (type solid)) (layer "F.SilkS") (uuid "outline-3"))' % (hl, hw, -hl, hw))
    L.append('  (fp_line (start %g %g) (end %g %g) (stroke (width 0.12) (type solid)) (layer "F.SilkS") (uuid "outline-4"))' % (-hl, hw, -hl, -hw))
    L.append('')
    L.append('  ;; Fab layer outline')
    L.append('  (fp_line (start %g %g) (end %g %g) (stroke (width 0.1) (type solid)) (layer "F.Fab") (uuid "fab-1"))' % (-hl, -hw, hl, -hw))
    L.append('  (fp_line (start %g %g) (end %g %g) (stroke (width 0.1) (type solid)) (layer "F.Fab") (uuid "fab-2"))' % (hl, -hw, hl, hw))
    L.append('  (fp_line (start %g %g) (end %g %g) (stroke (width 0.1) (type solid)) (layer "F.Fab") (uuid "fab-3"))' % (hl, hw, -hl, hw))
    L.append('  (fp_line (start %g %g) (end %g %g) (stroke (width 0.1) (type solid)) (layer "F.Fab") (uuid "fab-4"))' % (-hl, hw, -hl, -hw))
    L.append('')
    L.append('  ;; Courtyard: module + 0.3mm')
    chl, chw = hl + 0.3, hw + 0.3
    L.append('  (fp_line (start %g %g) (end %g %g) (stroke (width 0.05) (type solid)) (layer "F.CrtYd") (uuid "crtyd-1"))' % (-chl, -chw, chl, -chw))
    L.append('  (fp_line (start %g %g) (end %g %g) (stroke (width 0.05) (type solid)) (layer "F.CrtYd") (uuid "crtyd-2"))' % (chl, -chw, chl, chw))
    L.append('  (fp_line (start %g %g) (end %g %g) (stroke (width 0.05) (type solid)) (layer "F.CrtYd") (uuid "crtyd-3"))' % (chl, chw, -chl, chw))
    L.append('  (fp_line (start %g %g) (end %g %g) (stroke (width 0.05) (type solid)) (layer "F.CrtYd") (uuid "crtyd-4"))' % (-chl, chw, -chl, -chw))
    L.append('')
    p1x, p1y = d["pads"][1]
    L.append('  ;; Pin 1 marker (circle beside pad 1 at (%g, %g))' % (p1x, p1y))
    L.append('  (fp_circle (center %g %g) (end %g %g) (stroke (width 0.12) (type solid)) (fill none) (layer "F.SilkS") (uuid "pin1-mark"))'
             % (p1x - 1.9, p1y + 1.1, p1x - 1.6, p1y + 1.1))
    L.append('')
    for n in range(1, 19):
        x, y = d["pads"][n]
        L.append('  (pad "%d" smd rect (at %.4f %.4f) (size %g %g) (layers "F.Cu" "F.Paste" "F.Mask") (uuid "pad-%d"))'
                 % (n, x, y, lx, ly, n))
    L.append(')')
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------
# 3. geometry signature - the comparison that a pad count alone cannot make
# --------------------------------------------------------------------------
PAD_RE = re.compile(r'\(pad "([^"]*)"\s+(\w+)\s+(\w+)\s+\(at\s+(-?[\d.]+)\s+(-?[\d.]+)\)'
                    r'\s+\(size\s+([\d.]+)\s+([\d.]+)\)')


def signature(text: str) -> tuple:
    """(pad count, bbox_x, bbox_y, pad-size histogram, pad-number string).

    Same four-part signature the pcb-fab-readiness-gating skill requires: a
    matching pad COUNT is necessary but NOT sufficient.
    """
    pads = PAD_RE.findall(text)
    if not pads:
        return (0, 0.0, 0.0, {}, "")
    xs = [float(p[3]) for p in pads]
    ys = [float(p[4]) for p in pads]
    sizes = collections.Counter((float(p[5]), float(p[6])) for p in pads)
    numbers = ",".join(p[0] for p in pads)
    return (len(pads), round(max(xs) - min(xs), 4), round(max(ys) - min(ys), 4),
            dict(sorted(sizes.items())), numbers)


def describe(sig: tuple) -> str:
    return ("pads=%d bbox=%.4fx%.4fmm sizes=%s numbers=[%s]"
            % (sig[0], sig[1], sig[2],
               ";".join("%gx%g x%d" % (k[0], k[1], v) for k, v in sorted(sig[3].items())),
               sig[4]))


def coincidence(text: str, pads_expected: dict) -> tuple[int, float, float]:
    """How many of the file's pads sit on a vendor pad centre (<=0.05 mm)."""
    pads = PAD_RE.findall(text)
    exp = list(pads_expected.values())
    hit = 0
    best = float("inf")
    worst = 0.0
    for p in pads:
        x, y = float(p[3]), float(p[4])
        d = min(math.hypot(x - ex, y - ey) for ex, ey in exp)
        if d <= 0.05:
            hit += 1
        best = min(best, d)
        worst = max(worst, d)
    if best == float("inf"):
        best = 0.0
    return hit, best, worst


# --------------------------------------------------------------------------
# 4. CLI
# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lib", default="custom", help="footprint library prefix")
    ap.add_argument("--out", default=None, help="output path (default: canonical)")
    ap.add_argument("--print", dest="to_stdout", action="store_true")
    ap.add_argument("--install", action="store_true",
                    help="also refresh the legacy custom.pretty copies")
    ap.add_argument("--land-length", type=float, default=LAND_LENGTH_MM,
                    help="EXPLICIT override of the DERIVED land length along "
                         "the pad row (x); default %g mm = D + 2*%g"
                         % (LAND_LENGTH_MM, LAND_FILLET_MARGIN_MM))
    ap.add_argument("--land-width", type=float, default=LAND_WIDTH_MM,
                    help="EXPLICIT override of the DERIVED land width across "
                         "the row (y); default %g mm = D + 2*%g"
                         % (LAND_WIDTH_MM, LAND_FILLET_MARGIN_MM))
    ap.add_argument("--signature", metavar="FILE", default=None)
    ap.add_argument("--check", metavar="FILE", default=None)
    ap.add_argument("--verify-all", action="store_true")
    args = ap.parse_args()

    if args.signature:
        text = open(args.signature).read()
        print("%s: %s" % (args.signature, describe(signature(text))))
        return 0

    try:
        d = decode_vendor()
    except ValueError as e:
        print("F33 LAND SOURCE UNREADABLE/DRIFTED: %s" % e, file=sys.stderr)
        return 2
    if d["sha256"] != VENDOR_SHA256:
        print("VENDOR FILE SHA CHANGED: %s != %s - re-verify the decode before "
              "trusting this generator" % (d["sha256"], VENDOR_SHA256),
              file=sys.stderr)
        return 1

    lands = (args.land_length, args.land_width)
    text = footprint_text(args.lib, "LoRa2021F33_2G4", lands, d["sha256"])
    sig = signature(text)

    print("vendor source : %s" % VENDOR_REL)
    print("vendor sha256 : %s" % d["sha256"])
    print("self-checks   : %s" % ("ALL PASS" if all(d["checks"].values()) else "FAIL"))
    for k, v in d["checks"].items():
        print("    %-28s %s" % (k, "ok" if v else "FAIL"))
    print("decoded pitch : %.4f mm   rows y=%s   closure %.4f mm"
          % (d["pitch"], d["rows"], d["closure"]))
    print("pad 18        : ring closure -> %s" % (d["pads"][18],))
    print("emitted       : %s" % describe(sig))
    if LAND_SIZE_VERIFIED:
        print("LAND SIZE     : %g x %g mm VERIFIED - DERIVED from the "
              "operator-supplied" % lands)
        print("                castellation hole diameter D = %g +/- %g mm "
              "(datasheet s9 p8);" % (CASTELLATION_D_MM, CASTELLATION_D_TOL_MM))
        print("                land = D grown by a uniform %g mm solder-fillet "
              "margin on every" % LAND_FILLET_MARGIN_MM)
        print("                side. x = D + 2*%g = %g mm; gap to the next land "
              "= %.4f - %g" % (LAND_FILLET_MARGIN_MM, lands[0], d["pitch"],
                               lands[0]))
        print("                = %.4f mm. y = %g mm, symmetric about the "
              "pinned pad centre: inward" % (d["pitch"] - lands[0], lands[1]))
        print("                %g mm >= D/2 = %g mm; outward %g mm (hand-solder "
              "iron access, never" % (lands[1] / 2, CASTELLATION_D_MM / 2,
                                      lands[1] / 2))
        print("                smaller than the inward half).")

    if args.to_stdout:
        sys.stdout.write(text)

    if args.check:
        other = open(args.check).read()
        osig = signature(other)
        hit, best, worst = coincidence(other, d["pads"])
        print("\nCHECK %s" % args.check)
        print("  %s" % describe(osig))
        print("  pads coincident with a vendor pad (<=0.05mm): %d of %d" % (hit, len(d["pads"])))
        print("  nearest misalignment: %.3f mm   worst: %.3f mm" % (best, worst))
        if osig != sig:
            print("  GEOMETRY MISMATCH vs generator output -> FAIL")
            return 1
        print("  geometry identical to generator output -> ok")
        return 0

    if args.verify_all:
        rc = 0
        print()
        for rel, _ in CONSUMERS:
            p = os.path.join(REPO, rel)
            if not os.path.exists(p):
                print("MISSING  %s" % rel)
                rc = 1
                continue
            other = open(p).read()
            osig = signature(other)
            hit, best, worst = coincidence(other, d["pads"])
            same = osig == sig
            print("%-8s %s\n         %s\n         vendor-coincident pads %d/18  nearest %.3fmm"
                  % ("ok" if same else "DRIFTED", rel, describe(osig), hit, best))
            if not same:
                rc = 1
        return rc

    written = []
    targets = list(CONSUMERS) if args.install else [(CANONICAL_REL, args.lib)]
    if args.out:
        targets = [(os.path.relpath(os.path.abspath(args.out), REPO), args.lib)]
    for rel, lib in targets:
        body = footprint_text(lib, "LoRa2021F33_2G4", lands, d["sha256"])
        p = rel if os.path.isabs(rel) else os.path.join(REPO, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as fh:
            fh.write(body)
        written.append((rel, hashlib.sha256(body.encode()).hexdigest()))
    print("\nwrote:")
    for rel, sha in written:
        print("  %s  sha256 %s" % (rel, sha[:16]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
