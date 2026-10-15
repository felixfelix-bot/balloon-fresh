
"""Measure U4's pin endpoints and net names from GROUND TRUTH, not from assumed geometry."""
import re
S=("/home/c08r4d0r/worktrees/v9-route/tracker/hardware/schematics/flight_board/"
   "v9_flight.kicad_sch")
s=open(S,encoding="utf-8",errors="replace").read()

# 1. every label on the sheet: name + exact coords
labs=[]
for m in re.finditer(r'\(label "([^"]+)"\s*\n\s*\(at ([-\d.]+) ([-\d.]+) (\d+)\)', s):
    labs.append((m.group(1), float(m.group(2)), float(m.group(3))))
print(f"labels: {len(labs)}")
print("\n=== labels in U4's neighbourhood (x 300-370, y 25-80) ===")
for n,x,y in sorted(labs, key=lambda r:(r[2],r[1])):
    if 300<=x<=370 and 25<=y<=80:
        print(f"   {n:<22} ({x:7.2f},{y:7.2f})")

# 2. wire endpoints in the same neighbourhood
we=set()
for m in re.finditer(r'\(wire\s*\n\s*\(pts\s*\n\s*\(xy ([-\d.]+) ([-\d.]+)\) \(xy ([-\d.]+) ([-\d.]+)\)', s):
    x1,y1,x2,y2=(float(m.group(g)) for g in (1,2,3,4))
    for (x,y) in ((x1,y1),(x2,y2)):
        if 300<=x<=370 and 25<=y<=80: we.add((round(x,2),round(y,2)))
print(f"\n=== wire endpoints in U4's neighbourhood: {len(we)} ===")
for x,y in sorted(we, key=lambda r:(r[1],r[0])):
    # nearest label within 1mm
    best=None;bd=1.0
    for n,lx,ly in labs:
        d=((lx-x)**2+(ly-y)**2)**0.5
        if d<bd: bd=d;best=n
    print(f"   ({x:7.2f},{y:7.2f})  {best if best else ''}")
