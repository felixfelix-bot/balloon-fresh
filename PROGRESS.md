# Pin tie-off resolution — progress log

Branch: `pr/v8k-sch-board-sync`  
Worktree: `/home/c03rad0r/worktrees/bf-pin-tieoffs`  
Base (observed): `e28c21f63f20683ffa5d578e48d98efe76a1e0ec` (github, ngit, origin)

## 2026-10-07 — resolved 7 floating-pin TODO(unverified) markers from vendor documents

- Confirmed the 7 markers in `build_flight_sch.py` DECLARED_GAP matched the brief:
  U2.10/13/16/17, U3.15/VIO_SEL, U3.18/SAFEBOOT_N, U4.4.
- Sourced and cited three vendor documents:
  - NiceRF LoRa2021 module datasheet V1.3 (bare Gen4 18-pad module) — pin table §7.
  - Semtech LR2021/LR2022/LR2012 datasheet v2.2 — §23.5 "Unused Pins", §1.9.2/§1.9.3 VTCXO.
  - u-blox MAX-M10S Integration Manual UBX-20053088 R05 — Table 1 + §4.1.2 + §3.2.3.2.
  - TI TPS7A02 datasheet SBVS277C — Table 5-1 (DBV/SOT-23-5).
- Renamed `DECLARED_GAP` → `RESOLVED_NC` in the generator and updated `check_sch_gates.py`
  GATE 4 accordingly.
- Updated `LR2021_PINS` to datasheet names: pad 10 ANT_2G4, pad 13 VTCXO, pad 16 DIO8,
  pad 17 DIO7.
- Added citation annotations for each resolved pin (visible in `v_c3_flight.kicad_sch`).
- Regenerated and verified:
  - `grep -c '(comp (ref "' v_c3_flight.net` = 28
  - `check_sch_gates.py` → ALL GATES PASS
  - U5 value still `MS5611-01BA`

## Per-pin resolution table

| Pin | Function (from datasheet) | Prescribed tie-off | Citation |
|-----|----------------------------|-------------------|----------|
| U2.10 | 2.4G/S-band antenna port (ANT_2G4) | leave unconnected (unused RF pin) | NiceRF LoRa2021 DS V1.3 §7; Semtech LR2021 DS v2.2 §23.5 "Unused RF pins: Leave unconnected" |
| U2.13 | VTCXO supply output | leave unconnected (output, no external TCXO) | NiceRF LoRa2021 DS V1.3 §7; Semtech LR2021 DS v2.2 §1.9.2/§1.9.3 |
| U2.16 | DIO8 multipurpose I/O | leave unconnected (unused DIO) | NiceRF LoRa2021 DS V1.3 §7; Semtech LR2021 DS v2.2 §23.5 "Unused DIOs: Leave unconnected" |
| U2.17 | DIO7 multipurpose I/O | leave unconnected (unused DIO) | NiceRF LoRa2021 DS V1.3 §7; Semtech LR2021 DS v2.2 §23.5 "Unused DIOs: Leave unconnected" |
| U3.15 | VIO_SEL | leave open (3.3 V design) | u-blox MAX-M10S IM UBX-20053088 R05 §4.1.2, Table 1 |
| U3.18 | SAFEBOOT_N | leave open (normal operation) | u-blox MAX-M10S IM UBX-20053088 R05 Table 1, §3.2.3.2 |
| U4.4 | NC (no connect pin) | connect to GND or leave floating | TI TPS7A02 DS SBVS277C Table 5-1 |
