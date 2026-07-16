# FLRC Range Test Plan — Parameter Sweep for Coverage & Reliability

**Date:** 2026-07-16
**Status:** ACTIVE — ready to execute
**Repo:** balloon-fresh
**Depends on:** Nothing — current firmware is ready
**Blocks:** Nothing — runs in parallel with speed optimization

---

## 1. Objective

Measure FLRC link performance (packet loss, RSSI, throughput) across:
- Distances (1m to 500m+)
- FLRC bitrates (325–2600 kbps)
- TX power levels (0–12 dBm)
- Payload sizes (12–255 bytes)
- Antennas and orientations
- Environmental obstacles

Goal: build a complete link budget table showing what configurations work at what distances.

---

## 2. Current Baseline (Verified 2026-07-16)

| Parameter | Value |
|-----------|-------|
| Frequency | 2440 MHz |
| FLRC bitrate | 2600 kbps |
| TX power | +12 dBm |
| Payload | 255 bytes |
| Preamble | 8 symbols |
| Sync word | 0x12AD101B |
| SPI clock | 16 MHz (12 MHz actual on RP2040) |
| Throughput | 1391 kbps |
| Packet loss | 0% at bench distance (~30 cm) |
| Boards | 2x RP2040 Pico + NiceRF LR2021 |

**Firmware:** `firmware/rp2040/src/flrc_raw_tx.cpp` (env: `rp2040-raw-tx`), `flrc_raw_rx.cpp` (env: `rp2040-raw-rx`)

---

## 3. Parameters to Sweep

### 3.1 Distance
| Test Point | Environment | Notes |
|------------|-------------|-------|
| 1 m | Bench | Sanity check |
| 5 m | Indoor hallway | |
| 10 m | Indoor | Through 1 wall |
| 25 m | Indoor | Through 2 walls |
| 50 m | Outdoor LOS | Parking lot / garden |
| 100 m | Outdoor LOS | |
| 200 m | Outdoor LOS | |
| 500 m | Outdoor LOS | If achievable |

### 3.2 FLRC Bitrate
Lower bitrate = more energy per bit = better SNR = more range.

| Bitrate | Air time (255B) | Use case |
|---------|-----------------|----------|
| 2600 kbps | ~803 µs | Max throughput, shortest range |
| 1300 kbps | ~1606 µs | Balanced |
| 650 kbps | ~3212 µs | Extended range |
| 325 kbps | ~6424 µs | Max range, mesh relay fallback |

### 3.3 TX Power
| Power | Note |
|-------|------|
| +12 dBm | Max for 2.4 GHz on LR2021 |
| +10 dBm | |
| +6 dBm | |
| 0 dBm | Find minimum usable power |

### 3.4 Payload Size
| Size | Air time @ 2600kbps | Notes |
|------|---------------------|-------|
| 255 B | ~803 µs | Max payload |
| 127 B | ~400 µs | Half payload |
| 64 B | ~200 µs | Telemetry-sized |
| 32 B | ~100 µs | Minimal telemetry |
| 12 B | ~37 µs | Position ping only (lat/lon/alt) |

### 3.5 Preamble Length
| Symbols | Duration @ 2600kbps | Risk |
|---------|---------------------|------|
| 8 | ~3 µs | Current, safe |
| 4 | ~1.5 µs | Marginal sync |
| 2 | ~0.75 µs | Likely fails at range |

### 3.6 Frequency
| Frequency | Note |
|-----------|------|
| 2400 MHz | Band edge |
| 2440 MHz | Current center |
| 2480 MHz | Band edge |

### 3.7 Antenna
| Antenna | Type | Gain |
|---------|------|------|
| Wire dipole (current) | Omni | ~2 dBi |
| PCB trace | Semi-directional | ~0 dBi |
| External SMA dipole | Omni | ~3 dBi |

### 3.8 Orientation
| Orientation | Note |
|-------------|------|
| Vertical-vertical | Best case |
| Horizontal-horizontal | Best case (aligned) |
| Vertical-horizontal | Worst case (cross-pol, -20 dB) |
| Rotating (balloon sim) | Real-world: balloon spins |

### 3.9 Obstacles
| Environment | Loss |
|-------------|------|
| Open field (LOS) | 0 dB |
| Through 1 drywall | ~4 dB |
| Through 2 walls | ~8 dB |
| Through concrete | ~15 dB |
| Through glass window | ~2 dB |

---

## 4. Test Matrix (Prioritized)

### Phase 1: Distance Sweep at Baseline Config
**Config:** 2600 kbps, 255B, +12 dBm, preamble=8, 2440 MHz, wire dipole

| Test # | Distance | Environment | Expected |
|--------|----------|-------------|----------|
| R1.1 | 1 m | Bench | 0% loss |
| R1.2 | 5 m | Indoor LOS | 0% loss |
| R1.3 | 10 m | 1 wall | <5% loss |
| R1.4 | 25 m | 2 walls | <30% loss |
| R1.5 | 50 m | Outdoor LOS | <5% loss |
| R1.6 | 100 m | Outdoor LOS | ? |
| R1.7 | 200 m | Outdoor LOS | ? |
| R1.8 | 500 m | Outdoor LOS | ? |

### Phase 2: Bitrate Sweep at Max Usable Distance
Take the max distance from Phase 1 where loss < 30%. Sweep bitrates at that distance.

| Test # | Bitrate | Payload | Expected |
|--------|---------|---------|----------|
| R2.1 | 2600 kbps | 255 B | (Phase 1 result) |
| R2.2 | 1300 kbps | 255 B | Lower loss |
| R2.3 | 650 kbps | 255 B | Much lower loss |
| R2.4 | 325 kbps | 255 B | Should work |

### Phase 3: Payload Size Sweep
At max distance, at best bitrate from Phase 2.

| Test # | Payload | Expected |
|--------|---------|----------|
| R3.1 | 255 B | (Phase 2 result) |
| R3.2 | 127 B | Better |
| R3.3 | 64 B | Better still |
| R3.4 | 32 B | Near-zero loss? |
| R3.5 | 12 B | Position ping |

### Phase 4: Environmental & Antenna
At a fixed distance (~50 m outdoor).

| Test # | Variable | Value |
|--------|----------|-------|
| R4.1 | Orientation | Vertical-vertical |
| R4.2 | Orientation | Cross-polarization |
| R4.3 | Power | +6 dBm |
| R4.4 | Power | 0 dBm |
| R4.5 | Frequency | 2400 MHz |
| R4.6 | Frequency | 2480 MHz |

---

## 5. Required Hardware

- 2x RP2040 Pico + LR2021 boards (F242D = TX, 8332 = RX)
- 2x USB power banks (for portable TX)
- Laptop (connected to RX board via USB)
- Tape measure (or phone GPS for distance)
- Antenna variants (if available)
- Notebook or spreadsheet for results

---

## 6. Test Procedure

### 6.1 Flash Firmware
```bash
cd ~/repos/balloon-fresh/firmware/rp2040

# Flash TX board (F242D on ACM0)
pio run -e rp2040-raw-tx -t upload --upload-port /dev/ttyACM0

# Flash RX board (8332 on ACM3)
pio run -e rp2040-raw-rx -t upload --upload-port /dev/ttyACM3
```

For parameter changes (bitrate, payload, power), modify the compile-time constants in `flrc_raw_tx.cpp` and `flrc_raw_rx.cpp`, rebuild, reflash both boards.

### 6.2 Run Test
```bash
cd ~/repos/balloon-fresh
python3 scripts/coordinated_tx_rx_test.py
```

This script:
1. Sends RUN to RX board (2s head start to enter RX mode)
2. Sends RUN to TX board (starts 1000-packet burst)
3. Captures both serial ports for 15s
4. Parses TX_DONE count, RX packet count, throughput

### 6.3 Record Results
Fill the CSV row for each test point:

```
date,distance_m,bitrate_kbps,tx_power_dbm,payload_bytes,preamble,freq_mhz,antenna,orientation,obstacle,tx_sent,rx_received,loss_pct,rssi_dbm,throughput_kbps,notes
2026-07-16,1,2600,12,255,8,2440,wire_dipole,vv,none,1000,1018,0,N/A,1391,bench_baseline
```

---

## 7. Data Collection Format

CSV file: `data/range-test-results.csv`

| Column | Type | Example |
|--------|------|---------|
| date | date | 2026-07-16 |
| distance_m | int | 50 |
| bitrate_kbps | int | 2600 |
| tx_power_dbm | int | 12 |
| payload_bytes | int | 255 |
| preamble_symbols | int | 8 |
| freq_mhz | float | 2440 |
| antenna_type | string | wire_dipole |
| orientation | string | vv (vert-vert), hv (cross) |
| obstacle | string | none, 1wall, concrete |
| tx_sent | int | 1000 |
| rx_received | int | 950 |
| loss_pct | float | 5.0 |
| rssi_dbm | int | -75 (if available) |
| throughput_kbps | float | 1320 |
| notes | string | "wind, clear day" |

---

## 8. Decision Criteria

| Loss Rate | Verdict | Action |
|-----------|---------|--------|
| < 5% | Usable link | Deploy this config |
| 5–15% | Marginal | Add FEC or ACK/retry |
| 15–30% | Poor | Reduce bitrate or payload |
| > 30% | Not usable | Drop to lower bitrate, smaller payload |

---

## 9. RSSI Measurement

The LR2021 exposes RSSI via `GET_RSSI_INST` command (opcode 0x01, 0x18).

Firmware enhancement needed: add RSSI read to RX firmware after each packet:
```cpp
// Read RSSI after packet received
uint8_t cmd[] = { 0x01, 0x18 };  // GET_RSSI_INST
// Returns 2 bytes: status + RSSI (signed, dBm)
```

This is a firmware change to `flrc_raw_rx.cpp` — add RSSI reporting to the serial output.

---

## 10. Firmware Support Needed

### Current (ready for Phase 1):
- Fixed 2600 kbps, 255B, +12 dBm → distance sweep only

### For Phase 2 (bitrate sweep):
Change `SET_FLRC_MOD_PARAMS` byte in init:
```cpp
// 0x00 = 2600 kbps, 0x01 = 1300, 0x02 = 650, 0x03 = 325
uint8_t cmd_modparams[] = { 0x02, 0x48, BR_CODE, 0x25 };
```
Make `BR_CODE` a compile-time `#define`.

### For Phase 3 (payload sweep):
Change `FLRC_PKT_SIZE` from 255 to desired value.

### For Phase 4 (power sweep):
Change TX power byte in `SET_TX_POWER`:
```cpp
uint8_t cmd_power[] = { 0x02, 0x03, (uint8_t)(TX_POWER_DBM * 2), 0x04 };
```

### Runtime-configurable firmware (nice to have):
Add serial command parser to set bitrate/payload/power without reflashing. Parse commands like `CONFIG BR=1300 SIZE=127 POWER=6`.

---

## 11. Parallelism with Speed Track

This track uses the **current verified firmware** (1391 kbps). The speed optimization track may produce new firmware (ESP32 DMA, PIO fixes). These are independent:

- **Range tests** answer: "how far does 1391 kbps reach?"
- **Speed tests** answer: "can we go faster than 1391 kbps?"

If speed tests produce a faster firmware, range tests can re-run with the new firmware to measure how the higher bitrate affects range.

**Board sharing:** Both tracks use the same two RP2040 boards. Coordinate to avoid both trying to flash simultaneously.

---

## 12. Links

- [FLRC Final Summary](flrc-final-summary-2026-07-16.md)
- [Platform Analysis](flrc-platform-analysis-2026-07-16.md)
- [Speed Optimization Plan](PLAN-speed-optimization.md)
- [Timing Profile Data](flrc-timing-profile-2026-07-16.md)
- [AGENTS.md](../AGENTS.md) — full pin maps, build commands, inventory
