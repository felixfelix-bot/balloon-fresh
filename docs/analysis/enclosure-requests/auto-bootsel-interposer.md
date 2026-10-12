# Auto-BOOTSEL interposer — small bench case request

Target repository: `Amperstrand/enclosure-forge`

This is a request for a small, reusable **bench case/fixture** for the already-routed auto-BOOTSEL interposer. It is the lowest-priority enclosure target: the interposer is a programming aid, not flight hardware. The case should prevent bench shorts, hold the pogo/test-pin field in repeatable registration, and provide safe access to the programming controls.

Please treat the dimensions and geometry below as our measured/provenance-tagged inputs, not as authoritative. Re-measure from the supplied board and placed solids in the forge pipeline, and report any disagreement rather than silently compensating for it.

## 1. Board identity and pinned revision

- Project: `felixfelix-bot/balloon-fresh`
- Board generator: `tracker/hardware/auto_bootsel/auto_bootsel_pcb.py`
- Routed board: `tracker/hardware/auto_bootsel/auto-bootsel-interposer-placed.kicad_pcb`
- Unrouted/placed source: `tracker/hardware/auto_bootsel/auto-bootsel-interposer.kicad_pcb`
- Source revision: commit containing this request's measured snapshot (recorded in the git history accompanying this issue).
- Board name: auto-BOOTSEL interposer
- Board outline from generator constants: **30.0 mm × 28.0 mm**; nominal PCB thickness: `MEASUREMENTS_NEEDED` (confirm from fab stackup/board file before case release).
- Layer count and exact fab stack: `MEASUREMENTS_NEEDED` (named stand-in: PCB fab set / KiCad board setup).

The repository's host acceptance suite exercises the generated board and currently passes 28 tests, including netlist, routing, orientation and negative-control checks. This is evidence about the board snapshot, not a substitute for the forge's own geometry extraction.

## 2. Fab set

The board is currently a routed PCB snapshot, but the production fab archive/hash is not attached to this request yet: **`MEASUREMENTS_NEEDED`** (stand-in: export the final Gerber/drill set after the interposer fab freeze and record its SHA-256 here). Please use the pinned board file for initial envelope work and flag any discrepancy against the later fab set.

## 3. Outline, mounting, and registration

- Rectangular outline: 30.0 × 28.0 mm from `BOARD_W`/`BOARD_H` in the generator.
- Four M3 mounting-hole footprints (`H1`–`H4`) are placed at 4.0 mm from each board edge, from `MOUNT_HOLE_INSET`; nominal footprint is `MountingHole_3.2mm_M3`.
- Exact finished hole diameter, plated/non-plated status, and hole-to-edge fabrication tolerance: **`MEASUREMENTS_NEEDED`** (stand-in: fab drill file and placed-solid extraction).
- All ten signal/ground test points are intentionally at rotation 0. Their generator placements are the provenance for the present pin-field positions: RUN channel y=11.0 mm and BOOT channel y=16.0 mm; x positions are 6.0, 15.0, and 24.0 mm for the endpoint/test-point stations, with the 0402 link positions at x=10.5 and 19.5 mm.
- The case/fixture must register from the placed board and hole datums, not from a DXF callout or typed dimensions. The pogo-pin sweep, pin-tip diameter, stroke, and compression are **`MEASUREMENTS_NEEDED`** (stand-in: selected pogo hardware and target-board mating drawing).

## 4. Component solids and declared gaps

The interposer carries:

- `TP1`–`TP6`: six THT test points, library footprint `TestPoint_THTPad_D2.5mm_Drill1.2mm`.
- `R1`–`R4`: four 0402 resistor/link footprints, library footprint `R_0402_1005Metric`; R1/R2 populated 0R links, R3/R4 DNP bench park links.
- `H1`–`H4`: four M3 mounting-hole footprints, library footprint `MountingHole_3.2mm_M3`.

The checked-in board and vendored footprint files are the available geometry sources. Exact component height above/below each board face, test-point protrusion, and resistor body-height envelope: **`MEASUREMENTS_NEEDED`** (stand-in: placed-solid extraction from the pinned board plus vendor STEP where available). Any component without a validated 3D solid must be listed explicitly in the forge report as `not_modelled`; do not infer a zero-height body.

External mating hardware is not part of the PCB geometry package: ESP32-C3 controller, RP2040 target, pogo pins, cable/USB lead, and their plugs are **`MEASUREMENTS_NEEDED`** (stand-in: selected part numbers and caliper/STEP measurements).

## 5. User-facing semantics and connector directions

The interposer is a four-wire programming interposer between an ESP32-C3 controller and an RP2040 target:

- `TP1` = ESP32-side RUN / GPIO1 path.
- `TP2` = ESP32-side BOOTSEL / GPIO8 path.
- `TP3` = RP2040 RUN path.
- `TP4` = RP2040 GP0/BOOTSEL path.
- `TP5`, `TP6` = GND.
- R1/R2 are the populated 0R series links; R3/R4 are DNP bench-only signal-to-GND park links.

The case should make the orientation and ESP32-side/RP2040-side ends unambiguous, and should prevent insertion in the wrong orientation. Up axis, board-face datum, and exact controller/target mating direction are **`MEASUREMENTS_NEEDED`** (stand-in: bench harness drawing and selected target-board fixtures).

## 6. Mating envelopes and cable exit

Required mating interfaces:

- A repeatable pogo-pin/contact fixture for TP1–TP6.
- A serviceable cable exit for the USB/programming lead, with strain relief so insertion/removal does not load the PCB or pogo fixture.
- Clearance for the ESP32-C3 and RP2040-side wiring harnesses without forcing a bend over the test points.

Pogo pin part number, tip style, sweep/keep-out, compression stroke, wire gauge, connector/plug, bend radius, and cable-exit direction are **`MEASUREMENTS_NEEDED`** (stand-in: selected harness BOM and mating fixture drawing).

## 7. Installation and removal kinematics

The preferred operation is: place/register the interposer in the bench fixture, insert the target harness/board against the datum, press the contact fixture, perform programming, release, and remove without desoldering or removing the interposer from its case.

Please model the insertion sweep and maintenance removal path. The target-board registration datum, insertion direction, required vertical stroke, and whether the target remains captive in the fixture are **`MEASUREMENTS_NEEDED`** (stand-in: physical bench rig measurement). Do not assume a pogo pin can tolerate lateral insertion force.

## 8. Antenna/RF law

This is a bench programming fixture, not an RF enclosure. No RF antenna window or dielectric transmission claim is requested. Do not add or widen an RF window silently. Keep the case clear of the interposer's electrical contacts and disclose any conductive insert, shield, or material near the ESP32/RP2040 wiring.

## 9. Environment

- Use: indoor electronics bench; not flight hardware and not weatherproof equipment.
- Desired function: protect against accidental bench shorts and hold repeatable contact.
- IP rating, UV, condensation/freezing, and outdoor temperature requirements: **not applicable** for this target.
- Expected bench temperature and cleaning/ESD policy: **`MEASUREMENTS_NEEDED`** (stand-in: lab fixture requirements).

## 10. Mechanical interface and access

Please provide:

- Bench-fixture mounting holes or a compatible captive mounting interface so the pogo field cannot shift under insertion force.
- Cable exit and strain relief for the USB/programming lead.
- Access to BOOTSEL and RESET/RUN controls without removing the board from the case. If the interposer itself has no physical buttons, provide access/clearance to the connected RP2040/ESP32 controls through the fixture and document the chosen arrangement.

Bench mounting pattern, fastener type, insert choice, cable-gland/strain-relief part, and control-access geometry are **`MEASUREMENTS_NEEDED`** (stand-in: selected bench fixture hardware).

## 11. Non-boolean acceptance gates

A boolean non-overlap pass is necessary but not sufficient. Before calling the fixture validated, we need measured checks for:

- pogo alignment and contact repeatability over repeated insertions;
- contact force and board deflection;
- target-board registration and wrong-way insertion prevention;
- cable strain relief and cable-cycle survivability;
- insert pull-out / fastener retention if inserts are used;
- access to programming controls while installed;
- thermal soak only if a powered-in-case test exposes a credible heat concern.

Thresholds and cycle counts are **`MEASUREMENTS_NEEDED`** (stand-in: bench qualification plan). Please emit these as named gates in the forge report, not as an implied consequence of the volume boolean.

## 12. Geometry-availability matrix

| Module | MPN/revision | Geometry source | Hash/licence | Status / stand-in |
|---|---|---|---|---|
| Interposer PCB | auto-BOOTSEL, current routed snapshot | repository `.kicad_pcb` + generator | record against pinned git revision; project licence | available for extraction; verify against fab set |
| Test points TP1–TP6 | `TestPoint_THTPad_D2.5mm_Drill1.2mm` | vendored KiCad footprint; vendor solid not present | repository footprint; upstream KiCad footprint provenance | 2D footprint available; height/STEP `MEASUREMENTS_NEEDED` |
| R1–R4 | `R_0402_1005Metric` | vendored KiCad footprint; vendor solid not present | repository footprint; upstream KiCad footprint provenance | 2D footprint available; populated body height `MEASUREMENTS_NEEDED` |
| M3 holes H1–H4 | `MountingHole_3.2mm_M3` | vendored KiCad footprint | repository footprint; upstream KiCad footprint provenance | aperture/courtyard available; final drill tolerance `MEASUREMENTS_NEEDED` |
| ESP32-C3 controller | exact module revision `MEASUREMENTS_NEEDED` | no pinned solid in this board package | `MEASUREMENTS_NEEDED` | named external stand-in: controller BOM + STEP |
| RP2040 target board | exact board/revision `MEASUREMENTS_NEEDED` | no pinned solid in this board package | `MEASUREMENTS_NEEDED` | named external stand-in: target-board fab/STEP |
| Pogo/contact hardware | exact part `MEASUREMENTS_NEEDED` | no pinned solid | `MEASUREMENTS_NEEDED` | named external stand-in: fixture BOM + vendor drawing |
| USB/programming lead | exact plug/cable `MEASUREMENTS_NEEDED` | no pinned solid | `MEASUREMENTS_NEEDED` | named external stand-in: cable BOM + bend-radius measurement |

## 13. Scope boundaries and verification loop

The flight boards are explicit **non-requests**: `hub_board_v9` and `wing_board_v9 ×4` need a lightweight retention frame, not enclosures. The existing `balloon_dev_case` is also not requested here; it is our own OpenSCAD case and follows the separate re-home/REC-FIRST path.

This issue is a request, not a code contribution. The forge author is free to re-measure and contradict any input above. When a candidate case/fixture is returned, we will rerun the forge's `interference_report.json` against this pinned board revision ourselves before printing; a partner self-report is not verification.

## Acceptance summary

1. Board and target-board datums are extracted from placed solids.
2. Pogo alignment, mounting, cable exit/strain relief, and control access are explicit in the model.
3. Missing solids and every unmeasured value remain visibly marked `MEASUREMENTS_NEEDED`.
4. The forge report includes the non-boolean contact/retention gates, not only volume non-overlap.
5. The case is treated as an indoor bench aid, never as a flight enclosure or weatherproof claim.
