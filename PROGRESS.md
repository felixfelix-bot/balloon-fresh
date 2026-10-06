# Schematic ↔ board sync — progress log

Branch: `pr/v8k-sch-board-sync`
Worktree: `/home/c03rad0r/worktrees/bf-sch-sync`
Base: `ba73bb9` (tip of `pr/ms5611-baro`)

## 2026-10-07 — schematic brought up to v8i board of record
- Finding: generator `build_flight_sch.py` was frozen to the STALE `v_c3_flight_4layer_placed.kicad_pcb` (20 footprints); the board of record is `v8i_krt_gnss.kicad_pcb` (28 footprints, 25 nets, 4-layer, 45×55 mm, DRC-clean). The 8-component gap (ANT2, R_SER, C_SH1, C_SH2, MNT1–4) is the delta.
- Fix: re-pointed generator PCB + FROZEN_SHA256 at `v8i_krt_gnss.kicad_pcb`; added PART_MAP entries for `LoRa2021_Castellated` (→ balloon_flight:LR2021F33, 18-pin) and `MountingHole_2.2mm_M2` (→ Mechanical:MountingHole); updated LR2021_PINS to the 18-pad castellated pinout (net-derived names, floating pads left neutral); added the 8 refs to COLUMNS + a mounting-hole column; updated INTENTIONAL_NC/DECLARED_GAP to v8i's actual netless pads; mapped U5 to Sensor:BME280 symbol (BMP280 pad numbering) with value/footprint override to MS5611-01BA/LGA-8_3x5mm (fixes the MS5611-vs-BMP280 pin-numbering mismatch that caused ERC errors).
- GNSS path closed: ANT2.1 → GNSS_ANT → R_SER.1/.2 → GNSS_RF → U3.11 (RF_IN); C_SH1 shunts GNSS_RF to GND, C_SH2 shunts GNSS_ANT to GND. "no GPS antenna feed" annotation removed.
- Verification: `check_sch_gates.py` ALL GATES PASS (0 ERC errors, 1 warning); kicad-cli `sch export netlist` → 28 components; U5 = MS5611-01BA.
- Files touched: `build_flight_sch.py`, `v_c3_flight.kicad_sch`, `v_c3_flight.net`, `v_c3_flight-erc.rpt`, `sym-lib-table`, `balloon_flight.kicad_sym`, `balloon_flight.pretty/*.kicad_mod` (regenerated + 2 new: LoRa2021_Castellated, MountingHole_2.2mm_M2).