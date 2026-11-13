#!/usr/bin/env python3
"""Record the fab-readiness expectation for the canonical board, after checking it.

Run AFTER the routed board is promoted to canonical, so the recorded baseline IS the good state. From
then on, tracker/hardware/.githooks/pre-commit refuses any commit that would drop the board below it.

Usage: record_fab_readiness.py
"""
import json
import os
import subprocess
import sys

BOARDS = [
    "tracker/hardware/hub_board_v9.kicad_pcb",
    "tracker/hardware/wing_board/wing_board_v9.kicad_pcb",
    "tracker/hardware/base_station/base_station_v1_unrouted.kicad_pcb",
]
EXPECT = "tracker/hardware/FAB-READINESS.json"
KICAD_PY = os.path.expanduser("~/venvs/kicad/bin/python")
CODE = (
    "import pcbnew,sys,json;"
    "b=pcbnew.LoadBoard(sys.argv[1]);"
    "t=list(b.GetTracks());"
    "tr=[x for x in t if x.Type()!=pcbnew.PCB_VIA_T];"
    "vi=[x for x in t if x.Type()==pcbnew.PCB_VIA_T];"
    "print(json.dumps({'tracks':len(tr),'vias':len(vi),"
    "'nets_routed':len(set(x.GetNetname() for x in tr)),"
    "'nets_total':b.GetNetCount()-1}))"
)


def main():
    root = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                          capture_output=True, text=True).stdout.strip() or "."
    exp = {}
    for rel in BOARDS:
        p = os.path.join(root, rel)
        if not os.path.exists(p):
            print(f"  {rel}: absent, not recorded")
            continue
        r = subprocess.run([KICAD_PY, "-c", CODE, p], capture_output=True, text=True, timeout=300)
        try:
            m = json.loads(r.stdout.strip().splitlines()[-1])
        except Exception as e:
            print(f"  {rel}: could not measure ({e})")
            continue
        # accepted_unrouted = the shortfall that is DOCUMENTED, not silent
        m["accepted_unrouted"] = 0
        m["note"] = "recorded by record_fab_readiness.py; regression below these values is refused"
        exp[rel] = m
        print(f"  {rel}: tracks {m['tracks']}, vias {m['vias']}, "
              f"nets {m['nets_routed']}/{m['nets_total']}")
    with open(os.path.join(root, EXPECT), "w") as fh:
        json.dump(exp, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(f"\nwrote {EXPECT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
