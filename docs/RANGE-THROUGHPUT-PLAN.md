# Range & Throughput Test Plan

## Overview

Systematic characterization of LR2021 FLRC and LoRa modulation modes at varying distances to determine range-vs-rate tradeoff curves. Results feed into adaptive protocol design for balloon telemetry.

## Hardware

- **MCU**: 2x RP2040 (Pico W boards on DQ05)
  - TX board: E663B035973B8332
  - RX board: E663B035977F242D
- **Radio**: LR2021 (Semtech Gen 4), 2.4 GHz
- **Current modules**: +13 dBm (100 mW)
- **Phase 2 modules**: NiceRF F33-2G4 (+33 dBm / 2W PA) — awaiting arrival
- **Antenna**: Wire dipole, 61mm element at 2440 MHz (lambda/2)
- **Power**: Direct LiPo or powerbank with dummy load (>50mA total draw)

## Firmware

- **LR2021Raw library** (VERIFIED): Raw 2-byte opcode SPI, NO RadioLib
  - Library: `~/repos/balloon-fresh/firmware/rp2040-sweep/src/LR2021Raw.h`
  - Verified: 2500 pkts/s TX at 2600 kbps FLRC, 0 fails over 250K+ packets
  - RSSI: -77 dBm close range (correct 9-bit GET_FLRC_PACKET_STATUS 0x024B)
- **Range test firmware** (this worktree): `firmware/rp2040/src/flrc_range_{tx,rx}_{auto,gps}.cpp`
  - RSSI FIXED: 0x024B 9-bit assembly (was broken SX1280 0x0104)
  - Uses same raw opcode protocol, single-batch SPI transfers
- **BANNED**: RadioLib LR2021 driver (protocol mismatch, ADR-020), rp2040-flrc-max

### Known Constraints (from speed-tests track)

- Verified E2E with LR2021Raw: 2500 pkts/s at 2600 kbps FLRC, 0 fails over 250K+ packets
- Previous best: 1377 kbps (single-batch Arduino SPI, RadioLib era — superseded)
- Per-packet: RF air 803us (54%), SPI 535us (36%), loop 154us (10%)
- SPI bottleneck: Arduino per-byte overhead — only working path

### DO NOT RETRY (all failed on real hardware)
1. Pico SDK `spi_write_blocking` — fake TX_DONE, 0 RX packets
2. DMA via `spi0_hw->dr` — radio init fails
3. Direct HW SPI registers — no transmission
4. PIO state machine TX v1/v2/v3 — hangs, CDC death
5. 20 MHz RX SPI — 77% packet loss
6. Runtime SPI clock change — breaks radio permanently
7. Preamble 16→8 — breaks radio sync

---

## Phase 1: Ground-Level Characterization (EXECUTE NOW)

### Prerequisites
- [ ] Flash rp2040-flrc-max on both boards (TX + RX)
- [ ] Solve powerbank auto-shutoff (dummy load >50mA or direct LiPo)
- [ ] Add wire dipole antennas (61mm wire at 2440 MHz)
- [ ] Verify boards communicate at <1m (baseline check)

### Test Matrix

| Modulation | Bitrate | Distances (m, LOS) |
|-----------|---------|---------------------|
| FLRC | 2600 kbps | 10, 50, 100, 200, 500, 1000 |
| FLRC | 1300 kbps | 10, 50, 100, 200, 500, 1000 |
| FLRC | 650 kbps | 10, 50, 100, 200, 500, 1000 |
| FLRC | 325 kbps | 10, 50, 100, 200, 500, 1000 |
| LoRa | 22 kbps | 100, 500, 1000, 5000 |

### Per-Point Measurements
- Packet rate (pkts/s)
- RSSI (dBm, negated)
- Packet loss (%)
- Duration: minimum 60s per point

### RadioLib LR2021 FLRC Bitrate Constants
```
RADIOLIB_LR2021_FLRC_BR_2600  (0x00)  — 2666 kHz BW, max
RADIOLIB_LR2021_FLRC_BR_2080  (0x01)  — 2222 kHz BW
RADIOLIB_LR2021_FLRC_BR_1300  (0x02)  — 1333 kHz BW
RADIOLIB_LR2021_FLRC_BR_1040  (0x03)  — 1333 kHz BW
RADIOLIB_LR2021_FLRC_BR_650   (0x04)  — 888 kHz BW (default — what raw firmware was using)
RADIOLIB_LR2021_FLRC_BR_520   (0x05)  — 769 kHz BW
RADIOLIB_LR2021_FLRC_BR_325   (0x06)  — 444 kHz BW
RADIOLIB_LR2021_FLRC_BR_260   (0x07)  — 444 kHz BW
```

### Output
- Throughput-vs-distance curve for each modulation mode
- RSSI-vs-distance curve (note: AGC saturation at close range)
- Packet loss-vs-distance curve
- CSV data files per test point

---

## Phase 2: 2W Power Validation (AFTER F33 MODULES ARRIVE)

### Prerequisites
- NiceRF F33-2G4 modules (+33 dBm / 2W PA) in hand
- Flight PCB prototype built

### Test Plan
- Replace +13 dBm modules with F33-2G4 (+33 dBm)
- Repeat key distance points from Phase 1:
  - FLRC 2600 kbps: 100m, 500m, 1km, 2km, 5km
  - FLRC 650 kbps: 500m, 1km, 5km, 10km
  - LoRa 22 kbps: 1km, 5km, 10km, 50km
- Measure: range improvement vs +13 dBm baseline
- Expected: +20 dB power → ~10x range improvement (free space)

### Power Consumption
- 2W TX draws ~3-4W DC
- Duty cycle calculation for solar/supercap power budget
- Continuous TX thermal validation

---

## Phase 3: Altitude Simulation (NEEDS CIRCUIT DESIGN)

### Prerequisites
- Flight PCB with F33 module designed and fabricated
- Vacuum chamber access

### Test Plan
- Build flight PCB with F33 module
- Vacuum/pressure test (simulate 10-15km altitude)
- Cold soak (-60°C typical at altitude)
- UV exposure test
- Verify TX power stability and frequency accuracy under conditions

---

## Phase 4: First Flight

### Payload
- F33 + ESP32-C3 + solar + supercap + wire dipole
- Weight target: <14g (Mesh V1 variant)

### Ground Station
- F33 + directional antenna + Pi logger
- 24/7 systemd RX logger (existing `rx_range_logger.py`)

### Firmware
- Adaptive protocol: FLRC 2600 → 1300 → 650 → LoRa fallback
- Runtime modulation switching via `radio.beginFLRC()` / `radio.beginLoRa()`
- 24-byte binary telemetry with CRC-16

### Flight Parameters
- Altitude: 10-15 km
- Duration: 4-12 hours
- Log all packets with timestamps + GPS correlation

---

## Phase 5: Range Ceiling Discovery (POST-FLIGHT ANALYSIS)

### Analysis
- Correlate flight GPS with ground station packet log
- Plot throughput vs slant range
- Identify: at what range does each modulation drop below usable threshold?
- Define adaptive protocol thresholds for flight firmware

### Expected Range with 2W on Both Ends

| Modulation | Bitrate | Ground LOS | At Altitude |
|-----------|---------|-----------|-------------|
| FLRC | 2600 kbps | 2-5 km | 20-50 km |
| FLRC | 650 kbps | 10-20 km | 50-100+ km |
| LoRa | 22 kbps | 50-100 km | 200-500+ km |

---

## Test Data Location

- GPS data: `/tmp/gps4/20260722.csv` or `~/repos/balloon-fresh/docs/coordination/`
- RX logger: `/var/log/rx-logger/*.csv` on DQ05
- Previous walk data: 207,940 packets, 85 min, 3.5km walk (2026-07-22)
- Plots: `/tmp/plots/` (4 PNGs already generated)

## Previous Range Test Findings (2026-07-22 Walk)

- 750+ pkts/s at close range (0-35m) with LOS
- Signal lost beyond ~35m without LOS (2.4 GHz blocked by walls)
- RSSI stuck at -20 dBm (AGC saturation at close range)
- TX board kept dying — powerbank auto-shutoff at ~20mA draw
- 206,947 total packets captured during walk
- Need 200m+ with LOS and continuous TX power for real RSSI-vs-distance curve