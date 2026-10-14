#!/usr/bin/env python3
"""Grade the base-station route HONESTLY: against the FROZEN floors, not the router's relaxed ones.

The router wrote `output/bs_v1_routed.kicad_pro` and RELAXED the fab floor:
    via diameter     0.5 -> 0.25 mm   (15 of 117 objects below the ORIGINAL)
    via annular ring 0.1 -> 0.05 mm   (14 of 117 below the ORIGINAL)
    hole diameter    0.3 -> 0.15 mm
    copper-to-hole   0.25 -> 0.1 mm
The router's own log says it plainly: "Every checker ... grades against the NEW value, so this
copper will read clean." That is the SELF-GRADING HAZARD this campaign already documented for the
hub. So grade the copper the way the FROZEN rules would.

Reports:
  1. unconnected items from the board itself
  2. the routed minima actually present (track, via, drill)
  3. whether they clear the JLC floor AND the campaign's frozen floor
"""
import os
import re
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

BOARD = "/home/c08r4d0r/worktrees/v9-route/tracker/hardware/base_station/output/bs_v1_routed.kicad_pcb"

# FROZEN floors the campaign uses (2x JLC margin), from jlcpcb-s1-frozen.kicad_dru
FROZEN = dict(track=0.20, clearance=0.20, via_dia=0.60, via_drill=0.30)
# JLC's own capability floor
JLC = dict(track=0.10, clearance=0.10, via_dia=0.45, via_drill=0.20)

b = pcbnew.LoadBoard(BOARD)
print(f"board: {os.path.basename(BOARD)}")
print(f"footprints: {len(list(b.GetFootprints()))}   nets: {b.GetNetCount()}")

# --- 1. unconnected -------------------------------------------------------------------------
try:
    conn = b.GetConnectivity()
    conn.BuildConnectivity()
    unconn = conn.GetUnconnectedCount() if hasattr(conn, "GetUnconnectedCount") else None
except Exception as e:
    unconn = f"(API: {e})"
print(f"\n=== unconnected items ===")
print(f"  GetUnconnectedCount(): {unconn}")

# --- 2. routed minima -----------------------------------------------------------------------
tracks = list(b.GetTracks())
segs = [t for t in tracks if t.Type() == pcbnew.PCB_TRACE_T]
vias = [t for t in tracks if t.Type() == pcbnew.PCB_VIA_T]
tmin = min((t.GetWidth() / 1e6 for t in segs), default=None)
vmin = min((v.GetWidth() / 1e6 for v in vias), default=None)
dmin = min((v.GetDrill() / 1e6 for v in vias), default=None)
print(f"\n=== routed minima ===")
print(f"  tracks {len(segs)}   vias {len(vias)}")
print(f"  min track width      : {tmin}")
print(f"  min via diameter     : {vmin}")
print(f"  min via drill        : {dmin}")

# --- 3. verdict -----------------------------------------------------------------------------
print(f"\n=== verdict ===")
def chk(name, val, frozen, jlc):
    if val is None:
        print(f"  {name:22s} n/a")
        return
    f_ok = "PASS" if val >= frozen else "**BELOW FROZEN**"
    j_ok = "PASS" if val >= jlc else "**BELOW JLC FLOOR**"
    print(f"  {name:22s} {val:6.3f}  vs frozen {frozen:.3f} {f_ok:16s} "
          f"vs JLC {jlc:.3f} {j_ok}")

chk("track width", tmin, FROZEN["track"], JLC["track"])
chk("via diameter", vmin, FROZEN["via_dia"], JLC["via_dia"])
chk("via drill", dmin, FROZEN["via_drill"], JLC["via_drill"])

print()
print("NOTE: vias were routed at 0.6/0.3 as requested, but the router ADDED vias down to")
print("0.25/0.15 during escalation -- so any measurement must be against the SMALLEST present,")
print("which is what this script reports.")
