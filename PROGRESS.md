# MS5611 balloon flight PCB — progress log

Branch: `pr/ms5611-baro`
Worktree: `/home/c03rad0r/worktrees/bf-ms5611`

## 2026-10-07 M1 — design-backing artifacts fixed (in progress → commit)
- Replaced BMP280 with MS5611-01BA in current design-source files.
- Files touched:
  - `tracker/hardware/output/gerbers_v8b/v8b-bom.csv`: U5 now MS5611, footprint `Package_LGA:LGA-8_3x5mm_P1.25mm`.
  - `tracker/hardware/output/gerbers_v8b/v8b-pos.csv`: same U5 value/footprint.
  - `tracker/hardware/hub_board/hub_schematic.py`: stale BMP280 comment updated.
  - `tracker/hardware/schematics/flight_board/v_c3_flight.net`: U5 value+footprint → MS5611.
  - `tracker/hardware/schematics/flight_board/build_flight_sch.py`: PART_MAP maps both BMP280 and real MS5611 footprints to `Sensor_Pressure:MS5611-01BA`; added BARO_REF override loop.
  - `tracker/hardware/schematics/flight_board/v_c3_flight.kicad_sch`: regenerated from build script, U5 = `Sensor_Pressure:MS5611-01BA`.
  - `tracker/hardware/schematics/v_c3_flight.kicad_sch`: U5 symbol/value/footprint → MS5611-01BA / `Package_LGA:LGA-8_3x5mm_P1.25mm`.
- Verification: grep shows no BMP280 in active design files except explanatory comments (BMP280 no longer appears in BOM, netlist, generated schematics, or generator outputs). Legacy routed boards still carry BMP280 by design-policy (variants coexist, not overwritten).

## 2026-10-07 M2 — v8j MS5611 board variant plotted + gated (FAIL)
- Finding: uncommitted v8j_krt_ms5611 board (28 footprints) verified on disk to carry U5 = MS5611-01BA, footprint `Package_LGA:LGA-8_3x5mm_P1.25mm`; zero BMP280 references.
- Plotted gerbers + drill to `tracker/hardware/output/gerbers_v8j/` (kicad-cli 9.0.8).
- Gate: pcb_order_gate FAIL (exit 1) — 170 errors, 11 unconnected, 15 warnings. Worst rules: clearance=138, drill_out_of_range=12, unconnected=11, hole_clearance=9, track_dangling=4, silk_overlap=3.
- Status: WIP variant kept in-tree (coexists with v8i). Board+gerber sha256 bound in `tracker/hardware/v8j-GATE-RECORD.json`.
- Files: v8j_krt_ms5611.kicad_pcb, v8j_krt_ms5611.kicad_pro, gerbers_v8j/, v8j-GATE-RECORD.json
