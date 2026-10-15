
import re
SCH=("/home/c08r4d0r/worktrees/v9-route/tracker/hardware/schematics/flight_board/"
     "v9_flight.kicad_sch")
s=open(SCH,encoding="utf-8",errors="replace").read()

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

i=s.find('(property "Reference" "U4"')
j=s.rfind("\n\t(symbol",0,i)
inst=balanced(s,j+1)
m=re.search(r'\(at ([-\d.]+) ([-\d.]+) (\d+)\)', inst)
ix,iy,irot=float(m.group(1)),float(m.group(2)),int(m.group(3))
print(f"U4 instance at ({ix},{iy}) rot {irot}")

a=s.index("(lib_symbols"); lib=balanced(s,a)
k=lib.find('(symbol "SX1280_1_1"'); unit=balanced(lib,k)

# robust pin parse: walk each (pin ...) block
pins=[]
pos=0
while True:
    p=unit.find("(pin ",pos)
    if p<0: break
    blk=balanced(unit,p)
    at=re.search(r'\(at ([-\d.]+) ([-\d.]+) (\d+)\)',blk)
    nm=re.search(r'\(name "([^"]+)"',blk)
    nu=re.search(r'\(number "([^"]+)"',blk)
    if at and nm and nu:
        pins.append((nu.group(1),nm.group(1),float(at.group(1)),float(at.group(2))))
    pos=p+len(blk)
print(f"symbol pins: {len(pins)}")

labels=[]
for lm in re.finditer(r'\(label "([^"]+)"\s*\n\s*\(at ([-\d.]+) ([-\d.]+) (\d+)\)', s):
    labels.append((lm.group(1),float(lm.group(2)),float(lm.group(3))))
print(f"labels total: {len(labels)}")

# wires, as segments
wires=[]
for wm in re.finditer(r'\(wire\s*\n\s*\(pts\s*\n\s*\(xy ([-\d.]+) ([-\d.]+)\) \(xy ([-\d.]+) ([-\d.]+)\)', s):
    wires.append(tuple(float(wm.group(g)) for g in (1,2,3,4)))
print(f"wires total: {len(wires)}")

print("\nnum name          abs_x    abs_y   label(d<4mm)         wire-end(d<1mm)")
for nu,nm,px,py in sorted(pins,key=lambda r:(int(r[0]) if r[0].isdigit() else 99)):
    ax=ix+px; ay=iy-py
    bl=None;bd=99
    for lt,lx,ly in labels:
        d=((lx-ax)**2+(ly-ay)**2)**0.5
        if d<bd: bd=d;bl=lt
    wl=None;wd=99
    for (x1,y1,x2,y2) in wires:
        for (wx,wy) in ((x1,y1),(x2,y2)):
            d=((wx-ax)**2+(wy-ay)**2)**0.5
            if d<wd: wd=d;wl=f"({wx:.1f},{wy:.1f})"
    lab = f"{bl} d={bd:.2f}" if bd<4 else "-"
    wir = f"{wl} d={wd:.2f}" if wd<1 else "-"
    print(f"{nu:>3} {nm:<13} {ax:7.2f} {ay:7.2f}   {lab:<22} {wir}")
