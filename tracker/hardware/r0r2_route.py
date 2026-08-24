#!/usr/bin/env python3.14
"""R0+R2: Route RF traces (50Ω) first, then signal nets with collision-aware Manhattan routing.
GND/3V3 handled by inner-plane zones + thermal vias. Only signal/RF tracks here."""
import pcbnew
import math

BOARD_IN = "output/v5_vias.kicad_pcb"
BOARD_OUT = "output/v5_routed.kicad_pcb"

F_CU = 0
B_CU = 2

W_SIGNAL = int(0.20 * 1e6)
W_POWER  = int(0.40 * 1e6)
W_RF     = int(0.39 * 1e6)  # 50-ohm microstrip on 4-layer JLCPCB stackup

VIA_DRILL = int(0.3 * 1e6)
VIA_SIZE  = int(0.6 * 1e6)

def add_track(board, x1, y1, x2, y2, layer, width, nc):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(pcbnew.VECTOR2I(int(x1), int(y1)))
    t.SetEnd(pcbnew.VECTOR2I(int(x2), int(y2)))
    t.SetLayer(layer)
    t.SetWidth(width)
    t.SetNetCode(nc)
    board.Add(t)
    return (int(x1), int(y1), int(x2), int(y2), layer)

def add_via(board, x, y, nc):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pcbnew.VECTOR2I(int(x), int(y)))
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetDrill(VIA_DRILL)
    v.SetWidth(VIA_SIZE)
    v.SetNetCode(nc)
    v.SetLayerPair(F_CU, B_CU)
    board.Add(v)

def seg_cross(p1, p2, p3, p4):
    """Check if segment p1-p2 crosses segment p3-p4 (all (x,y) tuples)."""
    def ccw(A, B, C):
        return (C[1]-A[1])*(B[0]-A[0]) > (B[1]-A[1])*(C[0]-A[0])
    return ccw(p1, p3, p4) != ccw(p2, p3, p4) and ccw(p1, p2, p3) != ccw(p1, p2, p4)

def route_net(board, pads, layer, width, nc, existing_segs):
    """Route L-shaped track from pads[0] to each other pad. Returns (track_segs, via_count)."""
    new_segs = []
    vias = 0
    ref0, p0, x0, y0 = pads[0]
    for i in range(1, len(pads)):
        ref1, p1, x1, y1 = pads[i]
        # Try horizontal-then-vertical L-route
        mid_x, mid_y = x1, y0
        # Build segments for this route
        seg1 = (x0, y0, mid_x, y0, layer) if x0 != mid_x else None
        seg2 = (mid_x, y0, mid_x, y1, layer) if y0 != y1 else None
        
        # Check collision against existing segments
        collision = False
        for seg in [seg1, seg2]:
            if seg is None:
                continue
            sx1, sy1, sx2, sy2, sl = seg
            for ex in existing_segs + new_segs:
                if ex[4] != sl:
                    continue
                if seg_cross((sx1,sy1), (sx2,sy2), (ex[0],ex[1]), (ex[2],ex[3])):
                    collision = True
                    break
            if collision:
                break
        
        if collision:
            # Try B.Cu with via at both endpoints
            alt_layer = B_CU if layer == F_CU else F_CU
            seg1 = (x0, y0, mid_x, y0, alt_layer) if x0 != mid_x else None
            seg2 = (mid_x, y0, mid_x, y1, alt_layer) if y0 != y1 else None
            # Re-check collision on alternate layer
            alt_collision = False
            for seg in [seg1, seg2]:
                if seg is None:
                    continue
                sx1, sy1, sx2, sy2, sl = seg
                for ex in existing_segs + new_segs:
                    if ex[4] != sl:
                        continue
                    if seg_cross((sx1,sy1), (sx2,sy2), (ex[0],ex[1]), (ex[2],ex[3])):
                        alt_collision = True
                        break
                if alt_collision:
                    break
            if alt_collision:
                # Skip this connection
                continue
            # Place vias and route on alternate layer
            add_via(board, x0, y0, nc)
            add_via(board, x1, y1, nc)
            vias += 2
            for seg in [seg1, seg2]:
                if seg:
                    s = add_track(board, seg[0], seg[1], seg[2], seg[3], seg[4], width, nc)
                    new_segs.append(s)
        else:
            # Route on preferred layer
            for seg in [seg1, seg2]:
                if seg:
                    s = add_track(board, seg[0], seg[1], seg[2], seg[3], seg[4], width, nc)
                    new_segs.append(s)
    return new_segs, vias

# ===== LOAD BOARD =====
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

all_segs = []  # all track segments for collision detection
total_vias = 0
total_tracks = 0

# ===== R0: RF TRACES (50-ohm microstrip on F.Cu) =====
print("\n=== R0: RF TRACES ===")
rf_nets = ["RF_SUB_868", "RF_2G4_2400"]
for rn in rf_nets:
    pads = net_pads.get(rn, [])
    if len(pads) < 2:
        print(f"  {rn}: only {len(pads)} pads, skipping")
        continue
    nc = net_codes.get(rn, 0)
    ref0, p0, x0, y0 = pads[0]
    ref1, p1, x1, y1 = pads[1]
    # Direct track (shortest path) — RF needs straight trace
    seg = add_track(b, x0, y0, x1, y1, F_CU, W_RF, nc)
    all_segs.append(seg)
    total_tracks += 1
    print(f"  {rn}: {ref0}.{p0} -> {ref1}.{p1} ({abs(x1-x0)/1e6:.1f}x{abs(y1-y0)/1e6:.1f}mm, 50Ω)")

# Add ground stitching vias at both ends of each RF trace
for rn in rf_nets:
    pads = net_pads.get(rn, [])
    if len(pads) < 2:
        continue
    nc = net_codes.get("GND", 0)
    for ref0, p0, x0, y0 in pads[:2]:
        # Place 2 ground vias near each RF pad (offset 0.5mm perpendicular)
        for dy in [int(0.6e6), int(-0.6e6)]:
            # Check it's not on a pad
            gx, gy = x0, y0 + dy
            clear = True
            for fp in b.GetFootprints():
                for p in fp.Pads():
                    pp = p.GetPosition()
                    if abs(pp.x - gx) < int(0.5e6) and abs(pp.y - gy) < int(0.5e6):
                        clear = False
                        break
                if not clear:
                    break
            if clear:
                add_via(b, gx, gy, nc)
                total_vias += 1
print(f"  Ground stitching vias added")

# ===== R2: SIGNAL NETS (Manhattan routing with collision detection) =====
print("\n=== R2: SIGNAL ROUTING ===")
power_nets = {"GND", "3V3"}
signal_nets = [n for n in sorted(net_pads.keys()) if n not in power_nets and n not in rf_nets]

widths = {
    "SOLAR_IN": W_POWER,
    "VCAP": W_POWER,
    "LED_ANODE": W_SIGNAL,
    "VDIV_MID": W_SIGNAL,
}
# Default signal width for everything else

for sn in signal_nets:
    pads = net_pads.get(sn, [])
    if len(pads) < 2:
        continue
    nc = net_codes.get(sn, 0)
    w = widths.get(sn, W_SIGNAL)
    segs, vias = route_net(b, pads, F_CU, w, nc, all_segs)
    all_segs.extend(segs)
    total_tracks += len(segs)
    total_vias += vias
    if segs:
        print(f"  {sn}: {len(segs)} segments, {vias} vias")
    else:
        print(f"  {sn}: NOT ROUTED (collision)")

print(f"\n=== ROUTING SUMMARY ===")
print(f"Total tracks: {total_tracks}")
print(f"Total vias: {total_vias}")

pcbnew.SaveBoard(BOARD_OUT, b)
print(f"Saved {BOARD_OUT}")

# Verify
b2 = pcbnew.LoadBoard(BOARD_OUT)
tracks = list(b2.GetTracks())
vias = sum(1 for t in tracks if t.GetClass() == 'PCB_VIA')
trks = sum(1 for t in tracks if t.GetClass() == 'PCB_TRACK')
print(f"Verify: {trks} tracks, {vias} vias, {len(list(b2.Zones()))} zones, {len(list(b2.GetFootprints()))} footprints")
