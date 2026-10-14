#!/usr/bin/env python3
"""Refill all zones on a board -- the step that makes a routed board gradeable.

WHY THIS EXISTS (measured 2026-10-14)
-------------------------------------
Grading the strict 70x70 route produced 504 "clearance" violations, ALL of the
same shape:

    Clearance violation (rule 'S1 frozen JLCPCB clearance' clearance 0.2000 mm;
                         actual 0.0000 mm)
      Track [/F33_RESET_N] on In1.Cu, length 0.4243 mm
      Zone 'GND_PLANE_In1.Cu' [GND] on In1.Cu, priority 0

Signature: a signal track against a GND plane at **actual 0.0000 mm** -- i.e. the
track is sitting ON TOP of the plane's stored polygon.

That is not a clearance failure. It is a **STALE ZONE FILL**: the GND planes were
filled while the board was still unrouted, the router then added tracks, and the
zones were never refilled. KiCad's DRC reads the zone's STORED polygon, finds
copper where the track is, and reports 0.0000 mm. Refilling recomputes every zone
against the current copper, so the plane clears around each foreign-net track by
the 0.20 mm rule.

Same defect class as the rest of the campaign: the artifact and its DERIVED state
had drifted apart. A refill is required after ANY copper edit (routing, stitching)
and before DRC is meaningful.

Run:
  python3 refill_zones.py <board.kicad_pcb> [out.kicad_pcb]
"""
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else src
    board = pcbnew.LoadBoard(src)
    if board is None:
        print(f"cannot load {src}")
        return 2
    zones = board.Zones()
    print(f"zones on board: {zones.size() if hasattr(zones, 'size') else len(list(zones))}")
    filler = pcbnew.ZONE_FILLER(board)
    ok = filler.Fill(zones)
    pcbnew.SaveBoard(dst, board)
    print(f"refill returned: {ok}")
    print(f"wrote {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
