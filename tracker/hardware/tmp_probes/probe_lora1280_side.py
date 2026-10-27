#!/usr/bin/env python3
"""Probe: place LoRa1280 on B.Cu at a given rotation and report where the pins land.

Flip() segfaults on a library-loaded footprint, so the part must be Added to a board
first. One rotation per process, so a crash only kills one probe.
"""
import sys

import pcbnew

board_path, rot = sys.argv[1], float(sys.argv[2])
b = pcbnew.LoadBoard(board_path)
fp = pcbnew.FootprintLoad("tracker/hardware/footprints/lora1280", "LoRa1280")
tgt = pcbnew.VECTOR2I(int(53.0e6), int(68.1e6))
fp.SetPosition(tgt)
fp.SetOrientationDegrees(rot)
b.Add(fp)
if fp.GetLayer() != pcbnew.B_Cu:
    fp.Flip(tgt, False)
p1, p9, p16 = (fp.FindPadByNumber(n) for n in ("1", "9", "16"))
print(
    f"rot {rot:>6} -> fp {fp.GetLayerName():<5} pad {p1.GetLayerName():<5} "
    f"pin1 ({p1.GetPosition().x/1e6:6.2f},{p1.GetPosition().y/1e6:6.2f}) "
    f"pin9 ({p9.GetPosition().x/1e6:6.2f},{p9.GetPosition().y/1e6:6.2f}) "
    f"pin16 ({p16.GetPosition().x/1e6:6.2f},{p16.GetPosition().y/1e6:6.2f})"
)
