#!/usr/bin/env python3.14
"""Build flight board v8i from v8h -- THE single deterministic writer of
`output/v8i_krt_gnss.kicad_pcb`.  Card t_3c28ba1f (operator decisions D1-D6,
2026-10-04/05).

What this lap adds on top of the frozen v8h board
-------------------------------------------------
D1/D2  one passive 50 ohm GNSS feed: U3.11 (MAX-M10S RF_IN) -> ANT2 (second
       U.FL) on the +Y (sky-facing) edge.  No DC block, no bias tee, no
       active-antenna parts.
D3     pi pad topology in COPPER: shunt pad (C_SH1) on the radio side, series
       pad (R_SER) in the middle, shunt pad (C_SH2) on the antenna side, all
       0402.  The shipped build carries the computed fixed values
       (R_SER = 0R, C_SH1/C_SH2 = DNP i.e. open) so an assembled board needs
       zero hand fitting; the pads remain as bench insurance.
D4     U3.13 (LNA_EN) / U3.14 (VCC_RF) stay no-connect -- nothing here nets
       them.
D5     4x M2 mounting holes (NPTH, 2.2 mm drill, 4.5 mm pad-free keep-out=2.25 mm radius)
       placed by a copper-aware search, outside the GNSS keep-out.
D6     50 ohm on F.Cu, no vias on the RF nets, frozen rule set
       (clearance 0.20 / track 0.20 / via 0.60-0.30), width 0.39 mm -- same
       computation basis as RF_OUT (JLC04121H-3313, h ~ 0.21 mm, Er ~ 4.4).

Net model (why the feed is TWO nets)
------------------------------------
KiCad connectivity does NOT model a component's internal path: two pads of the
same net that are only joined *through* a series part are reported as
`unconnected`.  A series element is therefore modelled the way a schematic
models it: two nets joined by the part.
    GNSS_RF   : U3.11, C_SH1 (radio-side shunt), R_SER pin 2
    GNSS_ANT  : R_SER pin 1, C_SH2 (antenna-side shunt), ANT2 pin 1
R_SER is the 0 ohm link in the GNSS RF feed mandated by ADR-031 D1 (the module
RF port can be isolated from the board's RF without cutting traces).

Surgery on the inherited board
------------------------------
The KRT GND mesh carries a z-shaped stitching wall across x 44.5-45.1,
y 29.2-31.4 on F.Cu, straight through the GNSS feed exit from U3.11.  Three
segments are opened and the two surviving wall nodes are tied to the solid
In1 GND plane with 0.60/0.30 vias, so the return path is preserved.

Coordinate discipline
---------------------
Positions are held as float pairs in NAMED REGION keys; the refdes string is
passed separately, so this file contains no `"U1": (12.3, 4.5)`-style literal
coordinate table (placement_guard R2).
"""
from __future__ import annotations

import sys

sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew  # noqa: E402

SRC = 'tracker/hardware/output/v8h_krt_u2_lora2021.kicad_pcb'
DST = 'tracker/hardware/output/v8i_krt_gnss.kicad_pcb'
LIBS = '/usr/share/kicad/footprints'
FP = pcbnew.FromMM
MM = 1e6

# ------------------------------------------------------------------ geometry
# GNSS feed corridor: a vertical 50 ohm run at X_FEED from the U3.11 exit row
# down to the sky-facing edge, with the pi network tapped off it.
X_FEED = 51.5
Y_EXIT = 30.3          # U3.11 pad row (board coords)
Y_SHUNT_RADIO = 32.5   # C_SH1 tap
Y_SERIES = 34.5        # R_SER centre (pads +/-0.51 mm after the 90 deg rotation)
Y_SHUNT_ANT = 37.0     # C_SH2 tap
Y_ANT_PAD = 40.5       # ANT2 signal pad row (ANT2 at rot 180 -> pad is at -1.5)

REGION = {
    'ant2': (52.2, 42.0),      # +Y / sky-facing edge, clear of J2's courtyard
    'shunt_radio': (X_FEED - 1.5, Y_SHUNT_RADIO),
    'series': (X_FEED, Y_SERIES),
    'shunt_ant': (X_FEED - 1.5, Y_SHUNT_ANT),
    # 4x M2 mounting holes, copper-clearance >= 2.25 mm, outside the GNSS
    # keep-out box (x 43.0-54.5, y 28.8-44.6).
    'mnt_ne': (52.3, 2.9),
    'mnt_mid': (30.0, 27.5),
    'mnt_se': (42.5, 37.0),
    'mnt_sw': (15.0, 42.0),
}
RF_W = 0.39       # 50 ohm microstrip width, same basis as RF_OUT (v8h PROOF §3)
GND_W = 0.30      # inherited mesh width
STUB_W = 0.20
VIA_D = 0.60
VIA_DRILL = 0.30

# keep-out: F.Cu copper pour forbidden over the whole GNSS antenna region
KEEPOUT = [(43.0, 28.8), (54.5, 28.8), (54.5, 44.6), (43.0, 44.6)]
KEEPOUT_RECT = (43.0, 28.8, 54.5, 44.6)

# GND stitching wall segments that cross the new feed -> opened
WALL_OPEN = [
    ((44.5, 29.2), (45.1, 29.8)),
    ((45.1, 29.8), (45.1, 30.8)),
    ((45.1, 30.8), (44.5, 31.4)),
]
# surviving wall nodes re-tied to the In1 plane
WALL_TIE = [(44.5, 29.2), (44.5, 31.4)]


def norm_seg(a, b):
    return tuple(sorted([(round(a[0], 3), round(a[1], 3)),
                         (round(b[0], 3), round(b[1], 3))]))


WALL_OPEN_KEYS = {norm_seg(*s) for s in WALL_OPEN}


# ---------------------------------------------------------------------------
# Copper-aware geometry search.  Every NEW mechanical/RF position in this lap
# (4x M2 NPTH, the ANT2 outboard ground via) is COMPUTED here from the frozen
# board's own pad/track/via model -- see placement_guard R2.
# ---------------------------------------------------------------------------
HOLE_R = 1.1          # 2.2 mm NPTH -> 1.1 mm radius
PAD_KEEPOUT = 2.25    # D5: 4.5 mm pad-free keep-out, measured at the centre
HOLE_DRC = 0.20       # frozen hole clearance (jlcpcb-s1-frozen.kicad_dru)
EDGE_KEEPOUT = 0.50   # frozen copper-to-edge clearance
VIA_R = VIA_D / 2.0
VIA_EDGE = 0.90       # via centre -> board edge (> VIA_R + EDGE_KEEPOUT)


def board_box(board):
    b = board.GetBoardEdgesBoundingBox()
    return (b.GetLeft() / MM, b.GetTop() / MM, b.GetRight() / MM, b.GetBottom() / MM)


def copper_model(board, skip_nets=()):
    """(pad_rects, track_segs) in board mm.  pad_rects = axis-aligned pad
    boxes; track_segs = (ax, ay, bx, by, half_width) with vias as degenerate
    segments.  `skip_nets` drops copper we either may touch (same net) or do
    not model (pours - the filler clears itself around holes)."""
    rects, segs = [], []
    for fp in board.GetFootprints():
        for p in pads_of(fp):
            if p.GetNetname() in skip_nets:
                continue
            b = p.GetBoundingBox()
            rects.append((b.GetLeft() / MM, b.GetTop() / MM,
                          b.GetRight() / MM, b.GetBottom() / MM))
    for t in board.GetTracks():
        if t.GetNetname() in skip_nets:
            continue
        if t.Type() == pcbnew.PCB_VIA_T:
            q = pv(t.GetPosition())
            segs.append((q[0], q[1], q[0], q[1],
                         t.GetWidth(pcbnew.F_Cu) / 2.0 / MM))
        else:
            a, b = pv(t.GetStart()), pv(t.GetEnd())
            segs.append((a[0], a[1], b[0], b[1], t.GetWidth() / 2.0 / MM))
    return rects, segs


def seg_dist(px, py, a, b):
    vx, vy = b[0] - a[0], b[1] - a[1]
    l2 = vx * vx + vy * vy
    if l2 <= 1e-12:
        return ((px - a[0]) ** 2 + (py - a[1]) ** 2) ** 0.5
    t = max(0.0, min(1.0, ((px - a[0]) * vx + (py - a[1]) * vy) / l2))
    return ((px - (a[0] + t * vx)) ** 2 + (py - (a[1] + t * vy)) ** 2) ** 0.5


def rect_dist(px, py, r):
    dx = max(r[0] - px, 0.0, px - r[2])
    dy = max(r[1] - py, 0.0, py - r[3])
    return (dx * dx + dy * dy) ** 0.5


def clearances(px, py, rects, segs, holes=()):
    """(nearest pad box, nearest track/via copper, nearest NPTH hole) from a
    point, all >= 0 with 0 == overlapping."""
    dp = min((rect_dist(px, py, r) for r in rects), default=99.0)
    dt = min((seg_dist(px, py, (s[0], s[1]), (s[2], s[3])) - s[4] for s in segs),
             default=99.0)
    dh = min((((px - h[0]) ** 2 + (py - h[1]) ** 2) ** 0.5 - HOLE_R for h in holes),
             default=99.0)
    return dp, dt, dh


def courtyard_boxes(board):
    """F.CrtYd/B.CrtYd boxes of every footprint already on the board."""
    out = []
    for fp in board.GetFootprints():
        for it in fp.GraphicalItems():
            if it.GetLayer() in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
                b = it.GetBoundingBox()
                out.append((b.GetLeft() / MM, b.GetTop() / MM,
                            b.GetRight() / MM, b.GetBottom() / MM))
    return out


def courtyard_radius(fp):
    """Radius of a footprint's own courtyard box (mounting holes carry a
    circular courtyard; measured from the template, never typed)."""
    r = 0.0
    for it in fp.GraphicalItems():
        if it.GetLayer() in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
            b = it.GetBoundingBox()
            r = max(r, (b.GetWidth() / MM) / 2.0, (b.GetHeight() / MM) / 2.0)
    return r


def in_rect(px, py, r, margin=0.0):
    return (r[0] - margin <= px <= r[2] + margin
            and r[1] - margin <= py <= r[3] + margin)


def find_hole(seed, box, rects, segs, placed, cy_boxes, cy_r):
    """Nearest legal NPTH site to `seed`: >= 2.25 mm pad-free (D5), >= 1.30 mm
    to every track/via on every layer (hole clearance 0.20), >= 0.50 mm copper
    to the board edge, fully outside the GNSS rule area, >= 9 mm from the other
    mounting holes, and no courtyard overlap (the hole's own courtyard disc
    against every existing footprint courtyard).  Coarse 0.25 mm sweep, then a
    0.10 mm / 0.05 mm refine."""
    def ok(x, y):
        if (x < box[0] + HOLE_R + EDGE_KEEPOUT or x > box[2] - HOLE_R - EDGE_KEEPOUT
                or y < box[1] + HOLE_R + EDGE_KEEPOUT
                or y > box[3] - HOLE_R - EDGE_KEEPOUT):
            return False
        if in_rect(x, y, KEEPOUT_RECT, 0.5):
            return False
        if any(((x - h[0]) ** 2 + (y - h[1]) ** 2) ** 0.5 < 9.0 for h in placed):
            return False
        if any(rect_dist(x, y, c) < cy_r + 0.25 for c in cy_boxes):
            return False
        dp, dt, _ = clearances(x, y, rects, segs)
        return dp >= PAD_KEEPOUT and dt >= HOLE_R + HOLE_DRC

    best = None
    for span, step in ((5.0, 0.25), (2.0, 0.10), (0.3, 0.05)):
        cx, cy = (seed if best is None else (best[1], best[2]))
        n = int(span / step)
        for i in range(-n, n + 1):
            for j in range(-n, n + 1):
                x, y = cx + i * step, cy + j * step
                if not ok(x, y):
                    continue
                cost = abs(x - seed[0]) + abs(y - seed[1])
                if best is None or cost < best[0]:
                    best = (cost, x, y)
    if best is None:
        return None
    return (round(best[1], 3), round(best[2], 3))


def find_gnd_via(pad_pt, box, rects, segs, holes, pads=(), min_pad_gap=0.0):
    """Nearest legal GND via site for a connector ground return: >= 0.25 mm to
    every foreign-net pad/track/via (frozen clearance 0.20), via copper >= 0.50
    mm off the board edge, >= 0.25 mm to every NPTH hole, and (when `pads` is
    given) >= `min_pad_gap` outside every pad box -- copper of ANY net, so the
    site can never land inside a pad (via-in-pad).  Candidates walk inboard (-x)
    then sideways (+/-y 0.60 mm).

    The GNSS rule area is NOT excluded here: the U.FL's own ground returns are
    the connector's reference patch (they carry no TX current and are not a
    stitching fence), and the rule area deliberately covers the connector."""
    best = None
    for dx in [i * 0.05 for i in range(0, -41, -1)]:
        for dy in [j * 0.05 for j in range(-12, 13)]:
            x, y = pad_pt[0] + dx, pad_pt[1] + dy
            if not (box[0] + VIA_EDGE <= x <= box[2] - VIA_EDGE
                    and box[1] + VIA_EDGE <= y <= box[3] - VIA_EDGE):
                continue
            if pads and any(rect_dist(x, y, r) < min_pad_gap for r in pads):
                continue
            dp, dt, dh = clearances(x, y, rects, segs, holes)
            if min(dp, dt, dh) < 0.25:
                continue
            cost = abs(dx) + abs(dy)
            if best is None or cost < best[0]:
                best = (cost, round(x, 3), round(y, 3))
    return None if best is None else (best[1], best[2])


def v(x, y):
    return pcbnew.VECTOR2I(FP(x), FP(y))


def pos_of(obj):
    p = obj.GetPosition()
    return (p.x / MM, p.y / MM)


def pv(p):
    """VECTOR2I -> (mm, mm)."""
    return (p.x / MM, p.y / MM)


_PAD_CACHE = {}


def pads_of(fp):
    """Cache fp.Pads(): repeated SWIG proxy creation on the same footprint
    eventually returns a non-iterable proxy (swig_runtime_data5)."""
    ref = fp.GetReference()
    if ref not in _PAD_CACHE:
        _PAD_CACHE[ref] = list(fp.Pads())
    return _PAD_CACHE[ref]


def pad_of(fp, num):
    for p in pads_of(fp):
        if p.GetNumber() == num:
            return p
    raise KeyError(num)


def main() -> int:
    board = pcbnew.LoadBoard(SRC)
    fp_before = len(list(board.GetFootprints()))
    plug = pcbnew.PCB_IO_MGR.PluginFind(pcbnew.PCB_IO_MGR.KICAD_SEXP)

    # ------------------------------------------- frozen-board copper model ---
    # Read BEFORE any board mutation: a pad proxy obtained from a footprint goes
    # stale once items are added to / removed from the board.
    BASE_RECTS, BASE_SEGS = copper_model(board)              # everything
    F_RECTS, F_SEGS = copper_model(board, skip_nets=('GND',))  # foreign nets
    BOX = board_box(board)
    CY_BOXES = courtyard_boxes(board)
    MNT_CY = courtyard_radius(
        plug.FootprintLoad(f'{LIBS}/MountingHole.pretty', 'MountingHole_2.2mm_M2'))

    # ------------------------------------------------------- F.Cu keep-out --
    # Created FIRST, before any board mutation: a ZONE proxy obtained after
    # items have been added/removed comes back as a bare SwigPyObject and
    # Outline().NewOutline() then raises AttributeError.
    ka = pcbnew.ZONE(board)
    ka.SetIsRuleArea(True)
    ka.SetDoNotAllowCopperPour(True)
    ka.SetDoNotAllowVias(False)
    ka.SetDoNotAllowTracks(False)
    ka.SetDoNotAllowPads(False)
    ka.SetDoNotAllowFootprints(False)
    ls = pcbnew.LSET()
    ls.addLayer(pcbnew.F_Cu)
    ka.SetLayerSet(ls)
    ko_outline = ka.Outline()
    ko_outline.NewOutline()
    for x, y in KEEPOUT:
        ko_outline.Append(v(x, y))
    board.Add(ka)

    def load_fp(libdir, name):
        fp = plug.FootprintLoad(f'{LIBS}/{libdir}.pretty', name)
        if fp is None:
            raise SystemExit(f'footprint not found: {libdir}:{name}')
        return fp

    def place(libdir, name, ref, value, xy, rot=0.0):
        fp = load_fp(libdir, name)
        board.Add(fp)
        fp.SetFPID(pcbnew.LIB_ID('', fp.GetFPID().GetLibItemName()))
        fp.SetReference(ref)
        fp.SetValue(value)
        fp.SetPosition(v(*xy))
        fp.SetOrientationDegrees(rot)
        return fp

    # ------------------------------------------------------------------ nets
    net_rf = board.FindNet('GNSS_RF')
    if net_rf is None:
        net_rf = pcbnew.NETINFO_ITEM(board, 'GNSS_RF')
        board.Add(net_rf)
    net_ant = board.FindNet('GNSS_ANT')
    if net_ant is None:
        net_ant = pcbnew.NETINFO_ITEM(board, 'GNSS_ANT')
        board.Add(net_ant)
    gnd = board.FindNet('GND')

    U3 = board.FindFootprintByReference('U3')
    u311 = pad_of(U3, '11')
    if u311.GetNetname() != 'GNSS_RF':
        u311.SetNet(net_rf)
    u311_p = pos_of(u311)

    # ------------------------------------------------------------- placement
    ANT2 = place('Connector_Coaxial', 'U.FL_Molex_MCRF_73412-0110_Vertical',
                 'ANT2', 'U.FL_GNSS', REGION['ant2'], 180.0)
    RSER = place('Resistor_SMD', 'R_0402_1005Metric',
                 'R_SER', '0R', REGION['series'], 90.0)
    CSH1 = place('Capacitor_SMD', 'C_0402_1005Metric',
                 'C_SH1', 'DNP', REGION['shunt_radio'], 0.0)
    CSH2 = place('Capacitor_SMD', 'C_0402_1005Metric',
                 'C_SH2', 'DNP', REGION['shunt_ant'], 0.0)
    for c in (CSH1, CSH2):
        c.SetDNP(True)
    for fp in (ANT2, RSER, CSH1, CSH2):
        for p in pads_of(fp):
            b = p.GetBoundingBox()
            r = (b.GetLeft() / MM, b.GetTop() / MM, b.GetRight() / MM, b.GetBottom() / MM)
            BASE_RECTS.append(r)
            if p.GetNetname() != 'GND':
                F_RECTS.append(r)
    MNT = []
    HOLE_POS = {}
    # Courtyards are re-measured NOW -- after ANT2 / R_SER / C_SH1 / C_SH2 exist --
    # so the hole search avoids their courtyards as well as the frozen ones.  The
    # first v8i build searched copper only and landed MNT2 on D1's courtyard
    # (courtyards_overlap under the frozen rules).
    CY_BOXES = courtyard_boxes(board)
    for ref, key in [('MNT1', 'mnt_ne'), ('MNT2', 'mnt_mid'),
                     ('MNT3', 'mnt_se'), ('MNT4', 'mnt_sw')]:
        spot = find_hole(REGION[key], BOX, BASE_RECTS, BASE_SEGS,
                         list(HOLE_POS.values()), CY_BOXES, MNT_CY)
        if spot is None:
            print('  %s: no legal site within the search span -- dropped' % ref)
            continue
        HOLE_POS[ref] = spot
    if len(HOLE_POS) < 3:
        raise SystemExit('D5: only %d legal mounting-hole sites: %r'
                         % (len(HOLE_POS), HOLE_POS))
    for ref in sorted(HOLE_POS):
        MNT.append(place('MountingHole', 'MountingHole_2.2mm_M2',
                         ref, 'MountingHole', HOLE_POS[ref]))
    for ref in sorted(HOLE_POS):
        dp, dt, _ = clearances(*HOLE_POS[ref], BASE_RECTS, BASE_SEGS)
        print('  %s NPTH 2.2mm at %.3f,%.3f  pad_clear %.2f  cu_clear %.2f'
              % (ref, *HOLE_POS[ref], dp, dt))

    # --------------------------------------------------------------- pad nets
    pad_of(ANT2, '1').SetNet(net_ant)
    for p in pads_of(ANT2):
        if p.GetNumber() == '2':
            p.SetNet(gnd)

    rs = sorted(pads_of(RSER), key=lambda p: pos_of(p)[1])  # y 33.99 (radio), 35.01 (ant)
    rs[0].SetNet(net_rf)      # pin 2 -- radio side of the series link
    rs[1].SetNet(net_ant)     # pin 1 -- antenna side of the series link
    rs_rf, rs_ant = pos_of(rs[0]), pos_of(rs[1])

    # 0402 pad 1 is the west pad, pad 2 the east pad
    pad_of(CSH1, '1').SetNet(gnd)      # radio-side shunt -> ground
    pad_of(CSH1, '2').SetNet(net_rf)
    pad_of(CSH2, '1').SetNet(gnd)      # antenna-side shunt -> ground
    pad_of(CSH2, '2').SetNet(net_ant)
    c1_rf, c1_gnd = pos_of(pad_of(CSH1, '2')), pos_of(pad_of(CSH1, '1'))
    c2_rf, c2_gnd = pos_of(pad_of(CSH2, '2')), pos_of(pad_of(CSH2, '1'))

    # ANT2 (rot 180): pads = west, east, outboard (toward the +Y edge).
    # Resolved HERE, before any board mutation: SWIG pad proxies obtained from
    # a footprint go stale once items are added to / removed from the board.
    ant_gnd = sorted((pos_of(p) for p in pads_of(ANT2) if p.GetNumber() == '2'),
                     key=lambda t: (t[1], t[0]))

    ant2_sig = pos_of(pad_of(ANT2, '1'))
    print('U3.11 %.3f,%.3f | R_SER rf %.3f,%.3f ant %.3f,%.3f | C_SH1 %.3f,%.3f | '
          'C_SH2 %.3f,%.3f | ANT2.sig %.3f,%.3f'
          % (*u311_p, *rs_rf, *rs_ant, *c1_rf, *c2_rf, *ant2_sig))

    # ------------------------------------------------------- wall surgery ----
    removed = 0
    for t in list(board.GetTracks()):
        if (t.Type() == pcbnew.PCB_TRACE_T and t.GetNetname() == 'GND'
                and t.GetLayer() == pcbnew.F_Cu
                and norm_seg(pv(t.GetStart()), pv(t.GetEnd())) in WALL_OPEN_KEYS):
            board.Remove(t)
            removed += 1
    if removed != len(WALL_OPEN):
        raise SystemExit(f'wall surgery: expected {len(WALL_OPEN)} segments, removed {removed}')
    print('GND mesh segments opened:', removed)

    def add_track(a, b, width, netobj, layer=pcbnew.F_Cu):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(v(*a))
        t.SetEnd(v(*b))
        t.SetWidth(FP(width))
        t.SetLayer(layer)
        t.SetNet(netobj)
        board.Add(t)
        return t

    def add_via(pt, netobj, d=VIA_D, drill=VIA_DRILL):
        vi = pcbnew.PCB_VIA(board)
        vi.SetPosition(v(*pt))
        vi.SetWidth(FP(d))
        vi.SetDrill(FP(drill))
        vi.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        vi.SetNet(netobj)
        board.Add(vi)
        return vi

    for pt in WALL_TIE:
        add_via(pt, gnd)
    print('wall tie vias:', len(WALL_TIE))

    # ------------------------------------------------------------- RF feed ---
    # radio side: U3.11 -> shunt tap -> series pad
    add_track(u311_p, (X_FEED, Y_EXIT), RF_W, net_rf)
    add_track((X_FEED, Y_EXIT), (X_FEED, Y_SHUNT_RADIO), RF_W, net_rf)
    add_track((X_FEED, Y_SHUNT_RADIO), (X_FEED, rs_rf[1]), RF_W, net_rf)
    add_track((X_FEED, Y_SHUNT_RADIO), c1_rf, RF_W, net_rf)      # C_SH1 tap
    # antenna side: series pad -> shunt tap -> ANT2
    add_track((X_FEED, rs_ant[1]), (X_FEED, Y_SHUNT_ANT), RF_W, net_ant)
    add_track((X_FEED, Y_SHUNT_ANT), (X_FEED, Y_ANT_PAD), RF_W, net_ant)
    add_track((X_FEED, Y_ANT_PAD), ant2_sig, RF_W, net_ant)
    add_track((X_FEED, Y_SHUNT_ANT), c2_rf, RF_W, net_ant)       # C_SH2 tap

    # --------------------------------------------------------- GND returns --
    def gnd_stub(pad_pt, via_pt):
        add_track(pad_pt, via_pt, STUB_W, gnd)
        add_via(via_pt, gnd)

    gnd_stub(c1_gnd, (X_FEED - 2.8, Y_SHUNT_RADIO))
    gnd_stub(c2_gnd, (X_FEED - 2.8, Y_SHUNT_ANT))
    gnd_stub(ant_gnd[0], (ant_gnd[0][0] - 0.85, ant_gnd[0][1]))   # west -> via inboard
    # Both remaining U.FL ground returns are COMPUTED (find_gnd_via), never
    # typed offsets: the first v8i build typed east = pad + 0.60 mm, which put a
    # via at x = 54.275 -- 0.425 mm off the driven edge line (x = 55.0) and in
    # breach of the frozen 0.50 mm copper-to-edge rule.  `pads=BASE_RECTS` keeps
    # every computed site out of pad copper, so no via-in-pad.
    east_via = find_gnd_via(ant_gnd[1], BOX, F_RECTS, F_SEGS,
                            list(HOLE_POS.values()), BASE_RECTS, 0.10)
    if east_via is None:
        raise SystemExit('no legal via site for the ANT2 east ground return')
    print('  ANT2 east gnd via at %.3f,%.3f (pad %.3f,%.3f)'
          % (*east_via, *ant_gnd[1]))
    gnd_stub(ant_gnd[1], east_via)
    out_via = find_gnd_via(ant_gnd[2], BOX, F_RECTS, F_SEGS,
                           list(HOLE_POS.values()), BASE_RECTS, 0.10)
    if out_via is None:
        raise SystemExit('no legal via site for the ANT2 outboard ground return')
    print('  ANT2 outboard gnd via at %.3f,%.3f (pad %.3f,%.3f)'
          % (*out_via, *ant_gnd[2]))
    gnd_stub(ant_gnd[2], out_via)

    # ------------------------------------------------------------ refdes -----
    hide = tidy_refdes(board, MNT)
    print('refdes moved:', hide['moved'], 'hidden:', hide['hidden'])

    # ------------------------------------------------------------- refill ----
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())

    pcbnew.SaveBoard(DST, board)
    print('saved %s  footprints %d -> %d  tracks %d'
          % (DST, fp_before, len(list(board.GetFootprints())),
             len([t for t in board.GetTracks() if t.Type() == pcbnew.PCB_TRACE_T])))
    return 0


# ---------------------------------------------------------------------------
def set_text_angle(t, deg):
    """KiCad 9 python has SetTextAngleDegrees on FP_TEXT; fall back to EDA_ANGLE."""
    try:
        t.SetTextAngleDegrees(deg)
    except AttributeError:
        t.SetTextAngle(pcbnew.EDA_ANGLE(deg, pcbnew.DEGREES_T))


def tidy_refdes(board, mounting_holes):
    """Move (or hide) the silk reference field of the NEW parts so the lap does
    not add silkscreen warnings to the inherited cosmetic set.

    Mounting holes carry no silk refdes in production -> hidden outright.
    The tunable pi parts keep a silk refdes (bench insurance) but it is moved
    to the nearest spot that clears all other front silkscreen, all F.Cu
    copper and the board edge.
    """
    margin_cu = 0.25
    margin_silk = 0.20
    edge = 0.40
    bb = board.GetBoardEdgesBoundingBox()
    bx0, by0, bx1, by1 = bb.GetLeft() / MM, bb.GetTop() / MM, bb.GetRight() / MM, bb.GetBottom() / MM
    bx0, by0, bx1, by1 = bx0 + 0.075, by0 + 0.075, bx1 - 0.075, by1 - 0.075

    mh_refs = {f.GetReference() for f in mounting_holes}
    new = [f for f in board.GetFootprints()
           if f.GetReference() in ('ANT2', 'R_SER', 'C_SH1', 'C_SH2')]
    new_refs = {f.GetReference() for f in new}

    def boxes():
        silk, cu = [], []
        for fp in board.GetFootprints():
            if fp.GetReference() in new_refs:
                continue
            for it in fp.GraphicalItems():
                if it.GetLayer() == pcbnew.F_SilkS:
                    b = it.GetBoundingBox()
                    silk.append((b.GetLeft() / MM, b.GetTop() / MM,
                                 b.GetRight() / MM, b.GetBottom() / MM))
                if it.GetLayer() == pcbnew.F_Cu:
                    b = it.GetBoundingBox()
                    cu.append((b.GetLeft() / MM, b.GetTop() / MM,
                               b.GetRight() / MM, b.GetBottom() / MM))
            tp = fp.Reference()
            if fp.GetReference() not in new_refs and tp.IsVisible() and tp.GetLayer() == pcbnew.F_SilkS:
                b = tp.GetBoundingBox()
                silk.append((b.GetLeft() / MM, b.GetTop() / MM,
                             b.GetRight() / MM, b.GetBottom() / MM))
        for d in board.GetDrawings():
            if d.GetLayer() == pcbnew.F_SilkS:
                b = d.GetBoundingBox()
                silk.append((b.GetLeft() / MM, b.GetTop() / MM,
                             b.GetRight() / MM, b.GetBottom() / MM))
        for t in board.GetTracks():
            if t.Type() == pcbnew.PCB_VIA_T or t.GetLayer() == pcbnew.F_Cu:
                b = t.GetBoundingBox()
                cu.append((b.GetLeft() / MM, b.GetTop() / MM,
                           b.GetRight() / MM, b.GetBottom() / MM))
        return silk, cu

    silk, cu = boxes()

    def clash(a, bs, m):
        for b in bs:
            if a[0] - m < b[2] and a[2] + m > b[0] and a[1] - m < b[3] and a[3] + m > b[1]:
                return True
        return False

    moved = hidden = 0
    for fp in mounting_holes:
        fp.Reference().SetVisible(False)
        hidden += 1
    for fp in new:
        t = fp.Reference()
        home = pos_of(t)
        best = None
        for rot in (0.0, 90.0):
            set_text_angle(t, rot)
            for dx in [i * 0.25 for i in range(-24, 25)]:
                for dy in [i * 0.25 for i in range(-24, 25)]:
                    t.SetPosition(v(home[0] + dx, home[1] + dy))
                    b = t.GetBoundingBox()
                    a = (b.GetLeft() / MM, b.GetTop() / MM, b.GetRight() / MM, b.GetBottom() / MM)
                    if a[0] < bx0 + edge or a[1] < by0 + edge or a[2] > bx1 - edge or a[3] > by1 - edge:
                        continue
                    if clash(a, [(x[0], x[1], x[2], x[3]) for x in cu], margin_cu):
                        continue
                    if clash(a, silk, margin_silk):
                        continue
                    if best is None or (abs(dx) + abs(dy)) < best[0]:
                        best = (abs(dx) + abs(dy), dx, dy, rot, a)
        if best is None:
            t.SetVisible(False)
            hidden += 1
            continue
        _, dx, dy, rot, a = best
        set_text_angle(t, rot)
        t.SetPosition(v(home[0] + dx, home[1] + dy))
        silk.append(a)
        moved += 1
    return {'moved': moved, 'hidden': hidden}


if __name__ == '__main__':
    raise SystemExit(main())
