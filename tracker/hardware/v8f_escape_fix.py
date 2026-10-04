#!/usr/bin/env python3.14
"""v8f: legalise the two under-size GND escape vias at U5 on v8e.

Sites chosen by v8f_escape_probe.py (exact geometry, copper clearance 0.20 mm AND
copper-to-hole 0.25 mm AND 0.5 mm board edge, 0.01 mm safety over each rule):
  * via at (22.700, 36.300)  -> legal as-is, only the SIZE changes (0.45/0.2 -> 0.6/0.3)
  * via at (22.000, 35.700)  -> shift +0.075 mm in x to (22.075, 35.700), same size change

Everything else on the board is untouched. Writes a NEW file; v8e is never edited.
Zones are refilled afterwards (fill_for_delivery.py) so the In2 +3V3 pour regenerates its
antipads for the wider via — the step the earlier relocation pass skipped.
"""
import sys
sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew

SRC = "v8e_krt_novip.kicad_pcb"
DST = "v8f_unfilled.kicad_pcb"
MM = 1_000_000
mm = lambda v: v / MM
NEW_W, NEW_D = 0.6, 0.3

moves = {(22.000, 35.700): (22.075, 35.700)}   # old -> new, from the probe
b = pcbnew.LoadBoard(SRC)

under = [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T
         and round(mm(t.GetWidth(t.TopLayer())), 3) < NEW_W - 1e-9]
if len(under) != 2:
    sys.exit(f"ABORT: expected exactly 2 under-size vias, found {len(under)} — refusing to guess")

changed = 0
for v in under:
    old = (round(mm(v.GetPosition().x), 3), round(mm(v.GetPosition().y), 3))
    new = moves.get(old, old)
    if new != old:
        # re-attach every track that terminated on the old centre
        oldnm = pcbnew.VECTOR2I(int(round(old[0] * MM)), int(round(old[1] * MM)))
        for t in b.GetTracks():
            if t.Type() != pcbnew.PCB_TRACE_T:
                continue
            for getter, setter in ((t.GetStart, t.SetStart), (t.GetEnd, t.SetEnd)):
                p = getter()
                if abs(p.x - oldnm.x) <= 1 and abs(p.y - oldnm.y) <= 1:
                    setter(pcbnew.VECTOR2I(int(round(new[0] * MM)), int(round(new[1] * MM))))
        v.SetPosition(pcbnew.VECTOR2I(int(round(new[0] * MM)), int(round(new[1] * MM))))
    v.SetWidth(int(round(NEW_W * MM)))
    v.SetDrill(int(round(NEW_D * MM)))
    changed += 1
    print(f"  via {old} -> {new}  now {NEW_W}/{NEW_D} mm")

pcbnew.SaveBoard(DST, b)

# --- verify the edit landed (reload from disk, do not trust the in-memory board)
chk = pcbnew.LoadBoard(DST)
vias = [t for t in chk.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
under2 = [v for v in vias if round(mm(v.GetWidth(v.TopLayer())), 3) < NEW_W - 1e-9]
print(f"verify: footprints {len(list(chk.GetFootprints()))}  vias {len(vias)}  "
      f"under-0.6 {len(under2)}  touched {changed}")
print("wrote", DST)
