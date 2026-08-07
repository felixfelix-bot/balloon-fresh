#!/usr/bin/env python3.14
"""Analyze VCC pads, current cap-VCC distances, and existing bbox overlaps."""
import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew

BOARD = "/home/c03rad0r/repos/balloon-fresh/tracker/hardware/output/v_c3_flight_v5.kicad_pcb"
b = pcbnew.LoadBoard(BOARD)

def mm(nm):
    return nm / 1_000_000.0

def dist_nm(a, b):
    return ((a.x - b.x)**2 + (a.y - b.y)**2) ** 0.5

# ---- VCC/power pad discovery for each IC ----
POWER_NET_NAMES = ("VCC", "3V3", "+3V3", "3.3V", "VDD", "VBAT", "+BATT", "BATT", "VBUS", "+5V")

def power_pads(fp):
    res = []
    for pad in fp.Pads():
        net = pad.GetNetname()
        name = pad.GetPadName()
        # power pad = net name looks like power, OR pad named with VCC/3V3
        netup = (net or "").upper()
        if any(p in netup for p in ("3V3", "VCC", "VDD", "VBAT", "BATT", "VBUS", "+5V", "+3", "PWR", "VIN")):
            res.append((name, net, pad.GetPosition()))
    return res

ICS = ["U1", "U2", "U3", "U5", "U4"]
print("=" * 80)
print("IC VCC / POWER PADS")
print("=" * 80)
ic_vcc = {}
for ref in ICS:
    fp = b.FindFootprintByReference(ref)
    if not fp:
        print(f"  {ref}: NOT FOUND")
        continue
    pp = power_pads(fp)
    ic_vcc[ref] = pp
    if pp:
        print(f"  {ref} (center {mm(fp.GetPosition().x):.1f},{mm(fp.GetPosition().y):.1f}):")
        for name, net, pos in pp:
            print(f"      pad {name} net={net!r} at ({mm(pos.x):.2f},{mm(pos.y):.2f})")
    else:
        # show all pad nets to debug
        nets = sorted({(p.GetPadName(), p.GetNetname()) for p in fp.Pads()})
        print(f"  {ref}: NO power pads detected. All pads ({len(nets)}):")
        for name, net in nets[:40]:
            print(f"      pad {name} net={net!r}")

# ---- All distinct nets on the board ----
print()
print("=" * 80)
print("DISTINCT PAD NETS (non-empty)")
print("=" * 80)
nets = set()
for fp in b.GetFootprints():
    for pad in fp.Pads():
        n = pad.GetNetname()
        if n:
            nets.add(n)
for n in sorted(nets):
    print(f"  {n}")

# ---- Current cap-to-nearest-VCC distance ----
print()
print("=" * 80)
print("CURRENT CAP → IC VCC DISTANCES")
print("=" * 80)
CAPS = ["C1", "C2", "C3", "C4", "C_CAP"]
for cref in CAPS:
    cfp = b.FindFootprintByReference(cref)
    if not cfp:
        continue
    cpos = cfp.GetPosition()
    print(f"  {cref} at ({mm(cpos.x):.1f},{mm(cpos.y):.1f}):")
    for iref in ICS:
        for name, net, vpos in ic_vcc.get(iref, []):
            d = mm(dist_nm(cpos, vpos))
            print(f"      → {iref}.{name}({net}) dist={d:.2f}mm")

# ---- Current bbox overlaps ----
print()
print("=" * 80)
print("CURRENT PAIRWISE BBOX OVERLAPS")
print("=" * 80)
fps = list(b.GetFootprints())
fps.sort(key=lambda f: f.GetReference())
overlaps = []
for i in range(len(fps)):
    for j in range(i+1, len(fps)):
        bi = fps[i].GetBoundingBox()
        bj = fps[j].GetBoundingBox()
        # intersect
        ix0 = max(bi.GetOrigin().x, bj.GetOrigin().x)
        iy0 = max(bi.GetOrigin().y, bj.GetOrigin().y)
        ix1 = min(bi.GetEnd().x, bj.GetEnd().y)
        iy1 = min(bi.GetEnd().y, bj.GetEnd().y)
        # correct end:
        ix1 = min(bi.GetEnd().x, bj.GetEnd().x)
        iy1 = min(bi.GetEnd().y, bj.GetEnd().y)
        if ix0 < ix1 and iy0 < iy1:
            overlaps.append((fps[i].GetReference(), fps[j].GetReference(),
                             mm(ix1-ix0), mm(iy1-iy0)))
if not overlaps:
    print("  NONE — board is currently overlap-free.")
else:
    for a, c, dx, dy in overlaps:
        print(f"  {a} <-> {c}: overlap {dx:.2f} x {dy:.2f} mm")

print()
print(f"Total footprints: {len(fps)}")
