#!/usr/bin/env python3.14
"""R0+R2 v2: Route WITHOUT vias. Alternate F.Cu/B.Cu per net to avoid crossings.
GND/3V3 handled by inner-plane zones. No vias at all — avoids zone shorting."""
import pcbnew
import math

BOARD_IN = "output/v5_vias.kicad_pcb"
BOARD_OUT = "output/v5_routed.kicad_pcb"

F_CU = 0
B_CU = 2

W_SIGNAL = int(0.20 * 1e6)
W_POWER  = int(0.40 * 1e6)
W_RF     = int(0.39 * 1e6)

def add_track(board, x1, y1, x2, y2, layer, width, nc):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(pcbnew.VECTOR2I(int(x1), int(y1)))
    t.SetEnd(pcbnew.VECTOR2I(int(x2), int(y2)))
    t.SetLayer(layer)
    t.SetWidth(width)
    t.SetNetCode(nc)
    board.Add(t)
    return (int(x1), int(y1), int(x2), int(y2), layer)

def seg_cross(p1, p2, p3, p4):
    def ccw(A, B, C):
        return (C[1]-A[1])*(B[0]-A[0]) > (B[1]-A[1])*(C[0]-A[0])
    return ccw(p1, p3, p4) != ccw(p2, p3, p4) and ccw(p1, p2, p3) != ccw(p1, p2, p4)

def try_route(board, x0, y0, x1, y1, layer, width, nc, all_segs):
    """Try L-route on given layer. Returns list of segments if success, None if collision."""
    mid_x, mid_y = x1, y0
    seg1 = (x0, y0, mid_x, y0, layer) if x0 != mid_x else None
    seg2 = (mid_x, y0, mid_x, y1, layer) if y0 != y1 else None
    
    for seg in [seg1, seg2]:
        if seg is None:
            continue
        sx1, sy1, sx2, sy2, sl = seg
        for ex in all_segs:
            if ex[4] != sl:
                continue
            if seg_cross((sx1,sy1), (sx2,sy2), (ex[0],ex[1]), (ex[2],ex[3])):
                return None
    # No collision — commit tracks
    result = []
    for seg in [seg1, seg2]:
        if seg:
            s = add_track(board, seg[0], seg[1], seg[2], seg[3], seg[4], width, nc)
            result.append(s)
    return result

# Load board
b = pcbnew.LoadBoard(BOARD_IN)
print(f"Loaded {BOARD_IN}")

# Build net info
from collections import defaultdict
net_pads = defaultdict(list)
net_codes = {}
for i in range(b.GetNetCount()):
    n = b.GetNetInfo().GetNetItem(i)
    if n:
        net_codes[n.GetNetname()] = n.GetNetCode()

for fp in b.GetFootprints():
    ref = fp.GetReference()
    for p in fp.Pads():
        nn = p.GetNetname()
        if nn:
            pos = p.GetPosition()
            net_pads[nn].append((ref, p.GetPadName(), pos.x, pos.y))

all_segs = []
total_tracks = 0

# ===== R0: RF TRACES (50-ohm, F.Cu, direct path) =====
print("\n=== R0: RF TRACES (50Ω) ===")
rf_nets = ["RF_SUB_868", "RF_2G4_2400"]
for rn in rf_nets:
    pads = net_pads.get(rn, [])
    if len(pads) < 2:
        continue
    nc = net_codes.get(rn, 0)
    ref0, p0, x0, y0 = pads[0]
    ref1, p1, x1, y1 = pads[1]
    seg = add_track(b, x0, y0, x1, y1, F_CU, W_RF, nc)
    all_segs.append(seg)
    total_tracks += 1
    print(f"  {rn}: {ref0}.{p0} → {ref1}.{p1} ({abs(x1-x0)/1e6:.1f}x{abs(y1-y0)/1e6:.1f}mm)")

# ===== R2: SIGNAL NETS (alternate layers, no vias) =====
print("\n=== R2: SIGNAL ROUTING (no vias) ===")
power_nets = {"GND", "3V3"}
signal_nets = [n for n in sorted(net_pads.keys()) if n not in power_nets and n not in rf_nets]

widths = {
    "SOLAR_IN": W_POWER,
    "VCAP": W_POWER,
    "LED_ANODE": W_SIGNAL,
    "VDIV_MID": W_SIGNAL,
}

# Alternate layers: even nets on F.Cu, odd on B.Cu
for idx, sn in enumerate(signal_nets):
    pads = net_pads.get(sn, [])
    if len(pads) < 2:
        continue
    nc = net_codes.get(sn, 0)
    w = widths.get(sn, W_SIGNAL)
    
    routed = False
    ref0, p0, x0, y0 = pads[0]
    
    for i in range(1, len(pads)):
        ref1, p1, x1, y1 = pads[i]
        
        # Try F.Cu first, then B.Cu
        for layer in [F_CU, B_CU]:
            segs = try_route(b, x0, y0, x1, y1, layer, w, nc, all_segs)
            if segs:
                all_segs.extend(segs)
                total_tracks += len(segs)
                routed = True
                break
        
        if not routed and i < len(pads):
            # Try B.Cu with different L-direction (vertical-first)
            mid_x, mid_y = x0, y1
            seg1 = (x0, y0, x0, y1, B_CU) if y0 != y1 else None
            seg2 = (x0, y1, x1, y1, B_CU) if x0 != x1 else None
            collision = False
            for seg in [seg1, seg2]:
                if seg is None: continue
                for ex in all_segs:
                    if ex[4] != seg[4]: continue
                    if seg_cross((seg[0],seg[1]),(seg[2],seg[3]),(ex[0],ex[1]),(ex[2],ex[3])):
                        collision = True
                        break
                if collision: break
            if not collision:
                for seg in [seg1, seg2]:
                    if seg:
                        s = add_track(b, seg[0],seg[1],seg[2],seg[3],seg[4], w, nc)
                        all_segs.append(s)
                        total_tracks += 1
                routed = True
    
    status = "OK" if routed else "FAILED"
    print(f"  {sn}: {status}")

print(f"\nTotal tracks: {total_tracks}")
pcbnew.SaveBoard(BOARD_OUT, b)
print(f"Saved {BOARD_OUT}")

b2 = pcbnew.LoadBoard(BOARD_OUT)
trks = sum(1 for t in b2.GetTracks() if t.GetClass() == 'PCB_TRACK')
print(f"Verify: {trks} tracks, {len(list(b2.Zones()))} zones")
