#!/usr/bin/env python3
"""Route the v9 hub with FreeRouting, deterministically and reproducibly.

WHY THIS SCRIPT EXISTS
----------------------
The hub board (`tracker/hardware/hub_board_v9.kicad_pcb`) is plane-only: 39
footprints, 4 layers, 0 tracks, 0 vias, **101 unconnected items** measured with
`kicad-cli pcb drc` on 2026-10-11. Nothing else in the program can ship until it
routes, and routing it by hand is not reproducible.

The repo already contains a FreeRouting pipeline (`tracker/hardware/
freerouting_pipeline.py`), but it starts from `pcbnew.NewBoard()` and rebuilds a
board from scratch -- unusable here, because the v9 hub's placement is a FROZEN,
reviewed artefact (`PLACEMENT-S0-FREEZE-v9-hub.md`). Re-placing parts to route
them would invalidate the placement review, which is exactly the mistake
`--add-planes` and `--attach-models` were written to avoid. This script routes the
frozen board IN PLACE.

DETERMINISM / REPRODUCIBILITY
-----------------------------
FreeRouting is seeded per-run; `-mp <passes>` bounds the work. Two runs at the
same `-mp` on the same KiCad build produce the same geometry, which is what makes
the result reviewable. The DSN and SES are kept as build artefacts so the routed
board can be regenerated rather than trusted.

PIPELINE
--------
    hub_board_v9.kicad_pcb
      -> pcbnew.ExportSpecctraDSN        (this script, step 1)
      -> FreeRouting -de X.dsn -do Y.ses (step 2, external JVM)
      -> pcbnew.ImportSpecctraSES        (this script, step 3)
      -> kicad-cli pcb drc               (step 4, verify)

PITFALLS (each measured the hard way)
-------------------------------------
* FreeRouting v2.2.4 is compiled for Java 25 (class file 69). The system default
  `java` is 17 and fails with `UnsupportedClassVersionError`. Use
  `/usr/lib/jvm/java-25-openjdk-amd64/bin/java`.
* FreeRouting is a Swing app: without an X server it dies with "Couldn't get
  screen resolution". `xvfb-run -a` is required.
* `java -jar freerouting.jar --help` reports "Unknown command line argument",
  not usage. Use `-de` (design in), `-do` (design out), `-mp` (MAX PASSES),
  `-mt` (threads), `-oit` (exit-after-routing), `-us`/`-is` (units).
* `-mp` bounds PASSES, not wall-clock. Without `-oit` FreeRouting finishes its
  passes and then SITS ON THE GUI waiting for a human to export -- the SES is
  only written on a clean exit, so a run that exhausts its pass budget without
  `-oit` produces NO SES (measured 2026-10-12: 21+ min hung, no output) and a
  hard kill (SIGTERM, exit -15) is likewise session-fatal. We always pass
  `-oit` and still enforce a generous subprocess timeout so a wedged JVM can
  never hang the pipeline.
* The router exits 0 even when it finishes with unrouted nets. The ONLY verdict
  that counts is the DRC unconnected count afterwards; never read the JVM exit
  code as success.
* Never route with `pcbnew` under anything but `/usr/bin/python3.14` (3.11
  segfaults the interpreter).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

JAVA_HOME = "/usr/lib/jvm/java-25-openjdk-amd64"
FREEROUTING_JAR = "/home/c03rad0r/flight-board-worktree/tracker/hardware/flight-pcba/freerouting.jar"
DEFAULT_PASSES = 40
DEFAULT_THREADS = 3

DESIGN_RULES = {
    # Mirrors tracker/hardware/freerouting_pipeline.py::set_board_design_rules so
    # FreeRouting and the DRC check use ONE rule set. Values are mm.
    "m_MinClearance": 0.15,
    "m_TrackMinWidth": 0.15,
    "m_SolderMaskToCopperClearance": 0.05,
    "m_SolderMaskMinWidth": 0.05,
    "m_HoleClearance": 0.25,
    "m_CopperEdgeClearance": 0.50,
    "m_MinThroughDrill": 0.30,
}


def _pcbnew():
    sys.path.insert(0, "/usr/lib/python3/dist-packages")
    import pcbnew  # noqa: PLC0415
    return pcbnew


def patch_dsn_rules(dsn_path: str, width_um: int = 200, clearance_um: int = 200) -> None:
    """Rewrite the DSN's global and per-class routing rules to the BOARD's values.

    DSN UNIT SCALE -- the 2026-10-12 calibration, measured against the .kicad_pcb:
    --------------------------------------------------------------------------------------------
    `(resolution um 10)` scales ONLY coordinates (1 unit = 0.1 um). The RULE
    scalars -- (width N) and (clearance N) -- are RAW MICRONS and do NOT follow
    the resolution line. Proven by footprint calibration: C_CAP1 sits at x=8.7925
    mm in the .kicad_pcb and 8792.502 DSN units (0.1 um/unit) in placement, while
    the rule block carries `(clearance 200)` alongside a 0.2 mm KiCad netclass
    (kicad-cli DRC: "clearance 0.2000 mm"). So the exporter's 200 = 0.2 mm =
    exactly the board's own rule. KiCad's DSN was RIGHT all along.

    The 2026-10-12 routing history, all measured:
    ---------------------------------------------------------------
    run 1: exporter default (width 200 / clearance 200 = 0.2 mm)
           -> routed 97 -> 16 unrouted in 12 passes, 20 minutes.
           The 753 DRC violations afterwards were NOT track-through-pad: they
           were 501 "Track/Via vs Zone GND_PLANE" + 202 hole_clearance against
           the board's STORED PRE-ROUTE ZONE FILL. After ZONE_FILLER refill the
           same board shows 55 violations total (1 real clearance at 0.1992 mm,
           38 copper_edge, 12 pre-existing castellated drill, 4 starved thermal).
    runs 2-4: patch_dsn_rules scaled rules by 10000 (x500 of reality) because it
           read `(resolution um 10)` as applying to rules -> demanded 2.0/2.5 mm
           clearance. All three stalled identically at pass 2 (96/95 unrouted,
           134/121 violations): at 10x the board's clearance, the board's own
           geometry (castellated wing tabs, stitching vias, plane pullbacks)
           becomes a wall of permanent violations the router is told to preserve
           but can never satisfy.

    WHY THIS FUNCTION STILL EXISTS
    -------------------------------
    KiCad v9's exporter writes the rule block from the netclass, and this board
    defines no netclasses -- so the fallback pair is the ONLY thing standing
    between us and a repeat of the run-1 "route at 0.02 mm" myth (which was
    itself the unit misread above; 200 raw um = 0.2 mm, NOT 0.02). This function
    now takes raw um directly, asserts the exporter's block is exactly the
    expected (width 200)(clearance 200) pair, and rewrites it to the same values
    in EXPLICIT form -- a no-op rewrite that fails loudly if the exporter ever
    changes format, keeping the pipeline honest. The smd_smd exemption must
    survive (castellated wing pads touch by design; dropping it stalled run 2).
    """
    with open(dsn_path) as fh:
        content = fh.read()

    w, c = int(width_um), int(clearance_um)

    n_global = 0
    for old in (
        "(rule\n      (width 200)\n      (clearance 200)\n      (clearance 50 (type smd_smd))\n    )",
        "(rule\n      (width 200)\n      (clearance 200)\n    )",
    ):
        if old in content:
            content = content.replace(old, f"(rule\n      (width {w})\n      (clearance {c})\n      (clearance 50 (type smd_smd))\n    )")
            n_global += 1
    # Per-class rule inside the `(class ...)` block.
    old_class = "(rule\n        (width 200)\n        (clearance 200)\n      )"
    n_class = content.count(old_class)
    content = content.replace(old_class, f"(rule\n        (width {w})\n        (clearance {c})\n      )")

    if n_global == 0 and n_class == 0:
        raise SystemExit(
            f"patch_dsn_rules found no 0.2 mm rule block in {dsn_path} -- the exporter "
            "format changed, so the clearance is NOT patched. Refusing to route at an "
            "unknown clearance; re-derive the rule text from the DSN."
        )

    # WING-SOCKET PAD-HALF MERGE -- the poison pins, measured 2026-10-12:
    # FreeRouting run 5 on the stitched board made ZERO progress (started 18
    # unrouted, ended 18, board hash unchanged) because the DSN lists every
    # wing-socket pad TWICE: J_W1-4 and J_W1-4@1 -- F.Cu half and B.Cu half,
    # same net, same XY, different faces. No legal copper route can ever join
    # them: the inserted wing TAB bridges F and B mechanically (ADR-046
    # edge-card socket). The router burns its passes on 16 such pairs.
    # Fix: drop each pad's @N back-half when its front-half is on the same
    # pins line, restricted to the edge-card socket / castellated families
    # (J_W*, ANT*, CUT_SENSE*) whose @1 twin is the SAME land on the other
    # copper face -- same XY, joined mechanically by the inserted tab (not
    # joinable by copper). U1-41@1..12 etc are 12 REAL pads at different XY
    # and must keep their @N suffixes.
    EDGE_FAMILIES = ("J_W", "ANT", "CUT_SENSE")
    merged = 0

    def _merge_pins_span(m):
        nonlocal merged
        inner = m.group(1)
        tokens = inner.split()
        if not tokens or not any("@1" in t for t in tokens):
            return m.group(0)
        bases = {re.sub(r"@\d+$", "", t) for t in tokens}
        keep, dropped = [], 0
        for tok in tokens:
            tm = re.match(r"^(.*)@\d+$", tok)
            if tm:
                base = tm.group(1)
                if any(base.startswith(f) for f in EDGE_FAMILIES) and base in bases:
                    dropped += 1
                    continue
            keep.append(tok)
        if not dropped:
            return m.group(0)
        merged += dropped
        # tokens contain no parens, so no escaping concerns; whitespace shape
        # is irrelevant to DSN parsers -- keep it single-line if it came single
        sep = "\n " if "\n" in inner else " "
        return "(pins " + sep.join(keep) + ")"

    # block-aware: spans the WHOLE (pins ...) s-expr, incl. multi-line GND net
    # blocks where @N halves sit on continuation lines with no '(pins' marker
    content = re.sub(r"\(pins([^()]*?)\)", _merge_pins_span, content, flags=re.S)

    with open(dsn_path, "w") as fh:
        fh.write(content)
    print(f"  DSN rules asserted: width {w} um, clearance {c} um "
          f"({n_global} global, {n_class} class block(s)); "
          f"wing pad-halves merged: {merged}")


def export_dsn(board_path: str, dsn_path: str, *,
               width_um: int = 200, clearance_um: int = 200) -> None:
    pcbnew = _pcbnew()
    board = pcbnew.LoadBoard(board_path)
    drc = board.GetDesignSettings()
    for attr, mm in DESIGN_RULES.items():
        setattr(drc, attr, pcbnew.FromMM(mm))
    ok = pcbnew.ExportSpecctraDSN(board, dsn_path)
    if not ok:
        raise SystemExit(f"ExportSpecctraDSN refused to write {dsn_path}")
    # The design settings above do NOT survive into the DSN's rule block -- see
    # patch_dsn_rules() for the measurement that proves it. Patch the file.
    patch_dsn_rules(dsn_path, width_um=width_um, clearance_um=clearance_um)
    print(f"  DSN written: {dsn_path} ({os.path.getsize(dsn_path)} bytes)")


def run_freerouting(dsn_path: str, ses_path: str, passes: int, threads: int,
                    timeout_s: int = 1800) -> None:
    java = os.path.join(JAVA_HOME, "bin", "java")
    if not os.path.exists(java):
        raise SystemExit(f"Java 25 not found at {java}; FreeRouting v2.2.4 needs class file 69")
    if not os.path.exists(FREEROUTING_JAR):
        raise SystemExit(f"FreeRouting jar not found at {FREEROUTING_JAR}")
    # -oit (exit after routing): without it the JVM finishes its passes and then
    # waits on the Swing GUI for a human to export -- the SES is only written on
    # a clean exit, so a pass-budget-only run yields NO SES (measured 2026-10-12).
    cmd = ["xvfb-run", "-a", java, "-jar", FREEROUTING_JAR,
           "-de", dsn_path, "-do", ses_path, "-oit",
           "-mp", str(passes), "-mt", str(threads)]
    print(f"  routing: -mp {passes} -mt {threads} -oit (timeout {timeout_s}s; bounded, no LLM)")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        raise SystemExit(
            f"FreeRouting exceeded {timeout_s}s without exiting -- it may have "
            f"wedged. No SES is expected; raise -mp or lower the board scope."
        )
    for line in proc.stdout.splitlines():
        if "Auto-router pass" in line or "ERROR" in line or "unrouted" in line:
            print("   ", line.split("INFO")[-1].strip() or line.strip())
    if not os.path.exists(ses_path):
        raise SystemExit(
            f"FreeRouting produced no SES file. Note its exit code was {proc.returncode}, "
            f"which is NOT a success signal -- see the module docstring."
        )
    print(f"  SES written: {ses_path} ({os.path.getsize(ses_path)} bytes)")


def import_ses(board_path: str, ses_path: str, out_path: str, tol_nm: int = 1000) -> None:
    """Import the routed SES into the FROZEN board, asserting placement held.

    The placement assertion is a TOLERANCE, not an equality. Measured 2026-10-12:
    two 3.3 F supercaps sit at 2.0792502 mm, a position that is not a whole number
    of the DSN's 0.1 um grid. `ImportSpecctraSES` quantises that to KiCad's internal
    nanometre grid, so an exact tuple comparison reports a "move" of <1 nm. The SES
    itself is innocent: DSN `(place C_CAP2 20792.502 -30292.502)` at `um 10` and SES
    `(place "C_CAP2" 207925 -302925)` at `um 100` are the SAME coordinate. Anything
    at mm scale is a real move and must fail loudly, so the check reports the
    measured deviation rather than a bare boolean.
    """
    pcbnew = _pcbnew()
    board = pcbnew.LoadBoard(board_path)
    before = {fp.GetReference(): (fp.GetPosition(), fp.GetLayer(), fp.GetOrientation().AsDegrees())
              for fp in board.GetFootprints()}
    ok = pcbnew.ImportSpecctraSES(board, ses_path)
    if not ok:
        raise SystemExit(f"ImportSpecctraSES refused {ses_path}")

    worst = 0
    moved = []
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        if ref not in before:
            continue
        (p0, l0, o0) = before[ref]
        p1 = fp.GetPosition()
        d = max(abs(p1.x - p0.x), abs(p1.y - p0.y))
        worst = max(worst, d)
        if d > tol_nm or fp.GetLayer() != l0 or abs(fp.GetOrientation().AsDegrees() - o0) > 0.01:
            moved.append((ref, d, l0, fp.GetLayer()))
    if moved:
        raise SystemExit(
            f"import MOVED {len(moved)} footprint(s) beyond {tol_nm} nm: {moved[:8]} -- refusing "
            "to save. Routing must never move a part; the placement is frozen."
        )
    pcbnew.SaveBoard(out_path, board)
    print(f"  saved: {out_path}")
    print(f"  footprints {len(before)} (0 moved; worst deviation {worst} nm, tolerance {tol_nm} nm)")
    print(f"  tracks/vias {len(board.GetTracks())}")


def drc(board_path: str) -> dict:
    out = "/tmp/drc_routed.json"
    subprocess.run(["kicad-cli", "pcb", "drc", "--severity-error", "--format", "json",
                    "-o", out, board_path], capture_output=True, text=True)
    with open(out) as fh:
        d = json.load(fh)
    return {"violations": len(d.get("violations", [])),
            "unconnected": len(d.get("unconnected_items", []))}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("board", help="the frozen hub .kicad_pcb to route")
    ap.add_argument("--out", help="routed board path (default: BOARD with _routed suffix)")
    ap.add_argument("--workdir", default="/tmp", help="where DSN/SES artefacts go")
    ap.add_argument("--passes", type=int, default=DEFAULT_PASSES)
    ap.add_argument("--threads", type=int, default=DEFAULT_THREADS)
    ap.add_argument("--skip-route", action="store_true",
                    help="reuse an existing SES (for re-importing a finished run)")
    args = ap.parse_args(argv)

    out = args.out or args.board.replace(".kicad_pcb", "_routed.kicad_pcb")
    stem = os.path.join(args.workdir, os.path.basename(args.board).replace(".kicad_pcb", ""))
    dsn, ses = stem + ".dsn", stem + "_routed.ses"

    print("[1/4] export Specctra DSN from the frozen board")
    if args.skip_route and os.path.exists(ses):
        # Re-exporting here would OVERWRITE the DSN that produced the SES with one
        # carrying the explicit rules below, silently breaking the pairing. A SES
        # may only ever be imported alongside the DSN it was routed from.
        print(f"  keeping the existing {dsn} (must be the one {ses} was routed from)")
    else:
        export_dsn(args.board, dsn)
    print("[2/4] FreeRouting (external, deterministic, no LLM)")
    if args.skip_route and os.path.exists(ses):
        print(f"  reusing {ses}")
    else:
        run_freerouting(dsn, ses, args.passes, args.threads)
    print("[3/4] import SES into the frozen board (placement asserted unchanged)")
    import_ses(args.board, ses, out)
    print("[4/4] DRC on the routed board")
    d = drc(out)
    print(f"  violations {d['violations']}  unconnected {d['unconnected']}")
    return 0 if d["unconnected"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
