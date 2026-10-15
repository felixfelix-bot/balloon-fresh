
import re
S=("/home/c08r4d0r/worktrees/v9-route/tracker/hardware/schematics/flight_board/"
   "v9_flight.kicad_sch")
s=open(S,encoding="utf-8",errors="replace").read()

# ALL wire endpoints in the U4 area, unfiltered, sorted -- to identify the pin column exactly
pts={}
for m in re.finditer(r'\(wire\s*\n\s*\(pts\s*\n\s*\(xy ([-\d.]+) ([-\d.]+)\) \(xy ([-\d.]+) ([-\d.]+)\)', s):
    x1,y1,x2,y2=(float(m.group(g)) for g in (1,2,3,4))
    for (x,y) in ((x1,y1),(x2,y2)):
        if 300<=x<=365 and 25<=y<=80:
            pts.setdefault(round(x,2),set()).add(round(y,2))

for x in sorted(pts):
    ys=sorted(pts[x])
    print(f"x={x:7.2f}  ({len(ys)} pts): {ys}")

# The symbol's declared pin positions per U4's instance, from the lib definition
print()
a=s.index("(lib_symbols")
def balanced(t,st):
    inq=esc=False; d=0; i=st
    while i<len(t):
        c=t[i]
        if esc: esc=False
        elif c=="\\": esc=True
        elif c=='"': inq=not inq
        elif not inq:
            if c=="(": d+=1
            elif c==")":
                d-=1
                if d==0: return t[st:i+1]
        i+=1
    return t[st:]
lib=balanced(s,a)
k=lib.find('(symbol "SX1280_1_1"'); unit=balanced(lib,k)
pos=0
print("symbol pin coords (local) and the implied absolute for origin (335.28,50.8):")
while True:
    p=unit.find("(pin ",pos)
    if p<0: break
    blk=balanced(unit,p)
    at=re.search(r'\(at ([-\d.]+) ([-\d.]+) (\d+)\)',blk)
    nu=re.search(r'\(number "([^"]+)"',blk)
    nm=re.search(r'\(name "([^"]+)"',blk)
    if at and nu:
        px,py=float(at.group(1)),float(at.group(2))
        print(f"   {nu.group(1):>3} {nm.group(1):<10} local({px:7.2f},{py:7.2f})  -> abs(335.28+p) x={335.28+px:7.2f}  abs(50.8-p) y={50.8-py:7.2f}")
    pos=p+len(blk)
