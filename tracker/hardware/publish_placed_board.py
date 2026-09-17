#!/usr/bin/env python3
"""Publish the flight-board placement - THE single writer of the frozen board.

The only file-level owner of output/v_c3_flight_4layer_placed.kicad_pcb.
Everything here is mechanical: it runs the dedicated placement tool on a
prepared input and records the result.  It contains NO coordinate table -
positions are computed by the KRT placer under a bounded quench, and the only
constraints this file encodes are the mechanical seats that must not drift:

    LOCKED (mechanical interfaces, held at their seeded pose by the placer):
      ANT1  - U.FL RF port on the east edge: the antenna pigtail exits the
              enclosure's east face; its seat is a mechanical fact.
      J1    - 1x06 programming header, south edge.
      J2    - 1x04 debug header, south edge.
      SOLAR - 1x02 solar input, south edge.

Pipeline
--------
1. prep_placement_input.py   rips all copper, keeps the zone PLANES, drops
                             stale fill geometry
2. KiCadRoutingTools py_placer/place_optimize.py
                             --max-displacement 3 --max-passes 10
                             --halo-base 1.0 --halo-weight 6.0 --lock <above>
3. gate25_check.py           0 pad-box overlaps at 0.2mm, courtyards_overlap=0,
                             0 segments, fp >= 10  (referee, not a placement
                             input)
4. records the output sha256.

usage: python3 publish_placed_board.py
       (idempotent: reruns of the same lap produce the same board)
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

KRT = os.path.expanduser("~/tools/KiCadRoutingTools")
PLACER = os.path.join(KRT, "py_placer", "place_optimize.py")
PY314 = "/usr/bin/python3.14"

SOURCE_BOARD = os.path.join(HERE, "output", "v_c3_flight_4layer_routed.kicad_pcb")
WORK_DIR = os.path.join(HERE, "output", ".placement")
IN_PATH = os.path.join(WORK_DIR, "flight_placement_input.kicad_pcb")
LAP_PATH = os.path.join(WORK_DIR, "flight_krt_lap.kicad_pcb")
OUT_PATH = os.path.join(HERE, "output", "v_c3_flight_4layer_placed.kicad_pcb")

EDGES_LOCKED = ["ANT1", "J1", "J2", "SOLAR"]
PLACER_ARGS = ["--max-displacement", "3", "--max-passes", "10",
               "--halo-base", "1.0", "--halo-weight", "6.0",
               "--lock", *EDGES_LOCKED]


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def run(cmd, **kw):
    sys.stderr.write("+ " + " ".join(str(c) for c in cmd) + "\n")
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    sys.stderr.write(r.stdout[-2000:])
    sys.stderr.write(r.stderr[-1000:])
    if r.returncode != 0:
        sys.stderr.write(f"FAILED rc={r.returncode}\n")
        raise SystemExit(r.returncode)
    return r


def main() -> int:
    os.makedirs(WORK_DIR, exist_ok=True)
    from prep_placement_input import prep
    stats = prep(SOURCE_BOARD, IN_PATH)
    print("prepared input:", stats)
    run([PY314, PLACER, IN_PATH, LAP_PATH, *PLACER_ARGS], cwd=KRT)
    shutil.copyfile(LAP_PATH, OUT_PATH)
    try:
        import gate25_check as g
        res = g.gate25(OUT_PATH, margin=0.2,
                       drc_out=os.path.splitext(OUT_PATH)[0] + "_drc.json")
        print(json.dumps({k: res[k] for k in
                          ("footprints", "segments", "vias", "zones",
                           "pad_overlap_pairs_0.2mm",
                           "exact_pad_overlap_pairs_0.2mm",
                           "courtyards_overlap", "placement_gate")}, indent=2))
        detail = res
    except ImportError as e:
        print("gate25_check not importable:", e, file=sys.stderr)
        detail = {}
    record = {
        "frozen_artefact": os.path.relpath(OUT_PATH, REPO),
        "sha256": sha256(OUT_PATH),
        "source_board": os.path.relpath(SOURCE_BOARD, REPO),
        "source_sha256": sha256(SOURCE_BOARD),
        "placer": "KiCadRoutingTools py_placer/place_optimize.py",
        "placer_args": PLACER_ARGS,
        "edges_locked": EDGES_LOCKED,
        "prep": stats,
        "gate25": detail,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    rp = os.path.join(WORK_DIR, "placement_record.json")
    with open(rp, "w") as f:
        json.dump(record, f, indent=2)
    sys.stderr.write(f"placement record: {rp}\n")
    sys.stderr.write(f"frozen board: {OUT_PATH}\nsha256: {record['sha256']}\n")
    print(json.dumps(record["gate25"].get("placement_gate", "unknown")))
    return 0 if record["gate25"].get("placement_gate") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
