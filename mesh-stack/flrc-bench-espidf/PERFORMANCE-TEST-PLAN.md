# Performance Test Plan

## Overview
Comprehensive RF performance characterization of LR2021 dual-band (868 MHz + 2.4 GHz)
using two ESP32-C3 SuperMini boards. Covers bench verification, automated sweeps,
stress testing, and outdoor range characterization.

## Hardware
- **TX board**: ESP32-C3 (MAC 96:DC), ttyACM0, LR2021 + wire dipoles
- **RX board**: ESP32-C3 (MAC C6:98), ttyACM1, LR2021 + wire dipoles
- **Note**: TX board has flaky USB connector — may disconnect. TX role is fire-and-forget once flashed.

## Firmware Inventory (all built and tested)
| Binary | Size | Config | Purpose |
|--------|------|--------|---------|
| `range_tx.bin` | ~252KB | RANGE_TX | 16-window TX loop with NVS logging |
| `range_rx.bin` | ~283KB | RANGE_RX + GPS | RX scanner with GPS + NVS |
| `range_dump.bin` | ~198KB | DUMP | NVS data recovery via serial |
| `spi_loopback.bin` | ~201KB | SPI_LOOPBACK | SPI wiring verification (needs jumper) |
| `continuity_test.bin` | ~169KB | CONTINUITY | Solder short detection |
| `auto_tx.bin` | ~258KB | AUTONOMOUS_TX | Autonomous benchmark TX |
| `interactive.bin` | ~241KB | INTERACTIVE | Manual benchmarker |

---

## Checklist

### Phase 1: Commit & Push (5 min)
- [ ] 1.1 Verify git status and diff
- [ ] 1.2 Stage all new/modified files
- [ ] 1.3 Commit with descriptive message
- [ ] 1.4 Push to remote

### Phase 2: Flash Firmware (5 min)
- [ ] 2.1 Build range_tx.bin (RANGE_TX config)
- [ ] 2.2 Flash range_tx.bin to TX board (ttyACM0 / 96:DC)
- [ ] 2.3 Build range_rx.bin (RANGE_RX + GPS config)
- [ ] 2.4 Flash range_rx.bin to RX board (ttyACM1 / C6:98)

### Phase 3: Bench Verification of Range Test (15 min)
- [ ] 3.1 Monitor RX board serial: `python monitor_range.py --port /dev/ttyACM1`
- [ ] 3.2 Verify TX starts transmitting (LED blinks on TX board)
- [ ] 3.3 Verify RX detects TX within 30 seconds
- [ ] 3.4 Verify all 16 windows complete in one loop (~7 min)
- [ ] 3.5 Verify PKT CSV lines appear (per-packet data)
- [ ] 3.6 Verify RESULT CSV lines appear (per-window summaries)
- [ ] 3.7 Check PER = 0% and RSSI reasonable at 1m bench range
- [ ] 3.8 Save serial output to log file

### Phase 4: NVS Logging Verification (10 min)
- [ ] 4.1 Wait for at least 1 complete TX loop (16 windows)
- [ ] 4.2 Flash range_dump.bin to TX board
- [ ] 4.3 Verify TX NVS has per-window TX data (role=TX)
- [ ] 4.4 Flash range_dump.bin to RX board
- [ ] 4.5 Verify RX NVS has per-window RX data (role=RX, GPS fields)
- [ ] 4.6 Compare TX sent count with RX received count

### Phase 5: Automated Sweeps (1 hour, can be unattended)
- [ ] 5.1 Flash interactive.bin to both boards
- [ ] 5.2 Run FLRC bit rate sweep (2.4 GHz): 260, 325, 520, 650, 1040, 1300, 2080, 2600 kbps
- [ ] 5.3 Run FLRC bit rate sweep (868 MHz): same 8 bit rates
- [ ] 5.4 Run power sweep (2.4 GHz): 0, 2, 4, 6, 8, 10, 12 dBm
- [ ] 5.5 Run power sweep (868 MHz): 0, 5, 10, 15, 20, 22 dBm
- [ ] 5.6 Run packet size sweep: 10, 20, 30, 50, 75, 100, 150, 200, 255 bytes
- [ ] 5.7 Run coding rate sweep: CR 1/2, 2/3, 3/4, 1/0
- [ ] 5.8 Run LoRa SF sweep: SF7, SF8, SF9, SF10, SF11, SF12
- [ ] 5.9 Save all CSV results

### Phase 6: Stress & Endurance Test (1+ hour, unattended)
- [ ] 6.1 Flash range_tx.bin to TX board
- [ ] 6.2 Flash range_rx.bin to RX board
- [ ] 6.3 Start continuous monitoring: `python monitor_range.py --port /dev/ttyACM1`
- [ ] 6.4 Let run for 1+ hour (multiple TX loops)
- [ ] 6.5 Monitor for: intermittent failures, brownouts, packet loss patterns
- [ ] 6.6 Check thermal stability (radio should be warm, not hot)
- [ ] 6.7 Flash range_dump.bin after, verify accumulated data
- [ ] 6.8 Document any failures or anomalies

### Phase 7: Data Analysis & Documentation (30 min)
- [ ] 7.1 Merge all CSV files
- [ ] 7.2 Compare with previous RESULTS.md data
- [ ] 7.3 Update RESULTS.md with new findings
- [ ] 7.4 Update BENCHMARK-PLAN.md checklist
- [ ] 7.5 Update RANGE-TEST-PLAN.md checklist
- [ ] 7.6 Commit and push results

### Phase 8: Outdoor Range Test (future, needs GPS + travel)
- [ ] 8.1 Wire GPS module to RX board (MAX-M10S TX → GPIO1)
- [ ] 8.2 Verify GPS fix in serial output
- [ ] 8.3 Prepare TX power supply (USB power bank)
- [ ] 8.4 Test at increasing distances: 50m, 200m, 500m, 1km, 2km, 5km
- [ ] 8.5 Record GPS coordinates at each point
- [ ] 8.6 Plot RSSI/PER vs distance

---

## Test Matrix Summary

### Already Completed (RESULTS.md, 2026-06-11)
- LoRa SF9 868 MHz: 0% PER, 0.2 kbps
- FLRC 325/650/1300/2600 @ 868 MHz: all 0% PER
- FLRC burst test: 50% PER at 0ms, 0% PER at 20ms spacing
- FLRC 1300/2600 @ 2.4 GHz: 0% PER
- Power sweeps, packet size sweeps (initial)

### Still Needed
- Range test 16-window protocol verification (Phase 3)
- NVS logging verification (Phase 4)
- Complete automated sweep matrix (Phase 5)
- Endurance/stress data (Phase 6)
- Outdoor range data (Phase 8)
