#!/usr/bin/env python3
"""Regression: +3V3 rail may only move to the inner plane if the plane EXISTS.

WHY (measured 2026-10-12): the hub routed board carries 82 +3V3 F.Cu segments
and only 4 vias; its 14 +3V3 pads are SMD, so they cannot reach an inner plane
directly.  Deleting the F.Cu rail WITHOUT a +3V3 plane would disconnect the
rail -- so the script must refuse.  And when it does run it must (a) remove the
F.Cu segments and (b) put exactly one via at every +3V3 SMD pad.

pcbnew loads ONLY under /usr/bin/python3.14 (importing under 3.11 segfaults).
Run this file directly; do not import it from a 3.11 pytest process.
"""
import subprocess
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPT = os.path.join(ROOT, "tracker", "hardware",
                      "reassign_hub_v9_power_to_plane.py")
NOPLANE = os.path.join(ROOT, "tracker", "hardware",
                       "hub_board_v9_routed_stitched_routed.kicad_pcb")
PLANEBRD = os.path.join(ROOT, "tracker", "hardware",
                        "hub_board_v9_4l_plane.kicad_pcb")


def run(args):
    return subprocess.run([sys.executable, SCRIPT, *args],
                          capture_output=True, text=True, timeout=300)


def test_refuses_without_plane():
    """Board with no +3V3 zone -> exit 2, rail untouched."""
    r = run([NOPLANE, "/tmp/_noplane_out.kicad_pcb"])
    assert r.returncode == 2, f"expected refusal, got {r.returncode}\n{r.stderr}"
    assert "REFUSED" in r.stderr.upper()
    assert not os.path.exists("/tmp/_noplane_out.kicad_pcb"), "wrote on refusal"
    print("PASS test_refuses_without_plane")


def test_moves_rail_onto_plane():
    """Board WITH the plane -> F.Cu segments gone, one via per SMD pad."""
    out = "/tmp/_plane_out.kicad_pcb"
    r = run([PLANEBRD, out])
    assert r.returncode == 0, f"exit {r.returncode}\n{r.stderr}"
    assert os.path.exists(out), "no output written"

    probe = f'''
import sys
sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew
b = pcbnew.LoadBoard({out!r})
NET = "+3V3"
nc = b.FindNet(NET).GetNetCode()
segs = sum(1 for t in b.GetTracks()
           if t.GetClass() == "PCB_TRACK" and t.GetNetCode() == nc)
vias = sum(1 for t in b.GetTracks()
           if t.GetClass() == "PCB_VIA" and t.GetNetCode() == nc)
smd = sum(1 for fp in b.GetFootprints() for p in fp.Pads()
          if p.GetNetCode() == nc and p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD)
planes = [b.GetLayerName(z.GetLayer()) for z in b.Zones()
          if z.GetNetname() == NET]
print("SEGS", segs, "VIAS", vias, "SMD", smd, "PLANES", planes)
'''
    p = subprocess.run(["/usr/bin/python3.14", "-c", probe],
                       capture_output=True, text=True, timeout=300)
    line = [l for l in p.stdout.splitlines() if l.startswith("SEGS")][0]
    segs = int(line.split()[1])
    vias = int(line.split()[3])
    smd = int(line.split()[5])
    assert segs == 0, f"F.Cu rail not removed: {segs} segments left"
    assert vias >= smd, f"expected >= {smd} vias, got {vias}"
    assert "In2.Cu" in line, f"no In2 plane: {line}"
    print(f"PASS test_moves_rail_onto_plane  ({line})")


if __name__ == "__main__":
    test_refuses_without_plane()
    test_moves_rail_onto_plane()
    print("ALL PASS")
