#!/usr/bin/env python3
"""Fix track crossings — move every other crossing track to B.Cu with vias."""
import sys; sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew, json

PATH = '/home/c03rad0r/repos/balloon-fresh/tracker/hardware/output/v_c3_flight_final.kicad_pcb'
b = pcbnew.LoadBoard(PATH)

# Get all tracks on F.Cu
f_cu = pcbnew.F_Cu
b_cu = pcbnew.B_Cu
tracks = list(b.GetTracks())
seg_tracks = [t for t in tracks if t.Type() == pcbnew.PCB_TRACE_T]

print(f"Total tracks: {len(seg_tracks)}")

# Segment intersection check
def ccw(ax, ay, bx, by, cx, cy):
    return (cy - ay) * (bx - ax) > (by - ay) * (cx - ax)

def segments_intersect(x1,y1,x2,y2, x3,y3,x4,y4):
    """Check if line segment (x1,y1)-(x2,y2) intersects (x3,y3)-(x4,y4)"""
    # Handle shared endpoints (same net connected at pad)
    if abs(x1-x3) < 1000 and abs(y1-y3) < 1000: return False
    if abs(x1-x4) < 1000 and abs(y1-y4) < 1000: return False
    if abs(x2-x3) < 1000 and abs(y2-y3) < 1000: return False
    if abs(x2-x4) < 1000 and abs(y2-y4) < 1000: return False
    d1 = ccw(x3,y3,x4,y4,x1,y1)
    d2 = ccw(x3,y3,x4,y4,x2,y2)
    d3 = ccw(x1,y1,x2,y2,x3,y3)
    d4 = ccw(x1,y1,x2,y2,x4,y4)
    return d1 != d2 and d3 != d4

# Group tracks by net
net_groups = {}
for t in seg_tracks:
    net = t.GetNetname()
    if net not in net_groups:
        net_groups[net] = []
    net_groups[net].append(t)

print(f"Nets with tracks: {len(net_groups)}")

# Find all crossings between different nets
crossings = []
for n1, tracks1 in net_groups.items():
    for n2, tracks2 in net_groups.items():
        if n1 >= n2:
            continue
        for t1 in tracks1:
            s1 = t1.GetStart()
            e1 = t1.GetEnd()
            for t2 in tracks2:
                s2 = t2.GetStart()
                e2 = t2.GetEnd()
                if segments_intersect(s1.x,s1.y,e1.x,e1.y, s2.x,s2.y,e2.x,e2.y):
                    crossings.append((t1, t2))

print(f"Cross-net crossings found: {len(crossings)}")

# Strategy: for each crossing, move one track to B.Cu
# Move the track that belongs to the net with fewer total crossings (minimize changes)
# Track which tracks we've already moved
moved = set()

for t1, t2 in crossings:
    # Skip if either already moved
    if id(t1) in moved or id(t2) in moved:
        continue
    
    # Move t2 to B.Cu (add vias at endpoints)
    net = t2.GetNetname()
    netinfo = b.FindNet(net)
    netcode = netinfo.GetNetCode() if netinfo else 0
    
    s = t2.GetStart()
    e = t2.GetEnd()
    
    # Add via at start
    via1 = pcbnew.PCB_VIA(b)
    via1.SetPosition(pcbnew.VECTOR2I(s.x, s.y))
    via1.SetViaType(pcbnew.VIATYPE_THROUGH)
    via1.SetWidth(550000)  # 0.55mm
    via1.SetDrill(300000)  # 0.3mm
    via1.SetNetCode(netcode)
    b.Add(via1)
    
    # Add via at end
    via2 = pcbnew.PCB_VIA(b)
    via2.SetPosition(pcbnew.VECTOR2I(e.x, e.y))
    via2.SetViaType(pcbnew.VIATYPE_THROUGH)
    via2.SetWidth(550000)
    via2.SetDrill(300000)
    via2.SetNetCode(netcode)
    b.Add(via2)
    
    # Move track to B.Cu
    t2.SetLayer(b_cu)
    moved.add(id(t2))

print(f"Moved {len(moved)} tracks to B.Cu (with vias)")

# Fill zones
filler = pcbnew.ZONE_FILLER(b)
zones = list(b.Zones())
if zones:
    filler.Fill(zones)
    print(f"Filled {len(zones)} zones")

# Save
pcbnew.SaveBoard(PATH, b)
print("Saved")

# Verify
b2 = pcbnew.LoadBoard(PATH)
all_tracks = list(b2.GetTracks())
seg = [t for t in all_tracks if t.Type() == pcbnew.PCB_TRACE_T]
vias = [t for t in all_tracks if t.Type() == pcbnew.PCB_VIA_T]
f_count = sum(1 for t in seg if t.GetLayer() == f_cu)
b_count = sum(1 for t in seg if t.GetLayer() == b_cu)
print(f"VERIFIED: {len(seg)} tracks ({f_count} F.Cu, {b_count} B.Cu), {len(vias)} vias")
