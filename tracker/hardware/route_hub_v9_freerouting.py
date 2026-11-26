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
  not usage. The CLI flags are `-de`, `-do`, `-mp`, `-mt`, `-us`, `-is`.
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


def patch_dsn_rules(dsn_path: str, width_mm: float = 0.20, clearance_mm: float = 0.25) -> None:
    """Rewrite the DSN's global and per-class routing rules to REAL fab values.

    WHY THIS IS NOT OPTIONAL -- measured 2026-10-12.
    -------------------------------------------------
    KiCad's Specctra exporter writes `(width 200)(clearance 200)` at
    `(resolution um 10)`, i.e. a **0.02 mm** clearance, and it does so regardless of
    the `BOARD_DESIGN_SETTINGS` values set in `export_dsn()` -- the DSN carries the
    netclass rule, and this board defines no netclasses, so the exporter falls back
    to that 0.02 mm pair. Routing at 0.02 mm produced a board that is electrically
    connected (101 -> 20 unconnected) but physically illegal:

        clearance         501 new violations   ("actual 0.0000 mm")
        hole_clearance    202 new violations   ("actual 0.0000 mm")

    Tracks pass straight through neighbouring pads. The repo's own
    `tracker/hardware/freerouting_pipeline.py` hits exactly this and answers it with
    a comment -- "use TIGHT clearance for FreeRouting routing (it needs this to find
    paths). We'll fix DRC violations in post-processing" -- which is the expensive
    anti-pattern: it converts a routing problem into a hand-repair problem. This
    function instead states the real rules UP FRONT so the router is asked the
    question we actually want answered.

    WHY THIS IS NOT OPTIONAL -- the 2026-10-12 routing history, all measured:
    ---------------------------------------------------------------
    run 1: exporter default 0.02 mm clearance -> routed 97->16 unrouted but
           produced 753 DRC violations (501 clearance + 202 hole_clearance
           "actual 0.0000 mm" -- tracks threaded straight through pads).
    run 2: 0.25 mm, smd_smd exemption DROPPED -> stalled at pass 2
           (96 unrouted, 134 violations). The castellated wing pads
           (J_W1..J_W4) touch by design; KiCad's exporter writes
           `(clearance 50 (type smd_smd))` to exempt them. Dropping it
           made 134 unfixable violations and the router gave up.
    run 3: 0.25 mm WITH the exemption kept -> SAME stall (score 251.43,
           96 unrouted, 134 violations). Conclusion: at 0.25 mm the
           board's EXISTING geometry -- GND stitching vias, plane pullbacks,
           RF stubs, all laid out to the board's own 0.2 mm netclass
           clearance (KiCad DRC reports "clearance 0.2000 mm") -- becomes
           134 permanent violations the router is told to preserve but
           can never satisfy. The router is boxed in by the board itself.

    The fix: demand EXACTLY the board's own clearance, 0.2 mm. The
    existing geometry satisfies it by construction, so the router starts
    from a legal board and only has to solve connectivity.

    `(resolution um 10)`: 1 DSN unit = 0.1 um, so 1 mm = 10000 units.
    """
    with open(dsn_path) as fh:
        content = fh.read()

    w = int(round(width_mm * 10000))
    c = int(round(clearance_mm * 10000))

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
            f"patch_dsn_rules found no 0.02 mm rule block in {dsn_path} -- the exporter "
            "format changed, so the clearance is NOT patched. Refusing to route at an "
            "unknown clearance; re-derive the rule text from the DSN."
        )
    with open(dsn_path, "w") as fh:
        fh.write(content)
    print(f"  DSN rules patched: width {width_mm} mm, clearance {clearance_mm} mm "
          f"({n_global} global, {n_class} class block(s))")


def export_dsn(board_path: str, dsn_path: str, *,
               width_mm: float = 0.20, clearance_mm: float = 0.20) -> None:
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
    patch_dsn_rules(dsn_path, width_mm=width_mm, clearance_mm=clearance_mm)
    print(f"  DSN written: {dsn_path} ({os.path.getsize(dsn_path)} bytes)")


def run_freerouting(dsn_path: str, ses_path: str, passes: int, threads: int) -> None:
    java = os.path.join(JAVA_HOME, "bin", "java")
    if not os.path.exists(java):
        raise SystemExit(f"Java 25 not found at {java}; FreeRouting v2.2.4 needs class file 69")
    if not os.path.exists(FREEROUTING_JAR):
        raise SystemExit(f"FreeRouting jar not found at {FREEROUTING_JAR}")
    cmd = ["xvfb-run", "-a", java, "-jar", FREEROUTING_JAR,
           "-de", dsn_path, "-do", ses_path, "-mp", str(passes), "-mt", str(threads)]
    print(f"  routing: -mp {passes} -mt {threads} (this takes minutes; bounded, no LLM)")
    proc = subprocess.run(cmd, capture_output=True, text=True)
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
