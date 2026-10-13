#!/usr/bin/env python3
"""Parametric 3D (VRML) models for the v9 WING board's parts  ->  tracker/hardware/3dmodels/

WHY THIS FILE EXISTS
--------------------
The v9 wing board (`tracker/hardware/wing_board/wing_board_v9.kicad_pcb`) carries 12 placed
references but, until this generator existed, **no** of them carried a 3D model, so a
3D render of the wing showed a bare FR4 outline: the three solar cells that the whole wing
exists to fly were invisible.  The hub board's models are worse than absent -- they point at
`${KICAD9_3DMODEL_DIR}/...step`, i.e. at `kicad-packages3d`, a 4.77 GB package that is **not
installed** here (and must not be: the machine has ~3 GB free), so the hub renders bare too.

This generator emits **plain-text VRML 2.0** models that are committed in-repo, so a render
resolves with nothing installed.  Every dimension is cited in the model's own header; a
dimension with no in-repo source is written as `TODO(unverified)`, never guessed.

MEASURED MODEL CONVENTIONS (verified 2026-10-08 by probe, not assumed)
---------------------------------------------------------------------
KiCad's 3D model frame is: **X = footprint-local +x, Y = -(footprint-local +y), Z = up,
with Z = 0 at the board's TOP face.**  The unit is **2.54 mm (0.1 in)** -- a model authored
in mm must be divided by 2.54.  Both facts were measured, twice, independently:

1. Probe export.  A throwaway board (100 x 60 mm L-shaped outline with a 10 x 10 mm notch
   cut out of the board (0,0) corner) carrying a 4 x 4 x 1 mm marker model whose model-local
   Y was authored as -(footprint-local y) was exported with
   `kicad-cli pcb export vrml --units mm`.  The exported geometry reproduced the marker at
   exactly 4.00 x 4.00 x 1.00 mm, the model coordinates passed through with no rotation
   (the model subtree carries `rotation 0 0 1 0`), the board outline's notch came out
   mirrored in Y, and the model subtree carried `translation 0 0 0.11811024`
   (0.3 mm = half of the 0.6 mm board thickness).  So: Y is inverted, Z = board top face,
   and the scale factor is 2.54.
2. A shipped KiCad demo model, `/usr/share/kicad/demos/ecc83/3d_shapes/ecc83.wrl`, spans
   8.86 x 8.86 x 20.963 model units = 22.5 x 22.5 x 53.3 mm, against a footprint courtyard
   radius of 10.6 mm in `ecc83-pp.kicad_pcb` -- an ECC83 envelope is ~22 mm across and its
   axis is vertical.  8.86 units x 2.54 = 22.5 mm fits; 8.86 mm does not.

RUN
---
    python3 scripts/gen_3d_models_wing.py            # write/refresh the models
    python3 scripts/gen_3d_models_wing.py --check    # exit 1 if the tree is stale (CI mode)
"""
from __future__ import annotations

import argparse
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
MODEL_DIR = os.path.join(REPO, 'tracker', 'hardware', '3dmodels')

# The unit KiCad reads a VRML coordinate in (see the module docstring, probe 1 + 2).
MM_PER_UNIT = 2.54

# --------------------------------------------------------------------------- sources
# Every number below is quoted from an in-repo record.  Nothing is invented; where the
# repo has no number the model says so out loud.
ADR049 = 'docs/adr/049-wing-architecture.md'
ADR051 = 'docs/adr/051-hub-array-and-cut-topology.md'
ADR046 = 'docs/adr/046-wing-board-interface.md'
ADR048 = 'docs/adr/048-v9-hub-wing-interfaces.md'
ADR055 = 'docs/adr/055-hub-geometry-final.md'
BOARD = 'tracker/hardware/wing_board/wing_board_v9.kicad_pcb'
GEN = 'tracker/hardware/wing_board/build_wing_v9.py'

# cross-refs for the small cell: ADR-046 §3.3 places the 52 x 19 mm land field; the board file
# names the footprint "WingV9:SolarCell_52x19mm" with value "SolarCell_52x19mm_0.5V"; the 0.21 mm
# used is the top of the measured 0.20-0.21 mm band.
CELL_SMALL = dict(name='SolarCell_SMALL', x=52.07, y=19.65, z=0.21,
                  source=(f'{ADR049} section "Measured inputs", small cell: "Outline | 52.07 x '
                          f'19.65 x 0.20-0.21 mm".  Cross-refs: {ADR046} §3.3 (the 52 x 19 mm land '
                          f'field) and {BOARD} (footprint "WingV9:SolarCell_52x19mm").'))
CELL_LARGE = dict(name='SolarCell_LARGE', x=78.55, y=38.90, z=0.21,
                  source=(f'{ADR051} §1.4: "78.55 x 38.90 x 0.21 mm, 30.6 cm2, ~0.5 V, ~1.2 A" '
                          f'(large cell) -- repeated in {ADR049} section "Measured inputs".'))


def _u(mm: float) -> float:
    """mm -> KiCad VRML units (2.54 mm per unit)."""
    return round(mm / MM_PER_UNIT, 6)


def _pt_lines(points) -> str:
    return ',\n'.join('          %.6f %.6f %.6f' % (_u(x), _u(y), _u(z)) for x, y, z in points)


def _box_quads(x0, x1, y0, y1, z0, z1):
    """6 outward-wound quads (VRML frame: X = x, Y = -y_board, Z = up).

    Winding verified against `kicad-cli pcb export vrml` output: the top quad yields the
    exporter normal `0 0 1`, the bottom `0 0 -1` (see the module docstring, probe 1).
    """
    return [
        [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)],   # +z
        [(x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0)],   # -z
        [(x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0)],   # +y
        [(x1, y0, z0), (x1, y0, z1), (x0, y0, z1), (x0, y0, z0)],   # -y
        [(x1, y1, z0), (x1, y1, z1), (x1, y0, z1), (x1, y0, z0)],   # +x
        [(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)],   # -x
    ]


_SHAPE = """DEF {name} Transform {{
  children [
    Shape {{
      appearance Appearance {{
        material DEF {name}_mat Material {{
          diffuseColor {r} {g} {b}
          emissiveColor 0 0 0
          specularColor {sp} {sp} {sp}
          ambientIntensity 0.4
          transparency {tr}
          shininess {sh}
        }}
      }}
      geometry IndexedFaceSet {{
        coord Coordinate {{ point [
{pts}
        ] }}
        coordIndex [
          {idx}
        ]
      }}
    }}
  ]
}}"""


def _emit(name, quads, diffuse, transparency=0.0, shininess=0.2, specular=0.1) -> str:
    pts, idx, n = [], [], 0
    for quad in quads:
        pts.extend(quad)
        idx.append(', '.join(str(n + k) for k in range(len(quad))) + ', -1,')
        n += len(quad)
    return _SHAPE.format(name=name, r=diffuse[0], g=diffuse[1], b=diffuse[2],
                         sp=specular, tr=transparency, sh=shininess,
                         pts=_pt_lines(pts),
                         idx='\n          '.join(idx))


def _box(name, x0, x1, y0, y1, z0, z1, diffuse, **kw) -> str:
    return _emit(name, _box_quads(x0, x1, y0, y1, z0, z1), diffuse, **kw)


def _cylinder_z(name, dia, z0, z1, seg, diffuse, **kw) -> str:
    """Vertical cylinder centred on the model origin (NPTH hole marker, fiducial dot)."""
    r = dia / 2.0
    quads = []
    for i in range(seg):
        a0, a1 = 2 * math.pi * i / seg, 2 * math.pi * (i + 1) / seg
        p0 = (r * math.cos(a0), r * math.sin(a0))
        p1 = (r * math.cos(a1), r * math.sin(a1))
        quads.append([(p0[0], p0[1], z0), (p0[0], p0[1], z1),
                      (p1[0], p1[1], z1), (p1[0], p1[1], z0)])
    quads.append([(r * math.cos(2 * math.pi * i / seg), r * math.sin(2 * math.pi * i / seg), z1)
                  for i in range(seg)])
    quads.append([(r * math.cos(-2 * math.pi * i / seg), r * math.sin(-2 * math.pi * i / seg), z0)
                  for i in range(seg)])
    return _emit(name, quads, diffuse, **kw)


def _hdr(part, dims, source, extra=()):
    lines = [
        '# balloon-fresh -- parametric 3D model (plain-text VRML 2.0)',
        '# generator  : scripts/gen_3d_models_wing.py  '
        '(regenerate: python3 scripts/gen_3d_models_wing.py)',
        f'# part       : {part}',
        f'# dims_mm    : {dims}',
        '# frame      : X = footprint-local +x, Y = -(footprint-local +y), Z = up, '
        'Z=0 at the board TOP face',
        '# units      : 1 VRML unit = 2.54 mm (0.1 in) -- KiCad VRML convention; '
        'assign with (scale (xyz 1 1 1))',
    ]
    for s in source.splitlines():
        lines.append('# source     : ' + s)
    for e in extra:
        lines.append('# note       : ' + e)
    return '\n'.join(lines)


def _todo(*items):
    return [f'TODO(unverified): {i}' for i in items]


def _wrl(header: str, nodes) -> str:
    return '#VRML V2.0 utf8\n' + header.rstrip('\n') + '\n' + '\n'.join(nodes) + '\n'


# --------------------------------------------------------------------------- the models
def cell_model(cls) -> str:
    x, y, z = cls['x'], cls['y'], cls['z']
    hx, hy = x / 2.0, y / 2.0
    nodes = [
        # the illuminated (front) face -- deliberately deep violet-blue, NOT copper-coloured,
        # so that a render reads "solar cell" at a glance
        _box(cls['name'] + '_face', -hx, hx, -hy, hy, z, z + 0.001,
             (0.09, 0.10, 0.42), specular=0.55, shininess=0.85),
        # body: sides and back contact (silvery grey -- not an illuminated face)
        _box(cls['name'] + '_body', -hx, hx, -hy, hy, 0.0, z,
             (0.55, 0.56, 0.60), specular=0.25),
    ]
    return _wrl(_hdr(
        f'{cls["name"]} -- bare polycrystalline silicon cell, one cell of the wing string',
        f'{x} x {y} x {z} (x along the wing, y across the wing, z = thickness; '
        'cell centred on the footprint origin)',
        cls['source'],
        extra=[
            'the cell is modelled CENTRED on the footprint origin, which is what '
            f'{ADR046} §3.4 declares the cell centre to be (origins x = 30 / 88 / 146 mm).',
            'the 0.035 mm copper land + solder standoff under the cell is NOT modelled '
            '(it is 17 % of the cell thickness and would hide the lands).',
            'the illuminated face plate is lifted 0.001 mm above the body top only to stop the '
            'two shapes z-fighting on a shared face; it is a rendering epsilon, NOT a dimension '
            '(the modelled thickness stays 0.21 mm).',
        ] + _todo('solder-tab geometry of the cell (contact width, pitch, distance from the cell '
                  'edge) -- no in-repo source carries it; ADR-049 files it as the order blocker',
                  'whether the two terminations are BOTH on the front face, or one front and one '
                  'back -- ADR-049 section "Measured inputs" says front+back for the small cell, '
                  'while ADR-046 §3.4 assumes two lands at the two x ends')),
        nodes)


def tab_model() -> str:
    """J1 -- the 4-pin wing tab interface.  Lands are the real pads from the board file."""
    lands = (('1', 'SOLAR_P', 9.8), ('2', 'GND', 11.6), ('3', 'RF_FEED', 13.4),
             ('4', 'SOLAR_N', 15.2))
    nodes = [_box(f'tab_land_p{pin}', -7.0, -3.0, -ly - 0.6, -ly + 0.6, 0.0, 0.035,
                  (0.85, 0.68, 0.30), specular=0.6, shininess=0.8)
             for pin, _net, ly in lands]
    return _wrl(_hdr(
        'J1 -- wing tab, 4-pin interface (4 solder lands; the finger substrate is board outline)',
        '4 lands 4.0 x 1.2 x 0.035 thick at 1.8 mm pitch, land row centred at x = -5 mm, '
        'y = 9.8 / 11.6 / 13.4 / 15.2 mm; pinout 1=SOLAR_P 2=GND 3=RF_FEED 4=SOLAR_N',
        f'{BOARD} pads of footprint "WingV9:WingTab_v9_4pin" (4.0 x 1.2 rect at x=-5, '
        f'y = 9.8 .. 15.2); pinout {GEN} TAB_PADS and {ADR046} §2.1; F.Cu copper thickness '
        '0.035 mm from the board stackup.',
        extra=[
            'the 8 x 9 x 0.6 mm tab FINGER is board substrate (part of the Edge.Cuts outline) and '
            'is rendered by KiCad itself -- this model draws only the interface lands, so the tab '
            'is not double-drawn.',
            'lands are at the 0.035 mm F.Cu copper thickness; the solder fillet that will actually '
            'join the wing to the hub socket is NOT modelled.',
        ] + _todo('the hub-side socket: the 0.9 x 6.0 mm slot, its tolerance, and the 0.9 mm slot '
                  'vs 0.6 mm tab 0.00 mm worst-case clearance are ADR-048 items 3/6 -- hub side, '
                  'not on the wing')),
        nodes)


# H1 / H2 / H3 (2.2 mm NPTH) deliberately have NO MODEL.  Measured 2026-10-08: `kicad-cli pcb
# render` punches NPTH bores itself, and a marker that occupies the drill volume (a dia 2.2 x
# 0.6 cylinder at z = -0.6..0) PLUGS the bore -- the three hole sites go from 20/25 transparent
# pixels in a 5x5 window to 0/25, i.e. the hole disappears from the render.  A zero-thickness
# bore-liner variant was also tried and produced a byte-identical image to assigning no model, so
# it buys nothing.  Disposition: NO MODEL, and the hole is rendered by KiCad's own drill punching.
# (Also note: the 12 refs' pad copper -- including these holes' annular absence -- is drawn by the
# board renderer itself, which is why a "land" model below is copper-matched rather than new shape.)
#
# The same measurement is why the three fiducial dots, the RF1 pad and the J1 lands are modelled
# AT their real copper size: the renderer already draws that copper, and the model's job is only to
# make the reference explicit and tinted, never to invent an added body.
def fiducial_model() -> str:
    return _wrl(_hdr(
        'FID1 / FID2 / FID3 -- 1 mm fiducial (marker, not a part)',
        'dia 1.0 mm x 0.035 mm copper dot on the top face, centred on the footprint origin',
        f'{BOARD} (pad "1" smd circle, size 1 x 1) and footprint name "WingV9:Fiducial_1mm_Mask2mm" '
        '(1 mm copper, 2 mm mask opening), F.Cu 0.035 mm from the stackup.',
        extra=['NO PART EXISTS here; the 2 mm solder-mask opening is not modelled (it is a mask '
               'aperture, not geometry)']),
        [_cylinder_z('fiducial_dot', 1.0, 0.0, 0.035, 18, (0.87, 0.72, 0.25), specular=0.6)])


def ferrite_model() -> str:
    return _wrl(_hdr(
        'FB1 -- 0402 ferrite-bead provision (DNP: NOT FITTED on v9)',
        '1.016 x 0.508 x 0.5 body, modelled translucent to mark a provision rather than a part',
        f'the body length and width: the 0402 (imperial) size code is definitionally '
        f'0.040 x 0.020 in = 1.016 x 0.508 mm, and {BOARD} carries the matching footprint '
        f'"WingV9:FerriteBead_0402_V2provision" (pads 0.5 x 0.6 at x = +/-0.45).  The 0.5 mm '
        f'HEIGHT is TODO(unverified): a typical 0402 body height, not a sourced figure.',
        extra=[
            f'the board file gives Value "FerriteBead_0402_DNP_V2only" -- DNP, so this body is a '
            'PROVISION.  It is rendered at transparency 0.75 so that a render cannot be mistaken '
            'for a populated part.',
            f'the footprint pads (0.5 x 0.6 rect at x = +/-0.45, {BOARD}) are consistent with a 0402 '
            'body; they are board copper and are drawn by KiCad, not by this model.',
        ] + _todo('the 0.5 mm body height (the 0402 code fixes length and width only)',
                  'the actual ferrite part number and impedance -- the DNP provision fixes neither')),
        [_box('ferrite_body', -0.508, 0.508, -0.254, 0.254, 0.0, 0.5,
              (0.30, 0.30, 0.32), transparency=0.75, specular=0.2)])


def rf_provision_model() -> str:
    return _wrl(_hdr(
        'RF1 -- V2 RF-feed provision land (copper only; no component fitted on v9)',
        '2.0 x 2.0 x 0.035 mm copper land centred on the footprint origin',
        f'{BOARD} (pad "1" smd rect, size 2 x 2) and F.Cu 0.035 mm from the stackup; '
        f'{ADR046} §2.4 makes the wing RF a V2 provision.',
        extra=[f'the v9 wing carries only this land: no antenna, no matching network and no '
               f'connector exists to model ({ADR046} §2.4 and §3.4b)']),
        [_box('rf_provision_pad', -1.0, 1.0, -1.0, 1.0, 0.0, 0.035,
              (0.85, 0.68, 0.30), specular=0.6, shininess=0.8)])


MODELS = {
    'cells/solar_cell_small_52.07x19.65x0.21.wrl': cell_model(CELL_SMALL),
    'cells/solar_cell_large_78.55x38.90x0.21.wrl': cell_model(CELL_LARGE),
    'wing/wing_v9_tab_4pin_lands.wrl': tab_model(),
    'wing/wing_v9_fiducial_1mm_dot.wrl': fiducial_model(),
    'wing/ferrite_bead_0402_dnp.wrl': ferrite_model(),
    'wing/wing_v9_rf_provision_pad_2x2.wrl': rf_provision_model(),
}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--check', action='store_true',
                    help='do not write; exit 1 if the committed models differ from the generator')
    ap.add_argument('--out', default=MODEL_DIR, help=f'model tree (default {MODEL_DIR})')
    args = ap.parse_args(argv)

    stale, wrote = [], []
    for rel, text in MODELS.items():
        path = os.path.join(args.out, rel)
        old = open(path).read() if os.path.exists(path) else None
        if old == text:
            print(f'  ok      {rel}')
            continue
        stale.append(rel)
        if args.check:
            print(f'  STALE   {rel}')
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as fh:
            fh.write(text)
        wrote.append(rel)
        print(f'  wrote   {rel}  ({len(text)} bytes)')

    print(f'\nmodels: {len(MODELS)}  written: {len(wrote)}  stale: {len(stale)}')
    if args.check and stale:
        print('STALE MODEL TREE -- run: python3 scripts/gen_3d_models_wing.py', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
