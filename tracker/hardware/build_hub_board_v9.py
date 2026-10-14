#!/usr/bin/env python3
"""Build the FIRST v9 HUB board from the settled v9 schematic netlist.

WHY THIS FILE EXISTS
--------------------
No v9 hub PCB has ever been drawn (ADR-048 s5, ADR-051 s2.3, hub-outline-authority.md
s2: "No v9 hub PCB exists").  The v9 sheet
(`tracker/hardware/schematics/flight_board/v9_flight.kicad_sch`, generator
`build_flight_sch.py` v9 target) has only ever existed as a schematic.  This builder
turns its committed NETLIST into a placed board so the S0 placement gates
(`placement_guard.py`, `gate25_check.py`) can be run against a real artifact.

This file is the SINGLE WRITER of `tracker/hardware/hub_board_v9.kicad_pcb`
(placement_guard.py R1).  It holds NO hand-typed coordinate table (R2): every
position is (a) a netlist fact, (b) a library footprint's own measured geometry, or
(c) a COMPUTED parametric seat/pack over the outline.  The KRT quench
(`py_placer/place_optimize.py`, the registry's canonical_placement_source) refines
it and `placement_guard.py --gate25` + `gate25_check.py` grade it.

OUTLINE  (docs/analysis/hub-outline-authority.md, ADR-051 s2.3, ADR-055 s3/D5)
----------------------------------------------------------------------------
Recorded candidates, and why the outline is the one below:

  55.0 x 45.0 mm   the v8h-inherited outline; the ONLY outline encoded in a
                   generated artifact (`tracker/hardware/output/v8i_krt_gnss.kicad_pcb`
                   `(gr_rect (start 0 0) (end 55 45) ... "Edge.Cuts")`), ratified for
                   v9 by ADR-029 sContext.
  103.0 x 103.0 mm ADR-051 s2.3 / ADR-055 D5: the array-plane square for the
                   HORIZONTAL (full-duty) hub, sqrt(106.1 cm2) = 103.0 mm.
  ~90x90..~115x115 ADR-051 s2.3: the PRACTICAL outline incl. the four socket land
                   rows + their 1.5 mm component keep-out + the component court.
                   Recorded only as "~" (an approximation), so not used as a
                   frozen number here.

The outline WIDTH/HEIGHT are CLI parameters (`--outline WxH`); the default is
103.0 x 103.0.  The 55 x 45 mm default this builder first tried is MEASURABLY too
small for the v9 hub: the 39 footprinted components demand 2582 mm^2 of courtyard
against the board's 2475 mm^2, and a best-effort pack left 28 of 39 parts unseated.
See REPORT.md for the resolution, the numbers and the caveats (ADR-051 and ADR-055
are Status **Proposed**, and the array AREA is the operator's open duty choice).

WING-INTERFACE SLOT  (ADR-046 s4.3 / WING-TO-HUB-SOCKET-SPEC s8 item 2)
----------------------------------------------------------------------
The 0.9 mm routed slot is NOT emitted.  It is below JLCPCB's minimum NPTH slot
(1.0 mm) and its tolerance stack worst-cases to a 0.00 mm interference fit
(skill pcb-fab-readiness-gating, rule 15).  This builder takes the spec's own
documented fallback, Option B -- plain pads, no slot
(`docs/WING-TO-HUB-SOCKET-SPEC.md` s2.2) -- which needs no NPTH operation and no
tolerance stack.  Design change: the wing side must match (REPORT.md).

Run:  python3 build_hub_board_v9.py [--outline 55x45] [--out seed|placed]
"""
from __future__ import annotations

import argparse
import hashlib
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
SCH_DIR = os.path.join(HERE, "schematics", "flight_board")
NETLIST = os.path.join(SCH_DIR, "v9_flight.net")
V9_PRETTY = os.path.join(SCH_DIR, "v9_lib", "balloon_flight_v9.pretty")
TRACKER_PRETTY = os.path.join(HERE, "footprints", "tracker_mechanical.pretty")
KICAD_PRETTY = "/usr/share/kicad/footprints"

OUT_SEED = os.path.join(HERE, "output", "hub_board_v9_seed.kicad_pcb")
OUT_BOARD = os.path.join(HERE, "hub_board_v9.kicad_pcb")

DEFAULT_W, DEFAULT_H = 70.0, 70.0   # ADR-068 as REVISED by docs/fab/hub-v9/SEAT-PROBE-RESULT.md:
                                    # sized by COMPONENTS, not by the array -- but the correct
                                    # component floor is 70x70, not 60x60. The 72%-packing
                                    # arithmetic (2582 mm2 -> 59.9 mm) is right but INCOMPLETE:
                                    # it does not account for a single 39.65 x 22.30 mm rectilinear
                                    # body (U2, the LoRa2021F33-2G4), whose aspect ratio wastes more
                                    # area than the aggregate courtyard implies. MEASURED:
                                    #   seat_probe.py -> 60x60 overflows U2; 65x65 overflows U5;
                                    #   70x70 seats all 39 with NO overflow.
                                    #   60x60 routes 43/44 with GND open; 70x70 routes 48/48,
                                    #   148/148 pads, ZERO open nets.
                                    # 70x70 = 49.0 cm2 = 6.26 g at 0.6 mm, still inside JLCPCB's
                                    # 102 mm cheap tier, so the decoupling/cheap-tier arguments
                                    # for ADR-068 are unaffected. Array still rides the separate
                                    # overhanging carrier (ADR-063).
EDGE_STROKE = 0.15
BOARD_THICKNESS = 0.6   # inherited generated value (v8i .gbrjob); ADR-055 D4's 0.4 mm
                        # target is Proposed and its stack-up check is an open item.
LAYER_COUNT = 4         # ADR-029/030 flight board is 4-layer.

LOCAL_LIBS = {
    "balloon_flight_v9": V9_PRETTY,
    "Tracker_Mechanical": TRACKER_PRETTY,
}

# LOADER WORKAROUND (repo defect, reported not fixed)
# -------------------------------------------------------------------------
# The three committed v9_lib footprints and Tracker_Mechanical:Wing_Tab_4P are NOT
# loadable by KiCad 9 as committed: each carries a DUPLICATED
# `(version ...)/(generator ...)` header, and the F33/SX1280/Wing files carry
# `;;` / `#` comment lines the footprint parser rejects.  `kicad-cli fp export svg`
# and `pcbnew.FootprintLoad` both answer "Unable to load library".  The loader
# therefore reads a NORMALISED COPY from a build cache: comment lines and the
# duplicated header tokens are dropped and NOTHING ELSE is touched, so the emitted
# pad geometry is byte-identical to the committed file.  Repo files are untouched.
LIB_CACHE = os.path.join(HERE, "output", ".hub_v9_libcache")


def normalise_library(src_pretty: str, cache_pretty: str) -> str:
    os.makedirs(cache_pretty, exist_ok=True)
    for fn in sorted(os.listdir(src_pretty)):
        if not fn.endswith(".kicad_mod"):
            continue
        lines = open(os.path.join(src_pretty, fn), encoding="utf-8").read().split("\n")
        out, header_toks = [], 0
        for i, l in enumerate(lines):
            s = l.lstrip()
            if s.startswith("#") or s.startswith(";;"):
                continue
            if i < 12 and (s.startswith("(version ") or s.startswith("(generator ")
                           or s.startswith("(generator_version ")):
                header_toks += 1
                if header_toks > 1:
                    continue
            out.append(l)
        with open(os.path.join(cache_pretty, fn), "w", encoding="utf-8") as f:
            f.write("\n".join(out))
    return cache_pretty


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(65536), b""):
            h.update(c)
    return h.hexdigest()


def read_netlist(path: str):
    t = open(path, encoding="utf-8", errors="replace").read()
    comp_sec = re.search(r"\(components(.*?)\(libparts", t, re.S).group(1)
    comps = []
    for b in re.split(r"\n    \(comp ", comp_sec)[1:]:
        ref = re.search(r'\(ref "([^"]+)"\)', b).group(1)
        val = re.search(r'\(value "([^"]*)"\)', b)
        fp = re.search(r'\(footprint "([^"]*)"\)', b)
        comps.append({"ref": ref, "value": val.group(1) if val else "",
                      "lib_id": fp.group(1) if fp else ""})
    net_sec = re.search(r"\(nets(.*)", t, re.S).group(1)
    nets = []
    for b in re.split(r"\n    \(net ", net_sec)[1:]:
        code = int(re.search(r'\(code "(\d+)"\)', b).group(1))
        name = re.search(r'\(name "([^"]+)"\)', b).group(1)
        nodes = re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', b)
        nets.append((code, name, nodes))
    return comps, nets


def scaffold_text(w: float, h: float) -> str:
    cu = (['    (0 "F.Cu" signal)', '    (1 "In1.Cu" power)',
           '    (2 "In2.Cu" power)', '    (31 "B.Cu" signal)'] if LAYER_COUNT == 4
          else ['    (0 "F.Cu" signal)', '    (31 "B.Cu" signal)'])
    layers = "\n".join(cu + [
        '    (32 "B.Adhes" user)', '    (33 "F.Adhes" user)',
        '    (34 "B.Paste" user)', '    (35 "F.Paste" user)',
        '    (36 "B.SilkS" user "B.Silkscreen")',
        '    (37 "F.SilkS" user "F.Silkscreen")',
        '    (38 "B.Mask" user)', '    (39 "F.Mask" user)',
        '    (40 "Dwgs.User" user "User.Drawings")',
        '    (41 "Cmts.User" user "User.Comments")',
        '    (42 "Eco1.User" user "User.Eco1")',
        '    (43 "Eco2.User" user "User.Eco2")',
        '    (44 "Edge.Cuts" user)', '    (45 "Margin" user)',
        '    (46 "B.CrtYd" user "B.Courtyard")',
        '    (47 "F.CrtYd" user "F.Courtyard")',
        '    (48 "B.Fab" user "B.Fab")', '    (49 "F.Fab" user)',
    ])
    return f'''(kicad_pcb
  (version 20241229)
  (generator "build_hub_board_v9")
  (generator_version "9.0")
  (general
    (thickness {BOARD_THICKNESS})
    (legacy_teardrops no)
  )
  (paper "A4")
  (layers
{layers}
  )
  (setup
    (pad_to_mask_clearance 0.05)
    (aux_axis_origin 0 0)
    (grid_origin 0 0)
  )
  (net 0 "")
  (gr_rect
    (start 0 0)
    (end {w} {h})
    (stroke (width {EDGE_STROKE}) (type default))
    (fill none)
    (layer "Edge.Cuts")
    (uuid "00000000-0000-0000-0000-00000000000f")
  )
)
'''


# --------------------------------------------------------------------- loading
def load_everything(w: float, h: float):
    sys.path.insert(0, "/usr/lib/python3/dist-packages")
    import pcbnew

    comps, nets = read_netlist(NETLIST)
    HUB_PART_MODELS.update(_load_hub_part_models())
    scaf = os.path.join(HERE, "output", ".hub_v9_scaffold.kicad_pcb")
    os.makedirs(os.path.dirname(scaf), exist_ok=True)
    with open(scaf, "w") as f:
        f.write(scaffold_text(w, h))
    pcbnew.KIID.SeedGenerator(20261007)   # deterministic UUIDs -> deterministic file bytes
    board = pcbnew.LoadBoard(scaf)
    if board is None:
        raise SystemExit("scaffold failed to load")

    for _code, name, _n in nets:
        if name and board.FindNet(name) is None:
            board.Add(pcbnew.NETINFO_ITEM(board, name))

    pin_net = {(r, p): n for _c, n, nodes in nets for r, p in nodes}

    lib_dirs = {}
    for lib, d in LOCAL_LIBS.items():
        lib_dirs[lib] = normalise_library(d, os.path.join(LIB_CACHE, lib + ".pretty"))

    placed, skipped = [], []
    for c in comps:
        if not c["lib_id"]:
            skipped.append(c)
            continue
        lib, name = c["lib_id"].split(":", 1)
        libdir = lib_dirs.get(lib, os.path.join(KICAD_PRETTY, f"{lib}.pretty"))
        fp = pcbnew.FootprintLoad(libdir, name)
        if fp is None:
            raise SystemExit(f"FootprintLoad failed: {c['lib_id']} (from {libdir})")
        fp.SetReference(c["ref"])
        fp.SetValue(c["value"])
        fp.SetFPID(pcbnew.LIB_ID(lib, name))
        rel = HUB_PART_MODELS.get(c["ref"])
        if rel:
            attach_model(fp, rel)
        for pad in fp.Pads():
            nm = pin_net.get((c["ref"], pad.GetNumber()))
            if nm:
                pad.SetNet(board.FindNet(nm))
        board.Add(fp)
        placed.append((c["ref"], fp))
    return board, placed, skipped, comps, nets


# ------------------------------------------------------------------- 3D models
# Designator -> in-repo VRML model.  This mapping is deliberately NOT restated here: it is
# read from scripts/gen_3d_models_hub.py, which EMITS the models, so the board and the model
# tree cannot drift apart.
#
# Measured 2026-10-11 (scripts/model_resolution_census.py), before this hook existed: the board
# made 32 model references, 7 of which did not resolve, and 7 footprints carried no `(model ...)`
# block at all -- J_VCC, J_W1..J_W4, U2, U4.  U2 is the 39.0 x 21.0 mm `LoRa2021F33-2G4`, the
# largest body on the board and the 433 MHz bent-pipe downlink radio, and U4 is the SX1280 range
# radio.  `kicad-cli pcb render` reports that condition only as silence (exit 0, no warning), so
# the render looked populated while the radios were invisible to the spatial-review gate.
# The board file lives at tracker/hardware/, and KiCad expands ${KIPRJMOD} to the directory
# holding it -- so the reference is relative to the BOARD, not to the model tree.
MODEL_REF_PREFIX = "${KIPRJMOD}/3dmodels/"
HUB_PART_MODELS: dict[str, str] = {}


def _load_hub_part_models() -> dict:
    """Read PART_MODELS from the model generator (one source of truth for both)."""
    import importlib.util

    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    path = os.path.join(root, "scripts", "gen_3d_models_hub.py")
    spec = importlib.util.spec_from_file_location("gen_3d_models_hub", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return dict(mod.PART_MODELS)


def attach_model(fp, rel: str) -> None:
    """Replace fp's 3D models with the committed in-repo model `rel` (relative to the board).

    `${KIPRJMOD}` expands to the directory holding the board file -- here `tracker/hardware` --
    and the model tree sits beside it at `tracker/hardware/3dmodels`.

    Scale/offset/rotation are set explicitly to identity.  The VRML is authored in KiCad's
    convention of 2.54 mm per model unit (see the module docstring of
    `scripts/gen_3d_models_wing.py`, probe 1), so any non-identity transform would silently
    move or resize a body that a placement review is judging.  Changing an EXISTING model
    reference is the point here: U1/U3/U5/ANT1-ANT4 already pointed at files the installed
    `kicad-packages3d` does not ship, which resolves to no body drawn and no warning printed.
    """
    import pcbnew

    m = pcbnew.FP_3DMODEL()
    m.m_Filename = MODEL_REF_PREFIX + rel
    m.m_Scale = pcbnew.VECTOR3D(1.0, 1.0, 1.0)
    m.m_Offset = pcbnew.VECTOR3D(0.0, 0.0, 0.0)
    m.m_Rotation = pcbnew.VECTOR3D(0.0, 0.0, 0.0)
    m.m_Opacity = 1.0
    models = fp.Models()
    models.clear()
    models.push_back(m)


# --------------------------------------------------------------- measurement
def extent(fp):
    """Measured footprint extent (mm) - courtyard if present, else pads."""
    import pcbnew
    for layer in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
        cy = fp.GetCourtyard(layer)
        if cy.OutlineCount() > 0:
            bb = cy.BBox()
            return bb.GetWidth() / 1e6, bb.GetHeight() / 1e6, "courtyard"
    bb = fp.GetBoundingBox(False, False)
    return bb.GetWidth() / 1e6, bb.GetHeight() / 1e6, "bbox"


# ------------------------------------------------------------- floorplan seats
# The four wing interfaces sit one per hub edge at 90 deg spacing (ADR-046 s1 /
# WING-TO-HUB-SOCKET-SPEC s1).  The footprint's own datum is "the intersection of
# the hub's INTERFACE (outer) edge with the SLOT CENTRE LINE, +x INBOARD"
# (footprint descr).  The four U.FL RF sites sit on the board edge (ADR-029 D3,
# ADR-045 solder access).  WHICH edge carries which wing / which U.FL is a
# floorplan choice made here (no record fixes it); it is recorded in REPORT.md.
# These are SEATS THE TOOL DID NOT COMPUTE - the sanctioned "LLM supplies
# constraints" half of the registry rule; the positions themselves are computed
# from W/H here, not typed as literals.
EDGE_SEATS = [
    # ref,      edge,    rotation such that local +x points INBOARD
    ("J_W1", "west", 0.0),
    ("J_W2", "north", 270.0),
    ("J_W3", "east", 180.0),
    ("J_W4", "south", 90.0),
]
UF_SEATS = [
    ("ANT1", "west", 0.22),    # 433 MHz TX (ADR-034 D1/D2)
    ("ANT2", "north", 0.24),   # 2.4 GHz ranging, SX1280 (ADR-108 R1.3)
    ("ANT3", "east", 0.78),    # 2.4 GHz link RX, bare LoRa2021 (ADR-034 D1)
    ("ANT4", "north", 0.76),   # GNSS L1 - ADR-029 D3 puts it on the sky-facing edge
]


def edge_seat_xy(edge: str, w: float, h: float, frac: float, offset: float):
    """Computed seat on an edge; frac = fraction along the edge, offset = inboard mm."""
    if edge == "west":
        return offset, h * frac
    if edge == "east":
        return w - offset, h * frac
    if edge == "south":
        return w * frac, offset
    return w * frac, h - offset      # north


def wing_socket_inboard_offset(fp) -> float:
    """How far INBOARD the socket datum must sit for its lands to be ON the board.

    MEASURED DEFECT this repairs (2026-10-14): `apply_floorplan` seated each J_W
    footprint with `offset=0.0` -- "the datum IS the interface edge". But the
    footprint's datum is defined as the intersection of the hub's INTERFACE
    (outer) edge with the slot centre line, with **+x INBOARD**, while its
    4.0 x 1.2 mm lands sit at local **+3.0 mm** and its land set spans local
    y = -2.7..+2.7 from a 0.5-frac corner datum.

    The consequence, measured on `build_hub_board_v9.py --outline 60x60`:
    **16 of 32 wing-socket pads landed OUTSIDE the board outline** --
    J_W2 pads at y = 63.0 on a 60 mm board and J_W4 pads at y = -3.0. That is
    the same signature the router reported as
    `failed_multipoint: J_W2 (32.7, 63.0)` / `J_W4 (29.1..32.7, -3.0)` and it is
    why `/W*_SOLAR_N`, `/CUT_SENSE_W*` and `GND` were unroutable. A router cannot
    route to a pad that is not on the board.

    REQUIRED inboard offset = land reach + edge clearance, where
      land reach  = |land local x| + land length/2 = 3.0 + 2.0 = 5.0 mm
      edge clear  = max pad-y extent = 2.7 + 1.2/2 = 3.3 mm (so the corner-land
                    row also clears the adjacent edge)
      + a 0.2 mm fab edge clearance
    => 5.4 mm. Rounded UP to WING_SOCKET_MIN_OFFSET_MM for margin.

    The offset is chosen as the max over the footprint's own pads, so it stays
    correct if the land geometry changes, rather than being a magic literal.
    """
    import pcbnew
    reach = 0.0
    for p in fp.Pads():
        # pad centre in the footprint's LOCAL frame (rotation-free)
        dx = pcbnew.ToMM(p.GetPosition().x - fp.GetPosition().x)
        dy = pcbnew.ToMM(p.GetPosition().y - fp.GetPosition().y)
        # local x maps to -y and local y maps to x for the 90/270 seats; the
        # max of |dx|,|dy| plus half the pad extent bounds the reach either way.
        half = max(pcbnew.ToMM(p.GetSize().x), pcbnew.ToMM(p.GetSize().y)) / 2.0
        reach = max(reach, abs(dx) + half, abs(dy) + half)
    return reach + 0.2          # + fab edge clearance


def apply_floorplan(board, placed, w: float, h: float):
    """Seat the four wing sockets and the four U.FL sites; return the locked refs."""
    import pcbnew
    by_ref = dict(placed)
    locked = []
    for ref, edge, rot in EDGE_SEATS:
        if ref not in by_ref:
            continue
        fp = by_ref[ref]
        # Seat so the LANDS are on the board, not the datum. See
        # wing_socket_inboard_offset() for the measured defect this fixes.
        off = wing_socket_inboard_offset(fp)
        x, y = edge_seat_xy(edge, w, h, 0.5, off)
        fp.SetPosition(pcbnew.VECTOR2I(int(round(x * 1e6)), int(round(y * 1e6))))
        fp.SetOrientationDegrees(rot)
        locked.append(ref)
    for ref, edge, frac in UF_SEATS:
        if ref not in by_ref:
            continue
        fp = by_ref[ref]
        ew, eh, _ = extent(fp)
        x, y = edge_seat_xy(edge, w, h, frac, min(ew, eh) / 2.0)
        fp.SetPosition(pcbnew.VECTOR2I(int(round(x * 1e6)), int(round(y * 1e6))))
        locked.append(ref)
    return locked


def rel_rect(fp):
    """The rectangle the S0 gate measures, in mm relative to the footprint origin.

    This is deliberately the gate's OWN conservative pad-box proxy -- pad-centre
    bbox expanded by half the largest pad -- UNIONed with the footprint's own
    courtyard, so what the packer clears is at least what `gate25_check.py`
    (pad-overlap proxy) and `kicad-cli pcb drc` (courtyards_overlap) will grade.
    """
    import pcbnew
    base = fp.GetPosition()
    xs, ys, hx, hy = [], [], 0.0, 0.0
    for p in fp.Pads():
        pp = p.GetPosition()
        xs.append(pp.x / 1e6 - base.x / 1e6)
        ys.append(pp.y / 1e6 - base.y / 1e6)
        hx = max(hx, p.GetSize().x / 2e6)
        hy = max(hy, p.GetSize().y / 2e6)
    if not xs:
        xs, ys = [0.0], [0.0]
    rect = (min(xs) - hx, min(ys) - hy, max(xs) + hx, max(ys) + hy)

    cy = fp.GetCourtyard(pcbnew.F_CrtYd)
    if cy.OutlineCount() == 0:
        cy = fp.GetCourtyard(pcbnew.B_CrtYd)
    if cy.OutlineCount() > 0:
        bb = cy.BBox()
        r2 = (bb.GetX() / 1e6 - base.x / 1e6, bb.GetY() / 1e6 - base.y / 1e6,
              (bb.GetX() + bb.GetWidth()) / 1e6 - base.x / 1e6,
              (bb.GetY() + bb.GetHeight()) / 1e6 - base.y / 1e6)
        rect = (min(rect[0], r2[0]), min(rect[1], r2[1]),
                max(rect[2], r2[2]), max(rect[3], r2[3]))
    return rect


def overlaps(r, s, clr):
    return (r[0] - clr < s[2] and s[0] - clr < r[2]
            and r[1] - clr < s[3] and s[1] - clr < r[3])


def pack_rest(board, placed, locked, w: float, h: float):
    """Collision-checked bottom-left pack of the unseated parts.

    Deterministic, COMPUTED (placement_guard R2): parts are ordered by descending
    measured area and each is dropped on the first 1 mm grid point, scanned in
    reading order, at which its MEASURED rectangle clears the board edge, the
    already-seated mechanical interfaces and everything packed before it.  No
    coordinate is typed; the grid and the rectangles both come from the tool.
    """
    import pcbnew
    EDGE_M = 1.0
    CLR = 0.5
    locked_set = set(locked)
    rects = []
    for ref, fp in placed:
        if ref in locked_set:
            rx0, ry0, rx1, ry1 = rel_rect(fp)
            p = fp.GetPosition()
            rects.append((rx0 + p.x / 1e6, ry0 + p.y / 1e6,
                          rx1 + p.x / 1e6, ry1 + p.y / 1e6))

    rest = [(r, fp) for r, fp in placed if r not in locked_set]
    rel = {r: rel_rect(fp) for r, fp in rest}
    rest.sort(key=lambda e: -((rel[e[0]][2] - rel[e[0]][0]) *
                              (rel[e[0]][3] - rel[e[0]][1])))

    overflow = []
    for ref, fp in rest:
        rx0, ry0, rx1, ry1 = rel[ref]
        ew, eh = rx1 - rx0, ry1 - ry0
        spot = None
        gy = EDGE_M
        while gy + eh <= h - EDGE_M and spot is None:
            gx = EDGE_M
            while gx + ew <= w - EDGE_M:
                r = (gx, gy, gx + ew, gy + eh)
                if not any(overlaps(r, s, CLR) for s in rects):
                    spot = (gx, gy, r)
                    break
                gx += 1.0
            gy += 1.0
        if spot is None:
            # MEASURED DEFECT fixed 2026-10-14: an UNPLACEABLE part was left
            # wherever the netlist loader put it -- at the board ORIGIN (0,0) --
            # because this branch only `continue`d without moving the footprint.
            # Measured on --outline 60x60: U2 (the 39.0 x 21.0 mm LoRa2021F33-2G4,
            # the largest body on the board) sat at pos(0.00, 0.00) with a
            # 39.65 x 22.30 mm courtyard, overlapping J_W1 and most of the left
            # edge. That is what left GND and /SX1280_MISO unroutable: the router
            # was asked to route THROUGH a footprint parked in the corner.
            #
            # A part that does not fit must NOT be silently parked on live copper.
            # Park it WELL OUTSIDE the board so it cannot collide with anything,
            # to the RIGHT of the outline (x > w) on the SEAT's y-centre, so it is
            # visible in a render and trivially identifiable as the overflow part
            # rather than masquerading as placed.
            park_x = w + 20.0
            park_y = h / 2.0
            fp.SetPosition(pcbnew.VECTOR2I(int(round(park_x * 1e6)),
                                           int(round(park_y * 1e6))))
            overflow.append(ref)
            # deliberately NOT appended to `rects`: it is off-board by construction
            # and must not obstruct any later placement.
            continue
        gx, gy, r = spot
        fp.SetPosition(pcbnew.VECTOR2I(int(round((gx - rx0) * 1e6)),
                                       int(round((gy - ry0) * 1e6))))
        rects.append(r)
    return overflow


KRT_DIR = os.path.expanduser(os.environ.get("KRT_DIR", "~/repos/KiCadRoutingTools"))
# ^ MEASURED DEFECT, FIXED 2026-10-14: this was "~/tools/KiCadRoutingTools", which DOES NOT EXIST on
#   this host (the real checkout is ~/repos/KiCadRoutingTools -> /data/repos/KiCadRoutingTools).
#   run_krt then took its "placer absent" branch, printed a note, and returned 1 -- and main() did
#   NOT check that return code, so `--publish` reported success while leaving the STALE committed
#   board in place (103.15 x 103.15, the superseded ADR-055 D5 outline) instead of regenerating it
#   at the ADR-068 70 x 70 outline. Silent-stale-publish, the same class as the CPL that dropped U1.
#   Overridable via the KRT_DIR env var so the path is not hard-coded to one host.
PY314 = "/usr/bin/python3.14"
# KRT's own venv python, used when PY314 is absent on the host.
PY_FALLBACKS = [PY314, os.path.expanduser("~/repos/KiCadRoutingTools/.venv/bin/python"),
                sys.executable]
# The KRT lap that produced the frozen board.  The same tool/lap the registry
# names as canonical_placement_source; the seed this builder writes is its
# reproducible INPUT, and the lap is the frozen artifact.
EDGE_LOCKED = ["J_W1", "J_W2", "J_W3", "J_W4", "ANT1", "ANT2", "ANT3", "ANT4"]
KRT_ARGS = ["--max-displacement", "1", "--max-passes", "6", "--step", "1.0",
            "--clearance", "0.7", "--halo-base", "1.2", "--halo-weight", "12.0",
            "--no-rotate", "--lock", *EDGE_LOCKED]


def run_krt(seed_path: str, lap_path: str) -> int:
    """Polish the seed with the repo's canonical placer (KRT place_optimize.py).

    Returns 0 only when the placer RAN and succeeded. A missing placer is a FAILURE, not a note --
    see the KRT_DIR comment above for why that distinction cost us a stale published board.
    """
    import subprocess
    placer = os.path.join(KRT_DIR, "py_placer", "place_optimize.py")
    if not os.path.exists(placer):
        print(f"KRT PLACER MISSING at {placer}")
        print(f"  KRT_DIR={KRT_DIR} (override with the KRT_DIR env var)")
        print("  REFUSING to publish: the frozen board would be left STALE.")
        return 2

    py = next((p for p in PY_FALLBACKS if os.path.exists(p)), sys.executable)
    r = subprocess.run([py, placer, seed_path, lap_path, *KRT_ARGS],
                       cwd=KRT_DIR, capture_output=True, text=True)
    tail = (r.stdout or "").splitlines()
    for line in tail:
        if '"pad_overlap_pairs"' in line or "EXIT=" in line:
            print("krt:", line[-400:])
    if r.returncode != 0:
        print(f"KRT failed rc={r.returncode}: {(r.stderr or '')[-500:]}")
    return r.returncode


def add_gnd_plane(board, w: float, h: float, margin: float = 0.5,
                  ox: float = 0.0, oy: float = 0.0) -> list:
    """Pour a solid GND plane onto the 4-layer stack (ADR-029/030).

    The generated hub carried NO zone on any layer, so the 0.6 mm 4-layer stack
    provided no continuous return path -- every GND return had to share the
    signal layers, and In1.Cu/In2.Cu were declared but empty copper.  In1.Cu is
    the dedicated ground layer of this stackup; B.Cu takes a pour as well so the
    return is redundant and the outer faces are shielded.  F.Cu and In2.Cu are
    deliberately left clear for signal and power.

    ``margin`` is the copper-to-board-edge clearance; it must be at least the
    board setup edge-clearance rule (0.5 mm here) or DRC flags the pour.
    """
    import pcbnew
    net = board.FindNet("GND")
    if net is None:
        print("gnd plane       : GND net absent - no plane added")
        return []
    added = []
    # A 0.80x0.25 mm QFN land (U4's perimeter GND pads) cannot host two 0.3 mm
    # spokes across its short axis, so a THERMAL connection DRC-fails as
    # starved_thermal.  Connect any pad too small to take two spokes SOLID: the
    # QFN is reflow-only, and a solid tie is the lower-impedance answer there.
    # Must land before the fill so the override is honoured.
    SPOKE_MM = 0.3
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetname() != "GND":
                continue
            sz = pad.GetSize()
            if min(sz.x, sz.y) / 1e6 < 2 * SPOKE_MM:
                pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
    for layer, name in ((pcbnew.In1_Cu, "In1.Cu"), (pcbnew.F_Cu, "F.Cu"),
                        (pcbnew.B_Cu, "B.Cu")):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNet(net)
        z.SetZoneName(f"GND_PLANE_{name}")
        z.SetLocalClearance(pcbnew.FromMM(0.2))
        z.SetMinThickness(pcbnew.FromMM(0.25))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetThermalReliefSpokeWidth(pcbnew.FromMM(SPOKE_MM))
        poly = z.Outline()
        poly.NewOutline()
        for x, y in ((ox + margin, oy + margin), (ox + w - margin, oy + margin),
                     (ox + w - margin, oy + h - margin), (ox + margin, oy + h - margin)):
            poly.Append(pcbnew.FromMM(x), pcbnew.FromMM(y))
        board.Add(z)
        added.append(name)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    return added


def add_planes_to_frozen(path: str) -> int:
    """Add the GND planes to an already-frozen board, IN PLACE, without
    re-placing anything.

    Needed because the frozen boards on disk were generated from an earlier
    EDGE_SEATS offset than the current generator (5 edge-seated refs drift by
    1.000 mm), so a full regeneration would silently move them.  This path only
    appends zones and refills.
    """
    import pcbnew
    board = pcbnew.LoadBoard(path)
    if board is None:
        print(f"cannot load {path}")
        return 2
    # Board outline = BOARD-LEVEL Edge.Cuts graphics only.  Footprint-level
    # Edge.Cuts (the wing-tab slots carried by J_W1..J_W4) stick 6 mm past the
    # panel and would otherwise inflate the plane outline to 103.15 x 115.05.
    edges = [d for d in board.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]
    if not edges:
        print("no board-level Edge.Cuts - cannot size the plane")
        return 2
    xs, ys = [], []
    for d in edges:
        bb = d.GetBoundingBox()
        xs += [pcbnew.ToMM(bb.GetX()), pcbnew.ToMM(bb.GetX() + bb.GetWidth())]
        ys += [pcbnew.ToMM(bb.GetY()), pcbnew.ToMM(bb.GetY() + bb.GetHeight())]
    ox, oy = min(xs), min(ys)
    w, h = max(xs) - ox, max(ys) - oy
    before = board.GetAreaCount()
    planes = add_gnd_plane(board, w, h, ox=ox, oy=oy)
    pcbnew.SaveBoard(path, board)
    print(f"board           : {os.path.relpath(path, REPO)}")
    print(f"outline         : {w:g} x {h:g} mm at ({ox:g},{oy:g})")
    print(f"zones           : {before} -> {board.GetAreaCount()}  ({planes})")
    print(f"gnd plane       : {planes or 'none'}")
    print(f"sha256          : {sha256(path)}")
    return 0


def _placement_key(fp):
    """Everything about a footprint's PLACEMENT (not its model assignment)."""
    import pcbnew

    pos = fp.GetPosition()
    key = [int(pos.x), int(pos.y), int(fp.GetLayer())]
    for attr in ("GetOrientationDegrees", "GetOrientation"):
        fn = getattr(fp, attr, None)
        if fn is None:
            continue
        try:
            v = fn()
            key.append(round(float(v.AsDegrees() if hasattr(v, "AsDegrees") else v), 6))
            break
        except Exception:  # noqa: BLE001 - an introspection probe, not control flow
            continue
    return tuple(key)


def attach_models_to_frozen(path: str) -> int:
    """Attach the in-repo 3D models to an EXISTING board, in place.

    Never re-places anything: every footprint's placement key is compared before and after and
    any difference is a hard failure before the save.  The frozen board's placement is a
    reviewed artefact (`tracker/hardware/PLACEMENT-S0-FREEZE-v9-hub.md`) and a model assignment
    has no business moving a part -- this is the same no-silent-re-place rule that
    `--add-planes` exists to honour.
    """
    import pcbnew

    HUB_PART_MODELS.update(_load_hub_part_models())
    board = pcbnew.LoadBoard(path)
    if board is None:
        raise SystemExit(f"failed to load {path}")

    before = {fp.GetReference(): _placement_key(fp) for fp in board.GetFootprints()}
    refs_before = sorted(fp.GetReference() for fp in board.GetFootprints())

    attached, absent, already = [], [], []
    for ref, rel in sorted(HUB_PART_MODELS.items()):
        fp = board.FindFootprintByReference(ref)
        if fp is None:
            absent.append(ref)
            continue
        had = [m.m_Filename for m in fp.Models()]
        attach_model(fp, rel)
        (already if had == [MODEL_REF_PREFIX + rel] else attached).append(ref)

    after = {fp.GetReference(): _placement_key(fp) for fp in board.GetFootprints()}
    refs_after = sorted(fp.GetReference() for fp in board.GetFootprints())
    if refs_before != refs_after:
        raise SystemExit("REFUSING TO SAVE: the footprint set changed")
    moved = sorted(r for r in before if before[r] != after[r])
    if moved:
        raise SystemExit(f"REFUSING TO SAVE: attaching models moved {moved}")

    pcbnew.SaveBoard(path, board)
    print(f"board           : {os.path.relpath(path, REPO)}")
    print(f"footprints      : {len(refs_after)} (none moved, none added, none removed)")
    print(f"models attached : {len(attached)}  {', '.join(attached) if attached else '-'}")
    if already:
        print(f"models already  : {len(already)}  {', '.join(already)}")
    if absent:
        print(f"NOT ON BOARD    : {', '.join(absent)}")
    print(f"sha256          : {sha256(path)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outline", default=f"{DEFAULT_W:g}x{DEFAULT_H:g}",
                    help="board outline WxH in mm (default 103x103)")
    ap.add_argument("--out", default=OUT_SEED)
    ap.add_argument("--publish", action="store_true",
                    help="write the seed, run the KRT lap and write the FROZEN board")
    ap.add_argument("--add-planes", metavar="BOARD",
                    help="add the GND planes to an existing frozen board in place, "
                         "without re-placing any component")
    ap.add_argument("--attach-models", metavar="BOARD",
                    help="attach the committed in-repo 3D models to an existing board in place, "
                         "without re-placing any component")
    a = ap.parse_args()
    if a.add_planes:
        return add_planes_to_frozen(a.add_planes)
    if a.attach_models:
        return attach_models_to_frozen(a.attach_models)
    w, h = (float(v) for v in a.outline.lower().split("x"))

    import pcbnew
    board, placed, skipped, comps, nets = load_everything(w, h)
    locked = apply_floorplan(board, placed, w, h)
    overflow = pack_rest(board, placed, locked, w, h)
    planes = add_gnd_plane(board, w, h)
    pcbnew.SaveBoard(a.out, board)

    print(f"netlist         : {os.path.relpath(NETLIST, REPO)}  sha256 {sha256(NETLIST)}")
    print(f"components      : {len(comps)} on netlist / {len(placed)} placed / "
          f"{len(skipped)} with an EMPTY footprint field")
    for s in skipped:
        print(f"   unplaceable  {s['ref']:10s} {s['value']}")
    print(f"nets            : {len(nets)}")
    print(f"outline         : {w} x {h} mm ({LAYER_COUNT}-layer, {BOARD_THICKNESS} mm)")
    print(f"edge-seated     : {locked}")
    print(f"gnd plane       : {planes or 'none'}")
    if overflow:
        print(f"UNSEATED (pack ran out of room): {overflow}")
    print(f"seed            : {os.path.relpath(a.out, REPO)}  sha256 {sha256(a.out)}")

    if a.publish:
        rc = run_krt(a.out, OUT_BOARD)
        if rc == 0:
            print(f"frozen board    : {os.path.relpath(OUT_BOARD, REPO)}  "
                  f"sha256 {sha256(OUT_BOARD)}")
        else:
            # MEASURED DEFECT, FIXED 2026-10-14: this branch did not exist. The return code was
            # discarded, so a MISSING placer (return 2) or a failed lap (non-zero) printed a note and
            # the script still exited 0 -- leaving the STALE committed board in place while reporting
            # success. That is how tracker/hardware/hub_board_v9.kicad_pcb kept the superseded
            # 103.15 x 103.15 outline while the packaged board was correctly 70 x 70. A publish that
            # did not happen must NOT look like one that did.
            print(f"PUBLISH FAILED rc={rc}: {os.path.relpath(OUT_BOARD, REPO)} was NOT regenerated "
                  f"and may be STALE.")
            return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
