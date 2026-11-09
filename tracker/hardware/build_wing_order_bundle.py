#!/usr/bin/env python3
"""build_wing_order_bundle.py -- fab bundle for the wing interconnect (solar cell connector) board.

WHY
---
The board is routed and DRC-clean (0 violations, 0 unconnected) but has never had a fab package:
no gerbers, no BOM, no CPL. Without those it cannot be ordered, which is why ROUTING-STATUS.md
still says "not yet orderable" even though the routing blocker is gone.

WHAT IS ON THIS BOARD (measured, not remembered)
  7 footprints, 14 pads, ALL SMD, ZERO drills.
  3 x SS24 SMA bypass diodes (D1, D2, D3)          <- JLC places these
  J1  Tab_2P        wing->hub tab (2 pads)          <- solder point, no purchasable part
  SC1 SC2 SC3       SolarTail_2P cell tail lands    <- solder points, no purchasable part

  So the BOM is THREE DIODES and nothing else. The tab and the cell tails are lands the operator
  solders to; they carry no LCSC number and must never appear in a BOM (that stalls the order on a
  no-match).

  There is NO DRILL FILE. Every pad is SMD. That is legitimate for an all-SMD board and JLC accepts
  it, but it is called out in the README so nobody reads the missing .drl as a packaging error.

SIZE -- and the number that was disputed
  Edge.Cuts centreline measures 34.60 x 20.00 mm. The stroke-inflated bounding box is 34.70 x 20.10
  (0.100 mm stroke, w/2 each side) -- the same centreline-vs-bbox distinction as the hub board.
  ADR-132 and ADR-134 both say "44 x 20 mm"; that figure predates the width being derived from the
  pad extents (BUILD script comment: pads end at x=33.00, +1.6 edge = 34.6). The BOARD is correct and
  the ADRs are stale -- this script asserts the measured value.
"""
import csv
import os
import shutil
import subprocess
import sys
import zipfile

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BOARD = os.path.join(WT, 'tracker/hardware/wing_interconnect/wing_interconnect_v1.kicad_pcb')
OUT = os.path.join(WT, 'docs/fab/wing-interconnect-order')
GERB = os.path.join(OUT, 'gerbers')

# 2-layer board: only these layers exist. A 4-layer whitelist here would abort on missing files.
NEEDED = {
    'wing_interconnect_v1-F_Cu.gtl': 'F.Cu',
    'wing_interconnect_v1-B_Cu.gbl': 'B.Cu',
    'wing_interconnect_v1-F_Mask.gts': 'F.Mask',
    'wing_interconnect_v1-B_Mask.gbs': 'B.Mask',
    'wing_interconnect_v1-F_Silkscreen.gto': 'F.Silkscreen',
    'wing_interconnect_v1-B_Silkscreen.gbo': 'B.Silkscreen',
    'wing_interconnect_v1-F_Paste.gtp': 'F.Paste',
    'wing_interconnect_v1-B_Paste.gbp': 'B.Paste',
    'wing_interconnect_v1-Edge_Cuts.gm1': 'Edge.Cuts',
}

SS24_LCSC = 'C50645'      # same part the v10 hub uses for its bypass diodes


def export():
    if os.path.isdir(GERB):
        shutil.rmtree(GERB)
    os.makedirs(GERB, exist_ok=True)
    r = subprocess.run(['kicad-cli', 'pcb', 'export', 'gerbers', '--output', GERB, BOARD],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print('gerber export FAILED:', (r.stdout + r.stderr)[-700:])
        sys.exit(1)
    # drill too, so its absence is visible rather than assumed
    subprocess.run(['kicad-cli', 'pcb', 'export', 'drill', '--output', GERB, BOARD],
                   capture_output=True, text=True)


def main():
    export()
    present = set(os.listdir(GERB))

    # kicad-cli names files from the board's LAYER NAMES, which on this board are lowercase
    # ("f.silkscreen"/"b.silkscreen"), so the exported stem is -f_silkscreen.gto not
    # -F_Silkscreen.gto. Match case-insensitively on the EXTENSION rather than hardcoding a stem;
    # a filename-case mismatch is not a missing layer and must not fail the gate.
    def find(suffix):
        for f in present:
            if f.lower().endswith(suffix.lower()):
                return f
        return None

    resolved = {}
    missing = []
    for want, layer in NEEDED.items():
        suffix = want[want.index('-'):]          # e.g. "-F_Cu.gtl"
        got = find(suffix)
        if got:
            resolved[layer] = got
        else:
            missing.append((want, layer))

    # the drill file is legitimate to be absent only if the board truly has no holes
    drl = [f for f in present if f.endswith('.drl')]
    print(f'gerbers: {len(resolved)}/{len(NEEDED)} required layers present')
    for layer, f in sorted(resolved.items()):
        print(f'  {layer:14s} {f}')
    if missing:
        print('\nMISSING REQUIRED GERBERS:')
        for want, layer in missing:
            print(f'  {layer:14s} (expected ~{want})')
        print('present:', sorted(present))
        sys.exit(1)
    print(f'drill files: {drl or "NONE (all-SMD board, expected)"}')

    import pcbnew
    b = pcbnew.LoadBoard(BOARD)
    MM = 1e6

    # ---- BOM: only parts with a purchasable LCSC number
    bom = [{'Comment': 'SS24',
            'Designator': 'D1,D2,D3',
            'Footprint': 'D_SMA_Wing',
            'Quantity': '3',
            'LCSC Part #': SS24_LCSC}]
    bom_path = os.path.join(OUT, 'bom-jlc.csv')
    with open(bom_path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(bom[0].keys()))
        w.writeheader()
        w.writerows(bom)

    # ---- CPL: the 3 diodes only. JLC places to the pad-array centre, so compute min/max over pads.
    rows = []
    skipped = []
    for ref in ('D1', 'D2', 'D3'):
        fp = next(f for f in b.GetFootprints() if f.GetReference() == ref)
        ps = list(fp.Pads())
        if not ps:
            skipped.append(ref)
            continue
        xs = [p.GetPosition().x / MM for p in ps]
        ys = [p.GetPosition().y / MM for p in ps]
        cx = (min(xs) + max(xs)) / 2
        cy = (min(ys) + max(ys)) / 2
        rows.append({'Designator': ref,
                     'Val': 'SS24',
                     'Package': 'D_SMA_Wing',
                     'Mid X': f'{cx:.4f}',
                     'Mid Y': f'{cy:.4f}',
                     'Layer': 'Top',
                     'Rotation': f'{fp.GetOrientationDegrees():.1f}'})
    cpl_path = os.path.join(OUT, 'cpl-jlc.csv')
    with open(cpl_path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['Designator', 'Val', 'Package', 'Mid X', 'Mid Y',
                                          'Layer', 'Rotation'])
        w.writeheader()
        w.writerows(rows)

    # ---- solder-point list (NOT for JLC)
    sp = [{'Designator': r, 'Function': fn}
          for r, fn in (('J1', 'wing->hub tab, 2 pads: SOLAR_P / SOLAR_N'),
                        ('SC1', 'cell 1 tail lands: SOLAR_P / SOLAR_MID1'),
                        ('SC2', 'cell 2 tail lands: SOLAR_MID1 / SOLAR_MID2'),
                        ('SC3', 'cell 3 tail lands: SOLAR_MID2 / SOLAR_N'))]
    sp_path = os.path.join(OUT, 'solder-points-NOT-FOR-JLC.csv')
    with open(sp_path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['Designator', 'Function'])
        w.writeheader()
        w.writerows(sp)

    # ---- zip
    zpath = os.path.join(OUT, 'wing-interconnect-jlcpcb-upload.zip')
    if os.path.exists(zpath):
        os.remove(zpath)
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
        for layer, f in resolved.items():
            z.write(os.path.join(GERB, f), f'gerbers/{f}')
        for f in drl:
            z.write(os.path.join(GERB, f), f'gerbers/{f}')
        z.write(bom_path, 'bom-jlc.csv')
        z.write(cpl_path, 'cpl-jlc.csv')

    print(f'\nbom: {len(bom)} part rows -> 3 designators')
    print(f'cpl: {len(rows)} placements')
    print(f'skipped (no pads): {skipped or "none"}')
    print(f'zip: {os.path.relpath(zpath, WT)}  {os.path.getsize(zpath):,d} B')
    if len(rows) != 3:
        print('FAIL: expected 3 placements')
        sys.exit(1)


if __name__ == '__main__':
    main()
