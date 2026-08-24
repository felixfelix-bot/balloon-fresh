import sys; sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew

b = pcbnew.LoadBoard('/home/c03rad0r/repos/balloon-fresh/tracker/hardware/output/v2_adc_fixed2.kicad_pcb')

# Layer name lookup
n = b.GetLayerID

print("=== TRACKS BY LAYER ===")
layer_counts = {}
for t in b.GetTracks():
    layer = t.GetLayer()
    layer_counts[layer] = layer_counts.get(layer, 0) + 1
for layer_id, count in sorted(layer_counts.items()):
    print(f"  Layer {layer_id} ({b.GetLayerName(layer_id)}): {count} tracks")

print("\n=== B.Cu TRACKS ===")
for t in b.GetTracks():
    if t.GetLayer() == pcbnew.B_Cu:
        s = t.GetStart()
        e = t.GetEnd()
        is_via = (s == e)
        drill = ""
        if hasattr(t, 'GetDrillValue') and t.GetDrillValue() > 0:
            drill = f" drill={t.GetDrillValue()/1e6:.2f}"
        print(f"  net={t.GetNetname():12s} ({s.x/1e6:7.2f},{s.y/1e6:7.2f})->({e.x/1e6:7.2f},{e.y/1e6:7.2f}) w={t.GetWidth()/1e6:.2f}{drill}")

print("\n=== ALL VIAS ===")
for t in b.GetTracks():
    s = t.GetStart()
    e = t.GetEnd()
    if s == e and hasattr(t, 'GetDrillValue') and t.GetDrillValue() > 0:
        print(f"  Via net={t.GetNetname():12s} ({s.x/1e6:.2f},{s.y/1e6:.2f}) "
              f"size={t.GetWidth()/1e6:.2f} drill={t.GetDrillValue()/1e6:.2f} "
              f"layerSet={t.GetLayerSet()}")

print("\n=== BOARD EDGE/CUTS ===")
for item in b.GetDrawings():
    if item.GetClass() == 'PCB_SHAPE':
        s = item.GetStart()
        e = item.GetEnd()
        print(f"  Shape layer={item.GetLayer()} ({s.x/1e6:.2f},{s.y/1e6:.2f})->({e.x/1e6:.2f},{e.y/1e6:.2f})")

print("\n=== DESIGN RULES ===")
drb = b.GetDesignSettings()
print(f"  Min track width: {drb.m_TrackMinWidth/1e6:.3f}mm")
print(f"  Min via drill: {drb.m_ViasMinSize/1e6:.3f}mm")
print(f"  Min clearance: {drb.m_MinClearance/1e6:.3f}mm")
print(f"  Min via annular: {drb.m_ViasMinAnnularWidth/1e6:.3f}mm")

# Check footprint body outlines (to know where IC bodies are)
print("\n=== FOOTPRINT BOUNDING BOXES ===")
for fp in b.GetFootprints():
    bbox = fp.GetBoundingBox()
    print(f"  {fp.GetReference():8s} bbox=({bbox.GetX()/1e6:.1f},{bbox.GetY()/1e6:.1f}) "
          f"w={bbox.GetWidth()/1e6:.1f} h={bbox.GetHeight()/1e6:.1f}")
