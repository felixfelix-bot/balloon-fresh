# STATUS: balloon-range-tests

**Last Updated**: 2026-07-24 (session 4)
**Phase**: Adaptive sweep firmware built. All software done. Ready for outdoor test.

## Current State

### Bugs Fixed (all verified on hardware)
- RX FIFO race (commit 3dcddaf): GPIO IRQ poll replaces SPI poll. 8+ session bug dead.
- RSSI measurement (commit d85b5ea): LR2021 command 0x024B replaces SX1280 0x022A.
- PER calculation (commit 7a3d150): Multi-burst window handling via cumulative DEADBEEF tracking.
- Packet size mismatch (commit 7a3d150): rx-auto 144→127B matching TX.
- Noise floor measurement (commit 7a3d150): Auto at RX boot via RSSI_INST 0x020B.

### New: Adaptive Bitrate Sweep Firmware (commit 7b00ee2)
- GPS time module (gps_time.h/cpp): NMEA parser + PPS interrupt + millis() fallback
- Sweep scheduler (sweep_scheduler.h/cpp): 4-mode state machine, 12-min cycle
- TX sweep (flrc_range_tx_sweep.cpp): Auto-switches bitrate at window boundaries
- RX sweep (flrc_range_rx_sweep.cpp): Re-arms RX after each switch, full RSSI+PER preserved
- Works WITHOUT GPS (millis fallback). Auto-upgrades to UTC sync when GPS soldered.

### Cross-Track Learnings (from speed-tests, commit 80d9f1d)
- FLRC efficiency: 2600 kbps=23%, 325 kbps=60%. Lower bitrate = better throughput efficiency.
- LoRa bugs pre-solved: CR encoding (5 invalid), RSSI/SNR byte swap, BW codes (812kHz=0x0F).
- Runtime bitrate switching UNTESTED — #1 risk for sweep firmware.

### Total Firmware Envs: 14 (all compile clean)
- 9 original (tx-auto, raw-rx-127, rx-auto, 6x bitrate pairs)
- 3 new sweep (tx-sweep, rx-sweep, gps-time-test)
- 2 legacy (raw-rx, raw-rx-20mhz)

## Board Assignments

| Role | Serial | Notes |
|------|--------|-------|
| TX   | E663B035977F242D | F242D. Port swaps on reflash. |
| RX   | E663B035973B8332 | 8332. Port swaps on reflash. |

**ALWAYS verify by serial number. Acquire/release BOTH boards atomically.**

## Verified Performance (Indoor, ~30cm)

| Metric | Value | Notes |
|--------|-------|-------|
| Signal RSSI | -60 dBm | At 12.5 dBm TX power, PA enabled |
| Noise floor | -103 dBm | Measured at boot |
| SNR | 43 dB | Excellent link margin |
| PER | 0% | At 12.5 dBm, 2600 kbps, 127B |
| Throughput | 219 kbps | Continuous RX mode |
| TX rate | 1558 kbps | 500-pkt bursts, 0 timeouts |

## #1 RISK: Runtime Bitrate Switching

Our sweep firmware is the FIRST attempt at runtime FLRC bitrate changes on LR2021.
Speed-tests group avoided this entirely (used compile-time only).
Our approach switches between bursts (not during TX), so CDC death shouldn't apply.
BUT: radio may need full re-init of all registers, not just MOD_PARAMS.

**Verification needed before outdoor test**: Flash sweep firmware, confirm RSSI/PER
differs between bitrate windows at same distance. If identical → switch not working.

## Git State

- Branch: range-tests
- Latest: 80d9f1d (cross-track learnings + test_runner.py)
- All pushed to: ngit + GitHub (felixfelix-bot/balloon-fresh)
- Working tree: clean

## Next Steps (Physical — Operator Required)

1. Flash sweep firmware on both boards (rp2040-range-tx-sweep + rp2040-range-rx-sweep)
2. Verify runtime bitrate switching works (indoor smoke test — see SWEEP_SWITCH messages)
3. If switching works: outdoor test, stand at each distance 12 min for full cycle
4. If switching fails: fall back to compile-time bitrate envs (one reflash per bitrate)
5. Solder GPS module when ready (GP0=TX, GP1=RX, GP9=PPS) — zero code changes needed
