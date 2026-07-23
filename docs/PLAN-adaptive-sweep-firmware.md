# UPDATED PLAN: Adaptive Sweep + Outdoor Range Test

**Date:** 2026-07-24 (updated)
**Status:** All software complete. Sweep firmware built but runtime switching UNTESTED.

## COMPLETED

### Software Fixes (all verified on hardware)
- [x] GPIO IRQ poll (3dcddaf) — 8+ session FIFO race bug
- [x] RSSI via 0x024B (d85b5ea) — -60 dBm signal, -103 dBm noise floor
- [x] PER calculation (7a3d150) — multi-burst DEADBEEF tracking
- [x] Packet size 144→127B (7a3d150)
- [x] Noise floor at boot (7a3d150)

### Adaptive Sweep Firmware (7b00ee2, compiles, UNTESTED on hardware)
- [x] GPS time module (NMEA + PPS + millis fallback)
- [x] Sweep scheduler (4-mode, 12-min cycle, UTC/millis anchored)
- [x] TX sweep firmware
- [x] RX sweep firmware
- [x] Cross-track learnings integrated (80d9f1d)

### Build Verification
- [x] All 14 envs compile clean, zero regressions

---

## PHASE 7 (NEXT): Indoor Smoke Test of Sweep Firmware
**Requires:** Operator + boards connected
**Goal:** Verify runtime bitrate switching actually changes radio parameters

### Why This Matters
Speed-tests group avoided runtime bitrate changes entirely. Our sweep firmware is the first attempt. If the radio doesn't actually change bitrate, we need a fallback plan BEFORE going outdoors.

### Test Steps
1. Acquire both boards
2. Flash rp2040-range-tx-sweep (TX) and rp2040-range-rx-sweep (RX)
3. Monitor serial output for 13+ minutes (one full sweep cycle)
4. Verify SWEEP_SWITCH messages appear every 3 minutes
5. Compare RSSI across bitrate windows:
   - If RSSI differs between windows → switching works
   - If RSSI identical across all windows → switch failed, radio stuck at init bitrate
6. Compare RX packet count between windows:
   - Different counts per window suggests bitrate actually changed
   - Identical counts suggests no change

### Fallback If Switching Fails
Use compile-time bitrate envs (speed-tests approach):
- Flash rp2040-range-tx-2600 + rp2040-raw-rx-127, test 12 min
- Reflash rp2040-range-tx-1300 + rp2040-range-rx-1300, test 12 min
- Reflash rp2040-range-tx-650 + rp2040-range-rx-650, test 12 min
- Reflash rp2040-range-tx-325 + rp2040-range-rx-325, test 12 min
Slower (4 reflashes) but proven to work.

---

## PHASE 8: Outdoor Range Test
**Requires:** Operator outside, boards, USB battery

### Setup
- RX stays at laptop (connected via USB)
- TX on battery power, positioned at test distance
- Wait 12+ minutes per distance (one full sweep cycle)

### Test Points
1. 10m — baseline outdoor (expect strong signal)
2. 50m — moderate distance
3. 100m — practical range test
4. 500m — stress test (may lose FLRC, need LoRa)

### Data Collection
- Record serial output to file: `timeout 780 cat /dev/ttyACMx > distance_10m.txt`
- Parse with: `python3 tools/test_runner.py parse --file distance_10m.txt`
- Fill in: data/range-test-template.csv

### Expected Results (free-space path loss model)
At 2440 MHz, 12.5 dBm TX, PA enabled:
- 10m: -47 dBm (strong, expect 0% PER all bitrates)
- 50m: -61 dBm (strong, expect 0% PER)
- 100m: -67 dBm (moderate, 2600 may start dropping)
- 500m: -81 dBm (weak, 2600/1300 likely fail, 650/325 may work)

---

## PHASE 9: LoRa Fallback Mode (ADR-007 Phase 4)
**Requires:** Software development + future outdoor test

### What
Implement LoRa mode in the sweep firmware. When FLRC PER exceeds threshold, switch to LoRa SF7/SF12 for maximum range.

### Pre-Solved Bugs (from speed-tests)
- CR encoding: use 1-4, NOT 5
- RSSI/SNR: buf[2]=RSSI, buf[3]=SNR (LoRa only)
- BW codes: 812 kHz = 0x0F

### Status
Not started. Depends on successful FLRC outdoor results first.

---

## PHASE 10: GPS Integration
**Requires:** Operator solders GPS module

### Hardware
- GPS TX → GP1 (RP2040 UART0 RX)
- GPS RX → GP0 (RP2040 UART0 TX)
- GPS PPS → GP9 (interrupt)
- 3.3V + GND

### Software
ZERO code changes. Firmware auto-detects GPS lock via NMEA. Switches from millis() to UTC scheduling automatically.

### Recommended GPS Module
ATGM336H (cheap, multi-GNSS, 9600 baud default) or NEO-6M (common, well-documented).

---

## ROADMAP SUMMARY

```
Phase 7: Indoor sweep smoke test ← NEXT (needs operator)
    ↓
Phase 8: Outdoor range test (FLRC sweep)
    ↓
Phase 9: LoRa fallback mode (software)
    ↓
Phase 10: GPS integration (solder + zero code changes)
    ↓
Flight firmware: ADR-007 full adaptive protocol
```
