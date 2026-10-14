#!/usr/bin/env python3
"""Does U2 seat at each candidate outline? Measure, don't assume.

U2 is the 39.0 x 21.0 mm `LoRa2021F33-2G4` -- the largest body on the hub.
This runs the real generator at each outline and reports whether U2 lands ON the
board or is overflowed (parked off-board), plus the seating of every other part.

Run: python3 tracker/hardware/seat_probe.py [outline ...]
Default: 60 65 70 75 80 102
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
GEN = os.path.join(HERE, "build_hub_board_v9.py")

outlines = sys.argv[1:] or ["60", "65", "70", "75", "80", "102"]

print(f"{'outline':>9} | {'placed':>6} | {'overflow':<22} | U2 on board?")
print("-" * 62)
for o in outlines:
    seed = f"/tmp/seatprobe_{o}.kicad_pcb"
    # generate straight to a temp path so we never disturb the working seed
    r = subprocess.run([sys.executable, GEN, "--outline", f"{o}x{o}", "--out", "seed"],
                       cwd=HERE, capture_output=True, text=True, timeout=600)
    out = r.stdout + r.stderr
    os.replace(os.path.join(HERE, "seed"), seed)

    m = re.search(r"UNSEATED \(pack ran out of room\): \[(.*?)\]", out)
    overflow = m.group(1) if m else ""
    placed = re.search(r"(\d+) placed", out)
    placed = placed.group(1) if placed else "?"

    # ask pcbnew where U2 actually is
    probe = (
        "import pcbnew,sys;sys.path.insert(0,'/usr/lib/python3/dist-packages');"
        f"b=pcbnew.LoadBoard('{seed}');"
        "f=b.FindFootprintByReference('U2');"
        "p=f.GetPosition();"
        "print('%.1f %.1f' % (pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)))"
    )
    q = subprocess.run([sys.executable, "-c", probe], capture_output=True,
                       text=True, timeout=300)
    xy = q.stdout.strip()
    try:
        x, y = (float(v) for v in xy.split())
        on = "YES" if (x <= float(o) and y <= float(o)) else f"NO (parked at {x:.0f},{y:.0f})"
    except Exception:
        on = f"? ({xy})"
    print(f"{o:>6} mm | {placed:>6} | {overflow:<22} | {on}")
