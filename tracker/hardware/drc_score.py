#!/usr/bin/env python3
"""DRC scorecard — measurable progress for PCB routing attempts.

WHY THIS EXISTS
---------------
"Did the last routing attempt make the board better?" was answered by hand from
100 KB DRC text dumps (see drc_*.txt in this directory). That is not a metric.
This script turns every routing attempt into ONE comparable row so progress and
resource spend can be judged, not argued.

USAGE
-----
    # record a new measurement (runs kicad-cli, appends to history)
    python3 drc_score.py <board.kicad_pcb> --label v7 --cost-usd 0.42 \
        --tool freerouting --note "4-layer, before keepout fix"

    # print the scoreboard from recorded history
    python3 drc_score.py --compare
    python3 drc_score.py --compare --label v7      # one board's history

    # machine-readable
    python3 drc_score.py <board.kicad_pcb> --label v7 --json

METRICS (per attempt)
---------------------
    shorts            shorting_items count — ALWAYS blocking for fab
    clearance         clearance + hole_clearance + copper_edge_clearance
    unconnected       ratsnest items still open
    other             remaining violation types (silk, mask, courtyard, ...)
    violations        total
    fp                footprint count (an EMPTY board reports 0 violations!)
    vias, copper_mm   routing drag: copper length actually laid down
    fab_ready         1 only when shorts=0 AND clearance=0 AND unconnected=0

JUDGING RESOURCE USE (derived in --compare)
-------------------------------------------
    dViol            violations removed vs previous attempt with same label
    usd_per_dViol    cost of this attempt / violations removed  (lower better;
                     "no improvement" attempts still cost — they show as INF)
    vias_per_dViol   copper churn: how much re-routing bought that gain
    regressed        a later attempt with MORE blocking errors than an earlier
                     one — the signal that an iteration loop is thrashing

RULE: an attempt that does not reduce *shorts + unconnected* is not progress,
even if total violations fell (silk/mask noise moves the headline number).
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HISTORY = os.path.join(HERE, "drc_snapshots", "history.jsonl")

# Violation types that BLOCK fabrication at JLCPCB (2-layer 0.15mm defaults).
SHORT_TYPES = {"shorting_items"}
CLEARANCE_TYPES = {"clearance", "hole_clearance", "copper_edge_clearance",
                   "hole_to_hole", "track_dangling_via"}


def run_drc(board: str, timeout: int = 300) -> dict:
    """Run kicad-cli DRC and return the parsed JSON report."""
    out = "/tmp/drc_score_%d.json" % os.getpid()
    cmd = ["kicad-cli", "pcb", "drc", "--format", "json", "--output", out, board]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if not os.path.exists(out):
        sys.exit("DRC failed to produce a report (exit %s):\n%s\n%s"
                 % (proc.returncode, proc.stdout[-2000:], proc.stderr[-2000:]))
    with open(out) as fh:
        report = json.load(fh)
    os.unlink(out)
    return report


def count_copper(board: str) -> tuple[int, int, float]:
    """(vias, segments, total copper length in mm) straight from the S-expr."""
    with open(board, errors="replace") as fh:
        text = fh.read()
    vias = len(re.findall(r"\(via\b", text))
    total = 0.0
    segs = 0
    seg_re = re.compile(
        r"\(segment\s+\(start\s+([-\d.]+)\s+([-\d.]+)\)\s+\(end\s+([-\d.]+)\s+([-\d.]+)\)",
        re.S)
    for x1, y1, x2, y2 in seg_re.findall(text):
        dx = float(x2) - float(x1)
        dy = float(y2) - float(y1)
        total += (dx * dx + dy * dy) ** 0.5
        segs += 1
    return vias, segs, round(total, 1)


def measure(board: str, label: str, tool: str, cost_usd: float, note: str) -> dict:
    report = run_drc(board)
    viol = report.get("violations", []) or []
    unconn = report.get("unconnected_items", []) or []
    parity = report.get("schematic_parity", []) or []

    by_type: dict[str, int] = {}
    for v in viol:
        by_type[v.get("type", "unknown")] = by_type.get(v.get("type", "unknown"), 0) + 1

    shorts = sum(n for t, n in by_type.items() if t in SHORT_TYPES)
    clearance = sum(n for t, n in by_type.items() if t in CLEARANCE_TYPES)
    other = len(viol) - shorts - clearance

    with open(board, "rb") as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()[:12]
    fp = len(re.findall(r"\(footprint\b", open(board, errors="replace").read()))
    vias, segs, copper_mm = count_copper(board)

    row = {
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "label": label,
        "board": os.path.relpath(board, HERE) if board.startswith(HERE) else board,
        "sha256_12": digest,
        "tool": tool,
        "note": note,
        "cost_usd": round(float(cost_usd), 4),
        "fp": fp,
        "violations": len(viol),
        "shorts": shorts,
        "clearance": clearance,
        "other": other,
        "unconnected": len(unconn),
        "parity": len(parity),
        "vias": vias,
        "segments": segs,
        "copper_mm": copper_mm,
        "by_type": dict(sorted(by_type.items(), key=lambda kv: -kv[1])),
        "fab_ready": int(shorts == 0 and clearance == 0 and len(unconn) == 0),
    }
    # An empty board is trivially DRC-clean — never let it score as progress.
    if fp < 10:
        row["fab_ready"] = 0
        row["warning"] = "EMPTY/NEAR-EMPTY BOARD — DRC result not meaningful (fp<%d)" % 10
    return row


def blocking(row: dict) -> int:
    return row["shorts"] + row["clearance"] + row["unconnected"]


def save(row: dict) -> None:
    os.makedirs(os.path.dirname(HISTORY), exist_ok=True)
    with open(HISTORY, "a") as fh:
        fh.write(json.dumps(row) + "\n")


def load(label: str | None = None) -> list[dict]:
    if not os.path.exists(HISTORY):
        return []
    rows = []
    with open(HISTORY) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if label and r.get("label") != label:
                continue
            rows.append(r)
    return rows


def scoreboard(rows: list[dict]) -> str:
    if not rows:
        return "no history yet — record one with: drc_score.py <board> --label <name>"

    out = []
    header = ("ts                 label  tool          fp  viol  short  clr  unconn"
              "  vias  copper_mm   fab  dViol   usd   usd/dViol")
    out.append("PROGRESS SCOREBOARD — every routing attempt, one row")
    out.append(header)
    out.append("-" * len(header))

    prev_by_label: dict[str, dict] = {}
    for r in rows:
        prev = prev_by_label.get(r["label"])
        dv = "-"
        usd_dv = "-"
        if prev is not None:
            dv = "%+d" % (blocking(prev) - blocking(r))
            gained = blocking(prev) - blocking(r)
            if gained > 0 and r.get("cost_usd"):
                usd_dv = "%.2f" % (r["cost_usd"] / gained)
            elif r.get("cost_usd"):
                usd_dv = "INF"
        flag = ""
        if prev is not None and blocking(r) > blocking(prev):
            flag = "  REGRESSED"
        out.append("%-18s %-6s %-13s %3d %5d %6d %4d %7d %5d %9.1f %5d %6s %6.2f %8s%s"
                   % (r["ts"][5:16], r["label"][:6], (r.get("tool") or "-")[:13],
                      r["fp"], r["violations"], r["shorts"], r["clearance"],
                      r["unconnected"], r["vias"], r["copper_mm"],
                      r["fab_ready"], dv, r.get("cost_usd", 0.0), usd_dv, flag))
        prev_by_label[r["label"]] = r

    out.append("")
    best: dict[str, dict] = {}
    for r in rows:
        b = best.get(r["label"])
        if b is None or blocking(r) < blocking(b):
            best[r["label"]] = r
    for label, r in best.items():
        status = "FAB-READY" if r["fab_ready"] else "%d blocking open" % blocking(r)
        out.append("best[%s]: %s  (viol=%d shorts=%d clr=%d unconn=%d)  %s"
                   % (label, r["board"], r["violations"], r["shorts"],
                      r["clearance"], r["unconnected"], status))
    total_cost = sum(r.get("cost_usd", 0.0) for r in rows)
    total_attempts = len(rows)
    out.append("")
    out.append("spend: %d attempts, $%.2f total;  fab-ready labels: %d/%d"
               % (total_attempts, total_cost,
                  sum(1 for r in best.values() if r["fab_ready"]), len(best)))
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("board", nargs="?", help="path to .kicad_pcb")
    ap.add_argument("--label", help="board lineage label, e.g. v7 / f33 (groups history)")
    ap.add_argument("--tool", default="manual",
                    help="what produced this state: manual | freerouting | "
                         "orthoroute | konnect | deeppcb | skidl-script")
    ap.add_argument("--cost-usd", type=float, default=0.0,
                    help="inference/API spend attributed to this attempt")
    ap.add_argument("--note", default="", help="free-text context")
    ap.add_argument("--compare", action="store_true", help="print scoreboard only")
    ap.add_argument("--json", action="store_true", help="print the row as JSON")
    args = ap.parse_args()

    if args.compare or not args.board:
        print(scoreboard(load(args.label)))
        return

    if not os.path.exists(args.board):
        sys.exit("no such board: %s" % args.board)
    if not args.label:
        sys.exit("--label is required when recording (groups this board's history)")

    row = measure(args.board, args.label, args.tool, args.cost_usd, args.note)
    save(row)
    if args.json:
        print(json.dumps(row, indent=2))
    else:
        print(scoreboard(load(args.label)))
        if row.get("warning"):
            print("\nWARNING: %s" % row["warning"])


if __name__ == "__main__":
    main()
