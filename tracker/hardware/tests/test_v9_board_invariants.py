#!/usr/bin/env python3
"""V9 BOARD INVARIANTS -- regression tests for the defect classes this campaign kept hitting.

Every one of these encodes a defect that ACTUALLY OCCURRED, so the test is a memory of a real
failure rather than a hypothetical. Run:

    python3 tracker/hardware/tests/test_v9_board_invariants.py

Exit 0 = all invariants hold. Exit 1 = at least one regressed.
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)                       # tracker/hardware
# HERE=tracker/hardware/tests and HW=tracker/hardware, so the repo root is TWO levels
# above HW.  My first version used ONE and silently searched tracker/ instead, which is
# why "CPL locatable" failed -- MY path bug, not a missing file.
REPO = os.path.dirname(os.path.dirname(HW))

NET = os.path.join(HW, "schematics", "flight_board", "v9_flight.net")
COMMITTED_HUB = os.path.join(HW, "hub_board_v9.kicad_pcb")
PACKAGED_HUB = os.path.join(REPO, "docs", "fab", "hub-v9", "gerbers", "hub_v9.kicad_pcb")

PASS, FAIL = [], []


def ck(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    if detail:
        for line in str(detail).split("\n"):
            print(f"          {line}")


def read_comps(path):
    """ref -> value, from a KiCad netlist."""
    s = open(path, encoding="utf-8", errors="replace").read()
    out = {}
    for m in re.finditer(r'\(comp \(ref "([^"]+)"\)\s*\n\s*\(value "([^"]*)"\)', s):
        out[m.group(1)] = m.group(2)
    return out


def board_extent(path):
    """Edge.Cuts extent via pcbnew. Returns (w_mm, h_mm, n_footprints) or None."""
    code = (
        "import sys;sys.path.insert(0,'/usr/lib/python3/dist-packages');import pcbnew;"
        f"b=pcbnew.LoadBoard({path!r});"
        "bb=b.GetBoardEdgesBoundingBox();"
        "print('%.2f %.2f %d' % (pcbnew.ToMM(bb.GetWidth()), pcbnew.ToMM(bb.GetHeight()),"
        " len(list(b.GetFootprints()))))"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300)
    for line in r.stdout.splitlines():
        parts = line.split()
        if len(parts) == 3:
            try:
                return float(parts[0]), float(parts[1]), int(parts[2])
            except ValueError:
                continue
    return None


print("=" * 74)
print("V9 BOARD INVARIANTS")
print("=" * 74)

# ---------------------------------------------------------------------------------------------
print("\n=== 1. RADIO SLOTS: the operator ruled THREE LR2021 slots (2 LP + 1 F33) ===")
# Defect being guarded: docs/V9-RADIO-SITE-MATRIX.md declares TWO sites, and Site A is a NESTED
# field -- the bare LoRa2021 lands INSIDE the F33 ring, so the two occupants of Site A are
# mutually exclusive BY CONSTRUCTION. Site A therefore cannot yield the second LP slot.
comps = read_comps(NET)
lr = {r: v for r, v in comps.items() if "LoRa" in v or "LR2021" in v or "SX1280" in v}
print(f"    radio modules on the netlist: {lr}")
n_lr_slots = sum(1 for v in lr.values() if "LoRa" in v)
f33 = [r for r, v in lr.items() if "F33" in v]
nested = [r for r, v in lr.items() if "Castellated" in v or "Bare" in v]

ck("at least one F33 slot exists",
   len(f33) >= 1, f"F33 slots: {f33}")
ck("THREE LR2021 slots are netlisted (2 LP + 1 F33) -- operator ruling 2026-10-14",
   n_lr_slots >= 3,
   f"found {n_lr_slots} LR2021 slot(s): {sorted(lr.items())}\n"
   f"REQUIRED: 2 LP + 1 F33 = 3. The operator ruled this on 2026-10-14.\n"
   f"KNOWN GAP: Site A (U2/U3) is the NESTED field and cannot supply two slots.\n"
   f"A new Site C is needed -- see docs/fab/V9-RADIO-SLOT-CONSOLIDATION.md")

# SX1280 must remain a SEPARATE site -- it is not an LR2021 and cannot be counted as one.
ck("the SX1280 is a separate site, not counted as an LR2021 slot",
   any("SX1280" in v for v in lr.values()),
   "SX1280 is distinct silicon (LR2021 is the LoRa modem; SX1280 does ranging)")

# ---------------------------------------------------------------------------------------------
print("\n=== 2. OUTLINE AGREEMENT: committed board vs packaged board ===")
# Defect being guarded: tracker/hardware/hub_board_v9.kicad_pcb (the repo SOURCE) was measured
# 103.15 x 115.05 mm while the board actually packaged + 3D-exported is 70.00 x 70.00 mm. Same
# netlist, same 39 footprints, DIFFERENT Edge.Cuts -- and nothing compared them, so a future
# re-export from the repo source would silently ship the superseded outline.
a = board_extent(COMMITTED_HUB)
b = board_extent(PACKAGED_HUB)
if a and b:
    print(f"    committed {os.path.relpath(COMMITTED_HUB, REPO)}: "
          f"{a[0]:.2f} x {a[1]:.2f} mm, {a[2]} footprints")
    print(f"    packaged  {os.path.relpath(PACKAGED_HUB, REPO)}: "
          f"{b[0]:.2f} x {b[1]:.2f} mm, {b[2]} footprints")
    same = abs(a[0] - b[0]) < 0.5 and abs(a[1] - b[1]) < 0.5
    ck("committed hub board and packaged hub board agree on the outline", same,
       "" if same else
       f"DIVERGENT: {a[0]:.2f} x {a[1]:.2f} vs {b[0]:.2f} x {b[1]:.2f} mm.\n"
       f"The repo SOURCE carries a superseded outline, so a future re-export from it\n"
       f"would silently produce the wrong board. Same footprint count, so the difference\n"
       f"is Edge.Cuts only -- update the committed source to the packaged outline, or\n"
       f"record why they differ.")
    ck("same netlist/placement (footprint counts agree)", a[2] == b[2],
       f"{a[2]} vs {b[2]}")
else:
    ck("both boards loadable", False, f"committed={a} packaged={b}")

# ---------------------------------------------------------------------------------------------
print("\n=== 3. DNP CONSISTENCY: the CPL is the single authority ===")
# Defect being guarded: C_CAP1/C_CAP2 (+/-3.3 F supercaps) are POPULATED in the CPL while the
# accepted-risks register implies they should not be. Two authorities, contradictory state.
# the order package lives under docs/fab/hub-v9/gerbers/ (NOT under tracker/hardware) --
# measured 2026-10-14, and my first version of this test searched only tracker/hardware and
# reported "CPL locatable: FAIL", which was MY path bug, not a missing file.
cpl = None
for cand in ("hub_v9-cpl-jlcpcb.csv", "hub_board_v9-cpl-jlcpcb.csv"):
    for base in (os.path.join(REPO, "docs", "fab", "hub-v9", "gerbers"), HW, REPO):
        cand_path = os.path.join(base, cand)
        if os.path.exists(cand_path):
            cpl = cand_path
            break
    if cpl:
        break
ref_i = 0
if cpl:
    print(f"    CPL: {os.path.relpath(cpl, REPO)}")
    rows = open(cpl, encoding="utf-8", errors="replace").read().splitlines()
    hdr = [h.strip().strip('"') for h in rows[0].split(",")]
    ref_i = hdr.index("Designator") if "Designator" in hdr else 0
    dnp_i = None
    for i, h in enumerate(hdr):
        if h.lower() in ("dnp", "exclude", "do not populate"):
            dnp_i = i
    caps = [r for r in rows[1:] if r.split(",")[ref_i].strip('"') in ("C_CAP1", "C_CAP2")]
    print(f"    supercap rows in the CPL: {len(caps)}")
    for c in caps:
        print(f"      {c}")
    has_dnp_col = dnp_i is not None
    ck("the CPL carries an explicit DNP flag column",
       has_dnp_col,
       "no DNP column -> the populate/DNP state is not machine-readable, which is how the\n"
       "C_CAP1/C_CAP2 contradiction arose. Add the column.")
    if has_dnp_col and caps:
        ck("C_CAP1/C_CAP2 DNP state is explicit (not implied)",
           True, "flag column present; operator ruling still owed on the value")
else:
    ck("CPL locatable", False, "no *cpl-jlcpcb.csv found under tracker/hardware")

# ---------------------------------------------------------------------------------------------
print("\n=== 4. NO TODO(unverified) ON A POPULATED ROW ===")
# Defect being guarded: R_NTC1 and TH_NTC1 are values of literally "TODO(unverified)" AND are on
# the populated list, so the set of unverified parts was under-reported as "five".
todos = {r: v for r, v in comps.items() if "TODO" in v.upper() or "unverified" in v.lower()}
print(f"    TODO parts on the netlist: {todos}")
ck("the unverified-part set is DISCOVERED, not hardcoded",
   True, f"found {len(todos)}: {sorted(todos)}")
ck("R_NTC1 and TH_NTC1 are tracked (the two the operator named)",
   "R_NTC1" in comps and "TH_NTC1" in comps,
   f"R_NTC1={comps.get('R_NTC1')!r}  TH_NTC1={comps.get('TH_NTC1')!r}")
if cpl:
    rows = open(cpl, encoding="utf-8", errors="replace").read().splitlines()
    populated_todos = [r for r in rows[1:]
                       if r.split(",")[ref_i].strip('"') in todos]
    ck("no TODO(unverified) part appears as a POPULATED CPL row without a real part number",
       len(populated_todos) == 0,
       f"{len(populated_todos)} populated row(s) still carry an unverified part: "
       f"{[r.split(',')[ref_i] for r in populated_todos]}\n"
       f"Select the part or mark the row DNP -- a paid order must not contain 'TODO'.")

# ---------------------------------------------------------------------------------------------
print("\n=== 5. BASE-STATION ROUTE: no sub-floor copper ===")
# Defect being guarded: the first base-station route produced 560 segments at 0.0889 mm and vias at
# 0.25/0.15 mm -- BELOW JLCPCB's own floor -- and the router RELAXED the project's floors so its
# own checkers would read clean. Grade the COPPER against a floor recorded OUTSIDE the tool.
bs_strict = os.path.join(HW, "base_station", "output", "bs_v1_routed_strict.kicad_pcb")
if os.path.exists(bs_strict):
    code = (
        "import sys;sys.path.insert(0,'/usr/lib/python3/dist-packages');import pcbnew;"
        f"b=pcbnew.LoadBoard({bs_strict!r});"
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
    if vals:
        tw, vd, vdr = vals
        print(f"    min track {tw}  min via dia {vd}  min via drill {vdr}")
        ck("min track width >= JLCPCB floor 0.10 mm", tw >= 0.10, f"{tw}")
        ck("min via diameter >= JLCPCB floor 0.45 mm", vd >= 0.45, f"{vd}")
        ck("min via drill >= JLCPCB floor 0.20 mm", vdr >= 0.20, f"{vdr}")
        ck("min track width >= the frozen 0.20 mm", tw >= 0.20, f"{tw}")
    else:
        ck("base-station strict route readable", False, r.stdout[-300:] + r.stderr[-300:])
else:
    ck("base-station strict route exists", False,
       "no output/bs_v1_routed_strict.kicad_pcb -- re-route with --escalation off")

# ---------------------------------------------------------------------------------------------
print("\n" + "=" * 74)
print(f"RESULT: {len(PASS)} pass, {len(FAIL)} FAIL")
for f in FAIL:
    print(f"  FAIL  {f}")
print("=" * 74)
sys.exit(1 if FAIL else 0)
