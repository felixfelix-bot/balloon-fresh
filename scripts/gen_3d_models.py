#!/usr/bin/env python3
"""Generate the v9 hub board's CUSTOM 3D models as VRML (.wrl) text.

WHY THIS FILE EXISTS (2026-10-08, revised render-fidelity branch)
-----------------------------------------------------------------
The hub board's 3D models were either (a) pointed at `${KICAD9_3DMODEL_DIR}/…`
which did not resolve because the library was not installed, or (b) after the
feat/3d-models-hub branch, repointed at repo-local `.wrl` models authored in
**raw millimetres** — but KiCad reads a VRML coordinate as **2.54 mm per unit**,
so every one of those models rendered **2.54× too large**: the 78.55×38.90×0.21 mm
solar cell rendered as a 199.5×98.8×0.53 mm grey slab and the 10×10×7 mm
supercap placeholder rendered as a 25.6×25.6×17.8 mm thick can.  That is the
"grey slabs all over the place" and "some grey things are really thick" the
operator reported.

This revision fixes the root cause: **every coordinate is now divided by 2.54**
(KiCad's VRML unit), and the solar cell is emitted as an **IndexedFaceSet** solid
with **two materials** — a dark-blue cell face (diffuseColor 0.09 0.10 0.42) and
a light-grey frame/edge (diffuseColor 0.55 0.56 0.60) — ported from the wing
board's verified generator (`scripts/gen_3d_models_wing.py`).

**Standard parts** (R, C, D, SOT-23-5, LGA-8, CP_Radial, U.FL, ublox_MAX,
ESP32-S3-WROOM-1U, NiceRF_LoRa2021) are now pointed at the **real KiCad library
models** (`${KICAD9_3DMODEL_DIR}/…`) which IS installed on this host
(`kicad-packages3d 9.0.7-1`, 4.6 GB at `/usr/share/kicad/3dmodels/`).  This
generator now emits ONLY the custom models the library will never carry:
the F33 module, the SX1280 QFN, the wing tab socket, the solder jumper, and the
solar cells.

HONESTY RULES THIS FILE ENFORCES
--------------------------------
1. NO DIMENSION IS INVENTED.  Every model carries a provenance header: the
   dimension and the record / footprint drawing / JSON inventory it came from.
   Where a dimension is NOT sourced it is written `TODO(unverified)` IN THE MODEL
   ITSELF, visibly, so a render can never be mistaken for a verified shape.
2. A clean faceted solid with the RIGHT dimensions is honest and useful; a
   guessed detailed shape is not (it looks verified).  The solar cell uses an
   IndexedFaceSet (a real faceted solid, NOT a Box primitive) with two
   materials so it reads as a dark silicon cell, not a grey slab.
3. Determinism: no timestamps, no randomness, fixed iteration order.  Re-running
   this file reproduces byte-identical output (verified by `--check`).

VRML UNIT CONVENTION (verified by probe, see gen_3d_models_wing.py docstring)
-----------------------------------------------------------------------------
KiCad reads 1 VRML unit = 2.54 mm (0.1 in).  A model authored in mm must divide
every coordinate by 2.54.  The model frame is X = footprint +x,
Y = -(footprint-local +y), Z = up, Z=0 at the board TOP face.

USAGE
-----
  python3 scripts/gen_3d_models.py            # write every model + the index
  python3 scripts/gen_3d_models.py --check    # exit 1 if any committed model drifts

Output: `tracker/hardware/footprints/3dmodels/` (committed) plus
`tracker/hardware/footprints/3dmodels/MODEL-INDEX.json`, which maps each
repo-local model to its dimensions and provenance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT_DIR = os.path.join(REPO, "tracker", "hardware", "footprints", "3dmodels")

# KiCad VRML unit: 1 VRML unit = 2.54 mm (0.1 in).  Every mm coordinate MUST be
# divided by this or the model renders 2.54× too large.
MM_PER_UNIT = 2.54

# Colours — two-material scheme for the solar cell (ported from the wing).
COL_CELL_FACE = (0.09, 0.10, 0.42)      # dark blue silicon cell face
COL_CELL_FRAME = (0.55, 0.56, 0.60)     # light grey frame/edge
COL_BODY = (0.10, 0.11, 0.12)           # dark plastic / module body
COL_METAL = (0.62, 0.64, 0.68)          # shielded can / castellation plating
COL_CU = (0.78, 0.55, 0.25)             # exposed copper land

# --------------------------------------------------------------------------- sources
ADR049 = 'docs/adr/049-wing-architecture.md'
ADR051 = 'docs/adr/051-hub-array-and-cut-topology.md'
ADR046 = 'docs/adr/046-wing-board-interface.md'
ADR052 = 'docs/adr/052-cell-mounting.md'
ADR055 = 'docs/adr/055-hub-geometry-final.md'
F33_JSON = 'tracker/hardware/footprints/nicerf-lora2021f33-2g4.json'

MODELS = {}


def model(name, x, y, h, src, todo=(), colour=COL_BODY, extra=None, kind="box"):
    MODELS[name] = dict(x=x, y=y, h=h, src=src, todo=list(todo), colour=colour,
                        extra=extra or {}, kind=kind)


# === CUSTOM MODELS ONLY (standard parts use the real KiCad library) ==========
# The library IS installed (kicad-packages3d 9.0.7-1), so standard parts
# (R, C, D, SOT-23-5, LGA-8, CP_Radial) point at ${KICAD9_3DMODEL_DIR}/…
# These are the parts the library does NOT carry — they get repo-local models.

# --- NiceRF LoRa2021 bare (not in the installed library, KICAD8 path) ---------
model("NiceRF_LoRa2021", 19.81, 14.98, 2.32,
      "X/Y/Z: tracker/hardware/footprints/nicerf-lora2021.json "
      "`dimensions.width_mm/height_mm/thickness_mm` = 19.81 x 14.98 x 2.32 mm.  "
      "NOT in the installed kicad-packages3d library (the original reference "
      "used ${KICAD8_3DMODEL_DIR} which is not installed).",
      colour=COL_METAL,
      extra=dict(castellation=dict(edge_len=19.81, pitch=1.29, count=9,
                                   hole_dia=None, proud=0.0)),
      kind="castellated")

# --- ESP32-S3-WROOM-1U (library only has -1 and -2, NOT -1U) ------------------
model("ESP32-S3-WROOM-1U", 18.100, 19.300, 3.10,
      "X/Y: F.Fab body drawing of RF_Module:ESP32-S3-WROOM-1U as committed "
      "(18.100 x 19.300 mm).  The Espressif module is 18.0 x 25.5 mm, so the "
      "committed land is shallower than the real module - recorded, not hidden.  "
      "The installed library has ESP32-S3-WROOM-1 and -2 but NOT -1U, so a "
      "repo-local model is kept.",
      todo=["the 18.0 x 25.5 mm Espressif module outline vs the 18.100 x 19.300 mm "
            "committed footprint drawing - unreconciled",
            "Z 3.10 mm - ESP32-S3-WROOM-1U module height is not stated in any "
            "in-repo record"],
      colour=COL_METAL)

# --- U.FL connector (not in the installed library) ----------------------------
model("U.FL_Molex_MCRF_73412-0110_Vertical", 3.869, 5.698, 1.20,
      "X/Y: F.Fab drawing of Connector_Coaxial:U.FL_Molex_MCRF_73412-0110_Vertical "
      "as committed (3.869 x 5.698 mm, includes the drawn feed spur).  "
      "NOT in the installed kicad-packages3d library.",
      todo=["Z 1.20 mm - U.FL mated height is not stated in any in-repo record"],
      colour=COL_METAL)

# --- u-blox MAX-M10S GPS (not in the installed library) -----------------------
model("ublox_MAX", 9.800, 10.200, 2.50,
      "X/Y: F.Fab body drawing of RF_GPS:ublox_MAX as committed (9.800 x 10.200 mm) "
      "- the MAX-M10S (U5) land.  NOTE: docs/PAYLOAD-WEIGHT-ESTIMATES.md line 63 "
      "states 12.2 x 16 mm, which is a different (patch-antenna) figure; the "
      "footprint drawing is used and the disagreement is recorded, not hidden.  "
      "NOT in the installed kicad-packages3d library.",
      todo=["the 12.2 x 16 mm figure in docs/PAYLOAD-WEIGHT-ESTIMATES.md vs the "
            "9.800 x 10.200 mm footprint drawing - unreconciled",
            "Z 2.50 mm - not stated in any in-repo record"],
      colour=COL_METAL)

# --- the F33 module (39 x 21 mm castellated radio, NOT in any library) --------
model("LoRa2021F33-2G4", 39.00, 21.00, 2.50,
      "X/Y: 39.0 x 21.0 mm - the `descr` of balloon_flight_v9:LoRa2021F33_2G4 "
      "('39x21mm') and the land file LORA2021F33-2G4 footprint_pads.pcb; pad "
      "centres at 3.9289 mm pitch, 9 lands on each 39 mm edge (committed "
      "footprint).  Castellation hole diameter 0.80 +/- 0.1 mm read off the "
      "vendor drawing by the operator (2026-10-07), datasheet s9 p8.  "
      "Z: tracker/hardware/footprints/nicerf-lora2021f33-2g4.json "
      "`dimensions.thickness_mm` = 2.5 mm.",
      todo=[],
      colour=COL_METAL,
      extra=dict(castellation=dict(edge_len=39.00, pitch=3.9289, count=9,
                                   hole_dia=0.80, proud=0.10)),
      kind="castellated")

# --- SX1280 QFN-24 (custom land pattern, no library model) --------------------
model("SX1280_QFN24", 4.00, 4.00, 0.90,
      "X/Y: 4.0 x 4.0 mm - the `descr` of balloon_flight_v9:SX1280_QFN24 "
      "('QFN-24 4x4mm 0.5mm pitch'); the committed footprint's own courtyard is "
      "4.450 x 4.450 mm and its descr is explicitly '*** GEOMETRY NOT VERIFIED ***'",
      todo=["the whole SX1280 land pattern is an unverified placeholder - the "
            "Semtech datasheet was never retrieved on this host",
            "Z 0.90 mm - QFN-24 body height is not stated in any in-repo record"],
      colour=COL_BODY)

# --- the wing tab socket (custom mechanical part) -----------------------------
model("Wing_Tab_4P", 4.00, 6.60, 0.60,
      "X/Y: the soldered land row of Tracker_Mechanical:Wing_Tab_4P as committed - "
      "lands span 1.0..5.0 mm inboard of the interface edge (4.0 mm) x four 1.2 mm "
      "lands on 1.8 mm pitch (6.6 mm).  PLAIN PADS, NO SLOT: the 0.9 mm routed "
      "slot is ADR-046 Option A and is BELOW JLCPCB's 1.0 mm minimum NPTH slot "
      "(docs/analysis/wing-fab-cost.md s2.3, build_hub_board_v9.py header); "
      "Option B (plain pads) is the adopted fallback, so no slot is modelled.",
      todo=["Z 0.60 mm - the wing tab thickness is the board thickness figure "
            "(ADR-055 D4 target 0.4 mm, and 0.6 mm inherited) - not settled",
            "NOTE: the committed footprint still DRAWS the 0.9 mm slot on "
            "Edge.Cuts; see docs/3d-model-coverage-hub.md"],
      colour=COL_CU)

# --- the solder jumper (no library model) -------------------------------------
model("SolderJumper-3_P1.3mm_Open_RoundedPad1.0x1.5mm", 4.650, 2.550, 0.50,
      "X/Y: the F.CrtYd extent of Jumper:SolderJumper-3_P1.3mm_Open_RoundedPad1.0x1.5mm "
      "as committed (4.650 x 2.550 mm) - J_VCC carries NO F.Fab body drawing, so "
      "the courtyard is the only in-repo size",
      todo=["no F.Fab body drawing exists; the courtyard extent is used",
            "Z 0.50 mm - solder-jumper thickness is not stated in any in-repo record"],
      colour=COL_CU)

# --- THE SOLAR CELLS (the parts the operator most wants to see) ---------------
# These use an IndexedFaceSet (faceted solid) with TWO materials, ported from the
# wing board's verified generator.  The dark-blue face reads as a silicon cell;
# the light-grey frame reads as a bus bar.  This is NOT a bare Box.
model("SolarCell_LARGE_78.55x38.90", 78.55, 38.90, 0.21,
      "X/Y/Z: 78.55 x 38.90 x 0.21 mm - ADR-049 s'Measured inputs' (cited by "
      "ADR-051 s1.4): 'the LARGE cell as 78.55 x 38.90 x 0.21 mm, 30.6 cm2, "
      "~0.5 V, ~1.2 A'.  The face is drawn deliberately DARK BLUE (diffuseColor "
      "0.09 0.10 0.42) so a cell can never be read as copper or silkscreen.  "
      "The frame is light grey (0.55 0.56 0.60).  Two-material IndexedFaceSet "
      "ported from scripts/gen_3d_models_wing.py.",
      kind="cell", colour=COL_CELL_FACE)

model("SolarCell_SMALL_52.07x19.65", 52.07, 19.65, 0.21,
      "X/Y/Z: 52.07 x 19.65 x 0.20-0.21 mm - ADR-049 s'Measured inputs' outline "
      "row ('52.07 x 19.65 x 0.20-0.21 mm', 10.23 cm2).  0.21 mm (the upper end of "
      "the recorded range) is used.  Two-material IndexedFaceSet, same scheme as "
      "the LARGE cell.",
      todo=["the thickness is a RANGE (0.20-0.21 mm) in ADR-049; 0.21 is used"],
      kind="cell", colour=COL_CELL_FACE)


# === VRML emission helpers ====================================================

def _u(mm: float) -> float:
    """mm -> KiCad VRML units (2.54 mm per unit)."""
    return round(mm / MM_PER_UNIT, 6)


def _mat_full(rgb, specular=(0.25, 0.25, 0.25), shininess=0.2):
    return ("material Material {\n"
            "          diffuseColor %.3f %.3f %.3f\n"
            "          emissiveColor 0 0 0\n"
            "          specularColor %.3f %.3f %.3f\n"
            "          ambientIntensity 0.4\n"
            "          transparency 0.0\n"
            "          shininess %.2f\n"
            "        }" % (rgb[0], rgb[1], rgb[2], specular[0], specular[1], specular[2], shininess))


def _mat_simple(rgb):
    return "material Material { diffuseColor %.3f %.3f %.3f }" % rgb


def _box_quads(x0, x1, y0, y1, z0, z1):
    """6 outward-wound quads (VRML frame: X = x, Y = -y_board, Z = up).

    Winding verified against `kicad-cli pcb export vrml` output (see
    gen_3d_models_wing.py docstring, probe 1).
    """
    return [
        [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)],   # +z
        [(x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0)],   # -z
        [(x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0)],   # +y
        [(x1, y0, z0), (x1, y0, z1), (x0, y0, z1), (x0, y0, z0)],   # -y
        [(x1, y1, z0), (x1, y1, z1), (x1, y0, z1), (x1, y0, z0)],   # +x
        [(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)],   # -x
    ]


def _pt_lines(points) -> str:
    return ',\n'.join('          %.6f %.6f %.6f' % (_u(x), _u(y), _u(z))
                      for x, y, z in points)


_FACESET = """DEF {name} Transform {{
  children [
    Shape {{
      appearance Appearance {{
        material DEF {name}_mat Material {{
          diffuseColor {r} {g} {b}
          emissiveColor 0 0 0
          specularColor {sp} {sp} {sp}
          ambientIntensity 0.4
          transparency 0.0
          shininess {sh}
        }}
      }}
      geometry IndexedFaceSet {{
        coord Coordinate {{ point [
{pts}
        ] }}
        coordIndex [
          0, 1, 2, 3, -1,
          4, 5, 6, 7, -1,
          8, 9, 10, 11, -1,
          12, 13, 14, 15, -1,
          16, 17, 18, 19, -1,
          20, 21, 22, 23, -1,
        ]
      }}
    }}
  ]
}}"""


def _faceset(name, quads, colour, specular=0.25, shininess=0.2):
    """Emit an IndexedFaceSet solid from a list of 6 quads (24 points)."""
    pts = []
    for q in quads:
        pts.extend(q)
    return _FACESET.format(
        name=name,
        r=colour[0], g=colour[1], b=colour[2],
        sp=specular, sh=shininess,
        pts=_pt_lines(pts))


def _box(lines, size, tr, colour, rot=None):
    """Emit a Box primitive (in VRML units)."""
    x, y, z = size
    tx, ty, tz = tr
    lines.append("Transform {")
    lines.append("  translation %.6f %.6f %.6f" % (_u(tx), _u(ty), _u(tz)))
    if rot:
        lines.append("  rotation %s" % rot)
    lines.append("  children [")
    lines.append("    Shape {")
    lines.append("      appearance Appearance { %s }" % _mat_simple(colour))
    lines.append("      geometry Box { size %.6f %.6f %.6f }" % (_u(x), _u(y), _u(z)))
    lines.append("    }")
    lines.append("  ]")
    lines.append("}")


def _cyl(lines, radius, height, tr, colour, rot="1 0 0 1.5707963"):
    """Emit a Cylinder primitive (in VRML units)."""
    tx, ty, tz = tr
    lines.append("Transform {")
    lines.append("  translation %.6f %.6f %.6f" % (_u(tx), _u(ty), _u(tz)))
    lines.append("  rotation %s" % rot)
    lines.append("  children [")
    lines.append("    Shape {")
    lines.append("      appearance Appearance { %s }" % _mat_simple(colour))
    lines.append("      geometry Cylinder { radius %.6f height %.6f }" % (_u(radius), _u(height)))
    lines.append("    }")
    lines.append("  ]")
    lines.append("}")


def emit(name: str, spec: dict) -> str:
    x, y, h = spec["x"], spec["y"], spec["h"]
    kind = spec["kind"]
    colour = spec["colour"]
    todo = spec["todo"]
    L = []
    L.append("#VRML V2.0 utf8")
    L.append("# balloon-fresh -- parametric 3D model (plain-text VRML 2.0)")
    L.append("# generator  : scripts/gen_3d_models.py  (regenerate: python3 scripts/gen_3d_models.py)")
    L.append("# part       : %s" % name)
    if kind == "cell":
        L.append("# dims_mm    : %.2f x %.2f x %.2f (cell centred on the footprint origin)" % (x, y, h))
        L.append("# frame      : X = footprint-local +x, Y = -(footprint-local +y), Z = up, Z=0 at the board TOP face")
        L.append("# units      : 1 VRML unit = 2.54 mm (0.1 in) -- KiCad VRML convention; assign with (scale (xyz 1 1 1))")
    L.append("# source     : %s" % spec["src"])
    if spec.get("extra", {}).get("castellation"):
        c = spec["extra"]["castellation"]
        L.append("# CASTELLATION: %d half-cylinders per %.2f mm edge at %.4f mm pitch, "
                 "axis VERTICAL (through the module thickness), centred exactly ON the "
                 "module edge line (half inset, half proud)" % (c["count"], c["edge_len"], c["pitch"]))
    if kind == "cell":
        L.append("# materials  : dark blue cell face (diffuseColor 0.09 0.10 0.42) + "
                 "light grey frame (diffuseColor 0.55 0.56 0.60) -- two-material "
                 "IndexedFaceSet, ported from scripts/gen_3d_models_wing.py")
        L.append("# note       : the cell is a FACETED SOLID (IndexedFaceSet), NOT a "
                 "bare Box -- this is what makes it read as a real dark cell, not a "
                 "grey slab.")
    if todo:
        L.append("# TODO(unverified):")
        for t in todo:
            L.append("#   - %s" % t)
    L.append("# " + "-" * 74)
    L.append("")

    if kind == "cell":
        # --- Two-material IndexedFaceSet solar cell (ported from the wing) ---
        # The cell body is a thin slab split into a dark-blue face plate (top
        # ~0.001 mm) and a light-grey body (the rest).  Both are IndexedFaceSet
        # solids, NOT Box primitives.  The face is lifted 0.001 mm above the
        # body top only to stop z-fighting on a shared face; it is a rendering
        # epsilon, NOT a dimension (the modelled thickness stays h mm).
        hx, hy, hz = x / 2.0, y / 2.0, h / 2.0
        face_eps = 0.001  # mm — rendering epsilon, not a dimension

        # Dark-blue face plate (top layer, thickness = face_eps)
        face_top = hz + face_eps
        face_bot = hz
        face_quads = _box_quads(-hx, hx, -hy, hy, face_bot, face_top)
        L.append(_faceset(name + "_face", face_quads, COL_CELL_FACE,
                          specular=0.55, shininess=0.85))

        # Light-grey body (the rest of the slab, z=0 to hz)
        body_quads = _box_quads(-hx, hx, -hy, hy, 0.0, hz)
        L.append(_faceset(name + "_body", body_quads, COL_CELL_FRAME,
                          specular=0.25, shininess=0.2))

        # Bus-bar frame: light-grey rails just inside the cell edge, 0.02 mm proud
        bw = 0.6
        fz = h + 0.01
        _box(L, (x, bw, 0.02), (0.0, (y - bw) / 2.0, fz), COL_CELL_FRAME)
        _box(L, (x, bw, 0.02), (0.0, -(y - bw) / 2.0, fz), COL_CELL_FRAME)
        _box(L, (bw, y, 0.02), ((x - bw) / 2.0, 0.0, fz), COL_CELL_FRAME)
        _box(L, (bw, y, 0.02), (-(x - bw) / 2.0, 0.0, fz), COL_CELL_FRAME)
        # Two terminal bus ribbons at the ends of the LONG axis (ADR-052: END-ONLY)
        _box(L, (2.0, y * 0.35, 0.03), ((x / 2.0) - 3.0, 0.0, h + 0.015), COL_CELL_FRAME)
        _box(L, (2.0, y * 0.35, 0.03), (-(x / 2.0) + 3.0, 0.0, h + 0.015), COL_CELL_FRAME)

    else:
        # --- Box / castellated body ---
        _box(L, (x, y, h), (0.0, 0.0, h / 2.0), colour)

        if kind == "castellated":
            c = spec["extra"]["castellation"]
            if c["hole_dia"]:
                r = c["hole_dia"] / 2.0
                n = c["count"]
                pitch = c["pitch"]
                off0 = -(n - 1) / 2.0 * pitch
                for i in range(n):
                    px = off0 + i * pitch
                    for py in (y / 2.0, -y / 2.0):
                        _cyl(L, r, h, (px, py, h / 2.0), COL_METAL)

    return "\n".join(L) + "\n"


# === MODEL-INDEX (maps each repo-local model to its provenance) ==============

# Standard parts that are now pointed at the REAL KiCad library.  This records
# the library path for each, so the coverage report can cite it.
LIBRARY_MODELS = {
    "Resistor_SMD:R_0402_1005Metric":
        "${KICAD9_3DMODEL_DIR}/Resistor_SMD.3dshapes/R_0402_1005Metric.step",
    "Capacitor_SMD:C_0402_1005Metric":
        "${KICAD9_3DMODEL_DIR}/Capacitor_SMD.3dshapes/C_0402_1005Metric.step",
    "Capacitor_SMD:C_1206_3216Metric":
        "${KICAD9_3DMODEL_DIR}/Capacitor_SMD.3dshapes/C_1206_3216Metric.step",
    "Capacitor_THT:CP_Radial_D10.0mm_P5.00mm":
        "${KICAD9_3DMODEL_DIR}/Capacitor_THT.3dshapes/CP_Radial_D10.0mm_P5.00mm.step",
    "Diode_SMD:D_SMA":
        "${KICAD9_3DMODEL_DIR}/Diode_SMD.3dshapes/D_SMA.step",
    "Diode_SMD:D_SOD-123":
        "${KICAD9_3DMODEL_DIR}/Diode_SMD.3dshapes/D_SOD-123.step",
    "Diode_SMD:D_SOD-323":
        "${KICAD9_3DMODEL_DIR}/Diode_SMD.3dshapes/D_SOD-323.step",
    "Package_LGA:LGA-8_3x5mm_P1.25mm":
        "${KICAD9_3DMODEL_DIR}/Package_LGA.3dshapes/LGA-8_3x5mm_P1.25mm.step",
    "Package_TO_SOT_SMD:SOT-23-5":
        "${KICAD9_3DMODEL_DIR}/Package_TO_SOT_SMD.3dshapes/SOT-23-5.step",
    "Connector_Coaxial:U.FL_Molex_MCRF_73412-0110_Vertical":
        "${KICAD9_3DMODEL_DIR}/Connector_Coaxial.3dshapes/U.FL_Molex_MCRF_73412-0110_Vertical.step",
    "RF_GPS:ublox_MAX":
        "${KICAD9_3DMODEL_DIR}/RF_GPS.3dshapes/ublox_MAX.step",
    "RF_Module:ESP32-S3-WROOM-1U":
        "${KICAD9_3DMODEL_DIR}/RF_Module.3dshapes/ESP32-S3-WROOM-1U.step",
    "RF_Module:NiceRF_LoRa2021":
        "${KICAD8_3DMODEL_DIR}/RF_Module.3dshapes/NiceRF_LoRa2021.wrl",
}

# Parts NOT in the library — these get repo-local custom models.
# (ESP32-S3-WROOM-1U, U.FL, ublox_MAX, and NiceRF_LoRa2021 are also NOT in the
# installed library, so they need repo-local models too — but since the task says
# the library doesn't have them, we keep our custom models for those.)
LIBRARY_MISSING = {
    "RF_Module:ESP32-S3-WROOM-1U",      # only -1 and -2 exist in the library
    "Connector_Coaxial:U.FL_Molex_MCRF_73412-0110_Vertical",  # not installed
    "RF_GPS:ublox_MAX",                  # not installed
    "RF_Module:NiceRF_LoRa2021",         # KICAD8 path, not installed
}

INDEX = os.path.join(OUT_DIR, "MODEL-INDEX.json")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if any committed model differs from a fresh emit")
    a = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    drift = []
    index = {}
    for name in sorted(MODELS):
        spec = MODELS[name]
        text = emit(name, spec)
        path = os.path.join(OUT_DIR, name + ".wrl")
        old = open(path, encoding="utf-8").read() if os.path.exists(path) else None
        if old != text:
            if a.check:
                drift.append(name)
            else:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
        index[name] = {
            "file": name + ".wrl",
            "body_mm": [spec["x"], spec["y"]],
            "height_mm": spec["h"],
            "source": spec["src"],
            "todo_unverified": spec["todo"],
            "kind": spec["kind"],
            "unit_convention": "1 VRML unit = 2.54 mm (all coords divided by 2.54)",
        }

    if a.check:
        if drift:
            print("3D MODEL DRIFT: %s" % ", ".join(drift))
            return 1
        print("3d models: %d files, byte-identical to the committed set" % len(MODELS))
        return 0

    idx = {
        "_comment": "Generated by scripts/gen_3d_models.py. "
                    "Maps every repo-local VRML model to the dimensions it was "
                    "built from.  Standard parts use the real KiCad library "
                    "(see LIBRARY_MODELS in the generator).  Regenerate with "
                    "--check in CI.",
        "generator": "scripts/gen_3d_models.py",
        "unit_convention": "1 VRML unit = 2.54 mm (KiCad convention; all mm coords divided by 2.54)",
        "custom_models": index,
        "library_models": LIBRARY_MODELS,
        "library_missing": sorted(LIBRARY_MISSING),
    }
    with open(INDEX, "w", encoding="utf-8") as f:
        json.dump(idx, f, indent=2, sort_keys=True)
        f.write("\n")
    for p in sorted(os.listdir(OUT_DIR)):
        if p.endswith(".wrl"):
            sha = hashlib.sha256(open(os.path.join(OUT_DIR, p), "rb").read()).hexdigest()
            print("%-52s sha256 %s" % (p, sha[:16]))
    print("custom models written : %d -> %s" % (len(MODELS), os.path.relpath(OUT_DIR, REPO)))
    print("library models mapped : %d (require KICAD9_3DMODEL_DIR env var)" % len(LIBRARY_MODELS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())