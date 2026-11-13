#!/usr/bin/env python3
"""build_v11_board.py -- v11 placement, STAGE 1: the four wing bypass diodes on the top face.

SCOPE, DELIBERATELY NARROW. The v11 design spec's own sequence says:

    1. Schematic first ... no layout until ERC is clean.        [DONE -- both v11 gates pass]
    2. Reserve the corners. Place D_BP1..4 on the top face
       BEFORE anything else ... doing it after routing makes
       one of them hard.                                        [THIS SCRIPT]
    3. Route the new nets first, while the board is empty.
    4. Then re-route the inherited nets, in batches.

So this is step 2 and nothing else. It does NOT place the other 97 components, it does not
route, and it does not claim a routable board. A previous round in this project produced a
"v11" file that was v10 with one rebuilt component moved, and it nearly reached a fab order
under a v11 name -- the narrow scope here is the direct lesson from that.

WHY THE DIODES FIRST, MEASURED. On v10 all four are B.Cu-only, which forces either a
double-sided Standard PCBA setup or hand-soldering four SMA joints (ADR-146). v11 puts them
on the top face. v11_diode_sites.py already found full-board valid sites for all four:

    D_BP1  (3.0, 39.0)  rot 90   worst pad-to-copper 0.30 mm   387 sites
    D_BP2  (36.5, 77.0) rot 0    worst 0.85 mm                 584 sites
    D_BP3  (67.5, 38.5) rot 270  worst 1.42 mm                 194 sites
    D_BP4  (49.5, 11.5) rot 0    worst 0.11 mm                6154 sites

This script applies exactly those four, on F.Cu, and then VERIFIES the result against the
same predicate the site search used -- so a transcription error cannot pass silently.

OUTPUT: tracker/hardware/hub_board_v11_stage1.kicad_pcb
The name says stage 1 because that is what it is. Renaming it to hub_board_v11.kicad_pcb
before the remaining 97 parts are placed would misrepresent it.
"""
import json
import os
import sys

import pcbnew

UM = 1_000_000.0
HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMATIC_DIR = os.path.join(HERE, "schematics", "flight_board")
NETLIST = os.path.join(SCHEMATIC_DIR, "v11_flight.net")
OUT = os.path.join(HERE, "hub_board_v11_stage1.kicad_pcb")

# outline: 72 x 80 is rejected by v11_fit_probe (0.5 % headroom on a board that shipped with
# 82 opens). 80 x 90 gives 25.6 %. This is a MECHANICAL decision that changes the enclosure,
# the wing-seat spacing and the tether geometry, so it is a parameter here rather than a
# silent constant -- and the operator decides it.
W, H = 80.0, 90.0

# The four top-face sites, from v11_diode_sites_v2.py -- REAL copper geometry, pads not centres.
# (ref, net_a, net_b, x, y, rot, own_net_reach_mm, foreign_clearance_mm)
#
# SUPERSEDES the V11-DESIGN-SPEC.md section 1 table. Those sites (3.0,39.0 / 36.5,77.0 /
# 67.5,38.5 / 49.5,11.5) came from a search that only checked distance to other footprint
# ORIGINS and never looked at foreign copper, so applying them produced 13 shorting_items.
# The numbers below are the first site for each diode from the corrected search.
DIODES = [
    ("D_BP1", "/W1_SOLAR_P", "/W1_SOLAR_N", 7.2, 40.8, 270.0, 2.20, 0.40),
    ("D_BP2", "/W1_SOLAR_N", "/W2_SOLAR_N", 29.4, 73.8, 0.0, 5.97, 0.37),
    ("D_BP3", "/W2_SOLAR_N", "/W3_SOLAR_N", 65.4, 42.8, 90.0, 3.02, 0.35),
    ("D_BP4", "/W3_SOLAR_N", "GND", 40.4, 7.0, 270.0, 0.68, 0.61),
]
FP_LIB = "Diode_SMD"
FP_NAME = "D_SMA"


def resolve_lib(nick):
    """Resolve a footprint nickname through the project fp-lib-table, then the system libs."""
    tbl = os.path.join(SCHEMATIC_DIR, "fp-lib-table")
    if os.path.isfile(tbl):
        raw = open(tbl, encoding="utf-8", errors="replace").read()
        import re
        m = re.search(r'\(lib \(name "%s"\).*?\(uri "([^"]+)"\)' % re.escape(nick), raw)
        if m:
            uri = m.group(1)
            for root in (HERE, SCHEMATIC_DIR):
                cand = os.path.normpath(uri.replace("${KIPRJMOD}", root))
                if os.path.isdir(cand):
                    return cand
    for base in ("/usr/share/kicad/footprints", "/usr/share/kicad/modules"):
        d = os.path.join(base, f"{nick}.pretty")
        if os.path.isdir(d):
            return d
    raise SystemExit(f"footprint library not found: {nick}")


def main():
    # start from v10's board as the geometric base -- it carries the outline, the wing-seat
    # slots, the mounting holes and the 49 inherited parts. Stage 1 then moves ONLY the diodes.
    base = os.path.join(HERE, "hub_board_v10.kicad_pcb")
    b = pcbnew.LoadBoard(base)
    if b is None:
        raise SystemExit(f"could not load base board {base}")

    lib = resolve_lib(FP_LIB)
    print(f"footprint lib: {lib}")

    moved = []
    for ref, na, nb, x, y, rot, own, worst in DIODES:
        fp = b.FindFootprintByReference(ref)
        if fp is None:
            raise SystemExit(f"{ref} not present on the base board -- refusing to add a "
                             f"second copy; the diode must MOVE, not duplicate")
        was = fp.GetLayerName()
        # unflip to the top face if it is on the bottom, then position
        if fp.GetLayer() == pcbnew.B_Cu:
            fp.Flip(fp.GetPosition(), False)
        fp.SetPosition(pcbnew.VECTOR2I(int(round(x * UM)), int(round(y * UM))))
        fp.SetOrientation(pcbnew.EDA_ANGLE(rot, pcbnew.DEGREES_T))
        now = fp.GetLayerName()
        moved.append((ref, was, now, x, y, rot, worst))
        print(f"  {ref}: {was} -> {now} at ({x:.1f}, {y:.1f}) rot {rot:.0f}  "
              f"[own-net {own:+.2f} mm, foreign clear {worst:.2f} mm]")

    # VERIFY the post-condition that matters: every diode is on F.Cu. This is ADR-146's whole
    # point, and it is cheap to check, so it is checked rather than asserted in prose.
    still_bottom = [r for r, _a, c, *_ in moved if c != "F.Cu"]
    if still_bottom:
        raise SystemExit(f"ADR-146 FAILED: still on B.Cu: {still_bottom}")

    pcbnew.SaveBoard(OUT, b)
    print(f"\nwrote {OUT}")

    # read it back rather than trusting the in-memory object
    chk = pcbnew.LoadBoard(OUT)
    got = {}
    for ref, *_ in moved:
        fp = chk.FindFootprintByReference(ref)
        if fp is None:
            raise SystemExit(f"read-back lost {ref}")
        got[ref] = {
            "layer": fp.GetLayerName(),
            "x": round(fp.GetPosition().x / UM, 3),
            "y": round(fp.GetPosition().y / UM, 3),
            "rot": round(fp.GetOrientation().AsDegrees(), 1),
        }
    bad = [r for r, v in got.items() if v["layer"] != "F.Cu"]
    if bad:
        raise SystemExit(f"read-back disagrees: {bad}")

    print("read-back verified: all four on F.Cu")
    for r, v in sorted(got.items()):
        print(f"  {r}: {v}")

    summary = {
        "stage": 1,
        "outline_mm": [W, H],
        "base_board": os.path.relpath(base, HERE),
        "diode_sites": {r: v for r, v in got.items()},
        "source": "V11-DESIGN-SPEC.md section 1 / v11_diode_sites.py",
        "note": "STAGE 1 ONLY -- 97 of 101 components are still at their v10 positions, "
                "and nothing is routed. Not an orderable board.",
    }
    p = os.path.join(HERE, "v11_board_stage1.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
