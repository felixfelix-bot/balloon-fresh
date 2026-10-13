#!/usr/bin/env python3.14
"""Introspect U5 neighbourhood on the routed v8j board: pads, nearby tracks/vias, zones."""
import sys, math
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew
MM = 1e6
B = 'tracker/hardware/output/v8j_krt_ms5611.kicad_pcb'
b = pcbnew.LoadBoard(B)

print("ZONES:")
for z in b.Zones():
    print(f"  layer={b.GetLayerName(z.GetLayer()):>8} net={z.GetNetname():<10} prio={z.GetAssignedPriority()} filled={z.IsFilled()} clearance={z.GetLocalClearance()/MM:.3f}")

u5 = b.FindFootprintByReference('U5')
c = u5.GetPosition()
print(f"\nU5 center=({c.x/MM:.3f},{c.y/MM:.3f}) rot={u5.GetOrientationDegrees()}")
print("U5 PADS (abs, local, net):")
pads = {}
for p in u5.Pads():
    pp = p.GetPosition()
    pads[p.GetNumber()] = (pp.x, pp.y)
    print(f"  pad {p.GetNumber():>2} abs=({pp.x/MM:8.3f},{pp.y/MM:8.3f}) local=({(pp.x-c.x)/MM:+6.3f},{(pp.y-c.y)/MM:+6.3f}) net={p.GetNetname():<10} size=({p.GetSize().x/MM:.3f}x{p.GetSize().y/MM:.3f})")

interest = {'I2C_SDA','I2C_SCL','+3V3','GND','EN'}
print("\nTRACKS/VIAS within 9mm of U5 (nets of interest):")
for t in b.GetTracks():
    p = t.GetPosition()
    d = math.hypot((p.x-c.x)/MM, (p.y-c.y)/MM)
    if d > 9: continue
    if t.GetNetname() not in interest: continue
    if t.Type() == pcbnew.PCB_VIA_T:
        print(f"  VIA  net={t.GetNetname():<9} d={t.GetWidth()/MM:.3f} drill={t.GetDrill()/MM:.3f} @({p.x/MM:8.3f},{p.y/MM:8.3f}) dist={d:.2f}")
    else:
        s, e = t.GetStart(), t.GetEnd()
        print(f"  TRK  net={t.GetNetname():<9} w={t.GetWidth()/MM:.3f} L={t.GetLength()/MM:7.3f} layer={b.GetLayerName(t.GetLayer()):<5} ({s.x/MM:8.3f},{s.y/MM:8.3f})->({e.x/MM:8.3f},{e.y/MM:8.3f}) dist={d:.2f}")
print("\nNEARBY FOOTPRINTS (courtyard dist<6mm):")
for fp in b.GetFootprints():
    if fp.GetReference() == 'U5': continue
    pc = fp.GetPosition()
    d = math.hypot((pc.x-c.x)/MM, (pc.y-c.y)/MM)
    if d < 6:
        print(f"  {fp.GetReference():<6} {str(fp.GetFPID().GetLibItemName()):<40} @({pc.x/MM:.2f},{pc.y/MM:.2f}) dist={d:.2f}")
