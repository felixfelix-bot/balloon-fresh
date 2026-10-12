# ADR-063 implementation report

## Result

Implemented ADR-063 in `tracker/hardware/build_hub_board_v9.py` and regenerated
`tracker/hardware/hub_board_v9.kicad_pcb` at the provisional component-only outline
of 60.0 x 60.0 mm. This is the measured component floor (39 placed components,
2582 mm² courtyard demand); the array is no longer used to size the PCB.

PVA1/PVA2 remain DNP mechanical carrier datums on F.Cu, rotated 90 degrees. Their
computed positions are PVA1=(9.55,30.00,90°) and PVA2=(50.45,30.00,90°). With the
78.55 x 38.90 mm model and rotation, each cell extends beyond both board Y edges
by 9.275 mm and the pair extends beyond the X edges. The separate carrier is
represented by this datum; no carrier PCB was fabricated or ordered.

The carrier pitch is explicitly provisional: 40.90 mm (38.90 mm cell width +
2.00 mm gap). The S_crack coupon has not been run, so ADR-063 D4 remains open and
this pitch is not frozen.

## Generation evidence

Command:

    /usr/bin/python3.14 tracker/hardware/build_hub_board_v9.py --outline 60x60 --publish

Observed: KRT EXIT=0; pad_overlap_pairs=0; existing parts moved by additive scope:
0; 25 KiCad-library and 16 repo-local models assigned; unmapped models=[];
final board SHA-256 aead5ff660827607367621f8903c021c9ac4499c6988a7beeb9afb86c9c7f33a.

## Render evidence

Command:

    python3 scripts/render_board_views.py tracker/hardware/hub_board_v9.kicad_pcb tracker/hardware/renders/adr063 --models-dir /usr/share/kicad/3dmodels

The fail-closed model gate passed. Eight views and the contact sheet were produced;
contact sheet:
`tracker/hardware/renders/adr063/hub_board_v9_contact_sheet.png`.
The repo's requested `scripts/fleet/visual_consult.py --emit-evidence` could not be
engaged because that path is absent in this checkout. The available vision review
returned a contrary visual impression (it said cells looked contained), but that
is superseded for geometry by the measured footprint coordinates/model dimensions;
render perspective and unlabeled scale make that review non-authoritative.

## DRC evidence

`kicad-cli pcb drc --format json` exited 0 and wrote
`tracker/hardware/hub_board_v9_drc.json`. It reports 134 total non-electrical /
placement-related violations and 157 unconnected items. This is a design placement
artifact, not an orderability claim. No `shorting_items`, `clearance`, or
`tracks_crossing` violations were observed in the report. The board is not claimed
fab-ready; routing and the open carrier coupon remain future work.

## Remaining work

1. Run the real 0.21 mm-cell S_crack coupon at 1g/2g and cold soak.
2. Freeze carrier rib pitch and maximum overhang from that measurement.
3. Re-place/route the component board after the pitch and carrier interface are
   frozen; resolve the reported unconnected/placement issues before any fab gate.
