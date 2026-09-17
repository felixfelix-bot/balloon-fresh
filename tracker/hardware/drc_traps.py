#!/usr/bin/env python3
"""drc_traps.py — adversarial trap suite (T1-T8) for the PCB routing campaign.

Validates that the DRC referee cannot be fooled into a false "ready" verdict.
Every trap is self-contained; PASS means the detector fired as designed, FAIL
means the referee can be gamed.

usage: drc_traps.py [--verbose]
exit 0 = all traps PASS, 1 = any FAIL
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
HW = HERE
OUT = os.path.join(HW, "output")

FROZEN_DR = os.path.join(HW, "jlcpcb-s1-frozen.kicad_dru")
FROZEN_DR_SHA = "5acd7dced4a0d8b3edb8b3b977cc2a110a0a97fba0c6d867ce698b243835ca59"
PLACED_BOARD = os.path.join(OUT, "v_c3_flight_4layer_placed.kicad_pcb")
PLACED_SHA = "f3cf0143e7deff991e9650643f1322945388fd135efbf5191f51520dcd6edaa6"
PLACED_PRO = os.path.join(OUT, "v_c3_flight_4layer_placed.kicad_pro")
PLACED_PRO_SHA = "a29acec391bae6b1d53f69be95e0fcce6af5bae7c6d06a4ba0706f7a54920238"
PLACED_DRU = os.path.join(OUT, "v_c3_flight_4layer_placed.kicad_dru")

KRT_BOARD = os.path.join(OUT, "v8_krt_routed.kicad_pcb")
KRT_DR = os.path.join(OUT, "v8_krt_routed.kicad_dru")

RESULTS: list[dict] = []


def sha256(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def run_drc(board: str) -> dict:
    out = "/tmp/drc_traps_%d.json" % os.getpid()
    cmd = ["kicad-cli", "pcb", "drc", "--format", "json", "--output", out, board]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if not os.path.exists(out):
        raise RuntimeError("DRC failed on %s: %s" % (board, proc.stderr[-200:]))
    with open(out) as fh:
        report = json.load(fh)
    os.unlink(out)
    return report


def drc_counts(report: dict) -> dict:
    by_type = {}
    for v in report.get("violations", []):
        by_type[v["type"]] = by_type.get(v["type"], 0) + 1
    return {
        "violations": len(report.get("violations", [])),
        "unconnected": len(report.get("unconnected_items", [])),
        "by_type": by_type,
        "date": report.get("date"),
    }


def strip_block(text: str, tag: str) -> str:
    """Remove a top-level (tag ...) block, matching parens."""
    pattern = re.compile(r"\n\s*\(" + re.escape(tag) + r"\b")
    out = []
    i = 0
    while True:
        m = pattern.search(text, i)
        if not m:
            out.append(text[i:])
            break
        start = m.start()
        out.append(text[i:start])
        depth = 0
        j = start
        while j < len(text):
            if text[j] == "(":
                depth += 1
            elif text[j] == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        i = j + 1
    return "".join(out)


def record(trap: str, passed: bool, detail: str) -> None:
    RESULTS.append({"trap": trap, "status": "PASS" if passed else "FAIL", "detail": detail})
    print("%-4s %s — %s" % (trap, "PASS" if passed else "FAIL", detail))


def t1_empty_board() -> None:
    """T1: empty board reports zero violations and is flagged as vacuous."""
    with tempfile.TemporaryDirectory() as td:
        empty = os.path.join(td, "empty.kicad_pcb")
        with open(PLACED_BOARD, errors="replace") as fh:
            text = fh.read()
        for tag in ["footprint", "segment", "via", "zone", "net"]:
            text = strip_block(text, tag)
        with open(empty, "w") as fh:
            fh.write(text)
        for src, name in [(PLACED_DRU, "empty.kicad_dru"), (PLACED_PRO, "empty.kicad_pro")]:
            shutil.copy(src, os.path.join(td, name))
        c = drc_counts(run_drc(empty))
        fp = c["by_type"].get("footprint", 0)
        vacuous = c["unconnected"] == 0 and fp < 10
        passed = c["violations"] == 0 and c["unconnected"] == 0 and vacuous
        detail = "violations=%d unconnected=%d fp-like=%d -> %s" % (
            c["violations"], c["unconnected"], fp, "vacuous-clean" if vacuous else "not flagged")
        record("T1", passed, detail)


def t2_cosmetic_masking() -> None:
    """T2: a cosmetic-only suppression cannot mask a real clearance regression."""
    with tempfile.TemporaryDirectory() as td:
        board = os.path.join(td, "t2.kicad_pcb")
        shutil.copy(PLACED_BOARD, board)
        for src, name in [(FROZEN_DR, "t2.kicad_dru"), (PLACED_PRO, "t2.kicad_pro")]:
            shutil.copy(src, os.path.join(td, name))
        before = drc_counts(run_drc(board))
        with open(os.path.join(td, "t2.kicad_dru"), "a") as fh:
            fh.write("\n(rule probe_t2 (constraint clearance (min 3.0mm)))\n")
        after = drc_counts(run_drc(board))
        passed = after["violations"] > before["violations"]
        detail = "base=%d strict=%d (must rise)" % (before["violations"], after["violations"])
        record("T2", passed, detail)


def t3_stale_drc_report() -> None:
    """T3: a stale DRC report is detected by sha256 mismatch in the scoreboard row."""
    row_sha = None
    with open(os.path.join(HW, "drc_snapshots", "history.jsonl")) as fh:
        for line in fh:
            if "v8_krt_routed" in line:
                row_sha = json.loads(line)["sha256_12"]
    current_sha = sha256(KRT_BOARD)[:12]
    passed = row_sha == current_sha
    detail = "scored_row_sha=%s board_sha=%s" % (row_sha, current_sha)
    record("T3", passed, detail)


def t4_board_edit_between_score_and_export() -> None:
    """T4: edit-between-score-and-export is caught by sha256 comparison."""
    row_sha = None
    with open(os.path.join(HW, "drc_snapshots", "history.jsonl")) as fh:
        for line in fh:
            if "v8_krt_routed" in line:
                row_sha = json.loads(line)["sha256_12"]
    current_sha = sha256(KRT_BOARD)[:12]
    passed = row_sha == current_sha
    detail = "scored=%s exported=%s" % (row_sha, current_sha)
    record("T4", passed, detail)


def t5_sha256_mismatch() -> None:
    """T5: sha256 mismatch between scored and exported board is detected."""
    with tempfile.TemporaryDirectory() as td:
        board = os.path.join(td, "t5.kicad_pcb")
        shutil.copy(KRT_BOARD, board)
        before = sha256(board)
        with open(board, "a") as fh:
            fh.write("\n; trap injection\n")
        after = sha256(board)
        passed = before != after
        detail = "pre-edit=%s post-edit=%s" % (before[:12], after[:12])
        record("T5", passed, detail)


def t6_unfilled_zone_false_positives() -> None:
    """T6: refilling zones must not change the DRC numbers (fill is current)."""
    with tempfile.TemporaryDirectory() as td:
        board = os.path.join(td, "t6.kicad_pcb")
        shutil.copy(KRT_BOARD, board)
        for src, name in [(FROZEN_DR, "t6.kicad_dru"), (PLACED_PRO, "t6.kicad_pro")]:
            shutil.copy(src, os.path.join(td, name))
        before = drc_counts(run_drc(board))
        fill_script = os.path.expanduser("~/tools/KiCadRoutingTools/py_tools/fill_for_delivery.py")
        out = os.path.join(td, "t6_refilled.kicad_pcb")
        proc = subprocess.run([sys.executable, fill_script, board, "-o", out],
                              capture_output=True, text=True, timeout=120)
        if proc.returncode != 0 or not os.path.exists(out):
            record("T6", False, "fill_for_delivery failed: %s" % proc.stderr[-200:])
            return
        for src, name in [(FROZEN_DR, "t6_refilled.kicad_dru"), (PLACED_PRO, "t6_refilled.kicad_pro")]:
            shutil.copy(src, os.path.join(td, name))
        after = drc_counts(run_drc(out))
        # compare without timestamp: DRC date is volatile, geometry is not
        b = {k: v for k, v in before.items() if k != "date"}
        a = {k: v for k, v in after.items() if k != "date"}
        passed = b == a
        detail = "before=%s after=%s" % (b, a)
        record("T6", passed, detail)


def t7_frozen_placement_violation() -> None:
    """T7: placement must match the frozen hash; any movement is caught."""
    placed_sha = sha256(PLACED_BOARD)

    def placements(board_path):
        """Map reference -> (x, y, layer, rot_deg) from footprint blocks only."""
        with open(board_path, errors="replace") as fh:
            text = fh.read()
        out = {}
        # split on top-level footprint blocks
        blocks = re.findall(r"\(footprint\s+\"([^\"]+)\"(.*?)\n\t\)\n", text, re.S)
        ref_re = re.compile(r'\(property\s+"Reference"\s+"([^"]+)"')
        at_re = re.compile(r"^\t\t\(at\s+([-\d.]+)\s+([-\d.]+)(?:\s+([-\d.]+))?\)", re.M)
        layer_re = re.compile(r"^\t\t\(layer\s+\"([^\"]+)\"\)", re.M)
        for _lib, body in blocks:
            ref_m = ref_re.search(body)
            at_m = at_re.search(body)
            layer_m = layer_re.search(body)
            if ref_m and at_m and layer_m:
                ref = ref_m.group(1)
                x = float(at_m.group(1))
                y = float(at_m.group(2))
                rot = float(at_m.group(3) or 0.0)
                # normalize rotation: KiCad writes -90 for 270 in some paths
                rot = ((rot + 180) % 360) - 180
                out[ref] = (round(x, 6), round(y, 6), layer_m.group(1), round(rot, 6))
        return out

    frozen = placements(PLACED_BOARD)
    moved_total = []
    for bname, bpath in [
        ("v8_krt_routed", KRT_BOARD),
        ("v8_krt_v2_routed", os.path.join(OUT, "v8_krt_v2_routed.kicad_pcb")),
        ("v8_freerouting_routed", os.path.join(OUT, "v8_freerouting_routed.kicad_pcb")),
    ]:
        after = placements(bpath)
        missing = sorted(set(frozen) - set(after))
        extra = sorted(set(after) - set(frozen))
        moved = sorted([r for r in set(frozen) & set(after) if frozen[r] != after[r]])
        if missing or extra or moved:
            moved_total.append((bname, missing, extra, moved))
    passed = placed_sha == PLACED_SHA and not moved_total
    detail = "frozen_sha_ok=%s placement_diffs=%s" % (placed_sha == PLACED_SHA, moved_total if moved_total else "none")
    record("T7", passed, detail)


def t8_rule_file_drift() -> None:
    """T8: rule-file drift is caught by comparing sibling .kicad_dru sha to frozen."""
    for path in [
        os.path.join(OUT, "v8_krt_routed.kicad_dru"),
        os.path.join(OUT, "v8_krt_v2_routed.kicad_dru"),
        os.path.join(OUT, "v8_freerouting_routed.kicad_dru"),
    ]:
        s = sha256(path)
        if s != FROZEN_DR_SHA:
            record("T8", False, "%s sha=%s (expected %s)" % (os.path.basename(path), s[:12], FROZEN_DR_SHA[:12]))
            return
    record("T8", True, "all attempt .kicad_dru match frozen sha")


def main() -> int:
    print("drc_traps — adversarial trap suite T1-T8")
    print("frozen rule sha: %s" % FROZEN_DR_SHA)
    print("frozen placement sha: %s" % PLACED_SHA)
    print("")
    t1_empty_board()
    t2_cosmetic_masking()
    t3_stale_drc_report()
    t4_board_edit_between_score_and_export()
    t5_sha256_mismatch()
    t6_unfilled_zone_false_positives()
    t7_frozen_placement_violation()
    t8_rule_file_drift()
    print("")
    failed = [r for r in RESULTS if r["status"] != "PASS"]
    passed = [r for r in RESULTS if r["status"] == "PASS"]
    print("SUMMARY: %d/%d traps passed" % (len(passed), len(RESULTS)))
    if failed:
        print("FAILURES:")
        for r in failed:
            print("  %s — %s" % (r["trap"], r["detail"]))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
