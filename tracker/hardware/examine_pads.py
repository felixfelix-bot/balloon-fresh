#!/usr/bin/python3.14
"""Examine pad positions of key footprints to plan placement."""
import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew

BOARD_PATH = 'hub_board_v1_4layer.kicad_pcb'
NM = 1000000

b = pcbnew.LoadBoard(BOARD_PATH)

key_refs = ['U', 'U1', 'U2', 'U3', 'U4', 'U5', 'SC', 'D1', 'J']
for fp in b.GetFootprints():
    ref = fp.GetReference()
    if ref not in key_refs:
        continue
    pos = fp.GetPosition()
    orient = fp.GetOrientationDegrees()
    print(f"\n=== {ref} ({fp.GetValue()}) at ({pos.x/NM:.2f}, {pos.y/NM:.2f}) orient={orient:.1f} ===")
    for pad in fp.Pads():
        ppos = pad.GetPosition()
        sz = pad.GetSize()
        print(f"  Pad '{pad.GetPadName()}' at ({ppos.x/NM:.2f},{ppos.y/NM:.2f}) "
              f"size={sz.x/NM:.1f}x{sz.y/NM:.1f} net='{pad.GetNetname()}' "
              f"type={'THT' if pad.GetAttribute()==3 else 'SMD'}")
