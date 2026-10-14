#!/usr/bin/env python3
"""ORDER-PACKAGE CONSISTENCY GATE -- deterministic checks for the four defects the operator named.

Every check encodes a MEASURED failure. Run before any order:

    python3 tracker/hardware/tests/test_order_package_consistency.py

Exit 0 = consistent. Exit 1 = at least one defect class present.

THE FOUR DEFECT CLASSES (all real, all measured 2026-10-14):
  1. RADIO SLOT COUNT      -- three LR2021 slots ruled; the board carries two, and Site A is a
                              nested field that cannot supply the third.
  2. OUTLINE DISAGREEMENT  -- the committed repo board and the packaged board have DIFFERENT
                              Edge.Cuts, so a re-export from the repo source ships the wrong size.
  3. CPL WITHOUT DNP FLAG  -- the CPL is what JLC reads to place parts; with no DNP column, 12
                              designators flagged DNP in the BOM were listed as placements.
  4. TODO ON A POPULATED ROW -- D_CLAMP / R_NTC1 / TH_NTC1 carry 'TODO(unverified)' as a VALUE.
                              A TODO is a legal note, never a legal PART.
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(HW))

NET = os.path.join(HW, "schematics", "flight_board", "v9_flight.net")
COMMITTED_HUB = os.path.join(HW, "hub_board_v9.kicad_pcb")
PACKAGED_HUB = os.path.join(REPO, "docs", "fab", "hub-v9", "gerbers", "hub_v9.kicad_pcb")
GERBERS = os.path.join(REPO, "docs", "fab", "hub-v9", "gerbers")
CPL = os.path.join(GERBERS, "hub_v9-cpl-jlcpcb.csv")
BOM = os.path.join(GERBERS, "hub_v9-bom-jlc.csv")

PASS, FAIL = [], []


def ck(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    for line in str(detail).split("\n"):
        if line:
            print(f"          {line}")


def csv_rows(path):
    rows = []
    for line in open(path, encoding="utf-8", errors="replace").read().splitlines():
        if not line.strip():
            continue
        cells, cur, inq = [], "", False
        for ch in line:
            if ch == '"':
                inq = not inq
            elif ch == "," and not inq:
                cells.append(cur)
                cur = ""
            else:
                cur += ch
        cells.append(cur)
        rows.append([c.strip().strip('"') for c in cells])
    return rows


def board_fps(path):
    code = (
        "import sys;sys.path.insert(0,'/usr/lib/python3/dist-packages');import pcbnew;"
        f"b=pcbnew.LoadBoard({path!r});"
        "print(' '.join(sorted(f.GetReference() for f in b.GetFootprints())))"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300)
    out = set()
    for line in r.stdout.splitlines():
        if line.strip():
            out |= set(line.split())
    return out


def board_extent(path):
    """The OUTLINE size, from Edge.Cuts DRAWING ITEMS ONLY.

    HISTORY (this is why the function is written this narrowly): an earlier version used
    GetBoardEdgesBoundingBox(), which is inflated by TRACK/VIA/COPPER extents, not just the outline.
    It reported the packaged hub board as 70.15 x 71.65 when its Edge.Cuts are exactly 70.15 x 70.15
    -- the extra 1.50 mm of height was COPPER reaching past the edge, not the board being taller.
    That produced a FALSE "outline divergence" FAIL against a board that was actually fine. Measure
    the outline from the Edge.Cuts items themselves and nothing else.

    Also: both this repo's boards carry a uniform 0.075 mm outset on every side (103.075 - (-0.075)
    = 103.150), a drawing convention rather than a size. So compare OUTLINE-TO-OUTLINE and allow the
    outset to cancel; do not compare a nominal figure against a measured one.
    """
    code = (
        "import sys;sys.path.insert(0,'/usr/lib/python3/dist-packages');import pcbnew;"
        f"b=pcbnew.LoadBoard({path!r});"
        "xs=[];ys=[]\n"
        "for d in b.GetDrawings():\n"
        "    if d.GetLayer()==pcbnew.Edge_Cuts:\n"
        "        bb=d.GetBoundingBox();xs+=[pcbnew.ToMM(bb.GetLeft()),pcbnew.ToMM(bb.GetRight())]\n"
        "        ys+=[pcbnew.ToMM(bb.GetTop()),pcbnew.ToMM(bb.GetBottom())]\n"
        "print('%.4f %.4f' % (max(xs)-min(xs), max(ys)-min(ys)) if xs else 'None None')"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300)
    for line in r.stdout.splitlines():
        p = line.split()
        if len(p) == 2 and p[0] != "None":
            try:
                return float(p[0]), float(p[1])
            except ValueError:
                pass
    return None


print("=" * 74)
print("ORDER-PACKAGE CONSISTENCY GATE")
print("=" * 74)

# ---------------------------------------------------------------------------------------------
print("\n=== 1. RADIO SLOT COUNT (three LR2021 slots ruled 2026-10-14) ===")
s = open(NET, encoding="utf-8", errors="replace").read()
mods = {m.group(1): m.group(2) for m in
        re.finditer(r'\(comp \(ref "([^"]+)"\)\s*\n\s*\(value "([^"]*)"\)', s)}
lr = {r: v for r, v in mods.items() if "LoRa" in v}
print(f"    LR2021 slots: {sorted(lr.items())}")
print(f"    separate silicon: {[r for r, v in mods.items() if 'SX1280' in v]}")
ck("three LR2021 slots present (2 LP + 1 F33)", len(lr) >= 3,
   f"found {len(lr)}. REQUIRED 3. Site A (U2/U3) is the NESTED field and CANNOT supply two,\n"
   f"so a new Site C is needed -- see docs/fab/V9-RADIO-SLOT-CONSOLIDATION.md")

# ---------------------------------------------------------------------------------------------
print("\n=== 2. OUTLINE: committed repo board vs packaged board ===")
a = board_extent(COMMITTED_HUB)
b = board_extent(PACKAGED_HUB)
if a and b:
    print(f"    committed {os.path.relpath(COMMITTED_HUB, REPO)}: {a[0]:.2f} x {a[1]:.2f} mm")
    print(f"    packaged  {os.path.relpath(PACKAGED_HUB, REPO)}: {b[0]:.2f} x {b[1]:.2f} mm")
    same = abs(a[0] - b[0]) < 0.5 and abs(a[1] - b[1]) < 0.5
    ck("committed and packaged hub boards agree on the outline", same,
       "" if same else
       f"DIVERGENT {a[0]:.2f} x {a[1]:.2f} vs {b[0]:.2f} x {b[1]:.2f} mm.\n"
       f"The committed file is the SINGLE WRITER's output (tracker/hardware/build_hub_board_v9.py,\n"
       f"DEFAULT_W/H 70.0), and ADR-068 (revised 2026-10-14) sets the outline at 70 x 70. A stale\n"
       f"committed file means a re-export ships the WRONG board size -- regenerate it:\n"
       f"  python3 tracker/hardware/build_hub_board_v9.py")
else:
    ck("both hub boards loadable", False, f"committed={a} packaged={b}")

# ---------------------------------------------------------------------------------------------
print("\n=== 3. CPL: the DNP flag must be machine-readable and agree with the BOM ===")
if os.path.exists(CPL) and os.path.exists(BOM):
    cpl = csv_rows(CPL)
    hdr = cpl[0]
    has = any(h.upper() == "DNP" for h in hdr)
    print(f"    CPL header: {hdr}")
    ck("the CPL carries an explicit DNP column", has,
       "" if has else
       "no DNP column -> JLC reads the CPL to PLACE parts, so every designator flagged DNP\n"
       "in the BOM would be POPULATED. Measured: 12 such contradictions, including C_CAP1/\n"
       "C_CAP2 (stored energy, a functional issue) and U2/U3 (the radios).\n"
       "FIX: python3 tracker/hardware/fix_cpl_dnp.py --write")

    if has:
        di = hdr.index("DNP")
        cpl_dnp = {r[0] for r in cpl[1:] if len(r) > di and r[di].upper() == "Y"}
        bom_dnp = set()
        for r in csv_rows(BOM):
            if any(c.upper() == "DNP" for c in r) and len(r) > 1:
                for ref in r[1].split(","):
                    ref = ref.strip()
                    if ref:
                        bom_dnp.add(ref)
        cpl_refs = {r[0] for r in cpl[1:] if r}
        print(f"    BOM flags DNP: {len(bom_dnp)}   CPL flags DNP: {len(cpl_dnp)}")
        missing = sorted(x for x in (bom_dnp & cpl_refs) if x not in cpl_dnp)
        ck("every designator the BOM flags DNP is flagged DNP in the CPL", not missing,
           f"not flagged in the CPL: {missing}")
else:
    ck("CPL and BOM both present", False, f"{CPL}\n{BOM}")

# ---------------------------------------------------------------------------------------------
print("\n=== 4. NO TODO AS A PART ON A POPULATED ROW ===")
todos = {r: v for r, v in mods.items() if "TODO" in v.upper()}
print(f"    TODO-valued components on the netlist ({len(todos)}): {sorted(todos)}")
cpl_refs = {r[0] for r in csv_rows(CPL)[1:]} if os.path.exists(CPL) else set()
cpl_dnp = set()
if os.path.exists(CPL):
    rr = csv_rows(CPL)
    if any(h.upper() == "DNP" for h in rr[0]):
        di = rr[0].index("DNP")
        cpl_dnp = {r[0] for r in rr[1:] if len(r) > di and r[di].upper() == "Y"}
populated_todos = sorted((set(todos) & cpl_refs) - cpl_dnp)
ck("no TODO-valued part is a POPULATED CPL row", not populated_todos,
   "" if not populated_todos else
   f"populated rows carrying a TODO: {populated_todos}\n"
   f"Select the part, or flag the row DNP. A paid order must not contain 'TODO'.")



# ---------------------------------------------------------------------------------------------
print("\n=== 5. DRC GRADED AFTER A REFILL (the false-verdict guard) ===")
# MEASURED FAILURE THIS ENCODES: grading bs_v1_routed_strict.kicad_pcb with STALE zones reported
# 770 violations, of which 699 were copper-against-unfilled-zone artefacts (311 track+zone,
# 189 via+zone, 199 via+zone hole, ZERO pad+pad). After a pcbnew ZONE_FILLER refill the SAME board
# reports 88. So any DRC count taken before a refill is MEANINGLESS.
def stale_zone_artifact_count(json_path):
    """Count violations of the shape that a refill erases."""
    import json as _json
    try:
        d = _json.load(open(json_path))
    except Exception:
        return None
    n = 0
    for x in d.get("violations", []):
        descs = [i.get("description", "") for i in x.get("items", [])]
        if any(s.startswith("Zone") for s in descs):
            n += 1
    return n, len(d.get("violations", []))


STALE = os.path.join(os.path.dirname(CPL), "bs_v1_routed_strict-drc.json")
FILLED = os.path.join(os.path.dirname(CPL), "bs_v1_routed_strict_filled-drc.json")
if os.path.exists(STALE) and os.path.exists(FILLED):
    a = stale_zone_artifact_count(STALE)
    b = stale_zone_artifact_count(FILLED)
    print(f"    stale-zone grading : {a[1]} violations, {a[0]} zone-touching")
    print(f"    post-refill grading: {b[1]} violations, {b[0]} zone-touching")
    ck("a DRC report exists that was taken AFTER a zone refill", b[0] < a[0],
       f"the post-refill report carries FEWER zone-touching entries ({b[0]} vs {a[0]}), which is\n"
       f"the signature of a real refill. If both numbers match, the 'refilled' report was taken\n"
       f"before the fill and any violation count from it is NOT usable.")
else:
    print(f"    (no paired DRC reports present to compare)")

# ---------------------------------------------------------------------------------------------
print("\n" + "=" * 74)
print(f"RESULT: {len(PASS)} pass, {len(FAIL)} FAIL")
for f in FAIL:
    print(f"  FAIL  {f}")
print("=" * 74)
sys.exit(1 if FAIL else 0)
