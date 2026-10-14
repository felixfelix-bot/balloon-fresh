#!/usr/bin/env python3
"""Is a MIN TRACK of 0.089 mm real, and which nets carry it? Also get the true unconnected count.

0.089 mm is not a clean number the router was asked for (0.2 was requested). Investigate rather
than accept: cluster the track widths and list what is below the JLC floor.
"""
import collections
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

BOARD = "/home/c08r4d0r/worktrees/v9-route/tracker/hardware/base_station/output/bs_v1_routed.kicad_pcb"
b = pcbnew.LoadBoard(BOARD)

segs = [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_TRACE_T]

# --- cluster widths --------------------------------------------------------------------------
widths = collections.Counter(round(t.GetWidth() / 1e6, 4) for t in segs)
print("=== track-width histogram (mm -> count) ===")
for w, n in sorted(widths.items()):
    flag = ""
    if w < 0.10:
        flag = "  <-- BELOW JLC 0.10 FLOOR"
    elif w < 0.20:
        flag = "  <-- below the frozen 0.20"
    print(f"  {w:7.4f}  {n:5d}{flag}")

# --- which nets are below the JLC floor ------------------------------------------------------
print()
print("=== tracks below the JLC 0.10 mm floor ===")
for t in segs:
    w = t.GetWidth() / 1e6
    if w < 0.10:
        net = t.GetNetname()
        p0 = t.GetStart(); p1 = t.GetEnd()
        layer = b.GetLayerName(t.GetLayer())
        print(f"  {w:7.4f} mm  net={net:16s} layer={layer:8s} "
              f"({pcbnew.ToMM(p0.x):7.2f},{pcbnew.ToMM(p0.y):7.2f}) -> "
              f"({pcbnew.ToMM(p1.x):7.2f},{pcbnew.ToMM(p1.y):7.2f})")

# --- unconnected -----------------------------------------------------------------------------
print()
print("=== unconnected ===")
try:
    conn = b.GetConnectivity()
    items = conn.GetUnconnectedTracks() if hasattr(conn, "GetUnconnectedTracks") else None
    print(f"  GetUnconnectedTracks(): {len(items) if items is not None else 'n/a'}")
except Exception as e:
    print(f"  API: {e}")
try:
    ratsnest = b.GetConnectivity().GetRatsnestForItems()
    print(f"  ratsnest entries: {len(ratsnest) if ratsnest else 0}")
except Exception as e:
    print(f"  ratsnest API: {e}")

# fall back: count pads per net vs tracks per net for the 2 reported-open nets
print()
print("=== XIN / XOUT tracks (the 2 nets the router reported open) ===")
for want in ("XIN", "XOUT"):
    n = [t for t in segs if t.GetNetname() == want]
    print(f"  {want}: {len(n)} track segments")
    for t in n[:6]:
        p0, p1 = t.GetStart(), t.GetEnd()
        print(f"     {t.GetWidth()/1e6:6.3f} mm ({pcbnew.ToMM(p0.x):7.2f},{pcbnew.ToMM(p0.y):7.2f})"
              f" -> ({pcbnew.ToMM(p1.x):7.2f},{pcbnew.ToMM(p1.y):7.2f})")
    pads = [p for fp in b.GetFootprints() for p in fp.Pads() if p.GetNetname() == want]
    print(f"     pads on {want}: {[(p.GetParent().GetReference(), p.GetNumber()) for p in pads]}")
