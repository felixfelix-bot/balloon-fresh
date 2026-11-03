# Wing_Tab_4P — footprint notes (moved out of the .kicad_mod)

**Why this file exists:** these notes were stored as `#` comment lines *inside*
`Wing_Tab_4P.kicad_mod`. KiCad's S-expression parser has **no comment syntax**, so the
footprint failed to load and DRC reported `Footprint 'Wing_Tab_4P' not found in library
'Tracker_Mechanical'` for all four `J_W1..J_W4` (`lib_footprint_issues` x6 -- 4 for the J_W,
and 2 others for the v9 lib). The notes are kept here verbatim; the footprint is now clean.

## Verbatim notes

```
  # DATUM: the footprint ORIGIN is the intersection of the hub's INTERFACE (outer)
  # edge with the SLOT CENTRE LINE.  +x points INBOARD (into the hub), +y runs
  # ALONG the hub edge.  This datum is NEWLY DECIDED in ADR-048 (no in-repo
  # record fixes a hub-side datum); the land offsets below are cited.
  # TODO(unverified): hub v9 thickness / layer count (WING-TO-HUB-SOCKET-SPEC s8
  #   item 3) is not fixed by any in-repo source; the lands are on the two OUTER
  #   layers only.
  # TODO(unverified): the ASSEMBLY ORIENTATION.  WING-TO-HUB-SOCKET-SPEC s1 says
  #   the wing's long axis is "perpendicular to the hub plane" while the very next
  #   sentence ("Wings 1-2 horizontal, 3-4 inclined ~30 deg below the hub plane")
  #   and ADR-046 s4.1 ("wing plane normal to the hub plane") read the other way.
  #   No v9 hub PCB exists to place against, so no placement is asserted here.
  # 4 LANDS on the TOP face (F.Cu): WING-TO-HUB-SOCKET-SPEC s2 "8 lands per
  # interface (4 on the hub top face, 4 on the hub bottom face)".
  # Lands span x = 1.0 .. 5.0 mm from the interface edge: near edge 1.0 mm inboard
  # per ADR-046 s2.2 copper-to-board-edge clearance >= 1.0 mm (see ADR-048 D-1,
  # where the spec's >= 0.5 mm and its self-inconsistent land datum are recorded).
  # Pads 1..4 of the land row, viewed with +x inboard:
  #   1 = W<n>_SOLAR_P   (ADR-046 s2.1 pin 1; outermost - ADR-046 s2.1)
  #   2 = GND            (ADR-046 s2.1 pin 2)
  #   3 = W<n>_RF        (ADR-046 s2.1 pin 3, RF_FEED; NO NET on v9 - s2.4)
  #   4 = W<n>_SOLAR_N   (ADR-046 s2.1 pin 4; outermost)
  # the SAME 4 lands on the BOTTOM face (B.Cu): the tab is soldered from BOTH sides
  # ROUTED SLOT 0.9 mm x 6.0 mm - the wing tab's insertion key (ADR-046 s4.1,
  # WING-TO-HUB-SOCKET-SPEC s2.1 Option A).  On Edge.Cuts: it is a real board
  # cut-out, drawn as a CLOSED contour (a milled slot is a closed cut-out).
  # The contour runs on the insertion axis from the interface edge (x=0) 6.0 mm
  # inboard and must stop >= 5.0 mm short of the hub centre.
  # TODO(unverified): JLCPCB routed-slot width tolerance (0.9 mm +/-0.10 mm is an
  #   ASSUMPTION - ADR-046 s4.3 / spec s8 item 2) and the hub's actual component
  #   keep-out at the slot, which owns whether 6.0 mm depth is admissible
  #   (spec s8 item 1).
  # SLOT KEEP-OUT = slot outline + 1.0 mm on all sides (spec s4).  No copper other
  # than the four W<n>_* lands, no via, no courtyard and no silkscreen may enter it.
  # TODO(unverified): the hub's own routing/keep-out clearance rule may be larger
  #   than 1.0 mm; take the larger of the two (spec s4).
  # COURTYARD = the COMPONENT KEEP-OUT: no component body or courtyard within
  # 1.5 mm of the socket land row on either face (spec s4).  Land row bbox is
  # x 1.0..5.0, y -3.3..3.3; expanded 1.5 mm -> x -0.5..6.5, y -4.8..4.8.
  # TODO(unverified): the hub worker's placement gate may impose a larger value
  #   (spec s4); use the larger.
  # SILKSCREEN (spec s6): W<n> number, pin-1 marker, pin-4 marker, slot-axis
  # centre-line tick and the 90 deg orientation mark.  All clear of copper and of
  # the slot keep-out; text height 1.0 mm >= 0.8 mm, stroke 0.15 mm >= 0.12 mm.
```
