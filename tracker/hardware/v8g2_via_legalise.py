#!/usr/bin/env python3.14
"""v8g2: legalise the two under-size vias on v8g_krt_routed.

Card t_f48320db, step 6: "Target shorts 0 + clearance 0 + unconnected 0 with
vias >= 0.60/0.30".

Two vias on v8g_krt_routed sit at KRT's own fab floor (0.45/0.20):

  1. +3V3  at (22.000, 36.300) — worst foreign gap at 0.6 mm is 0.300 mm.
     Resize in place.  Nothing else moves.

  2. VCAP  at (18.300, 29.200) — the ONLY site that both fits a wide via and
     stays connected to U4.1.  Three rules meet there:

       F.Cu  EN track, centreline x = 18.900   -> 18.900 - 0.300 - 0.100 = 0.200  OK
       F.Cu  U4.2 GND pad, top edge y = 29.700 -> 29.700 - 0.300 - 0.200 = 0.200  OK
       In1   SOLAR_IN track (24.800,21.900)-(7.500,39.200)                  = 0.166  FAIL

     The VCAP via is placed tangent to the U4.1 pad; it IS U4.1's connection to
     the net (the EN track blocks the F.Cu corridor east, so there is no track to
     it).  Moving the via — which is what v8g_escape_probe.py proposed, 1.399 mm
     away — detaches U4.1 and leaves the board with 1 unconnected item.  So the
     via stays; the single constraining neighbour moves instead.

     The VCAP In1 track (18.300,29.200)-(23.300,24.200) and the SOLAR_IN diagonal
     are PARALLEL (both slope -1); SOLAR_IN runs 0.566 mm (centreline) from the
     via, i.e. 0.166 mm of copper gap.  Inserting one vertex 0.10 mm along the
     away-from-VCAP normal gives 0.266 mm to the via AND widens the SOLAR_IN<->
     VCAP-track gap from 0.366 to 0.466 mm — both constraints get safer, so the
     dogleg needs no new rule budget.

Geometry only — no hand-typed coordinates; the vertex is the perpendicular foot
of the via on SOLAR_IN, displaced along the segment normal.  Writes a NEW file.
Zones are refilled afterwards (fill_for_delivery.py).
"""
from __future__ import annotations

import math
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

SRC = "output/v8g_krt_routed.kicad_pcb"
DST = "output/v8g2_unfilled.kicad_pcb"
MM = 1_000_000
mm = lambda v: v / MM  # noqa: E731
NEW_W, NEW_D = 0.6, 0.3
DELTA = float(sys.argv[1]) if len(sys.argv) > 1 else 0.10

EXPECTED = {
    (22.000, 36.300): "+3V3",
    (18.300, 29.200): "VCAP",
}
VCAP = (18.300, 29.200)


def v2(x_mm: float, y_mm: float) -> "pcbnew.VECTOR2I":
    return pcbnew.VECTOR2I(int(round(x_mm * MM)), int(round(y_mm * MM)))


b = pcbnew.LoadBoard(SRC)

# ---- 1. the two clamped vias ----------------------------------------------
under = [t for t in b.GetTracks()
         if t.Type() == pcbnew.PCB_VIA_T
         and round(mm(t.GetWidth(t.TopLayer())), 3) < NEW_W - 1e-9]
found = {(round(mm(v.GetPosition().x), 3), round(mm(v.GetPosition().y), 3)):
         v.GetNetname() for v in under}
if found != EXPECTED:
    sys.exit(f"ABORT: under-size via set {found} != expected {EXPECTED}")
for v in under:
    old = (round(mm(v.GetPosition().x), 3), round(mm(v.GetPosition().y), 3))
    v.SetWidth(int(round(NEW_W * MM)))
    v.SetDrill(int(round(NEW_D * MM)))
    print(f"  via {old} net={v.GetNetname():5s} 0.45/0.20 -> {NEW_W}/{NEW_D} (in place)")

# ---- 2. dogleg the In1.Cu SOLAR_IN diagonal --------------------------------
seg = None
for t in b.GetTracks():
    if (t.Type() == pcbnew.PCB_TRACE_T and t.GetLayer() == pcbnew.In1_Cu
            and t.GetNetname() == "SOLAR_IN"):
        if seg is not None:
            sys.exit("ABORT: more than one In1.Cu SOLAR_IN segment")
        seg = t
if seg is None:
    sys.exit("ABORT: no In1.Cu SOLAR_IN segment")

A = (mm(seg.GetStart().x), mm(seg.GetStart().y))
C = (mm(seg.GetEnd().x), mm(seg.GetEnd().y))
width = seg.GetWidth()
net = seg.GetNet()
vx, vy = C[0] - A[0], C[1] - A[1]
L2 = vx * vx + vy * vy
tt = ((VCAP[0] - A[0]) * vx + (VCAP[1] - A[1]) * vy) / L2
P = (A[0] + tt * vx, A[1] + tt * vy)
# unit normal pointing AWAY from the VCAP via
n = (-vy / math.sqrt(L2), vx / math.sqrt(L2))
if (VCAP[0] - P[0]) * n[0] + (VCAP[1] - P[1]) * n[1] > 0:
    n = (-n[0], -n[1])
Pd = (P[0] + n[0] * DELTA, P[1] + n[1] * DELTA)
print(f"  SOLAR_IN ({A[0]:.3f},{A[1]:.3f})->({C[0]:.3f},{C[1]:.3f})")
print(f"    foot ({P[0]:.3f},{P[1]:.3f}) -> new vertex ({Pd[0]:.3f},{Pd[1]:.3f}) "
      f"(delta {DELTA:.3f} mm, normal ({n[0]:+.4f},{n[1]:+.4f}))")

b.Remove(seg)
for a, c in ((A, Pd), (Pd, C)):
    t = pcbnew.PCB_TRACK(b)
    t.SetStart(v2(*a))
    t.SetEnd(v2(*c))
    t.SetLayer(pcbnew.In1_Cu)
    t.SetWidth(width)
    t.SetNet(net)
    b.Add(t)

pcbnew.SaveBoard(DST, b)

# ---- 3. verify from disk ---------------------------------------------------
chk = pcbnew.LoadBoard(DST)
vias = [t for t in chk.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
under2 = [v for v in vias if round(mm(v.GetWidth(v.TopLayer())), 3) < NEW_W - 1e-9]
solarin = [t for t in chk.GetTracks()
           if t.Type() == pcbnew.PCB_TRACE_T and t.GetNetname() == "SOLAR_IN"
           and t.GetLayer() == pcbnew.In1_Cu]
print(f"verify {DST}: footprints {len(list(chk.GetFootprints()))}  vias {len(vias)}  "
      f"under-0.6 {len(under2)} (must be 0)  SOLAR_IN In1 segments {len(solarin)} (must be 2)")
sys.exit(1 if (under2 or len(solarin) != 2) else 0)
