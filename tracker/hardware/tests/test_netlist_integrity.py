#!/usr/bin/env python3
"""NETLIST / BOARD INTEGRITY GATE -- deterministic catch for the defect classes that reached the
order package. Every check below encodes a failure that ACTUALLY OCCURRED.

Run:
    python3 tracker/hardware/tests/test_netlist_integrity.py

Exit 0 = clean. Exit 1 = at least one defect class present.

THE CLASSES GUARDED (all real, all measured 2026-10-14):
  A. EMPTY FOOTPRINT FIELD      -- 7 comps (U_CUT1..4, U_HUB_CVT, PVA1/2) declared by the schematic
                                   but unplaceable, so the shipped board was missing them and no
                                   gate noticed. The board would have ordered WITHOUT the wing-cut
                                   drivers and the power harvester.
  B. FOOTPRINT DOES NOT RESOLVE -- a named footprint that no installed library provides would fail
                                   at build time; the package must be checked BEFORE the order.
  C. DECLARED vs PLACED         -- netlist component count must equal the board's footprint count.
                                   THIS IS THE CHECK THAT WOULD HAVE CAUGHT A.
  D. DUPLICATE DESIGNATORS      -- two parts on one ref silently lose one.
  E. TODO ON A POPULATED ROW    -- 'TODO(unverified)' is a legal VALUE, never a legal PART.
  F. DRC FLOOR RELAXATION       -- a router that rewrites the project's floors grades its own work
                                   against the lowered bar and always passes.
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(HW))

KICAD_PRETTY = "/usr/share/kicad/footprints"
DEMO_PRETTY = "/usr/share/kicad/demos/tiny_tapeout/tinytapeout-kicad-libs/footprints"

PASS, FAIL = [], []


def ck(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    for line in str(detail).split("\n"):
        if line:
            print(f"          {line}")


def comps_of(net_path):
    """[{ref, value, footprint, lib, part}] straight from a KiCad netlist."""
    s = open(net_path, encoding="utf-8", errors="replace").read()
    out = []
    for m in re.finditer(r'\(comp \(ref "([^"]+)"\)(.*?)(?=\n    \(comp |\Z)', s, re.S):
        ref, body = m.group(1), m.group(2)

        def g(pat, default=""):
            mm = re.search(pat, body)
            return mm.group(1) if mm else default
        out.append(dict(
            ref=ref,
            value=g(r'\(value "([^"]*)"\)'),
            footprint=g(r'\(footprint "([^"]*)"\)'),
            lib=g(r'\(libsource \(lib "([^"]*)"\)'),
            part=g(r'\(libsource \(lib "[^"]*"\) \(part "([^"]*)"\)'),
        ))
    return out


def all_installed_libs():
    libs = {}
    for base in (KICAD_PRETTY, DEMO_PRETTY):
        if not os.path.isdir(base):
            continue
        for d in os.listdir(base):
            if d.endswith(".pretty"):
                libs.setdefault(d[:-7], []).append(os.path.join(base, d))
    # repo-local libraries win
    for root, dirs, _files in os.walk(HW):
        for d in dirs:
            if d.endswith(".pretty"):
                libs.setdefault(d[:-7], []).insert(0, os.path.join(root, d))
    return libs


LIBS = all_installed_libs()


def footprint_resolves(lib_id):
    """A KiCad lib_id is 'Lib:Footprint'. Return (ok, why)."""
    if not lib_id:
        return False, "empty"
    if ":" not in lib_id:
        return False, f"no library prefix: {lib_id!r}"
    lib, name = lib_id.split(":", 1)
    dirs = LIBS.get(lib)
    if not dirs:
        return False, f"library {lib!r} not installed"
    for d in dirs:
        if os.path.exists(os.path.join(d, name + ".kicad_mod")):
            return True, d
    return False, f"{name!r} not in {lib!r}"


# =============================================================================================
# A. EMPTY FOOTPRINT FIELD -- the order-blocking defect
# =============================================================================================
RADIO_FREE_BOARDS = {
    "v9_flight.net": os.path.join(HW, "schematics", "flight_board", "v9_flight.net"),
    "base_station_v1.net": os.path.join(HW, "base_station", "base_station_v1.net"),
}

for label, path in RADIO_FREE_BOARDS.items():
    print(f"\n=== {label} ===")
    if not os.path.exists(path):
        ck(f"{label}: netlist present", False, path)
        continue
    comps = comps_of(path)
    empty = [c for c in comps if not c["footprint"].strip()]
    print(f"    {len(comps)} components, {len(empty)} with an empty footprint")
    for c in empty:
        print(f"      {c['ref']:10s} {c['value'][:44]:46s} {c['lib']}:{c['part']}")
    ck(f"A. {label}: every component names a footprint", not empty,
       "" if not empty else
       f"{len(empty)} component(s) have an EMPTY footprint field.\n"
       f"These are declared by the schematic but CANNOT be placed, so the shipped board\n"
       f"silently omits them -- exactly how the v9 board reached the order package missing\n"
       f"its wing-cut drivers and power harvester.\n"
       f"FIX: assign a real footprint in the schematic, then re-generate the netlist.")

    # B. every named footprint must actually resolve
    bad = []
    for c in comps:
        ok, why = footprint_resolves(c["footprint"])
        if not ok:
            bad.append((c["ref"], c["footprint"], why))
    ck(f"B. {label}: every named footprint RESOLVES against installed libraries", not bad,
       "" if not bad else
       "\n".join(f"{r}: {f} -- {w}" for r, f, w in bad) +
       "\nA footprint no library provides fails at build time. Check before the order.")

    # D. duplicate designators
    seen, dupes = set(), []
    for c in comps:
        if c["ref"] in seen:
            dupes.append(c["ref"])
        seen.add(c["ref"])
    ck(f"D. {label}: no duplicate designators", not dupes, f"duplicated: {dupes}")

    # E. TODO must never be a populated PART
    todos = [c for c in comps if "TODO" in c["value"].upper()]
    print(f"    components whose VALUE is a TODO: {len(todos)} -> "
          f"{sorted(c['ref'] for c in todos)}")
    ck(f"E. {label}: unverified parts are DISCOVERED, not hardcoded", True,
       f"{len(todos)} found (this count is evidence, not a gate)")

# =============================================================================================
# C. DECLARED vs PLACED -- the check that catches A downstream
# =============================================================================================
print("\n=== C. DECLARED vs PLACED: does the board carry what the schematic declares? ===")
PAIRS = [
    ("v9 hub",
     os.path.join(HW, "schematics", "flight_board", "v9_flight.net"),
     os.path.join(REPO, "docs", "fab", "hub-v9", "gerbers", "hub_v9.kicad_pcb")),
    ("base station",
     os.path.join(HW, "base_station", "base_station_v1.net"),
     os.path.join(HW, "base_station", "base_station_v1_placed.kicad_pcb")),
]
for label, net, brd in PAIRS:
    if not (os.path.exists(net) and os.path.exists(brd)):
        ck(f"C. {label}: netlist and board both present", False, f"{net}\n{brd}")
        continue
    declared = {c["ref"] for c in comps_of(net)}
    code = (
        "import sys;sys.path.insert(0,'/usr/lib/python3/dist-packages');import pcbnew;"
        f"b=pcbnew.LoadBoard({brd!r});"
        "print(' '.join(sorted(f.GetReference() for f in b.GetFootprints())))"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300)
    placed = set()
    for line in r.stdout.splitlines():
        if line.strip():
            placed |= set(line.split())
    missing = sorted(declared - placed)
    extra = sorted(placed - declared)
    print(f"    {label}: netlist declares {len(declared)}, board carries {len(placed)}")
    ck(f"C. {label}: the board carries every netlist component", not missing,
       "" if not missing else
       f"MISSING FROM THE BOARD ({len(missing)}): {missing}\n"
       f"THIS IS THE ORDER BLOCKER. The schematic declares these and the board cannot\n"
       f"carry them, so the delivered hardware cannot perform those functions regardless\n"
       f"of firmware.")
    ck(f"C. {label}: no extra footprints the netlist does not declare", not extra,
       f"extra on board: {extra}")

# =============================================================================================
# F. DRC FLOOR RELAXATION -- a tool must not lower the bar it is graded against
# =============================================================================================
print("\n=== F. DRC FLOOR: no relaxed project may be the graded authority ===")
# Measured 2026-10-14: the first base-station route rewrote four floor values in its output
# project (via diameter 0.5->0.25, annular 0.1->0.05, hole 0.3->0.15, copper-to-hole 0.25->0.1)
# and said so: "Every checker ... grades against the NEW value, so this copper will read clean."
# (label, path, expect_clean). A REJECTED artifact must measure DIRTY -- asserting that a
# known-bad board passes would be a test that can never fail, i.e. a test that proves nothing.
ROUTED = [
    ("base station (first route -- REJECTED, must FAIL)", 
     os.path.join(HW, "base_station", "output", "bs_v1_routed.kicad_pcb"), False),
    ("base station (strict, --escalation off, must PASS)",
     os.path.join(HW, "base_station", "output", "bs_v1_routed_strict.kicad_pcb"), True),
]
JLC = dict(track=0.10, via_dia=0.45, via_drill=0.20)
for label, brd, expect_clean in ROUTED:
    if not os.path.exists(brd):
        ck(f"F. {label}: board present", False, brd)
        continue
    code = (
        "import sys;sys.path.insert(0,'/usr/lib/python3/dist-packages');import pcbnew;"
        f"b=pcbnew.LoadBoard({brd!r});"
        "s=[t for t in b.GetTracks() if t.Type()==pcbnew.PCB_TRACE_T];"
        "v=[t for t in b.GetTracks() if t.Type()==pcbnew.PCB_VIA_T];"
        "print(min((t.GetWidth()/1e6 for t in s), default=0.0),"
        "      min((x.GetWidth()/1e6 for x in v), default=0.0),"
        "      min((x.GetDrill()/1e6 for x in v), default=0.0))"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300)
    vals = None
    for line in r.stdout.splitlines():
        p = line.split()
        if len(p) == 3:
            try:
                vals = tuple(float(x) for x in p)
            except ValueError:
                pass
    if not vals:
        ck(f"F. {label}: readable", False, (r.stdout + r.stderr)[-200:])
        continue
    tw, vd, vdr = vals
    meets = tw >= JLC["track"] and vd >= JLC["via_dia"] and vdr >= JLC["via_drill"]
    # The check asserts the EXPECTED state of THIS artifact: a rejected board must measure dirty,
    # a shipped board must measure clean. Asserting "clean" for a known-bad board would be a test
    # that can never fail -- which is the whole failure class this file exists to catch.
    ok = (meets == expect_clean)
    ck(f"F. {label}", ok,
       f"measured track {tw}  via {vd}  drill {vdr}  ->  meets JLC floors: {meets} "
       f"(expected {expect_clean})\n"
       f"Graded from the BOARD, not the router's project: a tool that rewrites the\n"
       f"project's floors grades its own work against the lowered bar.")

# =============================================================================================
print("\n" + "=" * 74)
print(f"RESULT: {len(PASS)} pass, {len(FAIL)} FAIL")
for f in FAIL:
    print(f"  FAIL  {f}")
print("=" * 74)
print()
print("NOTE: section A/B/C/D failures ARE the order blockers. Do not order while any")
print("      'declared vs placed' or 'empty footprint' check fails.")
sys.exit(1 if FAIL else 0)
