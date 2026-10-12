#!/usr/bin/env python3
"""drc_report.py -- decode a KiCad DRC JSON into a triaged summary.

WHY: this exact decode was hand-run ~8 times this session -- the same
json.load + Counter-by-type + "which of these are by-design?" loop, each time
re-typing the severity filter and re-deriving the waiver rules. One script.
It is the READ side of fab_preflight.py (which is the GATE side): use this to
understand a report, that to block a board.

USAGE:
  kicad-cli pcb drc --severity-error --format json -o /tmp/drc.json BOARD
  python3 tracker/hardware/drc_report.py /tmp/drc.json [--by-design] [--top N]

--by-design additionally classifies each item with the same waiver rules as
fab_preflight.py and prints WAIVED vs REAL, so the two tools can never drift:
they share is_waived() imported from fab_preflight.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fab_preflight import is_waived  # single source of waiver truth


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("report")
    ap.add_argument("--by-design", action="store_true",
                    help="split into waived (documented) vs real")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--list", action="store_true", help="print every real item")
    args = ap.parse_args()

    d = json.load(open(args.report))
    errs = d.get("violations", [])
    unconn = d.get("unconnected_items", [])
    allitems = errs + unconn

    print(f"KiCad DRC: {len(errs)} violations + {len(unconn)} unconnected "
          f"= {len(allitems)} items")

    by_type = Counter(v.get("type") for v in allitems)
    for t, n in by_type.most_common(args.top):
        print(f"  {n:4d}  {t}")

    if not args.by_design:
        return 0

    waived = [(v, f) for v in allitems for ok, f in (is_waived(v),) if ok]
    real = [v for v in allitems if not is_waived(v)[0]]
    print(f"\n-- by-design triage: {len(waived)} WAIVED, {len(real)} REAL")
    print("  waived families:",
          dict(Counter(f for _, f in waived)) or "{}")
    print("  REAL by type:", dict(Counter(v.get("type") for v in real)))
    if args.list:
        for v in real:
            first = v.get("items", [{}])[0].get("description", v.get("type", ""))
            print(f"    - [{v.get('type')}] {first[:95]}")
    return 1 if real else 0


if __name__ == "__main__":
    sys.exit(main())