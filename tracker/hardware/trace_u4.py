
import re, collections
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

i=s.find('(property "Reference" "U4"'); j=s.rfind("\n\t(symbol",0,i)
inst=balanced(s,j+1)
m=re.search(r'\(at ([-\d.]+) ([-\d.]+) (\d+)\)', inst)
ix,iy=float(m.group(1)),float(m.group(2))

a=s.index("(lib_symbols"); lib=balanced(s,a)
k=lib.find('(symbol "SX1280_1_1"'); unit=balanced(lib,k)
pins=[]; pos=0
while True:
    p=unit.find("(pin ",pos)
    if p<0: break
    blk=balanced(unit,p)
    at=re.search(r'\(at ([-\d.]+) ([-\d.]+) (\d+)\)',blk)
    nm=re.search(r'\(name "([^"]+)"',blk); nu=re.search(r'\(number "([^"]+)"',blk)
    if at and nm and nu: pins.append((nu.group(1),nm.group(1),float(at.group(1)),float(at.group(2))))
    pos=p+len(blk)

# build a connectivity graph on wire endpoints (snap to 0.01mm)
wires=[]
for wm in re.finditer(r'\(wire\s*\n\s*\(pts\s*\n\s*\(xy ([-\d.]+) ([-\d.]+)\) \(xy ([-\d.]+) ([-\d.]+)\)', s):
    x1,y1,x2,y2=(float(wm.group(g)) for g in (1,2,3,4))
    wires.append(((round(x1,2),round(y1,2)),(round(x2,2),round(y2,2))))

adj=collections.defaultdict(set)
for a_,b_ in wires:
    adj[a_].add(b_); adj[b_].add(a_)
# wires also connect at a point lying ON another segment (T junctions); add those
def on_seg(p,a_,b_):
    (px,py),(x1,y1),(x2,y2)=p,a_,b_
    if abs(x1-x2)<1e-6:  # vertical
        return abs(px-x1)<0.02 and min(y1,y2)-0.02<=py<=max(y1,y2)+0.02
    if abs(y1-y2)<1e-6:  # horizontal
        return abs(py-y1)<0.02 and min(x1,x2)-0.02<=px<=max(x1,x2)+0.02
    return False
pts=list(adj)
for p in pts:
    for a_,b_ in wires:
        if p!=a_ and p!=b_ and on_seg(p,a_,b_):
            adj[p].add(a_); adj[p].add(b_); adj[a_].add(p); adj[b_].add(p)

# labels: snap to a graph node if one is within 0.6mm
labels=[]
for lm in re.finditer(r'\(label "([^"]+)"\s*\n\s*\(at ([-\d.]+) ([-\d.]+) (\d+)\)', s):
    labels.append((lm.group(1),float(lm.group(2)),float(lm.group(3))))
lbl_at={}
for name,lx,ly in labels:
    best=None;bd=0.6
    for p in adj:
        d=((p[0]-lx)**2+(p[1]-ly)**2)**0.5
        if d<bd: bd=d;best=p
    if best: lbl_at.setdefault(best,[]).append(name)

# BFS from each pin's wire endpoint
print("num name        -> net reached via wires")
print("-"*64)
mapping={}
for nu,nm,px,py in sorted(pins,key=lambda r:(int(r[0]) if r[0].isdigit() else 99)):
    ax,ay=round(ix+px,2), round(iy-py,2)
    # nearest graph node
    start=None;bd=1.0
    for p in adj:
        d=((p[0]-ax)**2+(p[1]-ay)**2)**0.5
        if d<bd: bd=d;start=p
    net=None
    if start:
        seen={start}; q=[start]
        while q and not net:
            cur=q.pop(0)
            if cur in lbl_at: net=lbl_at[cur][0]; break
            for nx in adj[cur]:
                if nx not in seen: seen.add(nx); q.append(nx)
    mapping[nu]=net
    print(f"{nu:>3} {nm:<12} -> {net}")
import json
open("/tmp/u4_pin_nets.json","w").write(json.dumps(mapping,indent=1))
