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
