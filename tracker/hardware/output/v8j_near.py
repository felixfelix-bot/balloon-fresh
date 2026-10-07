#!/usr/bin/env python3.14
"""All copper within R mm of U5 on a board, any net."""
import sys, math
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew
MM = 1e6
B = sys.argv[1]; R = float(sys.argv[2]) if len(sys.argv) > 2 else 7.0
b = pcbnew.LoadBoard(B)
u5 = b.FindFootprintByReference('U5'); c = u5.GetPosition()
print(f"{B}  U5@({c.x/MM:.3f},{c.y/MM:.3f}) rot={u5.GetOrientationDegrees()} fpid={u5.GetFPID()}")
print("pads:", {p.GetNumber(): p.GetNetname() for p in u5.Pads()})
for z in b.Zones():
    print(f"zone {b.GetLayerName(z.GetLayer())} net={z.GetNetname()!r} filled={z.IsFilled()} clr={z.GetLocalClearance()/MM:.3f} prio={z.GetAssignedPriority()}")
print(f"--- copper within {R}mm of U5 ---")
rows = []
for t in b.GetTracks():
    p = t.GetPosition()
    d = math.hypot((p.x-c.x)/MM, (p.y-c.y)/MM)
    if d > R: continue
    if t.Type() == pcbnew.PCB_VIA_T:
        rows.append((d, f"VIA  {t.GetNetname():<10} @({p.x/MM:8.3f},{p.y/MM:8.3f}) d={t.GetWidth()/MM:.2f} drill={t.GetDrill()/MM:.2f}"))
    else:
        s, e = t.GetStart(), t.GetEnd()
        rows.append((d, f"TRK  {t.GetNetname():<10} {b.GetLayerName(t.GetLayer()):<5} w={t.GetWidth()/MM:.2f} ({s.x/MM:8.3f},{s.y/MM:8.3f})->({e.x/MM:8.3f},{e.y/MM:8.3f})"))
for d, s in sorted(rows):
    print(f"  {d:5.2f}  {s}")
print(f"--- other footprints within {R}mm ---")
for fp in b.GetFootprints():
    if fp.GetReference() == 'U5': continue
    pc = fp.GetPosition(); d = math.hypot((pc.x-c.x)/MM, (pc.y-c.y)/MM)
    if d < R:
        print(f"  {d:5.2f}  {fp.GetReference():<6} {str(fp.GetFPID().GetLibItemName()):<38} @({pc.x/MM:.2f},{pc.y/MM:.2f}) rot={fp.GetOrientationDegrees()}")
