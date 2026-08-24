#!/usr/bin/env python3
"""Re-route C3 flight PCB: full collision-aware (pads + tracks + B.Cu fallback)."""
import sys; sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew

PATH = '/home/c03rad0r/repos/balloon-fresh/tracker/hardware/output/v_c3_flight_final.kicad_pcb'
F_CU = pcbnew.F_Cu
B_CU = pcbnew.B_Cu
TRACK_W = 250000
CLEAR = 220000

b = pcbnew.LoadBoard(PATH)

# Rip all tracks
for t in list(b.GetTracks()):
    b.Remove(t)

# Collect pads by net
nets = {}
for fp in b.GetFootprints():
    for pad in fp.Pads():
        nn = pad.GetNetname()
        if not nn:
            continue
        if nn not in nets:
            nets[nn] = []
        pos = pad.GetPosition()
        nets[nn].append({'pos': (pos.x, pos.y), 'ref': fp.GetReference()})

POWER_NETS = {'+3V3', 'GND', 'VCAP', 'SOLAR_IN', 'EN'}

# Pad obstacles
obs_pads = []
for fp in b.GetFootprints():
    for pad in fp.Pads():
        pos = pad.GetPosition()
        sz = pad.GetSize()
        obs_pads.append((pos.x - sz.x // 2 - CLEAR, pos.y - sz.y // 2 - CLEAR,
                         pos.x + sz.x // 2 + CLEAR, pos.y + sz.y // 2 + CLEAR,
                         pad.GetNetname()))

existing = []  # (x1,y1,x2,y2,layer,net)


def orient(ax, ay, bx, by, cx, cy):
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def seg_cross(x1, y1, x2, y2, x3, y3, x4, y4):
    d1 = orient(x3, y3, x4, y4, x1, y1)
    d2 = orient(x3, y3, x4, y4, x2, y2)
    d3 = orient(x1, y1, x2, y2, x3, y3)
    d4 = orient(x1, y1, x2, y2, x4, y4)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


def pad_ok(sx, sy, ex, ey, net):
    for px1, py1, px2, py2, pn in obs_pads:
        if pn == net:
            continue
        if px1 <= sx <= px2 and py1 <= sy <= py2:
            return False
        if px1 <= ex <= px2 and py1 <= ey <= py2:
            return False
        if seg_cross(sx, sy, ex, ey, px1, py1, px2, py1):
            return False
        if seg_cross(sx, sy, ex, ey, px1, py2, px2, py2):
            return False
        if seg_cross(sx, sy, ex, ey, px1, py1, px1, py2):
            return False
        if seg_cross(sx, sy, ex, ey, px2, py1, px2, py2):
            return False
    return True


def trk_ok(sx, sy, ex, ey, layer, net):
    for ex1, ey1, ex2, ey2, el, en in existing:
        if el != layer or en == net:
            continue
        if seg_cross(sx, sy, ex, ey, ex1, ey1, ex2, ey2):
            return False
    return True


def try_l(sx, sy, ex, ey, net, layer):
    # Straight line
    if abs(sx - ex) < 2000 or abs(sy - ey) < 2000:
        if pad_ok(sx, sy, ex, ey, net) and trk_ok(sx, sy, ex, ey, layer, net):
            return [(sx, sy, ex, ey)]
    # L1: H then V
    mx, my = ex, sy
    if pad_ok(sx, sy, mx, my, net) and trk_ok(sx, sy, mx, my, layer, net) and \
       pad_ok(mx, my, ex, ey, net) and trk_ok(mx, my, ex, ey, layer, net):
        return [(sx, sy, mx, my), (mx, my, ex, ey)]
    # L2: V then H
    mx, my = sx, ey
    if pad_ok(sx, sy, mx, my, net) and trk_ok(sx, sy, mx, my, layer, net) and \
       pad_ok(mx, my, ex, ey, net) and trk_ok(mx, my, ex, ey, layer, net):
        return [(sx, sy, mx, my), (mx, my, ex, ey)]
    return None


tc = vc = 0
unrouted = []

for netname, pads in sorted(nets.items()):
    if netname in POWER_NETS or len(pads) < 2:
        continue
    ok = False
    for i in range(len(pads) - 1):
        sx, sy = pads[i]['pos']
        ex, ey = pads[i + 1]['pos']

        segs = try_l(sx, sy, ex, ey, netname, F_CU)
        layer = F_CU
        if not segs:
            segs = try_l(sx, sy, ex, ey, netname, B_CU)
            layer = B_CU
            if segs:
                ni = b.FindNet(netname)
                nc = ni.GetNetCode() if ni else 0
                for vx, vy in [(sx, sy), (ex, ey)]:
                    v = pcbnew.PCB_VIA(b)
                    v.SetPosition(pcbnew.VECTOR2I(vx, vy))
                    v.SetViaType(pcbnew.VIATYPE_THROUGH)
                    v.SetWidth(550000)
                    v.SetDrill(300000)
                    v.SetNetCode(nc)
                    b.Add(v)
                    vc += 1

        if segs:
            for s in segs:
                t = pcbnew.PCB_TRACK(b)
                t.SetLayer(layer)
                t.SetWidth(TRACK_W)
                t.SetStart(pcbnew.VECTOR2I(s[0], s[1]))
                t.SetEnd(pcbnew.VECTOR2I(s[2], s[3]))
                b.Add(t)
                existing.append((s[0], s[1], s[2], s[3], layer, netname))
                tc += 1
            ok = True
        else:
            if netname not in unrouted:
                unrouted.append(netname)

    status = "OK" if ok else "FAIL"
    print(f"  [{status}] {netname}")

# Thermal vias for power nets
for nn in POWER_NETS:
    if nn not in nets:
        continue
    ni = b.FindNet(nn)
    nc = ni.GetNetCode() if ni else 0
    for p in nets[nn]:
        v = pcbnew.PCB_VIA(b)
        v.SetPosition(pcbnew.VECTOR2I(p['pos'][0], p['pos'][1]))
        v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetWidth(550000)
        v.SetDrill(300000)
        v.SetNetCode(nc)
        b.Add(v)
        vc += 1

# Save (no zone fill — DRC will handle it)
pcbnew.SaveBoard(PATH, b)

# Verify
b2 = pcbnew.LoadBoard(PATH)
all_t = list(b2.GetTracks())
seg = [t for t in all_t if t.Type() == pcbnew.PCB_TRACE_T]
vias = [t for t in all_t if t.Type() == pcbnew.PCB_VIA_T]
print(f"\nVERIFIED: {len(seg)} tracks, {len(vias)} vias")
print(f"Unrouted: {len(unrouted)}")
for u in unrouted:
    print(f"  {u}")
