#!/usr/bin/env python3
"""Re-route C3 flight PCB with FULL collision detection: pads + tracks."""
import sys; sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew, math

PATH = '/home/c03rad0r/repos/balloon-fresh/tracker/hardware/output/v_c3_flight_final.kicad_pcb'
F_CU = pcbnew.F_Cu
B_CU = pcbnew.B_Cu
TRACK_W = 250000  # 0.25mm
CLEAR = 220000    # 0.22mm clearance

b = pcbnew.LoadBoard(PATH)

# Step 1: Remove ALL existing tracks and vias
for t in list(b.GetTracks()):
    b.Remove(t)
print("Ripped all tracks")

# Step 2: Collect pads by net
nets = {}
for fp in b.GetFootprints():
    for pad in fp.Pads():
        nn = pad.GetNetname()
        if not nn:
            continue
        if nn not in nets:
            nets[nn] = []
        pos = pad.GetPosition()
        nets[nn].append({'ref': fp.GetReference(), 'pos': (pos.x, pos.y), 'pad': pad})

# Step 3: Build obstacle map — all pads as bounding boxes
POWER_NETS = {'+3V3', 'GND', 'VCAP', 'SOLAR_IN', 'EN'}
obstacle_pads = []  # [(x1,y1,x2,y2,netname)]
for fp in b.GetFootprints():
    for pad in fp.Pads():
        pos = pad.GetPosition()
        sz = pad.GetSize()
        x1 = pos.x - sz.x//2 - CLEAR
        y1 = pos.y - sz.y//2 - CLEAR
        x2 = pos.x + sz.x//2 + CLEAR
        y2 = pos.y + sz.y//2 + CLEAR
        obstacle_pads.append((x1, y1, x2, y2, pad.GetNetname()))

# Step 4: Track collision detection
existing_tracks = []  # [(x1,y1,x2,y2,layer,netname)]

def seg_cross(x1,y1,x2,y2, x3,y3,x4,y4, margin=0):
    """Check if segments (x1,y1)-(x2,y2) and (x3,y3)-(x4,y4) cross, with margin."""
    # Bounding box check with margin
    if max(x1,x2)+margin < min(x3,x4)-margin or min(x1,x2)-margin > max(x3,x4)+margin:
        return False
    if max(y1,y2)+margin < min(y3,y4)-margin or min(y1,y1)-margin > max(y3,y4)+margin:
        return False
    # CCW orientation test
    def orient(ax,ay,bx,by,cx,cy):
        return (bx-ax)*(cy-ay) - (by-ay)*(cx-ax)
    d1 = orient(x3,y3,x4,y4,x1,y1)
    d2 = orient(x3,y3,x4,y4,x2,y2)
    d3 = orient(x1,y1,x2,y2,x3,y3)
    d4 = orient(x1,y1,x2,y2,x4,y4)
    if ((d1>0 and d2<0) or (d1<0 and d2>0)) and ((d3>0 and d4<0) or (d3<0 and d4>0)):
        return True
    # Collinear endpoint check (shared endpoints at pads are OK)
    return False

def pad_collision(x1,y1,x2,y2, my_net):
    """Check if segment hits any foreign pad."""
    for px1,py1,px2,py2,pnet in obstacle_pads:
        if pnet == my_net:
            continue
        # Check if segment passes through pad bbox
        # Line-box intersection: check if segment enters the box
        if seg_cross(x1,y1,x2,y2, px1,py1,px2,py1) or \
           seg_cross(x1,y1,x2,y2, px1,py1,px1,py2) or \
           seg_cross(x1,y1,x2,y2, px2,py1,px2,py2) or \
           seg_cross(x1,y1,x2,y2, px1,py2,px2,py2):
            return True
        # Also check if either endpoint is inside pad
        if px1 <= x1 <= px2 and py1 <= y1 <= py2:
            return True
        if px1 <= x2 <= px2 and py1 <= y2 <= py2:
            return True
    return False

def track_collision(x1,y1,x2,y2, layer, my_net):
    """Check if segment crosses any existing track of different net on same layer."""
    for ex1,ey1,ex2,ey2,el,en in existing_tracks:
        if el != layer or en == my_net:
            continue
        if seg_cross(x1,y1,x2,y2, ex1,ey1,ex2,ey2):
            return True
    return False

def try_route(sx, sy, ex, ey, netname, layer):
    """Try to route from (sx,sy) to (ex,ey). Returns list of track segments or None."""
    # Try straight line
    if abs(sx-ex) < 1000 or abs(sy-ey) < 1000:
        if not pad_collision(sx,sy,ex,ey, netname) and not track_collision(sx,sy,ex,ey, layer, netname):
            return [(sx,sy,ex,ey)]
        return None
    
    # Try L-shape option 1: H then V
    mid = (ex, sy)
    ok1 = not pad_collision(sx,sy,mid[0],mid[1], netname) and not track_collision(sx,sy,mid[0],mid[1], layer, netname)
    ok2 = not pad_collision(mid[0],mid[1],ex,ey, netname) and not track_collision(mid[0],mid[1],ex,ey, layer, netname)
    if ok1 and ok2:
        return [(sx,sy,mid[0],mid[1]), (mid[0],mid[1],ex,ey)]
    
    # Try L-shape option 2: V then H
    mid = (sx, ey)
    ok1 = not pad_collision(sx,sy,mid[0],mid[1], netname) and not track_collision(sx,sy,mid[0],mid[1], layer, netname)
    ok2 = not pad_collision(mid[0],mid[1],ex,ey, netname) and not track_collision(mid[0],mid[1],ex,ey, layer, netname)
    if ok1 and ok2:
        return [(sx,sy,mid[0],mid[1]), (mid[0],mid[1],ex,ey)]
    
    return None

# Step 5: Route all signal nets
track_count = 0
via_count = 0
unrouted = []

for netname, pads in sorted(nets.items()):
    if netname in POWER_NETS:
        continue  # plane-connected
    if len(pads) < 2:
        continue
    
    # Route each pad pair (chain routing)
    routed_this_net = False
    for i in range(len(pads) - 1):
        sx, sy = pads[i]['pos']
        ex, ey = pads[i+1]['pos']
        
        # Try F.Cu first
        segs = try_route(sx, sy, ex, ey, netname, F_CU)
        used_layer = F_CU
        
        if not segs:
            # Try B.Cu
            segs = try_route(sx, sy, ex, ey, netname, B_CU)
            used_layer = B_CU
            # Need vias at both ends
            if segs:
                netinfo = b.FindNet(netname)
                nc = netinfo.GetNetCode() if netinfo else 0
                for vx, vy in [(sx, sy), (ex, ey)]:
                    via = pcbnew.PCB_VIA(b)
                    via.SetPosition(pcbnew.VECTOR2I(vx, vy))
                    via.SetViaType(pcbnew.VIATYPE_THROUGH)
                    via.SetWidth(550000)
                    via.SetDrill(300000)
                    via.SetNetCode(nc)
                    b.Add(via)
                    via_count += 1
        
        if segs:
            for sx2,sy2,ex2,ey2 in segs:
                t = pcbnew.PCB_TRACK(b)
                t.SetLayer(used_layer)
                t.SetWidth(TRACK_W)
                t.SetStart(pcbnew.VECTOR2I(sx2, sy2))
                t.SetEnd(pcbnew.VECTOR2I(ex2, ey2))
                b.Add(t)
                existing_tracks.append((sx2,sy2,ex2,ey2,used_layer,netname))
                track_count += 1
            routed_this_net = True
        else:
            unrouted.append(netname)

    if routed_this_net:
        print(f"  Routed: {netname}")
    else:
        print(f"  FAILED: {netname}")

# Step 6: Thermal vias for power nets
for netname in POWER_NETS:
    if netname not in nets:
        continue
    netinfo = b.FindNet(netname)
    nc = netinfo.GetNetCode() if netinfo else 0
    for p in nets[netname]:
        via = pcbnew.PCB_VIA(b)
        via.SetPosition(pcbnew.VECTOR2I(p['pos'][0], p['pos'][1]))
        via.SetViaType(pcbnew.VIATYPE_THROUGH)
        via.SetWidth(550000)
        via.SetDrill(300000)
        via.SetNetCode(nc)
        b.Add(via)
        via_count += 1
    print(f"  [POWER] {netname}: {len(nets[netname])} thermal vias")

# Step 7: Fill zones
filler = pcbnew.ZONE_FILLER(b)
zones = list(b.Zones())
if zones:
    filler.Fill(zones)

# Step 8: Save
pcbnew.SaveBoard(PATH, b)

# Step 9: Verify
b2 = pcbnew.LoadBoard(PATH)
all_t = list(b2.GetTracks())
seg = [t for t in all_t if t.Type() == pcbnew.PCB_TRACE_T]
vias = [t for t in all_t if t.Type() == pcbnew.PCB_VIA_T]
print(f"\nVERIFIED: {len(seg)} tracks, {len(vias)} vias")
print(f"Unrouted nets: {len(unrouted)}")
for u in unrouted:
    print(f"  {u}")
