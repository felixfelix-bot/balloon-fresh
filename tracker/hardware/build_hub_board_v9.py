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

DEFAULT_W, DEFAULT_H = 103.0, 103.0   # ADR-051 s2.3 / ADR-055 D5, the grown hub panel;
                                      # see the OUTLINE note above and REPORT.md.
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
        for pad in fp.Pads():
            nm = pin_net.get((c["ref"], pad.GetNumber()))
            if nm:
                pad.SetNet(board.FindNet(nm))
        board.Add(fp)
        placed.append((c["ref"], fp))
    return board, placed, skipped, comps, nets


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


def apply_floorplan(board, placed, w: float, h: float):
    """Seat the four wing sockets and the four U.FL sites; return the locked refs."""
    import pcbnew
    by_ref = dict(placed)
    locked = []
    for ref, edge, rot in EDGE_SEATS:
        if ref not in by_ref:
            continue
        fp = by_ref[ref]
        x, y = edge_seat_xy(edge, w, h, 0.5, 0.0)   # datum IS the interface edge
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
            overflow.append(ref)
            continue
        gx, gy, r = spot
        fp.SetPosition(pcbnew.VECTOR2I(int(round((gx - rx0) * 1e6)),
                                       int(round((gy - ry0) * 1e6))))
        rects.append(r)
    return overflow


KRT_DIR = os.path.expanduser("~/tools/KiCadRoutingTools")
PY314 = "/usr/bin/python3.14"
# The KRT lap that produced the frozen board.  The same tool/lap the registry
# names as canonical_placement_source; the seed this builder writes is its
# reproducible INPUT, and the lap is the frozen artifact.
EDGE_LOCKED = ["J_W1", "J_W2", "J_W3", "J_W4", "ANT1", "ANT2", "ANT3", "ANT4"]
KRT_ARGS = ["--max-displacement", "1", "--max-passes", "6", "--step", "1.0",
            "--clearance", "0.7", "--halo-base", "1.2", "--halo-weight", "12.0",
            "--no-rotate", "--lock", *EDGE_LOCKED]


def run_krt(seed_path: str, lap_path: str) -> int:
    """Polish the seed with the repo's canonical placer (KRT place_optimize.py)."""
    import subprocess
    placer = os.path.join(KRT_DIR, "py_placer", "place_optimize.py")
    if not os.path.exists(placer):
        print(f"KRT placer absent at {placer} - seed left as the frozen board")
        return 1
    r = subprocess.run([PY314, placer, seed_path, lap_path, *KRT_ARGS],
                       cwd=KRT_DIR, capture_output=True, text=True)
    tail = (r.stdout or "").splitlines()
    for line in tail:
        if '"pad_overlap_pairs"' in line or "EXIT=" in line:
            print("krt:", line[-400:])
    if r.returncode != 0:
        print(f"KRT failed rc={r.returncode}: {r.stderr[-500:]}")
    return r.returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outline", default=f"{DEFAULT_W:g}x{DEFAULT_H:g}",
                    help="board outline WxH in mm (default 103x103)")
    ap.add_argument("--out", default=OUT_SEED)
    ap.add_argument("--publish", action="store_true",
                    help="write the seed, run the KRT lap and write the FROZEN board")
    a = ap.parse_args()
    w, h = (float(v) for v in a.outline.lower().split("x"))

    import pcbnew
    board, placed, skipped, comps, nets = load_everything(w, h)
    locked = apply_floorplan(board, placed, w, h)
    overflow = pack_rest(board, placed, locked, w, h)
    pcbnew.SaveBoard(a.out, board)

    print(f"netlist         : {os.path.relpath(NETLIST, REPO)}  sha256 {sha256(NETLIST)}")
    print(f"components      : {len(comps)} on netlist / {len(placed)} placed / "
          f"{len(skipped)} with an EMPTY footprint field")
    for s in skipped:
        print(f"   unplaceable  {s['ref']:10s} {s['value']}")
    print(f"nets            : {len(nets)}")
    print(f"outline         : {w} x {h} mm ({LAYER_COUNT}-layer, {BOARD_THICKNESS} mm)")
    print(f"edge-seated     : {locked}")
    if overflow:
        print(f"UNSEATED (pack ran out of room): {overflow}")
    print(f"seed            : {os.path.relpath(a.out, REPO)}  sha256 {sha256(a.out)}")

    if a.publish:
        rc = run_krt(a.out, OUT_BOARD)
        if rc == 0:
            print(f"frozen board    : {os.path.relpath(OUT_BOARD, REPO)}  "
                  f"sha256 {sha256(OUT_BOARD)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
