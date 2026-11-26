#!/usr/bin/env python3
"""Build the base-station board UNROUTED and electrically clean, from the ERC-gated netlist.

WHY A DRIVER AND NOT A BIGGER BUILDER. Three separate measured defects have to be fixed in a
fixed order, and each one has to be re-measured afterwards:

  1. STALE PARTS. `base_station_v1_placed{,_v2}.kicad_pcb` carry 44 footprints. The current
     netlist (`base_station_v1.net`, which `base_station_parity.py` proves equals the ERC-gated
     schematic) declares 53. Twelve parts are ABSENT from the board (C_FLASH, the U_MCU
     decoupling set C_MCU_P10/P22/P23/P33/P42/P43/P48/P49/P50, C_VREG_OUT, R_PG) and three
     that no longer exist are STILL on it (R_EN, R_FB1, R_FB2 -- removed by the startup-
     circularity fix). Measuring it: `tracker/hardware/tests/test_netlist_integrity.py`
     reports two FAIL C-checks against them on master.
     Repair: re-place from the netlist. This MOVES PARTS, so it is reported as a placement
     change and gated by density_gate.py, never applied silently.

  2. STALE POUR. Both committed boards carry a `filled_polygon` written before placement: one
     unbroken rectangle under every part. `kicad-cli pcb drc` then reports 37 `clearance` +
     37 `solder_mask_bridge`, all pad-vs-zone, all at `actual 0.0000 mm`, all on two
     footprints. Measured with the pad's own copper polygon against the zone's FILLED polygon:
     0.0000 mm before a refill, 0.2005 mm after, against an untouched 0.200 mm zone rule.
     Repair: refill. This is NOT a rule relaxation -- the rule is read back from the file.

  3. SILK. 69 silk violations (48 overlap / 16 over copper / 5 edge) are a HARD gate with no
     allow-list (AGENTS.md 23-26) and must be fixed BEFORE routing (24).
     Repair: silk_repair.py, which only moves reference TEXT and footprint silk GRAPHICS.

ORDER IS THE GATE ORDER (AGENTS.md 21): schematic -> ERC -> netlist -> board -> DRC -> silk.
The output is UNROUTED BY DESIGN: 0 tracks. Its unconnected count is the ratnest, and this
driver PRINTS the arithmetic proof of that (sum of pads-1 over every non-GND multi-pad net)
so "82 unconnected" cannot be mistaken for 82 lost connections.

Usage:
  build_unrouted_board.py [--outline 70x50] [-o OUT.kicad_pcb] [--workdir DIR] [--json R.json]
Exit: 0 = built, every gate green; 1 = built, a gate failed; 2 = could not run.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PY = "/usr/bin/python3"
ENV = dict(os.environ, PYTHONPATH="/usr/lib/python3/dist-packages")

DEFAULT_OUT = os.path.join(HERE, "base_station_v1_unrouted.kicad_pcb")
# the project file that owns the RATIFIED DRC floors. A board saved without its sibling
# .kicad_pro inherits KiCad's stock rules instead (min through-hole 0.3 vs the project's 0.2),
# which produces phantom drill violations -- measured on the hub.
RULES_PRO = os.path.join(HERE, "base_station_v1_placed_v2.kicad_pro")


def run(cmd, label):
    r = subprocess.run(cmd, capture_output=True, text=True, env=ENV)
    out = ((r.stdout or "") + (r.stderr or ""))
    out = "\n".join(ln for ln in out.splitlines()
                    if "Debug: Adding duplicate image handler" not in ln)
    print(f"--- {label}: rc={r.returncode}")
    for ln in out.strip().splitlines()[-12:]:
        print(f"    {ln}")
    return r.returncode, out


def drc(board, out_json):
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all",
                    "-o", out_json, board], capture_output=True, text=True)
    with open(out_json) as fh:
        return json.load(fh)


def ratnest_arithmetic(board):
    """sum(pads-1) over every non-GND net with 2+ electrically-named pads.

    This is what KiCad's unconnected count MUST equal on a board with no copper: every pad on
    a net beyond the first needs one connection. If the DRC count is larger, copper is missing;
    if smaller, something is joined that should not be.
    """
    import pcbnew
    b = pcbnew.LoadBoard(board)
    per_net = {}
    for fp in b.GetFootprints():
        for p in fp.Pads():
            n = p.GetNetname()
            if n:
                per_net.setdefault(n, []).append((fp.GetReference(), p.GetNumber()))
    total, nets = 0, 0
    for n, pads in per_net.items():
        if n == "GND" or len(pads) < 2:
            continue
        total += len(pads) - 1
        nets += 1
    single = sorted(n for n, ps in per_net.items() if n != "GND" and len(ps) == 1)
    return {"ratnest_expected": total, "multi_pad_nets": nets,
            "gnd_pads": len(per_net.get("GND", [])), "single_pad_nets": single,
            "tracks": len(list(b.GetTracks())), "footprints": len(list(b.GetFootprints())),
            "nets_total": len(per_net)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outline", default="70x50")
    ap.add_argument("-o", "--out", default=DEFAULT_OUT)
    ap.add_argument("--workdir", default=None)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()

    if not shutil.which("kicad-cli"):
        print("REFUSED: kicad-cli not on PATH -- cannot grade, so declining to build")
        return 2
    for need in ("place_base_station.py", "refill_zones.py", "silk_repair.py",
                 "placement_gate.py", "density_gate.py"):
        if not os.path.exists(os.path.join(HERE, need)):
            print(f"REFUSED: required stage missing: {need}")
            return 2

    wd = a.workdir or tempfile.mkdtemp(prefix="bs_unrouted_")
    os.makedirs(wd, exist_ok=True)
    out = os.path.abspath(a.out)
    base = os.path.splitext(out)[0]
    staged = os.path.join(wd, "placed.kicad_pcb")
    staged2 = os.path.join(wd, "spread.kicad_pcb")
    refilled = os.path.join(wd, "refilled.kicad_pcb")

    # ---- 0. the project scaffolding that makes library lookups and rules resolve -----------
    shutil.copyfile(RULES_PRO, os.path.join(wd, "placed.kicad_pro"))
    shutil.copyfile(RULES_PRO, os.path.join(wd, "refilled.kicad_pro"))
    if os.path.abspath(base + ".kicad_pro") != os.path.abspath(RULES_PRO):
        shutil.copyfile(RULES_PRO, base + ".kicad_pro")
    for name in ("fp-lib-table", "sym-lib-table"):
        src = os.path.join(HERE, name)
        if os.path.exists(src):
            dst = os.path.join(wd, name)
            if os.path.abspath(dst) != os.path.abspath(src):
                shutil.copyfile(src, dst)
            dst2 = os.path.join(os.path.dirname(out), name)
            if os.path.abspath(dst2) != os.path.abspath(src):
                shutil.copyfile(src, dst2)
    libdst = os.path.join(os.path.dirname(out), "library.pretty")
    if os.path.isdir(os.path.join(HERE, "library.pretty")) and not os.path.exists(libdst):
        shutil.copytree(os.path.join(HERE, "library.pretty"), libdst)

    # ---- 1. place from the ERC-gated netlist ----------------------------------------------
    rc, _ = run([PY, os.path.join(HERE, "place_base_station.py"),
                 "--outline", a.outline, "--out", staged], "1/4 place from netlist")
    if rc != 0:
        print("FAILED: placement stage")
        return 2

    # ---- 1b. spread the rows over the FULL usable height ------------------------------------
    # pack_rest() starts at the top edge, so a tall outline leaves a dead strip at the bottom
    # (measured: 55.32 x 13.25 mm = 732.1 mm2 empty, 33 % of a 55x40 board) and crams every
    # designator into the packed band. Respacing is additive in Y only, so it can only ADD
    # clearance -- and it is what lets the 0.80 mm fab-minimum labels find room.
    rc, _ = run([PY, os.path.join(HERE, "respace_rows.py"), staged, "-o", staged2,
                 "--json", os.path.join(wd, "respace.json")], "1b/5 respace rows")
    if rc != 0:
        # not fatal: a board whose rows already fill the height has nothing to respace
        print("         (respace declined -- rows already fill the usable height)")
        import shutil as _sh
        _sh.copyfile(staged, staged2)

    # ---- 2. refill the pours ---------------------------------------------------------------
    rc, _ = run([PY, os.path.join(HERE, "refill_zones.py"), staged2, "-o", refilled,
                 "--json", os.path.join(wd, "refill.json")], "2/4 refill zones")
    if rc != 0:
        print("FAILED: zone refill stage")
        return 1

    # ---- 3. silkscreen legibility, BEFORE routing ------------------------------------------
    rc, _ = run([PY, os.path.join(HERE, "silk_repair.py"), "--board", refilled, "-o", out,
                 "--json", base + ".silk-moves.json"], "3/4 silk repair")
    silk_rc = rc

    # ---- 3b. hide 3D models whose file does not resolve --------------------------------------
    # By TEXT: `Models()` returns copies and there is no `RemoveModel()`, so an `m_Show=False`
    # set in Python does not survive SaveBoard. HIDE, never SUBSTITUTE -- the installed library
    # carries LFCSP-32 ..._EP3.6x3.6mm against this footprint's ..._EP3.1x3.1mm, a different
    # exposed pad, and a wrong body renders silently (kicad-cli exits 0 either way).
    # The commit gate (pad_audit.py) counts an unresolved model only while it is still SHOWN.
    rc, _ = run([PY, os.path.join(HERE, "hide_unresolved_models.py"), out,
                 "--json", base + ".models.json"], "3b/4 hide unresolved 3D models")
    if rc != 0:
        print("FAILED: a 3D model reference does not resolve and could not be hidden")
        return 1

    # ---- 4. grade ---------------------------------------------------------------------------
    doc = drc(out, base + ".drc.json")
    errors = [v for v in doc["violations"] if v.get("severity") == "error"]
    warns = [v for v in doc["violations"] if v.get("severity") != "error"]
    rat = ratnest_arithmetic(out)
    rc_p, _ = run([PY, os.path.join(HERE, "placement_gate.py"), out], "4/4 placement gate")
    rc_d, _ = run([PY, os.path.join(HERE, "density_gate.py"), out,
                   "--json", base + ".density.json"], "4/4 density gate")

    print()
    print(f"=== GRADE {os.path.basename(out)}")
    print(f"  outline      : {a.outline} mm")
    print(f"  footprints   : {rat['footprints']}   tracks/vias: {rat['tracks']}")
    print(f"  nets         : {rat['nets_total']} (multi-pad non-GND {rat['multi_pad_nets']}, "
          f"GND pads {rat['gnd_pads']})")
    print(f"  violations   : {len(doc['violations'])} total = "
          f"{len(errors)} ERROR + {len(warns)} warning")
    for v in errors:
        print(f"    ERROR {v['type']}: "
              + " <-> ".join(i.get("description", "?") for i in v["items"]))
    for v in warns:
        print(f"    warn  {v['type']}: "
              + " <-> ".join(i.get("description", "?") for i in v["items"]))
    print(f"  unconnected  : {len(doc['unconnected_items'])} records on an UNROUTED board")
    print(f"  ratnest proof: sum(pads-1) over the {rat['multi_pad_nets']} non-GND multi-pad "
          f"nets = {rat['ratnest_expected']}")
    same = len(doc["unconnected_items"]) == rat["ratnest_expected"]
    print(f"  => unconnected == ratnest : {same} "
          f"({'every open is an unrouted connection, none is lost connectivity' if same else 'MISMATCH -- investigate'})")
    if rat["single_pad_nets"]:
        print(f"  single-pad nets (off-board / deliberately open): {rat['single_pad_nets']}")
    print(f"  placement    : rc={rc_p}   density: rc={rc_d}   silk: rc={silk_rc}")

    ok = (not errors) and silk_rc == 0 and rc_p == 0 and rc_d == 0 and same
    print()
    print(f"BUILD: {'CLEAN (unrouted, 0 electrical errors)' if ok else 'GATE FAILED'}")
    if not ok:
        print(f"  errors={len(errors)} silk_rc={silk_rc} placement_rc={rc_p} "
              f"density_rc={rc_d} ratnest_match={same}")

    if a.json:
        json.dump({"board": out, "outline": a.outline,
                   "violations_total": len(doc["violations"]),
                   "errors": len(errors), "warnings": len(warns),
                   "unconnected": len(doc["unconnected_items"]), **rat,
                   "silk_rc": silk_rc, "placement_rc": rc_p, "density_rc": rc_d,
                   "ok": ok}, open(a.json, "w"), indent=1)
        print(f"report       : {a.json}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
