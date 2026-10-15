
import re
NET=("/home/c08r4d0r/worktrees/v9-route/tracker/hardware/schematics/flight_board/v9_flight.net")
s=open(NET,encoding="utf-8",errors="replace").read()

# Build net -> [(ref,pin,pinfunction,pintype)]
nets={}
for m in re.finditer(r'\(net \(code "\d+"\) \(name "([^"]+)"\)(.*?)(?=\(net \(code|$)', s, re.S):
    name=m.group(1); body=m.group(2)
    members=[]
    for n in re.finditer(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)(?: \(pinfunction "([^"]*)"\))?(?: \(pintype "([^"]*)"\))?', body):
        members.append((n.group(1),n.group(2),n.group(3) or "",n.group(4) or ""))
    nets[name]=members

def show(n, limit=25):
    if n not in nets:
        print(f"  net {n!r}: NOT FOUND")
        return
    ms=nets[n]
    print(f"  net {n!r}: {len(ms)} members")
    for r,p,pf,pt in ms[:limit]:
        print(f"     {r:<12} pin {p:<4} {pf:<14} {pt}")

print("=== what is ON the rail /F33_VCC ? ===")
show("/F33_VCC")
print()
print("=== its neighbours ===")
for n in ("/F33_VCC_SEL","/GNSS_VCC","+3V3","/VSCAP","/F33_3V3"):
    if n in nets:
        print(f"\n{n}:")
        show(n, 12)
