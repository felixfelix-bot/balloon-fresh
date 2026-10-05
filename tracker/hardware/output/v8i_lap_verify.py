#!/usr/bin/env python3.14
"""Evidence collector for the v8i GNSS + mechanics lap (card t_3c28ba1f).

Reads the frozen v8i board and prints, from the board's own geometry only:

  * placement table + PLACEMENT_HASH (sha256 over REF|footprint|x|y|rot|value)
  * board sha256 / sha256_12
  * D5 mounting holes: drill, position, pad-free and copper clearance
  * D1/D2 GNSS feed: net membership, every RF segment (width/layer), the
    pi-network pad nets, and the U3.11 -> ANT2.1 endpoint chain
  * D6 rule check: unique width on the two RF nets, all-F.Cu, zero vias on them
  * the F.Cu GNSS keep-out rule area and what is forbidden inside it
  * D4: U3.13 / U3.14 pad nets (must stay no-connect)
  * via histogram (fab-margin: every via must be 0.60 / 0.30)
  * ANT1 / ANT2 port coordinates and their distance to the nearest board edge

Never writes board copper.  Exit 1 if any assertion fails.
"""
from __future__ import annotations

import hashlib
import sys

sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew  # noqa: E402

BOARD = 'tracker/hardware/output/v8i_krt_gnss.kicad_pcb'
MM = 1e6
RF_NETS = ('RF_OUT', 'GNSS_RF', 'GNSS_ANT')
PASS = True


def mm(v):
    return round(v / MM, 4)


def check(label, ok, detail=''):
    global PASS
    PASS = PASS and bool(ok)
    print('  [%s] %s%s' % ('PASS' if ok else 'FAIL', label,
                           (' -- ' + detail) if detail else ''))


def main() -> int:
    raw = open(BOARD, 'rb').read()
    full = hashlib.sha256(raw).hexdigest()
    b = pcbnew.LoadBoard(BOARD)

    print('board           : %s' % BOARD)
    print('sha256          : %s' % full)
    print('sha256_12       : %s' % full[:12])
    print('copper layers   : %d' % b.GetCopperLayerCount())
    bb = b.GetBoardEdgesBoundingBox()
    print('edge bbox       : %.3f,%.3f .. %.3f,%.3f  (%.3f x %.3f mm)'
          % (mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()),
             mm(bb.GetBottom()), mm(bb.GetWidth()), mm(bb.GetHeight())))

    print('\n## placement + hash')
    rows = []
    for f in sorted(b.GetFootprints(), key=lambda f: f.GetReference()):
        p = f.GetPosition()
        rows.append('%s|%s|%.4f|%.4f|%.1f|%s'
                    % (f.GetReference(), f.GetFPID().GetLibItemName(), mm(p.x), mm(p.y),
                       f.GetOrientationDegrees(), f.GetValue()))
    for r in rows:
        print('  ' + r)
    phash = hashlib.sha256('\n'.join(rows).encode()).hexdigest()
    print('PLACEMENT_HASH  : %s' % phash)
    print('PLACEMENT_HASH_12: %s' % phash[:12])
    print('footprints      : %d' % len(rows))

    print('\n## D5 mounting holes (NPTH 2.2 mm)')
    holes = []
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                pos = p.GetPosition()
                holes.append((f.GetReference(), mm(p.GetDrillSize().x), mm(pos.x), mm(pos.y)))
    for ref, drill, x, y in sorted(holes):
        de = min(x - mm(bb.GetLeft()) - 0.075, mm(bb.GetRight()) - 0.075 - x,
                 y - mm(bb.GetTop()) - 0.075, mm(bb.GetBottom()) - 0.075 - y)
        print('  %s drill %.2f at (%.3f,%.3f)  hole-edge to board edge %.3f mm'
              % (ref, drill, x, y, de - drill / 2.0))
    check('4x M2 NPTH present (D5)', len(holes) == 4, '%d found' % len(holes))
    check('all holes 2.2 mm drill', all(abs(h[1] - 2.2) < 1e-6 for h in holes))
    pair_min = min((((a[2] - c[2]) ** 2 + (a[3] - c[3]) ** 2) ** 0.5
                    for i, a in enumerate(holes) for c in holes[i + 1:]), default=99.0)
    check('mounting holes >= 9 mm apart (search constraint)', pair_min >= 9.0,
          'min pair %.3f mm' % pair_min)

    print('\n## D1/D2 GNSS feed')
    for net in RF_NETS:
        segs = [t for t in b.GetTracks()
                if t.GetNetname() == net and t.Type() == pcbnew.PCB_TRACE_T]
        vias = [t for t in b.GetTracks()
                if t.GetNetname() == net and t.Type() == pcbnew.PCB_VIA_T]
        widths = sorted({mm(t.GetWidth()) for t in segs})
        layers = sorted({b.GetLayerName(t.GetLayer()) for t in segs})
        length = sum((t.GetLength() / MM) for t in segs)
        print('  %-9s segments %d  length %.3f mm  widths %s  layers %s  vias %d'
              % (net, len(segs), length, widths, layers, len(vias)))
        check('%s width == 0.39 mm (RF_OUT basis)' % net, widths == [0.39], str(widths))
        check('%s on F.Cu only (D6)' % net, layers == ['F.Cu'], str(layers))
        check('%s has ZERO vias (D6)' % net, not vias)
    for pad_ref, pad_num, want in (('U3', '11', 'GNSS_RF'),
                                   ('R_SER', '2', 'GNSS_RF'),
                                   ('C_SH1', '2', 'GNSS_RF'),
                                   ('R_SER', '1', 'GNSS_ANT'),
                                   ('C_SH2', '2', 'GNSS_ANT'),
                                   ('ANT2', '1', 'GNSS_ANT')):
        fp = b.FindFootprintByReference(pad_ref)
        got = [p.GetNetname() for p in fp.Pads() if p.GetNumber() == pad_num]
        check('%s.%s net == %s' % (pad_ref, pad_num, want), got == [want], str(got))
    print('  pi topology: C_SH1 shunt (radio side), R_SER 0R series, C_SH2 shunt (antenna side)')
    print('  DNP flags   : C_SH1=%s C_SH2=%s' % (b.FindFootprintByReference('C_SH1').IsDNP(),
                                                 b.FindFootprintByReference('C_SH2').IsDNP()))

    print('\n## D4 no-connects on U3')
    for num in ('13', '14'):
        got = [p.GetNetname() for p in b.FindFootprintByReference('U3').Pads()
               if p.GetNumber() == num]
        check('U3.%s stays no-connect' % num, got == [''], str(got))

    print('\n## F.Cu GNSS keep-out (rule area)')
    areas = [z for z in b.Zones() if z.GetIsRuleArea()]
    for z in areas:
        bx = z.GetBoundingBox()
        print('  layer %s forbid_pour=%s  box %.1f,%.1f .. %.1f,%.1f'
              % (b.GetLayerName(z.GetLayer()), z.GetDoNotAllowCopperPour(),
                 mm(bx.GetLeft()), mm(bx.GetTop()), mm(bx.GetRight()), mm(bx.GetBottom())))
    check('exactly one F.Cu GNSS rule area',
          len(areas) == 1 and b.GetLayerName(areas[0].GetLayer()) == 'F.Cu',
          '%d rule area(s)' % len(areas))
    if areas:
        kx = areas[0].GetBoundingBox()

        def inside(pt):
            return (mm(kx.GetLeft())) <= mm(pt.x) <= mm(kx.GetRight()) and \
                   (mm(kx.GetTop())) <= mm(pt.y) <= mm(kx.GetBottom())

        tx_inside = [t for t in b.GetTracks()
                     if t.GetNetname() == 'RF_OUT'
                     and inside(t.GetStart()) and inside(t.GetEnd())]
        check('no RF_OUT (2.4 GHz TX) copper inside the keep-out', not tx_inside,
              '%d segment(s)' % len(tx_inside))
        WALL_TIE = {(44.5, 29.2), (44.5, 31.4)}   # the lap's own In1 return ties
        gnd_vias = {(mm(t.GetPosition().x), mm(t.GetPosition().y))
                    for t in b.GetTracks()
                    if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == 'GND'
                    and inside(t.GetPosition())}
        new_returns = {(52.875, 42.0), (51.45, 43.5), (49.875, 42.0),
                       (48.7, 32.5), (48.7, 37.0)}
        extra = gnd_vias - WALL_TIE - new_returns
        print('  GND vias inside the rule area: %s' % sorted(gnd_vias))
        print('    wall-return ties (lap)     : %s' % sorted(gnd_vias & WALL_TIE))
        print('    U.FL / pi ground returns   : %s' % sorted(gnd_vias & new_returns))
        check('no frozen GND stitching vias left inside the keep-out', not extra,
              str(sorted(extra)))
        copper = {}
        for t in b.GetTracks():
            if inside(t.GetStart()):
                k = t.GetNetname() or '(no net)'
                copper[k] = copper.get(k, 0) + 1
        for f in b.GetFootprints():
            for p in f.Pads():
                if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                    continue
                if inside(p.GetPosition()):
                    k = p.GetNetname() or '(no net)'
                    copper[k] = copper.get(k, 0) + 1
        print('  every copper item inside the rule area, by net: %s'
              % sorted(copper.items()))
        foreign = {k: v for k, v in copper.items()
                   if k not in ('GND', 'GNSS_RF', 'GNSS_ANT')}
        known = {'I2C_SCL', 'I2C_SDA'}
        print('  LISTED DEVIATION: inherited low-speed signals inside the rule area: %s'
              % ({k: v for k, v in foreign.items()} or 'none'))
        check('nothing inside the rule area except GND, the GNSS feed, and the two '
              'listed inherited I2C debug lanes',
              set(foreign) <= known, str(sorted(set(foreign) - known)))
        pour = [z for z in b.Zones() if not z.GetIsRuleArea()
                and b.GetLayerName(z.GetLayer()) == 'F.Cu']
        check('no F.Cu signal pour in the keep-out region', not pour,
              'F.Cu pour zones: %d' % len(pour))

    print('\n## via histogram (fab margin)')
    hist = {}
    for t in b.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            key = '%.2f/%.2f' % (mm(t.GetWidth(pcbnew.F_Cu)), mm(t.GetDrill()))
            hist[key] = hist.get(key, 0) + 1
    for k in sorted(hist):
        print('  %s : %d' % (k, hist[k]))
    check('every via is 0.60/0.30', set(hist) == {'0.60/0.30'}, str(sorted(hist)))

    print('\n## RF parts and edges')
    for ref in ('ANT1', 'ANT2'):
        f = b.FindFootprintByReference(ref)
        p = f.GetPosition()
        de = min(mm(p.x) - mm(bb.GetLeft()), mm(bb.GetRight()) - mm(p.x),
                 mm(p.y) - mm(bb.GetTop()), mm(bb.GetBottom()) - mm(p.y))
        print('  %s (%s) at (%.3f,%.3f) rot %.0f  origin to nearest edge %.3f mm'
              % (ref, f.GetValue(), mm(p.x), mm(p.y), f.GetOrientationDegrees(), de))
    a1 = b.FindFootprintByReference('ANT1').GetPosition()
    a2 = b.FindFootprintByReference('ANT2').GetPosition()
    d = (((a1.x - a2.x) / MM) ** 2 + ((a1.y - a2.y) / MM) ** 2) ** 0.5
    print('  ANT1 origin -> ANT2 origin: %.3f mm' % d)

    print('\n## totals')
    segs = [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_TRACE_T]
    print('  segments %d  vias %d  copper %.1f mm  zones %d'
          % (len(segs), sum(hist.values()), sum(t.GetLength() / MM for t in segs),
             len(b.Zones())))
    print('\nRESULT: %s' % ('ALL CHECKS PASSED' if PASS else 'FAILURES ABOVE'))
    return 0 if PASS else 1


if __name__ == '__main__':
    raise SystemExit(main())
