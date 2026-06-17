# Range Test Plan — LR2021 RF Characterization

## Overview
Comprehensive RF characterization of LR2021 (NiceRF LoRa2021) across all modes, frequencies,
and parameter combinations. TX fixed at high point, RX mobile in car with GPS + laptop.

## Hardware
- **TX**: ESP32-C3 (96:DC) + LR2021, Sub-GHz + 2.4GHz antennas, USB power bank, fixed location
- **RX**: ESP32-C3 (C6:98) + LR2021 + GPS (MAX-M10S on GPIO1), Sub-GHz + 2.4GHz antennas, laptop via USB-C
- **GPS**: u-blox MAX-M10S, UART1 RX on GPIO1, 9600 baud, NMEA, non-blocking cached reads

## 16 Test Windows Per Loop (~7 min)

### LoRa Windows (8)
| # | Name           | Band | SF | BW kHz | CR  | PKT | Count | Delay |
|---|----------------|------|----|--------|-----|-----|-------|-------|
| 1 | L12-868-S12    | 868  | 12 | 125    | 4/5 | 28B | 20    | 1s    |
| 2 | L12-868-S9     | 868  | 9  | 125    | 4/5 | 28B | 20    | 1s    |
| 3 | L12-868-S9W    | 868  | 9  | 500    | 4/5 | 28B | 20    | 500ms |
| 4 | L12-868-S7     | 868  | 7  | 125    | 4/5 | 28B | 20    | 500ms |
| 5 | L12-868-S9CR7  | 868  | 9  | 125    | 4/7 | 28B | 20    | 1s    |
| 6 | L12-2G4-S12    | 2.4G | 12 | 125    | 4/5 | 28B | 20    | 1s    |
| 7 | L12-2G4-S9     | 2.4G | 9  | 125    | 4/5 | 28B | 20    | 1s    |
| 8 | L12-2G4-S7     | 2.4G | 7  | 125    | 4/5 | 28B | 20    | 500ms |

### FLRC Windows (8)
| #  | Name            | Band | BR kbps | CR   | PKT  | Count | Delay |
|----|-----------------|------|---------|------|------|-------|-------|
| 9  | F868-260-CR12   | 868  | 260     | 1/2  | 50B  | 50    | 100ms |
| 10 | F868-650-CR34   | 868  | 650     | 3/4  | 50B  | 50    | 50ms  |
| 11 | F868-1300-CR10  | 868  | 1300    | 1/0  | 100B | 100   | 10ms  |
| 12 | F868-1300-CR34  | 868  | 1300    | 3/4  | 100B | 100   | 10ms  |
| 13 | F868-2600-CR10  | 868  | 2600    | 1/0  | 100B | 100   | 10ms  |
| 14 | F2G4-260-CR12   | 2.4G | 260     | 1/2  | 50B  | 50    | 100ms |
| 15 | F2G4-1300-CR10  | 2.4G | 1300    | 1/0  | 100B | 100   | 10ms  |
| 16 | F2G4-2600-CR10  | 2.4G | 2600    | 1/0  | 100B | 100   | 10ms  |

## Sync Protocol
- TX sends 5 sync packets (20B markers) before each window
- RX scans through candidate modes, detects sync, reconfigures, counts data
- No clock alignment needed between boards
- TX loops forever until power disconnected

## Data Output
- Per-packet CSV: `range_packets_YYYYMMDD_HHMMSS.csv` (every received packet with GPS)
- Per-window CSV: `range_summary_YYYYMMDD_HHMMSS.csv` (window summary with GPS)
- Serial lines: `PKT,...` (per-packet) and `RESULT,...` (per-window)
- GPS: non-blocking cached reads, 1 Hz update rate, latest fix reused

## GPS Wiring (deferred)
- MAX-M10S TX → GPIO1 (ESP32-C3 UART1 RX)
- VCC → 3.3V, GND → GND
- Firmware already supports GPS, compiles with GPS code
- Without GPS wired: fix=0, all GPS fields=0 in CSV

## Implementation Checklist
- [ ] Create RANGE-TEST-PLAN.md
- [ ] Fix gpio_install_isr_service double-init in EspHalC3.h
- [ ] Copy GPS component from tracker firmware
- [ ] Create range_test.h (16 window definitions)
- [ ] Create range_test.cpp (TX loop + RX scanner + GPS per-packet)
- [ ] Update Kconfig.projbuild (RANGE_TX, RANGE_RX, RANGE_TEST_GPS)
- [ ] Update main/CMakeLists.txt (add sources + GPS dependency)
- [ ] Build range_tx.bin and range_rx.bin
- [ ] Create monitor_range.py (auto-detect + dual CSV)
- [ ] Install pyserial
- [ ] Flash both boards and bench verify all 16 windows
- [ ] Commit and push

## Deferred
- [ ] Wire GPS to RX board (GPIO1)
- [ ] City driving test campaign
- [ ] Post-process CSV data, plot RSSI/PER vs distance
