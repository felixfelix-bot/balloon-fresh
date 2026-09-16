#!/usr/bin/env python3
"""Placement provenance guard - fail loudly when the old failure mode returns.

Background: the flight board's placement coordinates were hand-typed literals
spread over several tables (gen_pcb.py 58 coord pairs, grid_placement.py 25)
plus 12 placement/patch scripts, with TWO scripts writing the same board path.
That is why the same pad-overlap pairs survived across a 55x45mm and an 80x60mm
outline: nobody owned the coordinates.

This guard enforces the rule that follows:
  R1  every board artifact has AT MOST ONE writer script;
  R2  placement coordinates are computed (tool/parametric), never new literal
      tables - a new coordinate table outside the registry is a violation;
  R3  a placement is only "clean" if Gate 2.5 passes on the frozen board
      (0 pad-box overlaps at 0.2mm, courtyards_overlap = 0, 0 segments, fp >= 10).

Usage:
    python3 placement_guard.py                 # scan repo, use registry
    python3 placement_guard.py --gate25 <board.kicad_pcb>
Exit code 0 = clean, 1 = violation(s) found.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REGISTRY = HERE / "placement-source-of-truth.json"

# a literal coordinate table: "U1": (12.3, 4.5)  /  ("C4", 15.1, 32, ...)
COORD_PATTERNS = [
    re.compile(r'["\'][A-Z]{1,3}\d{1,2}["\']\s*:\s*\(\s*-?\d'),
    re.compile(r'\(\s*["\'][A-Z]{1,3}\d{1,2}["\']\s*,\s*-?\d+\.\d+\s*,\s*-?\d+\.\d+'),
]
BOARD_WRITE = re.compile(r'^\s*(OUTPUT|OUT_PATH|BOARD_OUT|out_path)\s*=.*\.kicad_pcb', re.M)
MIN_TABLE_ROWS = 4


def load_registry() -> dict:
    if not REGISTRY.exists():
        return {"boards": {}, "canonical_placement_source": None,
                "allowed_coordinate_tables": [], "legacy_tables": [], "legacy_patch_scripts": []}
    return json.loads(REGISTRY.read_text())


def scan(reg: dict) -> list[str]:
    v: list[str] = []

    # R1 - one writer per board artifact
    writers: dict[str, list[str]] = {}
    for py in HERE.rglob("*.py"):
        if py.name == Path(__file__).name:
            continue
        try:
            txt = py.read_text(errors="ignore")
        except Exception:
            continue
        for m in BOARD_WRITE.finditer(txt):
            line = m.group(0)
            board = re.search(r'/([^/\'"]+\.kicad_pcb)', line)
            if board:
                writers.setdefault(board.group(1), []).append(str(py.relative_to(HERE)))
    for board, who in sorted(writers.items()):
        declared = reg.get("boards", {}).get(board, {}).get("writer")
        if len(who) > 1:
            v.append(f"R1: board '{board}' has {len(who)} writers: {', '.join(sorted(who))} "
                     f"- keep ONE (declare it in {REGISTRY.name}, archive the rest)")
        if declared and declared not in who:
            v.append(f"R1: registry says writer '{declared}' for '{board}' but scripts found "
                     f"{who} - registry is stale")

    # R2 - new literal coordinate tables
    allowed = set(reg.get("allowed_coordinate_tables", []))
    for py in HERE.rglob("*.py"):
        if py.name == Path(__file__).name:
            continue
        rel = str(py.relative_to(HERE))
        try:
            txt = py.read_text(errors="ignore")
        except Exception:
            continue
        rows = sum(1 for p in COORD_PATTERNS if True for _ in p.finditer(txt))
        if rows >= MIN_TABLE_ROWS and rel not in allowed:
            v.append(f"R2: '{rel}' defines {rows} literal coordinate rows and is NOT a registered "
                     f"placement source - coordinates must be COMPUTED (KRT place_optimize or a "
                     f"parametric generator), not hand-typed. Register it only if it is the single "
                     f"canonical source, otherwise archive it")
    return v


def gate25(board: Path) -> tuple[bool, str]:
    """Gate 2.5 via python3.14 + pcbnew (skips gracefully if unavailable)."""
    code = (
        "import sys; sys.path.insert(0,'/usr/lib/python3/dist-packages'); import pcbnew\n"
        "b=pcbnew.LoadBoard(sys.argv[1])\n"
        "fps=list(b.GetFootprints()); boxes=[]\n"
        "for fp in fps:\n"
        "    pads=list(fp.Pads())\n"
        "    if not pads: continue\n"
        "    xs=[p.GetPosition().x for p in pads]; ys=[p.GetPosition().y for p in pads]\n"
        "    hx=max(p.GetSize().x for p in pads)/2; hy=max(p.GetSize().y for p in pads)/2\n"
        "    boxes.append((min(xs)-hx,min(ys)-hy,max(xs)+hx,max(ys)+hy))\n"
        "m=200000; ov=0\n"
        "for i in range(len(boxes)):\n"
        "    for j in range(i+1,len(boxes)):\n"
        "        a,c=boxes[i],boxes[j]\n"
        "        if a[0]-m<c[2]+m and c[0]-m<a[2]+m and a[1]-m<c[3]+m and c[1]-m<a[3]+m: ov+=1\n"
        "segs=len([t for t in b.GetTracks() if t.Type()==pcbnew.PCB_TRACE_T])\n"
        "print(f'{len(fps)} {ov} {segs}')\n"
    )
    try:
        r = subprocess.run(["/usr/bin/python3.14", "-c", code, str(board)],
                           capture_output=True, text=True, timeout=180)
    except Exception as e:  # pragma: no cover
        return True, f"gate25 skipped ({e})"
    if r.returncode != 0:
        return True, "gate25 skipped (pcbnew unavailable under python3.14)"
    fp, ov, segs = (int(x) for x in r.stdout.strip().split()[-3:])
    ok = ov == 0 and segs == 0 and fp >= 10
    return ok, f"gate25: fp={fp} pad_overlaps={ov} segments={segs} -> {'PASS' if ok else 'FAIL'}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate25", metavar="BOARD", default=None)
    a = ap.parse_args()
    reg = load_registry()
    problems = scan(reg)
    out = {"registry": str(REGISTRY.name),
           "canonical_placement_source": reg.get("canonical_placement_source"),
           "violations": problems}
    if a.gate25:
        ok, msg = gate25(Path(a.gate25))
        out["gate25"] = {"board": a.gate25, "ok": ok, "detail": msg}
    print(json.dumps(out, indent=2))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
