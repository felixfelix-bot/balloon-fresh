"""Close the t1_103_4L_06 residual with fresh page loads, regenerated 2026-10-08.

Runs under python3.13 (playwright 1.60). Writes res_*.json/txt into
~/quote-scratch/measurements/ via measure2.measure().
"""
import sys
sys.path.insert(0, "/home/c03rad0r/repos/jlcpcb-service")
sys.path.insert(0, "/home/c03rad0r/quote-scratch")
import measure2 as M
from jlcpcb_client.session import browser

cfgs = [
    {"name": "res_103_4L_06", "x": 103, "y": 103,
     "opts": [["Layers", "4"], ["PCB Thickness", "0.6mm"]],
     "note": "CLOSE t1_103_4L_06 residual: fresh load, 103mm 4L 0.6mm"},
    {"name": "res_103_4L_16", "x": 103, "y": 103,
     "opts": [["Layers", "4"], ["PCB Thickness", "1.6mm"]],
     "note": "fresh control: 103mm 4L 1.6mm"},
    {"name": "res_102_4L_16", "x": 102, "y": 102,
     "opts": [["Layers", "4"], ["PCB Thickness", "1.6mm"]],
     "note": "fresh decision-size control: 102mm 4L 1.6mm"},
    {"name": "res_102_4L_04_ENIG", "x": 102, "y": 102,
     "opts": [["Layers", "4"], ["Surface Finish", "ENIG"], ["PCB Thickness", "0.4mm"]],
     "note": "follow-up (b): 102mm 4L 0.4mm ENIG"},
]

with browser(headless=True) as pg0:
    ctx = pg0.context
    for c in cfgs:
        try:
            M.measure(ctx, c["name"], c["x"], c["y"], [list(o) for o in c["opts"]],
                      qty=c.get("qty", 5), surf=c.get("surf"), note=c.get("note", ""))
        except Exception as e:
            print("FAILED", c["name"], repr(e)[:200])
print("CLOSEOUT DONE")
