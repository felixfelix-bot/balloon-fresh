import sys; sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew

b = pcbnew.LoadBoard('/home/c03rad0r/repos/balloon-fresh/tracker/hardware/output/v2_adc_fixed2.kicad_pcb')

conn = b.GetConnectivity()
print(f"Unconnected ratsnest count: {conn.GetUnconnectedCount(False)}")

power_nets = {'3V3', 'GND', 'VCAP', 'SOLAR_IN'}
tracks = list(b.GetTracks())

def dist(p1, p2):
    return ((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)**0.5

print("\n=== POWER PADS — CONNECTIVITY STATUS ===")
print(f"{'Ref':9s}{'Pad':5s}{'Net':11s}{'Pos':>22s}  Status")
unconnected_pads = []
for fp in b.GetFootprints():
    for pad in fp.Pads():
        net = pad.GetNetname()
        if net not in power_nets:
            continue
        pos = pad.GetPosition()
        px, py = pos.x, pos.y
        pad_size = pad.GetSize()
        tol = max(pad_size.x, pad_size.y)/2 + 300000
        touching = 0
        for t in tracks:
            if t.GetNetname() != net:
                continue
            s = t.GetStart()
            e = t.GetEnd()
            if dist((s.x, s.y), (px, py)) < tol or dist((e.x, e.y), (px, py)) < tol:
                touching += 1
        status = "OK" if touching > 0 else "*** UNCONNECTED ***"
        print(f"  {fp.GetReference():7s}-{pad.GetNumber():4s} {net:10s} "
              f"({px/1e6:7.2f},{py/1e6:7.2f})mm touching={touching} {status}")
        if touching == 0:
            unconnected_pads.append((fp, pad, net, px, py))

print(f"\n=== {len(unconnected_pads)} UNCONNECTED POWER PADS ===")
for fp, pad, net, px, py in unconnected_pads:
    print(f"  {fp.GetReference()}-{pad.GetNumber()} {net} ({px/1e6:.2f},{py/1e6:.2f})mm")

# Also: list ALL pads and ALL track obstacles (for routing — obstacles are pads of DIFFERENT nets)
print("\n=== ALL PADS (for obstacle map) ===")
for fp in b.GetFootprints():
    for pad in fp.Pads():
        pos = pad.GetPosition()
        sz = pad.GetSize()
        print(f"  {fp.GetReference():8s}-{pad.GetNumber():4s} {pad.GetNetname():12s} "
              f"({pos.x/1e6:7.2f},{pos.y/1e6:7.2f})mm size=({sz.x/1e6:.2f}x{sz.y/1e6:.2f})")
