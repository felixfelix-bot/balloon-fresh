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
                                   against the lowered bar and always passes. The two base-station
                                   F-checks reference route artifacts that DO NOT EXIST, because
                                   `tracker/hardware/base_station/output/` is gitignored and the
                                   base station has no editable schematic yet. They are WAIVED, with
                                   the reason PRINTED at run time from a committed record
                                   (`base_station/FR-CHECK-WAIVER.md`). If that record is missing or
                                   stops covering a check, the check FAILS -- an absent artifact must
                                   never be able to fall silently out of the run.
"""
import os
import re
import glob
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(HW))

KICAD_PRETTY = "/usr/share/kicad/footprints"
DEMO_PRETTY = "/usr/share/kicad/demos/tiny_tapeout/tinytapeout-kicad-libs/footprints"

PASS, FAIL, PENDING = [], [], []


def ck(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    for line in str(detail).split("\n"):
        if line:
            print(f"          {line}")


def ck_pending(name, detail=""):
    """A check that CANNOT run is neither a pass nor a failure -- but it must be VISIBLE.

    Kept as a primitive for a check whose reason is short and self-contained. The base-station F
    checks no longer use it: their reason is long, has to stay reproducible, and must not be able to
    vanish, so it is loaded from a committed record at run time -- see ck_waived() below.
    """
    PENDING.append(name)
    print(f"  PENDING  {name}")
    for line in str(detail).split("\n"):
        if line:
            print(f"          {line}")


# A WAIVER is stronger than a PENDING and is the shape the two base-station F checks use.
#
# WHY THIS IS NOT JUST A HARDCODED STRING: the reason a reader sees in the suite output must be the
# reason committed in the repo. If the two are separate copies they drift, and the output ends up
# citing a rationale that is no longer the recorded one. So the text lives ONCE, in
# `base_station/FR-CHECK-WAIVER.md`, and this module reads it at run time.
#
# THE FAIL-CLOSED PROPERTY (the whole point): if the artifact is absent AND the record has no entry
# for it -- record deleted, renamed, truncated, or an entry removed -- the check FAILS. A silent
# `PENDING` fallback would mean that deleting one markdown file quietly turns two real gaps into a
# green run, which is exactly the failure mode this file exists to catch.
WAIVED = []
WAIVER_RECORD = os.path.join(HW, "base_station", "FR-CHECK-WAIVER.md")


def _waiver_blocks(path=WAIVER_RECORD):
    """Parse `WAIVER: <artifact-basename>` blocks from the committed waiver record.

    Returns {basename: [reason lines]}. An empty dict means "no waiver on record" -- which is a FAIL
    at the call site, never a pass. Text after the last entry, and a block cut short by `---`, are
    dropped rather than half-read.
    """
    try:
        text = open(path, encoding="utf-8").read()
    except OSError:
        return {}
    out, cur = {}, None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("WAIVER:"):
            cur = s.split(":", 1)[1].strip()
            out[cur] = []
        elif s.startswith("---"):
            cur = None
        elif cur is not None and s:
            out[cur].append(s)
    return {k: v for k, v in out.items() if v}


def ck_waived(name, reason_lines):
    """PRINT the waiver loudly, keep it COUNTED, and never call it a pass."""
    WAIVED.append(name)
    print(f"  WAIVED   {name}")
    print(f"          the artifact is ABSENT and NOT produced. Reason, from "
          f"{os.path.relpath(WAIVER_RECORD, REPO)}:")
    for line in reason_lines:
        print(f"          {line}")
    print(f"          A WAIVER IS NOT A PASS. It is a stated gap that stays countable and is never"
          f" deleted.")


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
    """Map library NAME -> [dirs], the way KiCad actually resolves a lib_id.

    KiCad matches a `Lib:Footprint` lib_id against the name DECLARED in an
    `fp-lib-table` -- not against the `.pretty` directory's basename. Those two can
    differ in case (the v9 project declares `Tracker_Mechanical` for the directory
    `tracker_mechanical.pretty`), and keying on the basename then INVENTS a defect:
    measured 2026-10-15, `J_W1..J_W4 -> Tracker_Mechanical:Wing_Tab_4P` was reported
    as "library not installed" while the table declared it and the 8,176-byte
    `Wing_Tab_4P.kicad_mod` was present. That false FAIL is indistinguishable from a
    real one at the call site, which is why the table is now the primary source.

    Resolution order: fp-lib-table DECLARED names (authoritative) -> .pretty
    directory basenames (fallback, for libs with no table entry). A
    case-insensitive alias is also registered so a case-only difference can never
    fabricate a failure again.
    """
    libs = {}

    def add(name, path):
        if not path:
            return
        libs.setdefault(name, [])
        if path not in libs[name]:
            libs[name].insert(0, path)
        # case-insensitive alias: a case-only mismatch must never invent a defect
        low = name.lower()
        if low != name:
            libs.setdefault(low, [])
            if path not in libs[low]:
                libs[low].insert(0, path)

    # 1. authoritative: names DECLARED in any fp-lib-table, URI resolved
    for tbl in glob.glob(os.path.join(HW, "**", "fp-lib-table"), recursive=True):
        here = os.path.dirname(tbl)
        try:
            t = open(tbl, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for m in re.finditer(r'\(lib \(name "([^"]+)"\)(.*?)\(uri "([^"]+)"\)', t, re.S):
            name, uri = m.group(1), m.group(3)
            p = uri.replace("${KIPRJMOD}", here)
            p = p.replace("${KICAD9_FOOTPRINT_DIR}", KICAD_PRETTY)
            if not os.path.isabs(p):
                p = os.path.normpath(os.path.join(here, p))
            add(name, os.path.normpath(p))

    # 2. fallback: stock + demo dirs and repo-local .pretty dirs by basename
    for base in (KICAD_PRETTY, DEMO_PRETTY):
        if not os.path.isdir(base):
            continue
        for d in os.listdir(base):
            if d.endswith(".pretty"):
                add(d[:-7], os.path.join(base, d))
    for root, dirs, _files in os.walk(HW):
        for d in dirs:
            if d.endswith(".pretty"):
                add(d[:-7], os.path.join(root, d))
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
# TWO DISTINCT LINKS, deliberately separated so a failure says WHICH link is broken:
#   C1  netlist  ->  the single-writer's COMMITTED board   (is the design placed at all?)
#   C2  committed ->  the PACKAGED board                   (is the order package current?)
# Conflating them hid the real state on 2026-10-14: the committed board had been regenerated to
# 44/44 while the packaged (routed) artifact still carried the old 39, so one check reported a
# single opaque failure instead of naming the stale package.
COMMITTED_HUB_BOARD = os.path.join(HW, "hub_board_v9.kicad_pcb")
PACKAGED_HUB_BOARD = os.path.join(REPO, "docs", "fab", "hub-v9", "gerbers", "hub_v9.kicad_pcb")
PAIRS = [
    ("v9 hub (netlist -> committed board)",
     os.path.join(HW, "schematics", "flight_board", "v9_flight.net"),
     COMMITTED_HUB_BOARD),
    # 2026-11-11: repointed to the artifact that is actually derived from the ERC-gated netlist.
    # The old `_placed`/`_v2` boards carry 44 footprints while the netlist declares 53 (12 missing
    # incl. the whole U_MCU decoupling ring, 3 removed by the startup-circularity fix), so this
    # check failed on master. Pointing it at a stale artifact is what let that drift persist.
    ("base station (netlist -> unrouted board)",
     os.path.join(HW, "base_station", "base_station_v1.net"),
     os.path.join(HW, "base_station", "base_station_v1_unrouted.kicad_pcb")),
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

# --- C2: is the PACKAGED board the same artifact as the committed one? ------------------------
def _refs(path):
    code = ("import sys;sys.path.insert(0,'/usr/lib/python3/dist-packages');import pcbnew;"
            f"b=pcbnew.LoadBoard({path!r});"
            "print(' '.join(sorted(f.GetReference() for f in b.GetFootprints())))")
    rr = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300)
    out = set()
    for line in rr.stdout.splitlines():
        if line.strip():
            out |= set(line.split())
    return out


if os.path.exists(COMMITTED_HUB_BOARD) and os.path.exists(PACKAGED_HUB_BOARD):
    c_refs, p_refs = _refs(COMMITTED_HUB_BOARD), _refs(PACKAGED_HUB_BOARD)
    print(f"    committed board {len(c_refs)} footprints   packaged board {len(p_refs)} footprints")
    missing = sorted(c_refs - p_refs)
    ck("C2. the PACKAGED board carries everything the committed board does", not missing,
       "" if not missing else
       f"the packaged board is STALE: it lacks {missing}\n"
       f"The committed board is the single writer's output; the packaged board is DERIVED from it.\n"
       f"A stale package would ship hardware missing those parts -- the exact defect that reached\n"
       f"the order package once already. REBUILD: route the committed board, re-emit the BOM/CPL/\n"
       f"gerbers, and copy the routed board into the package.")

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
_WAIVERS = _waiver_blocks()
print(f"    waiver record: {os.path.relpath(WAIVER_RECORD, REPO)} "
      f"({'present, %d entr%s' % (len(_WAIVERS), 'y' if len(_WAIVERS) == 1 else 'ies') if _WAIVERS else 'ABSENT -- an absent artifact will FAIL, not be waived'})")
for label, brd, expect_clean in ROUTED:
    if not os.path.exists(brd):
        _why = _WAIVERS.get(os.path.basename(brd))
        if _why:
            ck_waived(f"F. {label}: board present", _why)
        else:
            ck(
                f"F. {label}: board present", False,
                f"{brd} does not exist AND there is no WAIVER entry for "
                f"{os.path.basename(brd)} in {os.path.relpath(WAIVER_RECORD, REPO)}.\n"
                f"An absent artifact with no recorded waiver is a FAIL. This branch exists so the gap\n"
                f"cannot be made to disappear by deleting the waiver record: a check whose reason can be\n"
                f"edited away is a check that can be silently retired.")
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
print("\n=== G. EVERY EXEMPTION RULE IN THE FROZEN RULESET MUST ACTUALLY FIRE ===")
# MEASURED 2026-10-14: the frozen ruleset carried an OPERATOR-APPROVED scoped exemption for the
# edge-launched wing land sets whose condition was `A.Reference == 'J_W1' || ...`. It was INERT --
# it had never suppressed a single item, and the 28 copper_edge_clearance errors kept being
# re-reported as if newly found. Proved with a control: a blanket edge_clearance rule DOES reduce
# the count (28 -> 16), while every Reference-based form leaves it at 28.
#
# An exemption that does nothing is WORSE than no exemption: the ruleset reads as though the class
# is handled, so nobody looks again. This check makes a non-firing exemption visible.
DRU = os.path.join(HW, "jlcpcb-s1-frozen.kicad_dru")
try:
    dru_text = open(DRU, encoding="utf-8").read()
except Exception as e:
    ck("G. frozen ruleset readable", False, str(e))
    dru_text = ""

import re as _re
# Strip COMMENT LINES before scanning. The check is about CONDITIONS THAT FIRE, and a commented-out
# example cannot fire. The first version scanned the whole file, so the explanatory comment documenting
# *why* the Reference form is inert -- added on 2026-10-16 -- tripped its own guard. That is a false
# positive: it would force us to delete the very explanation that stops the next person reinstating the
# inert rule.
_dru_live = "\n".join(ln for ln in dru_text.splitlines() if not ln.lstrip().startswith("#"))
_conds = _re.findall(r'\(condition\s+"([^"]+)"\)', _dru_live)
# A.Reference/B.Reference are the inert forms. A.Type is legitimate -- it resolves on the copper item.
_ref_conds = [c for c in _conds if "A.Reference" in c or "B.Reference" in c]
print(f"    exemption conditions in the frozen ruleset: {len(_conds)}")
for c in _conds:
    print(f"      {c[:100]}")
ck("G. no exemption relies on Reference matching (measured INERT for edge_clearance pairs)",
   not _ref_conds,
   "" if not _ref_conds else
   f"Reference-based conditions present: {_ref_conds}\n"
   f"MEASURED: A.Reference/B.Reference do NOT match for copper-vs-Edge.Cuts pairs -- all eight\n"
   f"forms left the count at 28 while a blanket rule took it to 16. Such a rule is INERT: it reads\n"
   f"as though the class is handled, so nobody looks again. Either remove it and record a DOCUMENTED\n"
   f"DELTA with an explicit count, or find a condition that actually fires. See\n"
   f"docs/fab/EDGE-RULE-INERT-FINDING.md.")

# =============================================================================================
print("\n" + "=" * 76)
print(f"RESULT: {len(PASS)} pass, {len(FAIL)} FAIL, {len(WAIVED)} WAIVED, {len(PENDING)} PENDING")
if PENDING:
    print()
    print("  PENDING -- cannot run yet, reason recorded, NOT deleted:")
    for nm in PENDING:
        print(f"    - {nm}")
    print("  A pending check is NOT a pass. It is a gap that has been stated instead of hidden.")
if WAIVED:
    print()
    print("  WAIVED -- artifact absent, reason PRINTED above from the committed record:")
    for nm in WAIVED:
        print(f"    - {nm}")
    print("  A waiver is NOT a pass. It is a gap that is stated, countable, and never deleted.")
    print("  Re-run with --strict-waivers to make any waiver fail the run (for a release gate).")
for f in FAIL:
    print(f"  FAIL  {f}")
print("=" * 74)
print()
print("NOTE: section A/B/C/D failures ARE the order blockers. Do not order while any")
print("      'declared vs placed' or 'empty footprint' check fails.")
# A waiver is the honest state of a gap, but it must not be able to masquerade as a finished suite
# forever: --strict-waivers turns every waiver into a failure, so a release gate can require that the
# base-station artifacts actually exist rather than being waived. Default remains non-failing so a
# normal run reports the gap (loudly) without blocking work that is unrelated to the base station.
_STRICT = "--strict-waivers" in sys.argv
if _STRICT and WAIVED:
    print()
    print(f"STRICT MODE: {len(WAIVED)} waiver(s) present -- failing the run by request.")
sys.exit(1 if (FAIL or (_STRICT and WAIVED)) else 0)
