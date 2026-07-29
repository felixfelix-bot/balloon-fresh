#!/usr/bin/env python3
"""Generate V1 non-PA hub board PCB using pcbnew Python API."""
import sys, os
sys.path.insert(0, '/usr/lib/python3/dist-packages')
os.environ['KICAD9_SYMBOL_DIR'] = '/usr/share/kicad/symbols'

import pcbnew
from pcbnew import (
    BOARD, FOOTPRINT, PAD, PCB_TRACK, PCB_VIA, PCB_SHAPE,
    ZONE, NETINFO_LIST, NET, wxPoint,
    F_Cu, B_Cu, F_Mask, B_Mask, F_Paste, B_Paste,
    F_SilkS, B_SilkS, Edge_Cuts, F_Fab, B_Fab, F_CrtYd, B_CrtYd,
)

print(f"KiCad pcbnew: {pcbnew.GetBuildVersion()}")

BOARD_W = 50  # mm
BOARD_H = 40  # mm
MM = 1000000  # IU per mm in KiCad

def mm(x):
    return int(x * MM)

board = BOARD()
board.SetCopperLayerCount(2)

# Board outline
for x1, y1, x2, y2 in [
    (0, 0, BOARD_W, 0),
    (BOARD_W, 0, BOARD_W, BOARD_H),
    (BOARD_W, BOARD_H, 0, BOARD_H),
    (0, BOARD_H, 0, 0),
]:
    seg = PCB_SHAPE(board)
    seg.SetStart(wxPoint(mm(x1), mm(y1)))
    seg.SetEnd(wxPoint(mm(x2), mm(y2)))
    seg.SetLayer(Edge_Cuts)
    seg.SetWidth(mm(0.15))
    board.Add(seg)

print(f"Board outline: {BOARD_W}x{BOARD_H}mm")

# Load footprints
fp_dir = os.path.join(os.path.dirname(__file__), "..", "hub_board_diy", "custom.pretty")
fp_dir = os.path.abspath(fp_dir)
print(f"Footprint dir: {fp_dir}")

# List available footprints
for f in os.listdir(fp_dir):
    print(f"  Footprint: {f}")

outpath = os.path.join(os.path.dirname(__file__), "hub_board_v1.kicad_pcb")
board.Save(outpath)
print(f"Saved: {outpath}")
