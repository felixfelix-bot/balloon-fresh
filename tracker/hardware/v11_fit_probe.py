#!/usr/bin/env python3
"""v11_fit_probe.py -- does v11 physically fit, and how much bigger must the outline be?

WHY THIS EXISTS BEFORE ANY PLACEMENT CODE. v10 fitted 49 footprints on 72 x 80 mm. The v11
netlist carries 101 components (ADR-148 analog sense block, four nichrome cut channels, the
solar front end). Writing a placer before measuring capacity is how a project spends a week
nudging parts around an outline that cannot hold them -- which already happened once here: the
base-station packer top-stacked 23 parts into the top third and the "empty space at the bottom"
cost an operator round trip.

METHOD. Sum the real courtyard/bbox area of every footprint the netlist names, from the actual
libraries, then compare against usable board area (outline minus a placement margin on all four
sides). No estimator, no lookup table of "typical" sizes: the footprints are loaded and
measured.

A footprint that cannot be loaded is REPORTED, never skipped silently -- an under-counted area
would produce a confident "it fits" for a board that does not.
"""
import json
import os
import re
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMATIC_DIR = os.path.join(HERE, "schematics", "flight_board")
NETLIST = os.path.join(SCHEMATIC_DIR, "v11_flight.net")

# Outline candidates to test. v10 shipped 72 x 80.
OUTLINES = [(72.0, 80.0), (80.0, 90.0), (90.0, 100.0), (100.0, 100.0)]
# Placement margin per side: the repo's own seat rules put connectors >= 10 mm from west/east
# and >= 8.9 mm from north/south. Use a single conservative value for a capacity estimate.
MARGIN = 5.0
# Packing efficiency actually achieved on v10, measured, so the estimate is anchored to this
# project's own placer rather than an idealised 85 % textbook figure.
V10_ACHIEVED_EFFICIENCY = None  # filled in below from the real board

UM = 1_000_000.0


def parse_netlist_components(path):
    """Return [(ref, footprint, value)] from a KiCad netlist, without a full S-expr parser."""
    t = open(path, encoding="utf-8", errors="replace").read()
    out = []
    # The comp block does not end on a fixed indent, so anchor on the NEXT comp/net instead.
    starts = [m.start() for m in re.finditer(r'\(comp \(ref "', t)]
    if not starts:
        return []
    starts.append(t.find("(nets", starts[-1]))
    for i in range(len(starts) - 1):
        blk = t[starts[i]:starts[i + 1]]
        ref = re.match(r'\(comp \(ref "([^"]+)"', blk).group(1)
        fp = re.search(r'\(footprint "([^"]*)"', blk)
        val = re.search(r'\(value "([^"]*)"', blk)
        out.append((ref, fp.group(1) if fp else "", val.group(1) if val else ""))
    return out


def load_footprint(lib_id):
    """Load a footprint by LIB:NICKNAME using the PROJECT's fp-lib-table.

    KiCad's own mechanism is KICAD7_FOOTPRINT_DIR + the project fp-lib-table; guessing at
    ${KIPRJMOD}/<nick> only works for the repo-local libs and silently fails for every standard
    library (Capacitor_SMD, Package_QFN, ...), which is 90 % of the parts.
    """
    if not lib_id or ":" not in lib_id:
        return None, "no footprint field"
    nick, name = lib_id.split(":", 1)

    # 1. resolve through the project fp-lib-table, which is what the board itself uses.
    #    ${KIPRJMOD} is the directory holding the .kicad_pro, i.e. tracker/hardware -- NOT
    #    schematics/flight_board. Resolving it as the schematic dir silently breaks every
    #    repo-local lib and leaves only the system libs working.
    tbl = os.path.join(SCHEMATIC_DIR, "fp-lib-table")
    if os.path.isfile(tbl):
        raw = open(tbl, encoding="utf-8", errors="replace").read()
        m = re.search(r'\(lib \(name "%s"\).*?\(uri "([^"]+)"\)' % re.escape(nick), raw)
        if m:
            uri = m.group(1)
            for root in (HERE, SCHEMATIC_DIR):
                cand = os.path.normpath(uri.replace("${KIPRJMOD}", root))
                try:
                    fp = pcbnew.FootprintLoad(cand, name)
                except Exception:
                    fp = None
                if fp is not None:
                    return area_of(fp), "ok"

    # 2. fall back to the KiCad system footprint libraries
    for base in ("/usr/share/kicad/footprints", "/usr/share/kicad/modules"):
        d = os.path.join(base, f"{nick}.pretty")
        if os.path.isdir(d):
            try:
                fp = pcbnew.FootprintLoad(d, name)
            except Exception:
                fp = None
            if fp is not None:
                return area_of(fp), "ok"

    return None, f"footprint not loadable: {lib_id}"


def area_of(fp):
    """Courtyard-ish area: use the bounding box of pads + fab body, in mm^2."""
    bb = fp.GetBoundingBox(False, False)
    return (bb.GetWidth() / UM) * (bb.GetHeight() / UM)


def main():
    comps = parse_netlist_components(NETLIST)
    if not comps:
        print("FATAL: netlist parsed to zero components -- refusing to report a capacity")
        return 2

    loaded, failed, total = [], [], 0.0
    for ref, fp, val in comps:
        a, why = load_footprint(fp)
        if a is None:
            failed.append((ref, val, why))
        else:
            loaded.append((ref, val, a))
            total += a

    print(f"components in netlist : {len(comps)}")
    print(f"footprints measured   : {len(loaded)}")
    print(f"footprints UNMEASURED : {len(failed)}   <-- area is UNDER-counted by these")
    for r, v, w in failed[:12]:
        print(f"    {r:12s} {v:22s} {w}")
    if len(failed) > 12:
        print(f"    ... and {len(failed) - 12} more")

    # v10 achieved efficiency, measured from the board that actually shipped
    v10_path = os.path.normpath(os.path.join(HERE, "hub_board_v10.kicad_pcb"))
    v10 = pcbnew.LoadBoard(v10_path)
    if v10 is None:
        print(f"FATAL: could not load {v10_path} -- cannot anchor packing efficiency")
        return 2
    v10_area = sum(area_of(f) for f in v10.GetFootprints())
    v10_board = 72.0 * 80.0
    eff = v10_area / v10_board
    print(f"\nv10 measured: {len(v10.GetFootprints())} fps, footprint area {v10_area:.0f} mm2 "
          f"on {v10_board:.0f} mm2 = {eff * 100:.1f} % occupancy")

    print(f"\nv11 footprint area total: {total:.0f} mm2 "
          f"(+{len(failed)} unmeasured parts not included)")
    print(f"ratio v11/v10 area      : {total / v10_area:.2f}x")
    # Occupancy was measured against the WHOLE board (5760 mm2), not a margin-reduced area.
    # Applying it to a margin-reduced "usable" area would charge the placement margin twice and
    # understate capacity. Required outline area is therefore  v11_area / efficiency, compared
    # against the FULL outline area -- the same basis v10's own number was measured on.
    need_board = total / eff
    print(f"outline area needed at v10's measured {eff * 100:.1f} % occupancy: "
          f"{need_board:.0f} mm2")
    print()
    print("outline        board(mm2)   headroom    verdict")
    for w, h in OUTLINES:
        board = w * h
        ok = board >= need_board
        head = (board - need_board) / need_board * 100.0
        print(f"  {w:5.0f} x {h:<5.0f} {board:9.0f}   {head:+6.1f}%     "
              f"{'FITS' if ok else 'DOES NOT FIT'}")

    side = need_board ** 0.5
    print(f"\nminimum square outline at v10's packing efficiency: ~{side:.0f} x {side:.0f} mm")
    print("NOTE: v10 shipped at 60.7 % occupancy with 82 unconnected nets. Matching that")
    print("efficiency means matching that outcome, so treat a 0-5 % headroom as 'will not")
    print("route', not as 'fits'.")
    print("CAVEAT: this is AREA only. It cannot see clearance, keepouts, antenna seats, the")
    print("wing-seat slots, or connector edges. A board that 'fits' by area can still be")
    print("unroutable. Treat this as a go/no-go on the outline, not as a placement.")

    summary = {
        "netlist": NETLIST,
        "components": len(comps),
        "measured": len(loaded),
        "unmeasured": [{"ref": r, "value": v, "why": w} for r, v, w in failed],
        "v11_area_mm2": round(total, 1),
        "v10_area_mm2": round(v10_area, 1),
        "v10_occupancy_pct": round(eff * 100, 2),
        "min_square_outline_mm": round(side, 1),
    }
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "v11_fit_probe.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"\nwrote {p}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
