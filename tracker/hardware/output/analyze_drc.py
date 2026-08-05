#!/usr/bin/env python3.14
"""Analyze DRC issues on both balloon boards using pcbnew API."""
import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew
import math
import json

def analyze_board(pcb_file, label):
    board = pcbnew.LoadBoard(pcb_file)
    
    print("=" * 90)
    print(f"{label}: {pcb_file}")
    print("=" * 90)
    
    bb = board.GetBoardEdgesBoundingBox()
    print(f"Board size: {pcbnew.ToMM(bb.GetWidth()):.1f} x {pcbnew.ToMM(bb.GetHeight()):.1f} mm")
    print(f"Board origin: ({pcbnew.ToMM(bb.GetX()):.1f}, {pcbnew.ToMM(bb.GetY()):.1f})")
    print()
    
    # Collect all footprints with pad details
    footprints = {}
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        val = fp.GetValue()
        pos = fp.GetPosition()
        x = pcbnew.ToMM(pos.x)
        y = pcbnew.ToMM(pos.y)
        orient = fp.GetOrientationDegrees()
        
        pads = []
        for pad in fp.Pads():
            padpos = pad.GetPosition()
            px = pcbnew.ToMM(padpos.x)
            py = pcbnew.ToMM(padpos.y)
            net = pad.GetNetname()
            padname = pad.GetName()
            size = pad.GetSize()
            sw = pcbnew.ToMM(size.x)
            sh = pcbnew.ToMM(size.y)
            pads.append({
                'name': padname,
                'net': net,
                'x': px,
                'y': py,
                'w': sw,
                'h': sh,
            })
        
        footprints[ref] = {
            'ref': ref,
            'value': val,
            'x': x,
            'y': y,
            'orient': orient,
            'pads': pads,
        }
        
        print(f"  {ref:8s} [{val:20s}] at ({x:6.2f}, {y:6.2f}) orient={orient:5.1f}° pads={len(pads)}")
        for p in pads:
            print(f"    pad {p['name']:8s} [{p['net']:18s}] at ({p['x']:6.2f}, {p['y']:6.2f}) size=({p['w']:.2f}x{p['h']:.2f})")
        print()
    
    # Analyze tracks
    tracks = list(board.GetTracks())
    print(f"\nTotal tracks: {len(tracks)}")
    net_tracks = {}
    for t in tracks:
        net = t.GetNetname() or "(none)"
        net_tracks[net] = net_tracks.get(net, 0) + 1
    for net, count in sorted(net_tracks.items()):
        print(f"  {net:20s}: {count:3d} segments")
    
    # Check clearance between critical adjacent pads on U1
    print("\n" + "-" * 80)
    print("U1 PAD-TO-PAD DISTANCE ANALYSIS (the shorting issue)")
    print("-" * 80)
    if 'U1' in footprints:
        u1_pads = footprints['U1']['pads']
        for i in range(len(u1_pads)):
            for j in range(i+1, len(u1_pads)):
                p1 = u1_pads[i]
                p2 = u1_pads[j]
                dist = math.sqrt((p1['x']-p2['x'])**2 + (p1['y']-p2['y'])**2)
                if dist < 1.0:  # Only show close pads
                    # Approximate edge-to-edge distance (subtract half sizes)
                    edge_dist = dist - (p1['w'] + p2['w'])/4 - (p1['h'] + p2['h'])/4
                    print(f"  {p1['name']:8s} ({p1['x']:.2f},{p1['y']:.2f}) [{p1['net']:18s}] <-> "
                          f"{p2['name']:8s} ({p2['x']:.2f},{p2['y']:.2f}) [{p2['net']:18s}] "
                          f"center={dist:.3f}mm approx_edge={edge_dist:.3f}mm")
    
    return footprints

print("\n" + "#" * 90)
print("# V1-FAST ANALYSIS")
print("#" * 90)
fp1 = analyze_board("v1_fast_routed.kicad_pcb", "V1-FAST")

print("\n\n" + "#" * 90)
print("# V2-ADC ANALYSIS")
print("#" * 90)
fp2 = analyze_board("v2_adc_routed2.kicad_pcb", "V2-ADC")
