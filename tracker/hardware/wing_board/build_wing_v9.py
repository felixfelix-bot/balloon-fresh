#!/usr/bin/env python3
"""Build the v9 WING board  ->  tracker/hardware/wing_board/wing_board_v9.kicad_pcb

WHY THIS FILE EXISTS
--------------------
`wing_schematic.py` (the pre-existing wing generator) is the SCHEMATIC SOURCE for the
wing.  It is electrically correct -- 3x Device:Solar_Cell in series, a wing tab, an RF
feed, an optional ferrite bead -- but it fakes the PHYSICAL side: every solar cell and
every RF pad is a `TestPoint:TestPoint_THTPad_D2.0mm_Drill1.0mm`, which is a 2 mm test
via, not a solar-cell land and not an orderable assembly.  It also collapses the
3-cell string's negative terminal onto the same net as the tab's GND pin, which a
4-wings-in-series stack (ADR-006) cannot do (ADR-046 s0.2).

This builder therefore:
  * READS the generator's netlist (`wing_schematic.net`, the committed output of
    `wing_schematic.py`) and ASSERTS the expected nets are present, so the reuse is
    checked rather than claimed;
  * reproduces that series topology with REAL footprints:
      - SolarCell_52x19mm: a real 1.6 x 4.0 mm solder land per cell terminal;
      - WingTab_v9_4pin: a 4-land edge tab whose pinout is fixed by ADR-046 s2.1
        (1=SOLAR_P, 2=GND, 3=RF_FEED, 4=SOLAR_N);
      - real NPTH handling holes, fiducials and the V2 provisions;
  * SPLITS the generator's single GND net into SOLAR_N (the string's negative) and GND
    (the tab's ground/plane reference), per ADR-046 s0.2;
  * DROPS the generator's V2-only etched PCB Yagi, keeping only the tab's RF_FEED
    provision land (ADR-046 s2.4).

WRITE PATH
----------
The file is emitted as KiCad 9 S-expression text directly -- no pcbnew module.  This is
the repo's own idiom (`tracker/hardware/gen_pcb.py`: "Writes S-expression text directly
-- no pcbnew module needed").  Reason: in the fleet's KiCad 9.0.8 python bindings the
`pcbnew.PCB_SHAPE(board)` / `pcbnew.FOOTPRINT(board)` constructors reject a board created
by `pcbnew.CreateEmptyBoard()` (SWIG overload resolution failure against
`BOARD_ITEM *`), so a from-scratch board cannot be built through the bindings here.
Emitted text is validated by the repo's own gates (kicad-cli DRC, drc_score.py,
fleet/pcb_order_gate.py) -- not by this file's own claims.

Geometry (board-local mm, origin = body lower-left, +x toward the tip) is fixed by
docs/adr/046-wing-board-interface.md s3.  Nothing here invents a number not in that ADR.

Run:  python3 build_wing_v9.py
"""
from __future__ import annotations

import os
import re
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
NETLIST = os.path.join(HERE, 'wing_schematic.net')
OUT = os.path.join(HERE, 'wing_board_v9.kicad_pcb')

# ------------------------------------------------------------------ reuse the source
EXPECTED_NETS = {'GND', 'RF_SIGNAL', 'SOLAR_MID1', 'SOLAR_MID2', 'SOLAR_OUT'}


def read_source_netlist(path: str) -> dict:
    """Parse the generator's netlist -> {net_name: [(ref, pin), ...]}.

    Balanced-paren scan from the `(nets` section; each `(net (code N)(name "X") ...)`
    block contributes its `(ref "R")(pin "P")` node pairs.
    """
    text = open(path).read()
    i = text.find('(nets')
    if i < 0:
        raise SystemExit(f'no (nets section in {path}')
    nets: dict[str, list[tuple[str, str]]] = {}
    depth = 0
    start = None
    for j, c in enumerate(text[i:], start=i):
        if c == '(':
            depth += 1
            if depth == 2:
                start = j
        elif c == ')':
            if depth == 2 and start is not None:
                body = text[start:j + 1]
                if body.lstrip().startswith('(net'):
                    m = re.search(r'\(name\s+"([^"]*)"\)', body)
                    if m:
                        nets[m.group(1)] = re.findall(
                            r'\(ref\s+"([^"]*)"\)\s*\(pin\s+"([^"]*)"\)', body)
                start = None
            depth -= 1
            if depth == 0:
                break
    return nets


def check_reuse(nets: dict) -> None:
    missing = EXPECTED_NETS - set(nets)
    if missing:
        raise SystemExit(f'source netlist is missing nets {sorted(missing)} -- refusing '
                         f'to build a wing that does not match wing_schematic.py')
    print('reuse check OK: wing_schematic.py nets ->',
          {k: nets[k] for k in sorted(nets)})
    if not any(r.startswith('SC') for r, _ in nets.get('GND', [])):
        raise SystemExit('source netlist no longer ties the last cell to GND -- '
                         'ADR-046 s0.2 assumes it does; re-read the source')
    print('confirmed: source collapses last-cell(-) onto GND; v9 SPLITS it into '
          'SOLAR_N + GND (ADR-046 s0.2)')


# ------------------------------------------------------------------ geometry (ADR-046)
BODY_W, BODY_H = 176.0, 25.0
TAB_LEN, TAB_W = 8.0, 9.0
TAB_Y0, TAB_Y1 = 8.0, 17.0
CELL_CX = (30.0, 88.0, 146.0)          # cell centres: 4+26, 62+26, 120+26
LAND_W, LAND_H = 1.6, 4.0              # ADR-046 s3.4
TAB_LAND_W, TAB_LAND_H = 4.0, 1.2
TAB_PAD_X = -5.0
TAB_PADS = (('1', 'SOLAR_P', 9.8), ('2', 'GND', 11.6),
            ('3', 'RF_FEED', 13.4), ('4', 'SOLAR_N', 15.2))
TRACK_W = 0.4

NETS = ['SOLAR_P', 'SOLAR_N', 'SOLAR_MID1', 'SOLAR_MID2', 'GND', 'RF_FEED']
NET_IDX = {n: i + 1 for i, n in enumerate(NETS)}

_Layers = """  (layers
    (0 "F.Cu" signal)
    (31 "B.Cu" signal)
    (32 "B.Adhes" user "B.Adhesive")
    (33 "F.Adhes" user "F.Adhesive")
    (34 "B.Paste" user)
    (35 "F.Paste" user)
    (36 "B.SilkS" user "B.Silkscreen")
    (37 "F.SilkS" user "F.Silkscreen")
    (38 "B.Mask" user)
    (39 "F.Mask" user)
    (40 "Dwgs.User" user "User.Drawings")
    (41 "Cmts.User" user "User.Comments")
    (42 "Eco1.User" user "User.Eco1")
    (43 "Eco2.User" user "User.Eco2")
    (44 "Edge.Cuts" user)
    (45 "Margin" user)
    (46 "B.CrtYd" user "B.Courtyard")
    (47 "F.CrtYd" user "F.Courtyard")
    (48 "B.Fab" user)
    (49 "F.Fab" user)
  )"""

_Setup = """  (setup
    (stackup
      (layer "F.SilkS" (type "Top Silk Screen"))
      (layer "F.Paste" (type "Top Solder Paste"))
      (layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))
      (layer "F.Cu" (type "copper") (thickness 0.035))
      (layer "dielectric 1" (type "core") (thickness 0.51) (material "FR4") (loss_tangent 0.02) (epsilon_r 4.5))
      (layer "B.Cu" (type "copper") (thickness 0.035))
      (layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))
      (layer "B.Paste" (type "Bottom Solder Paste"))
      (layer "B.SilkS" (type "Bottom Silk Screen"))
      (copper_finish "None")
      (dielectric_constraints no)
    )
    (pad_to_mask_clearance 0.05)
    (aux_axis_origin 0 0)
    (grid_origin 0 0)
  )"""


_UUID_N = 0


def u() -> str:
    """Deterministic uuid (ADR-030 zero-inference/deterministic pipeline): the same
    builder input must produce the same board bytes, so this is a namespaced uuid5
    over a monotonic counter, NOT uuid4."""
    global _UUID_N
    _UUID_N += 1
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'balloon-fresh/feat-wing-board-v9/{_UUID_N}'))


def fmt(v: float) -> str:
    s = f'{v:.6f}'.rstrip('0').rstrip('.')
    return s if s else '0'


# ------------------------------------------------------------------ s-expr emitters
def gr_line(x1, y1, x2, y2, layer='Edge.Cuts', width=0.1):
    return (f'  (gr_line (start {fmt(x1)} {fmt(y1)}) (end {fmt(x2)} {fmt(y2)})\n'
            f'    (stroke (width {width}) (type default)) (layer "{layer}") (uuid "{u()}"))')


def gr_text(txt, x, y, size=1.0, layer='F.SilkS'):
    return (f'  (gr_text "{txt}" (at {fmt(x)} {fmt(y)} 0) (layer "{layer}") (uuid "{u()}")\n'
            f'    (effects (font (size {size} {size}) (thickness 0.12))))')


def segment(net, x1, y1, x2, y2, layer='F.Cu', width=TRACK_W):
    n = NET_IDX[net]
    return (f'  (segment (start {fmt(x1)} {fmt(y1)}) (end {fmt(x2)} {fmt(y2)})\n'
            f'    (width {width}) (layer "{layer}") (net {n}) (uuid "{u()}"))')


def prop(name, val, layer='F.Fab', hidden=True):
    # KiCad 9 canonical order: (at)(layer)(hide)(uuid)(effects).  `hide` is a direct
    # child of the property, NOT inside (effects) -- getting that wrong makes
    # kicad-cli report only "Failed to load board".
    h = '\n      (hide yes)' if hidden else ''
    return (f'    (property "{name}" "{val}"\n'
            f'      (at 0 0 0)\n'
            f'      (layer "{layer}"){h}\n'
            f'      (uuid "{u()}")\n'
            f'      (effects\n        (font\n          (size 1 1)\n          (thickness 0.15)\n        )\n      )\n    )')


def pad(num, kind, shape, x, y, w, h, layers, net=None, drill=None, rot=None):
    """kind: smd | thru_hole | np_thru_hole"""
    at = f'{fmt(x)} {fmt(y)}' + (f' {rot}' if rot is not None else '')
    s = [f'    (pad "{num}" {kind} {shape} (at {at}) (size {fmt(w)} {fmt(h)})']
    if drill is not None:
        s.append(f' (drill {fmt(drill)})')
    s.append(' (layers ' + ' '.join(f'"{l}"' for l in layers) + ')')
    if net is not None:
        n = NET_IDX[net]
        s.append(f' (net {n} "{net}")')
    s.append(f' (uuid "{u()}"))')
    return ''.join(s)


def footprint(libname, ref, value, x, y, body, attr='smd'):
    head = [f'  (footprint "{libname}"',
            '    (layer "F.Cu")',
            f'    (uuid "{u()}")',
            f'    (at {fmt(x)} {fmt(y)})',
            prop('Reference', ref, 'F.SilkS'),
            prop('Value', value),
            f'    (attr {attr})' if attr else None]
    lines = [h for h in head if h]
    lines.append(body)
    lines.append('  )')
    return '\n'.join(lines)


def cell_footprint(ref, cx, net_left, net_right):
    b = []
    b.append(f'    (fp_rect (start {fmt(-26)} 3) (end {fmt(26)} 22)'
             f' (stroke (width 0.12) (type solid)) (fill no) (layer "F.SilkS") (uuid "{u()}"))')
    b.append(f'    (fp_text user "+" (at {fmt(-26)} 23.6) (layer "F.SilkS") (uuid "{u()}")'
             f' (effects (font (size 1 1) (thickness 0.12))))')
    b.append(f'    (fp_text user "-" (at {fmt(26)} 23.6) (layer "F.SilkS") (uuid "{u()}")'
             f' (effects (font (size 1 1) (thickness 0.12))))')
    # real solder lands, one per cell terminal (ADR-046 s3.4)
    b.append(pad('1', 'smd', 'rect', -28.0, 0.0, LAND_W, LAND_H,
                 ('F.Cu', 'F.Paste', 'F.Mask'), net_left))
    b.append(pad('2', 'smd', 'rect', 28.0, 0.0, LAND_W, LAND_H,
                 ('F.Cu', 'F.Paste', 'F.Mask'), net_right))
    return footprint('WingV9:SolarCell_52x19mm', ref, 'SolarCell_52x19mm_0.5V',
                     cx, 12.5, '\n'.join(b))


def tab_footprint():
    b = []
    for num, netname, y in TAB_PADS:
        b.append(pad(num, 'smd', 'rect', TAB_PAD_X, y, TAB_LAND_W, TAB_LAND_H,
                     ('F.Cu', 'F.Paste', 'F.Mask'), netname))
    for txt, y in (('P', 9.8 - 1.7), ('N', 15.2 + 1.7)):
        b.append(f'    (fp_text user "{txt}" (at {fmt(TAB_PAD_X)} {fmt(y)})'
                 f' (layer "F.SilkS") (uuid "{u()}")'
                 f' (effects (font (size 0.6 0.6) (thickness 0.1))))')
    b.append(f'    (fp_rect (start {fmt(TAB_PAD_X-2.0)} {fmt(TAB_Y0+0.4)})'
             f' (end {fmt(TAB_PAD_X+2.0)} {fmt(TAB_Y1-0.4)})'
             f' (stroke (width 0.1) (type solid)) (fill none) (layer "F.SilkS") (uuid "{u()}"))')
    # footprint origin at (0,0): pads carry the absolute tab x as their local offset
    return footprint('WingV9:WingTab_v9_4pin', 'J1', 'WingTab_v9_4pin',
                     0.0, 0.0, '\n'.join(b))


def hole_footprint(ref, x, y):
    b = pad('', 'np_thru_hole', 'circle', 0.0, 0.0, 2.2, 2.2,
            ('*.Cu', '*.Mask'), None, drill=2.2)
    return footprint('WingV9:MountingHole_2.2mm_NPTH', ref, 'MountingHole_NPTH_2.2mm',
                     x, y, b, attr=None)


def fiducial_footprint(ref, x, y):
    b = pad('1', 'smd', 'circle', 0.0, 0.0, 1.0, 1.0, ('F.Cu', 'F.Mask'))
    return footprint('WingV9:Fiducial_1mm_Mask2mm', ref, 'Fiducial_1mm_Mask2mm',
                     x, y, b)


def ferrite_footprint(x, y):
    b = [pad('1', 'smd', 'rect', -0.45, 0.0, 0.5, 0.6, ('F.Cu', 'F.Paste', 'F.Mask')),
         pad('2', 'smd', 'rect', 0.45, 0.0, 0.5, 0.6, ('F.Cu', 'F.Paste', 'F.Mask'))]
    return footprint('WingV9:FerriteBead_0402_V2provision', 'FB1',
                     'FerriteBead_0402_DNP_V2only', x, y, '\n'.join(b))


def rf_provision_footprint(x, y):
    b = pad('1', 'smd', 'rect', 0.0, 0.0, 2.0, 2.0, ('F.Cu', 'F.Mask'))
    return footprint('WingV9:RF_ProvisionPad_v2only', 'RF1', 'RF_ProvisionPad_v2only',
                     x, y, b)


# ------------------------------------------------------------------ main
def main() -> int:
    nets_src = read_source_netlist(NETLIST)
    check_reuse(nets_src)

    parts = []
    parts.append('(kicad_pcb')
    parts.append('  (version 20241229)')
    parts.append('  (generator "wing_board_build_wing_v9")')
    parts.append('  (generator_version "9.0")')
    parts.append('  (general\n    (thickness 0.6)\n    (legacy_teardrops no)\n  )')      # ADR-046 s3.2
    parts.append('  (paper "A4")')
    parts.append(_Layers)
    parts.append(_Setup)
    parts.append('  (net 0 "")')
    for i, n in enumerate(NETS, start=1):
        parts.append(f'  (net {i} "{n}")')

    # --- footprint: outline (body + tab), ADR-046 s3.2
    pts = [(-TAB_LEN, TAB_Y0), (0, TAB_Y0), (0, 0), (BODY_W, 0), (BODY_W, BODY_H),
           (0, BODY_H), (0, TAB_Y1), (-TAB_LEN, TAB_Y1), (-TAB_LEN, TAB_Y0)]
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        parts.append(gr_line(x1, y1, x2, y2))

    # --- 3 solar cells, string order: SC1(+,-) SC2(+,-) SC3(+,-)  (ADR-046 s3.3/s3.4)
    lefts = ('SOLAR_P', 'SOLAR_MID1', 'SOLAR_MID2')
    rights = ('SOLAR_MID1', 'SOLAR_MID2', 'SOLAR_N')
    for ref, cx, lf, rt in zip(('SC1', 'SC2', 'SC3'), CELL_CX, lefts, rights):
        parts.append(cell_footprint(ref, cx, lf, rt))

    parts.append(tab_footprint())

    # --- handling / mounting / provisions
    for i, x in enumerate((8.0, 88.0, 170.0), start=1):
        parts.append(hole_footprint(f'H{i}', x, 1.7))
    for i, x in enumerate((30.0, 105.0, 145.0), start=1):
        parts.append(fiducial_footprint(f'FID{i}', x, 1.7))
    parts.append(ferrite_footprint(58.0, 1.7))
    parts.append(rf_provision_footprint(118.0, 1.7))

    # --- routing (ADR-046 s2.3)
    parts.append(segment('SOLAR_P', 2.0, 12.5, 2.0, 9.8))
    parts.append(segment('SOLAR_P', 2.0, 9.8, -5.0, 9.8))
    parts.append(segment('SOLAR_MID1', 58.0, 12.5, 60.0, 12.5))
    parts.append(segment('SOLAR_MID2', 116.0, 12.5, 118.0, 12.5))
    for a, b in (((174.0, 12.5), (174.0, 23.5)), ((174.0, 23.5), (3.4, 23.5)),
                 ((3.4, 23.5), (3.4, 15.2)), ((3.4, 15.2), (-5.0, 15.2))):
        parts.append(segment('SOLAR_N', a[0], a[1], b[0], b[1]))

    # --- board silkscreen
    parts.append(gr_text('WING v9  SOLAR 176x25x0.6  4-pin tab  ADR-046', 88.0, 24.2))
    parts.append('  (embedded_fonts no)')
    parts.append(')')

    open(OUT, 'w').write('\n'.join(parts) + '\n')

    txt = open(OUT).read()
    print(f'\nwrote {OUT}')
    print('  footprints :', len(re.findall(r'\(footprint\b', txt)))
    print('  pads       :', len(re.findall(r'\(pad\b', txt)))
    print('  segments   :', len(re.findall(r'\(segment\b', txt)))
    print('  gr_lines   :', len(re.findall(r'\(gr_line\b', txt)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
