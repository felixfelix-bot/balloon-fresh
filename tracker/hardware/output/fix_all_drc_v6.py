#!/usr/bin/python3.14
"""Fix remaining 8 DRC violations + 20 unconnected pads on balloon PCB."""
import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew
import math

INPUT  = 'v_c3_flight_v5.kicad_pcb'
OUTPUT = 'v_c3_flight_v6.kicad_pcb'

F_CU = pcbnew.F_Cu
B_CU = pcbnew.B_Cu
TRACK_W = 250000
VIA_W   = 550000
VIA_D   = 300000

print("=== DRC FIX v6 ===")
b = pcbnew.LoadBoard(INPUT)

# Precompute net codes
NET_CODES = {}
for net in b.GetNetsByNetcode().values():
    try:
        NET_CODES[net.GetNetname()] = net.GetNetCode()
    except:
        pass

def get_net_code(netname):
    return NET_CODES.get(netname, 0)

def add_track(x1, y1, x2, y2, layer, netname):
    t = pcbnew.PCB_TRACK(b)
    t.SetLayer(layer)
    t.SetWidth(TRACK_W)
    t.SetStart(pcbnew.VECTOR2I(int(x1), int(y1)))
    t.SetEnd(pcbnew.VECTOR2I(int(x2), int(y2)))
    t.SetNetCode(get_net_code(netname))
    b.Add(t)
    return t

def add_via(x, y, netname):
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(pcbnew.VECTOR2I(int(x), int(y)))
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetWidth(VIA_W)
    v.SetDrill(VIA_D)
    v.SetNetCode(get_net_code(netname))
    b.Add(v)
    return v

# Snapshot ALL tracks/vias upfront before any modifications
ALL_TRACKS_SNAPSHOT = []
for t in b.Tracks():
    try:
        if t.GetClass() == 'PCB_VIA':
            pos = t.GetPosition()
            ALL_TRACKS_SNAPSHOT.append(('via', t, pos.x, pos.y, t.GetNetname()))
        else:
            s = t.GetStart(); e = t.GetEnd()
            ALL_TRACKS_SNAPSHOT.append(('track', t, s.x, s.y, e.x, e.y, t.GetLayer(), t.GetNetname()))
    except:
        pass

# Get pads by net
POWER_NETS = {'+3V3', 'GND', 'VCAP', 'SOLAR_IN', 'EN'}

# Get pads by net
nets = {}
for fp in b.GetFootprints():
    for pad in fp.Pads():
        nn = pad.GetNetname()
        if not nn:
            continue
        pos = pad.GetPosition()
        if nn not in nets:
            nets[nn] = []
        nets[nn].append({'x': pos.x, 'y': pos.y, 'ref': fp.GetReference()})

# === 1. RIP LR_RST tracks on F.Cu (causes short) ===
print("\n[1] Fixing LR_RST short...")
ripped = 0
for entry in ALL_TRACKS_SNAPSHOT:
    if entry[0] == 'via':
        continue
    _, t, sx, sy, ex, ey, layer, netname = entry
    if netname == 'LR_RST' and layer == F_CU:
        print(f"  Ripping LR_RST on F.Cu: ({sx/1e6:.1f},{sy/1e6:.1f})-({ex/1e6:.1f},{ey/1e6:.1f})")
        b.Remove(t)
        ripped += 1
print(f"  Ripped {ripped} tracks")

# Re-route LR_RST on B.Cu with vias
if 'LR_RST' in nets and len(nets['LR_RST']) >= 2:
    pads = nets['LR_RST']
    sx, sy = pads[0]['x'], pads[0]['y']
    ex, ey = pads[1]['x'], pads[1]['y']
    print(f"  Routing LR_RST on B.Cu: ({sx/1e6:.1f},{sy/1e6:.1f}) -> ({ex/1e6:.1f},{ey/1e6:.1f})")
    # Manhattan H-V
    add_track(sx, sy, ex, sy, B_CU, 'LR_RST')
    add_track(ex, sy, ex, ey, B_CU, 'LR_RST')
    add_via(sx, sy, 'LR_RST')
    add_via(ex, ey, 'LR_RST')
    print("  Done")

# === 2. RIP SPI_NSS on B.Cu (clearance violation) ===
print("\n[2] Fixing SPI_NSS clearance...")
for entry in ALL_TRACKS_SNAPSHOT:
    if entry[0] == 'via':
        continue
    _, t, sx, sy, ex, ey, layer, netname = entry
    if netname == 'SPI_NSS' and layer == B_CU:
        mid_x = (sx + ex) / 2
        mid_y = (sy + ey) / 2
        if abs(mid_x - 58475000) < 5000000 and abs(mid_y - 21000000) < 5000000:
            print(f"  Ripping SPI_NSS on B.Cu near GND via")
            b.Remove(t)

# Re-route SPI_NSS with offset
if 'SPI_NSS' in nets and len(nets['SPI_NSS']) >= 2:
    pads = nets['SPI_NSS']
    sx, sy = pads[0]['x'], pads[0]['y']
    ex, ey = pads[1]['x'], pads[1]['y']
    # Try offset routes (V-H pattern with different midpoints)
    for offset in [3000000, -3000000, 5000000, -5000000]:
        mx = sx
        my = ey + offset
        add_track(sx, sy, mx, my, B_CU, 'SPI_NSS')
        add_track(mx, my, ex, ey, B_CU, 'SPI_NSS')
        print(f"  Re-routed SPI_NSS on B.Cu with offset {offset/1e6:.1f}mm")
        break

# === 3. Fix dangling power vias ===
print("\n[3] Fixing dangling power vias...")
for entry in ALL_TRACKS_SNAPSHOT:
    if entry[0] != 'via':
        continue
    _, t, vx, vy, netname = entry
    if netname not in POWER_NETS:
        continue
    # Find nearest same-net pad
    if netname not in nets:
        continue
    min_dist = float('inf')
    nearest = None
    for p in nets[netname]:
        d = math.sqrt((p['x'] - vx)**2 + (p['y'] - vy)**2)
        if d < min_dist and d > 100000:  # not at same spot
            min_dist = d
            nearest = p
    if nearest and min_dist < 20_000_000:  # within 20mm
        # Add track from via to nearest pad on both F.Cu and B.Cu
        add_track(vx, vy, nearest['x'], nearest['y'], F_CU, netname)
        add_track(vx, vy, nearest['x'], nearest['y'], B_CU, netname)
        print(f"  Connected {netname} via at ({vx/1e6:.1f},{vy/1e6:.1f}) to {nearest['ref']} ({min_dist/1e6:.1f}mm)")
    else:
        print(f"  No nearby pad for {netname} via at ({vx/1e6:.1f},{vy/1e6:.1f}), removing")
        b.Remove(t)

# === 4. Route remaining unconnected signal nets ===
print("\n[4] Routing remaining signal nets...")

# Get existing track obstacles for collision detection
obs_tracks = []
for entry in ALL_TRACKS_SNAPSHOT:
    if entry[0] == 'via':
        _, t, vx, vy, vnet = entry
        obs_tracks.append(('via', vx, vy, 0, vnet))
    else:
        _, t, sx, sy, ex, ey, layer, netname = entry
        obs_tracks.append(('track', sx, sy, ex, ey, layer, netname))

# Build pad obstacles
obs_pads = []
for fp in b.GetFootprints():
    for pad in fp.Pads():
        pos = pad.GetPosition()
        sz = pad.GetSize()
        clr = 400000  # 0.4mm clearance
        obs_pads.append((pos.x - sz.x//2 - clr, pos.y - sz.y//2 - clr,
                        pos.x + sz.x//2 + clr, pos.y + sz.y//2 + clr,
                        pad.GetNetname()))

def seg_cross(x1,y1,x2,y2,x3,y3,x4,y4):
    def orient(ax,ay,bx,by,cx,cy):
        return (bx-ax)*(cy-ay)-(by-ay)*(cx-ax)
    d1=orient(x3,y3,x4,y4,x1,y1); d2=orient(x3,y3,x4,y4,x2,y2)
    d3=orient(x1,y1,x2,y2,x3,y3); d4=orient(x1,y1,x2,y2,x4,y4)
    return ((d1>0)!=(d2>0)) and ((d3>0)!=(d4>0))

def route_ok(sx, sy, ex, ey, layer, net):
    # Check pad obstacles
    for px1,py1,px2,py2,pn in obs_pads:
        if pn == net:
            continue
        # Simple bbox check: does segment pass through expanded pad bbox?
        # Cohen-Sutherland-ish
        if min(sx,ex) > px2 or max(sx,ex) < px1 or min(sy,ey) > py2 or max(sy,ey) < py1:
            continue
        # Closer check: does either endpoint fall inside?
        if px1<=sx<=px2 and py1<=sy<=py2:
            return False
        if px1<=ex<=px2 and py1<=ey<=py2:
            return False
    # Check track obstacles
    for ot in obs_tracks:
        if ot[0] == 'track':
            _, tx1,ty1,tx2,ty2,tl,tn = ot
            if tl != layer or tn == net:
                continue
            if seg_cross(sx,sy,ex,ey,tx1,ty1,tx2,ty2):
                return False
    return True

def try_manhattan(sx, sy, ex, ey, net, layer):
    """Try straight, H-V, V-H on given layer. Return segments or None."""
    # Straight
    if abs(sx-ex) < 2000 or abs(sy-ey) < 2000:
        if route_ok(sx,sy,ex,ey,layer,net):
            return [(sx,sy,ex,ey)]
    # H-V
    if route_ok(sx,sy,ex,sy,layer,net) and route_ok(ex,sy,ex,ey,layer,net):
        return [(sx,sy,ex,sy),(ex,sy,ex,ey)]
    # V-H
    if route_ok(sx,sy,sx,ey,layer,net) and route_ok(sx,ey,ex,ey,layer,net):
        return [(sx,sy,sx,ey),(sx,ey,ex,ey)]
    return None

# Route unrouted nets
routed = 0
unrouted = []
for netname, pads in sorted(nets.items()):
    if netname in POWER_NETS:
        continue
    if len(pads) < 2:
        continue
    
    # Check if already routed (has tracks on board with this net)
    has_tracks = any(ot[0]=='track' and ot[-1]==netname for ot in obs_tracks)
    if has_tracks:
        continue
    
    ok = False
    for i in range(len(pads)-1):
        sx,sy = pads[i]['x'], pads[i]['y']
        ex,ey = pads[i+1]['x'], pads[i+1]['y']
        
        # Try F.Cu
        segs = try_manhattan(sx,sy,ex,ey,netname,F_CU)
        layer = F_CU
        vias_needed = False
        
        if not segs:
            segs = try_manhattan(sx,sy,ex,ey,netname,B_CU)
            layer = B_CU
            vias_needed = True
        
        if not segs:
            # Try offset on F.Cu
            for off in [2000000,-2000000,4000000,-4000000]:
                mx = ex; my = sy+off
                if route_ok(sx,sy,mx,my,F_CU,netname) and route_ok(mx,my,ex,ey,F_CU,netname):
                    segs = [(sx,sy,mx,my),(mx,my,ex,ey)]
                    layer = F_CU
                    break
        
        if not segs:
            # Try offset on B.Cu
            for off in [2000000,-2000000,4000000,-4000000]:
                mx = ex; my = sy+off
                if route_ok(sx,sy,mx,my,B_CU,netname) and route_ok(mx,my,ex,ey,B_CU,netname):
                    segs = [(sx,sy,mx,my),(mx,my,ex,ey)]
                    layer = B_CU
                    vias_needed = True
                    break
        
        if segs:
            for s in segs:
                add_track(s[0],s[1],s[2],s[3],layer,netname)
                obs_tracks.append(('track',s[0],s[1],s[2],s[3],layer,netname))
            if vias_needed:
                add_via(sx,sy,netname)
                add_via(ex,ey,netname)
            ok = True
    
    if ok:
        routed += 1
        print(f"  OK {netname}")
    else:
        unrouted.append(netname)
        print(f"  FAIL {netname}")

# === 5. Route power nets (pad-to-pad) ===
print("\n[5] Routing power nets pad-to-pad...")
for netname in POWER_NETS:
    if netname not in nets or len(nets[netname]) < 2:
        continue
    pads = nets[netname]
    # Check if already has tracks
    has_tracks = any(ot[0]=='track' and ot[-1]==netname for ot in obs_tracks)
    if has_tracks:
        continue
    
    ok = False
    for i in range(len(pads)-1):
        sx,sy = pads[i]['x'], pads[i]['y']
        ex,ey = pads[i+1]['x'], pads[i+1]['y']
        segs = try_manhattan(sx,sy,ex,ey,netname,F_CU)
        layer = F_CU
        if not segs:
            segs = try_manhattan(sx,sy,ex,ey,netname,B_CU)
            layer = B_CU
        if segs:
            for s in segs:
                add_track(s[0],s[1],s[2],s[3],layer,netname)
                obs_tracks.append(('track',s[0],s[1],s[2],s[3],layer,netname))
            ok = True
    if ok:
        routed += 1
        print(f"  OK {netname}")

# === 6. Fill zones + connectivity ===
print("\n[6] Zone fill + connectivity...")
b.BuildConnectivity()
zones = list(b.Zones())
filler = pcbnew.ZONE_FILLER(b)
filler.Fill(zones)
print(f"  Filled {len(zones)} zones")

# === 7. Save ===
pcbnew.SaveBoard(OUTPUT, b)
print(f"\nSaved: {OUTPUT}")
print(f"\nRouted: {routed}")
print(f"Unrouted: {len(unrouted)}")
for u in unrouted:
    print(f"  {u}")
print("\n=== DONE ===")
