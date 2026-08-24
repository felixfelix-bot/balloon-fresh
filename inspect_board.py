import sys; sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew, json

b = pcbnew.LoadBoard('/home/c03rad0r/repos/balloon-fresh/tracker/hardware/output/v2_adc_fixed2.kicad_pcb')

# Layer constants
F_CU = pcbnew.F_Cu
B_CU = pcbnew.B_Cu
UV = 1000000  # 1mm in KiCad internal units (nm actually *1e6? no, nm)

# Actually KiCad uses nm: pos.x is in nm. 1mm = 1000000 nm
# Wait, modern pcbnew uses 1nm = 1 IU. Let me verify by checking pad coords.

# Collect all pads
pads = []
for fp in b.GetFootprints():
    for pad in fp.Pads():
        pos = pad.GetPosition()
        size = pad.GetSize()
        pads.append({
            'ref': fp.GetReference(),
            'pad': pad.GetNumber(),
            'net': pad.GetNetname(),
            'x': pos.x,
            'y': pos.y,
            'sx': size.x,
            'sy': size.y,
            'layer': str(pad.GetLayer()),
            'shape': str(pad.GetShape()),
        })

# Group by net
nets = {}
for p in pads:
    nets.setdefault(p['net'], []).append(p)

print("=== NET SUMMARY ===")
for net in sorted(nets):
    print(f"  {net}: {len(nets[net])} pads")

# Focus on power nets
print("\n=== POWER PADS ===")
for net in ('3V3','GND','VCAP','SOLAR_IN','+3V3'):
    if net in nets:
        print(f"\n--- {net} ---")
        for p in sorted(nets[net], key=lambda x: (x['x'], x['y'])):
            print(f"  {p['ref']}-{p['pad']} ({p['x']/1e6:7.2f},{p['y']/1e6:7.2f})mm "
                  f"size=({p['sx']/1e6:.2f}x{p['sy']/1e6:.2f}) layer={p['layer']} shape={p['shape']}")

# Inspect existing tracks to understand clearance requirements
print("\n=== EXISTING TRACKS (first 20) ===")
tracks = list(b.GetTracks())
print(f"Total tracks: {len(tracks)}")
for t in tracks[:20]:
    if hasattr(t, 'GetStart'):
        s = t.GetStart()
        e = t.GetEnd()
        print(f"  Track net={t.GetNetname()} ({s.x/1e6:.2f},{s.y/1e6:.2f})->({e.x/1e6:.2f},{e.y/1e6:.2f}) "
              f"layer={t.GetLayer()} width={t.GetWidth()/1e6:.2f}mm")

# Check track widths
widths = {}
for t in tracks:
    if hasattr(t, 'GetWidth'):
        w = t.GetWidth()
        widths[w] = widths.get(w, 0) + 1
print("\n=== TRACK WIDTHS (nm) ===")
for w in sorted(widths):
    print(f"  {w/1e6:.3f}mm: {widths[w]} tracks")

# Check existing vias
vias = [t for t in tracks if hasattr(t, 'GetStart') and t.GetStart() == t.GetEnd() and hasattr(t, 'GetDrillValue') and t.GetDrillValue() > 0]
print(f"\n=== VIAS: {len(vias)} ===")
for v in vias[:10]:
    pos = v.GetStart()
    print(f"  Via net={v.GetNetname()} ({pos.x/1e6:.2f},{pos.y/1e6:.2f}) "
          f"size={v.GetWidth()/1e6:.2f}mm drill={v.GetDrillValue()/1e6:.2f}mm")

# Board outline check
print("\n=== BOARD EDGES ===")
for item in b.GetDrawings():
    print(f"  {item.GetClass()} layer={item.GetLayer()}")
