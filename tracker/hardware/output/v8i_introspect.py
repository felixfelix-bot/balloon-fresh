import sys, json
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew

B = 'tracker/hardware/output/v8h_krt_u2_lora2021.kicad_pcb'
b = pcbnew.LoadBoard(B)
MM = 1e6

def mm(v):
    return round(v/MM, 4)

# bounding box
bb = b.GetBoardEdgesBoundingBox()
print("EDGE_BBOX mm:", mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom()),
      "W=", mm(bb.GetWidth()), "H=", mm(bb.GetHeight()))

print("LAYERS(cu):", b.GetCopperLayerCount())
print("FOOTPRINTS:")
for fp in b.GetFootprints():
    p = fp.GetPosition()
    print("  %-6s %-45s pos=(%8.3f,%8.3f) rot=%6.1f layer=%s pads=%d npth=%d" % (
        fp.GetReference(), str(fp.GetFPID()), mm(p.x), mm(p.y), fp.GetOrientationDegrees(),
        b.GetLayerName(fp.GetLayer()), fp.GetPadCount(),
        sum(1 for pd in fp.Pads() if pd.GetAttribute()==pcbnew.PAD_ATTRIB_NPTH)))

print("NETS:")
for code, net in b.GetNetsByNetcode().items():
    if code == 0: continue
    print("  %3d %s" % (code, net.GetNetname()))

print("TRACKS RF-ish:")
for t in b.GetTracks():
    nn = t.GetNetname()
    if 'RF' in nn.upper() or 'ANT' in nn.upper() or 'GNSS' in nn.upper() or 'GPS' in nn.upper():
        if t.Type()==pcbnew.PCB_TRACE_T:
            s=t.GetStart(); e=t.GetEnd()
            print("  TRACE net=%-16s layer=%-6s w=%.4f (%8.3f,%8.3f)->(%8.3f,%8.3f)" % (
                nn, b.GetLayerName(t.GetLayer()), mm(t.GetWidth()), mm(s.x),mm(s.y),mm(e.x),mm(e.y)))
        elif t.Type()==pcbnew.PCB_VIA_T:
            p=t.GetPosition()
            print("  VIA   net=%-16s d=%.3f drill=%.3f (%8.3f,%8.3f)" % (nn, mm(t.GetWidth()), mm(t.GetDrill()), mm(p.x),mm(p.y)))

print("ZONES:")
for z in b.Zones():
    print("  zone layer=%s net=%s prio=%s filled=%s" % (
        b.GetLayerName(z.GetLayer()), z.GetNetname(), z.GetAssignedPriority(), z.IsFilled()))

print("NPTH pads on board:")
for fp in b.GetFootprints():
    for pd in fp.Pads():
        if pd.GetAttribute()==pcbnew.PAD_ATTRIB_NPTH:
            p=pd.GetPosition()
            print("  %s.%s drill=%.3f (%8.3f,%8.3f)" % (fp.GetReference(), pd.GetNumber(), mm(pd.GetDrillSize().x), mm(p.x),mm(p.y)))
print("DONE")
