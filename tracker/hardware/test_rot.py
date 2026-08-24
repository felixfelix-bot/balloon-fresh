#!/usr/bin/env python3
"""Quick test: check rotation API and bbox behavior."""
import pcbnew

b = pcbnew.LoadBoard("/home/c03rad0r/repos/balloon-fresh/tracker/hardware/hub_board_v1_4layer.kicad_pcb")
fps = list(b.GetFootprints())

# Find U1 (RP2040-Zero)
for fp in fps:
    if fp.GetReference() == "U1":
        bbox0 = fp.GetBoundingBox()
        print(f"U1 at 0deg: W={bbox0.GetWidth()/1e6:.2f} H={bbox0.GetHeight()/1e6:.2f}")
        
        # Try SetOrientation with EDA_ANGLE
        try:
            fp.SetOrientation(pcbnew.EDA_ANGLE(90, pcbnew.DEGREES_T))
            bbox90 = fp.GetBoundingBox()
            print(f"U1 at 90deg: W={bbox90.GetWidth()/1e6:.2f} H={bbox90.GetHeight()/1e6:.2f}")
        except Exception as e:
            print(f"EDA_ANGLE failed: {e}")
            try:
                fp.SetOrientation(90.0)
                bbox90 = fp.GetBoundingBox()
                print(f"U1 at 90deg (float): W={bbox90.GetWidth()/1e6:.2f} H={bbox90.GetHeight()/1e6:.2f}")
            except Exception as e2:
                print(f"Float failed: {e2}")
        
        # Reset
        fp.SetOrientation(pcbnew.EDA_ANGLE(0, pcbnew.DEGREES_T))
        
    if fp.GetReference() == "U":
        bbox0 = fp.GetBoundingBox()
        print(f"U at 0deg: W={bbox0.GetWidth()/1e6:.2f} H={bbox0.GetHeight()/1e6:.2f}")
        fp.SetOrientation(pcbnew.EDA_ANGLE(90, pcbnew.DEGREES_T))
        bbox90 = fp.GetBoundingBox()
        print(f"U at 90deg: W={bbox90.GetWidth()/1e6:.2f} H={bbox90.GetHeight()/1e6:.2f}")
        fp.SetOrientation(pcbnew.EDA_ANGLE(0, pcbnew.DEGREES_T))

# Also check GetFootprintRect vs GetBoundingBox for a couple parts
for fp in fps:
    ref = fp.GetReference()
    bb = fp.GetBoundingBox()
    # Check if there's a courtyard
    has_courtyard = False
    for item in fp.GraphicalItems():
        if item.GetLayer() == pcbnew.F_CrtYd:
            has_courtyard = True
            break
    print(f"{ref}: bbox W={bb.GetWidth()/1e6:.2f} H={bb.GetHeight()/1e6:.2f} courtyard={has_courtyard}")
