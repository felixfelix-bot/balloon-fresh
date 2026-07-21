# Comprehensive Range Test Plan (2026-07-17)

## PURPOSE

Systematically characterize the LR2021 FLRC radio link across all
parameters affecting range, reliability, and real-world performance.
This data informs antenna design, power budget, flight planning, and
mesh network topology.

## CURRENT PROVEN CONFIGURATION

| Parameter | Value | Source |
|-----------|-------|--------|
| Frequency | 2440 MHz | Commit dceb6e5 |
| Modulation | FLRC 2600 kbps | RadioLib beginFLRC() |
| TX power | +12 dBm (0x0C) | Firmware default |
| Packet size | 255 bytes | Test firmware |
| Sync word | 0x12AD101B | TX/RX matched |
| Preamble | 16 bits | Standard |
| Throughput | 1377 kbps | Measured |
| Packet loss | 0% at <1m | Measured |
| Boards | 2x RP2040 + LR2021 | Proven link |

## PARAMETERS TO SWEEP (8 AXES)

### Axis 1: Distance (PRIMARY)
**Goal:** Find maximum reliable range at each configuration.

Distances: 1m, 5m, 10m, 25m, 50m, 100m, 200m, 500m

Protocol:
1. TX board fixed at waist height, antenna vertical
2. RX board carried, antenna vertical
3. Send 1000-packet burst at each distance
4. Record: packets received, packet loss %, RSSI if available
5. Mark distance where loss exceeds 1%, 5%, 10%, 50%

Environment variants:
- Indoor (walls, WiFi interference)
- Outdoor line-of-sight (parking lot, field)
- Outdoor with obstruction (trees, buildings between)

Test matrix: 8 distances × 3 environments = 24 data points

### Axis 2: TX Power
**Goal:** Quantify range gain from power increase.

Power levels (LR2021 register 0x0807):
- 0 dBm (0x00)
- +3 dBm (0x03)
- +6 dBm (0x06)
- +9 dBm (0x09)
- +12 dBm (0x0C) — current default
- +12.5 dBm (0x0D) — max

Protocol:
1. Fix distance at 50m (outdoor LOS)
2. Sweep power levels
3. Record packet loss at each level
4. Calculate: dB power increase vs meters gained

Test matrix: 6 power levels at 2 distances (10m, 50m) = 12 data points

### Axis 3: Packet Size
**Goal:** Find optimal payload size for range vs throughput tradeoff.

Packet sizes: 16, 32, 64, 128, 200, 255 bytes

Protocol:
1. Fix distance at 50m, power at +12 dBm
2. TX sends 1000 packets at each size
3. Record: packet loss, throughput (kbps)
4. Calculate: link budget improvement from smaller packets

Expected: smaller packets survive lower SNR → greater range.
FLRC doesn't have spreading gain like LoRa, but shorter packets have
lower collision/corruption probability.

Test matrix: 6 sizes at 2 distances (10m, 50m) = 12 data points

### Axis 4: Modulation Mode
**Goal:** Compare FLRC range vs LoRa range on same hardware.

Modes to test:
- FLRC 2600 kbps (current — fastest, shortest range)
- FLRC 1300 kbps (half rate, potentially better sensitivity)
- LoRa SF5 BW1250 (fastest LoRa)
- LoRa SF7 BW312 (medium range)
- LoRa SF12 BW312 (max range, slowest)

Protocol:
1. Fix distance at 100m, power at +12 dBm
2. Switch both TX and RX to each mode
3. Send 100 packets (fewer for LoRa SF12 — very slow)
4. Record: packet loss, time per packet, effective throughput

NOTE: This requires firmware changes. FLRC mode is current. LoRa mode
needs new init sequence. Can use RadioLib's LoRa begin() or raw SPI.

Test matrix: 5 modes at 1 distance (100m) = 5 data points

### Axis 5: Antenna Configuration
**Goal:** Quantify antenna impact on range.

Antennas to test:
- PCB trace antenna (if on LR2021 module)
- Wire dipole (λ/2 = 61mm at 2440 MHz)
- PCB Yagi (if available from wing board design)
- Ground station high-gain (if available)

Protocol:
1. Fix distance at 50m, power at +12 dBm, FLRC mode
2. Test each antenna on BOTH TX and RX (symmetric)
3. Record: packet loss at fixed distance

Orientation variants:
- Both vertical (reference)
- TX vertical, RX horizontal (polarization mismatch)
- Rotating RX (simulate balloon rotation)

Test matrix: 4 antennas × 3 orientations = 12 data points

### Axis 6: Frequency Channel
**Goal:** Check for WiFi interference impact across 2.4 GHz band.

Frequencies: 2400, 2412, 2422, 2440, 2462, 2480 MHz

Protocol:
1. Fix distance at 10m, power at +12 dBm
2. Sweep frequency on both boards
3. Record: packet loss, any corruption patterns
4. Scan WiFi channels with `iwlist scan` to correlate

NOTE: 2440 MHz = WiFi channel 9 (between ch8 and ch9). Most WiFi uses
channels 1, 6, 11 (2412, 2437, 2462). FLRC at 2440 may avoid WiFi peaks.

Test matrix: 6 frequencies at 1 distance = 6 data points

### Axis 7: EBYTE E28-2G4M27S (+27 dBm PA)
**Goal:** Quantify range with external power amplifier.

NOTE: This requires hardware integration (SPI mux or board swap).
NOT available for initial range tests. List for future.

Expected: +15 dB gain over LR2021's +12 dBm. That's 5.6× range in
free space (√(10^1.5) = 5.6). At 50m baseline, expect ~280m.

### Axis 8: Mobile/Flight Conditions
**Goal:** Simulate real balloon conditions.

Tests:
- Moving RX (walk/drive at 5 km/h, 30 km/h)
- Elevated TX (second floor window, roof)
- Rotating antenna (slow rotation, simulate balloon spin)
- Temperature (if cold environment available)

NOT required for initial characterization. Document for future.

### Axis 9: GPS-Enabled Autonomous Testing (ROADMAP)

**Goal:** Eliminate laptop dependency. TX board carries GPS, logs distance
automatically. Walk freely with power bank only.

**Hardware needed:**
- GPS module (soldered to RP2040 board, UART NMEA 9600 baud)
- Free RP2040 pins: GP20/GP21 (Serial2 = UART1) for GPS RX/TX
- Power bank (USB 5V → RP2040 VBUS)

**Firmware phases:**

Phase 1 — GPS NMEA parsing (TX board):
- Read $GPGGA/$GPRMC sentences from GPS module over Serial2 (9600 baud)
- Parse lat/lon, store in struct
- Embed coordinates in TX packet payload (bytes 4-20: lat float, lon float, sat count)
- Reduce payload data bytes accordingly (255 - 12 = 243 data bytes)

Phase 2 — RX distance calculation (RX board, stays on computer):
- Extract GPS coords from received packets
- Compute distance from last known RX position (or fixed base station coords)
- Log per-packet: seq, rssi, lat, lon, distance_m
- Output: RANGE_RESULT_RX with gps_lat, gps_lon, distance_m fields

Phase 3 — Fully autonomous (both boards on power banks):
- RX logs to flash storage (RP2040 has 2MB flash, ~1MB free after firmware)
- Read back results via serial after test session
- No computer needed during test at all

**GPS module pinout (when soldered):**
```
GPS TX → RP2040 GP21 (UART1 RX)
GPS RX → RP2040 GP20 (UART1 TX)
GPS VCC → 3.3V
GPS GND → GND
```

**Test protocol with GPS:**
1. Both boards plugged into power banks
2. Walk with TX board, GPS acquires fix (~30s cold start)
3. TX transmits continuously, embedding current GPS position
4. RX logs every packet with timestamp + GPS position + RSSI
5. Post-test: dump RX flash, plot distance vs RSSI/loss curve
6. Continuous distance data — not just fixed points

**Priority:** After baseline phone-GPS distance sweep (Session 1). GPS firmware
is v2 enhancement for finer-grained data and laptop-free operation.

---

## TEST EXECUTION ORDER

### Session 1: Baseline + Distance (2 hours)
1. Verify current firmware still works (1m test, expect 0% loss)
2. Distance sweep outdoor LOS: 10m, 25m, 50m, 100m
3. Record all results in standard format
4. Commit results

### Session 2: Power + Packet Size (1 hour)
1. At 50m, sweep TX power: 0, 3, 6, 9, 12, 12.5 dBm
2. At 50m, sweep packet size: 16, 32, 64, 128, 255 bytes
3. Commit results

### Session 3: Modulation Comparison (2 hours)
1. Flash LoRa firmware to both boards
2. At 100m, test each LoRa mode
3. Compare with FLRC results
4. Commit results

### Session 4: Antenna + Frequency (1 hour)
1. At 50m, test different antennas
2. At 10m, sweep frequencies
3. Commit results

**Total: ~6 hours of testing across 4 sessions**

---

## DATA RECORDING FORMAT

Each test produces a line:

```
RANGE_TEST,date=2026-07-17,distance_m=50,power_dbm=12,pkt_size=255,\
mode=FLRC2600,freq_mhz=2440,antenna=wire_dipole,orientation=both_vert,\
packets_sent=1000,packets_rx=998,loss_pct=0.2,throughput_kbps=1377,\
notes=outdoor_LOS_parking_lot
```

Save to: docs/range-test-results-2026-07-XX.md

---

## FIRMWARE NEEDED

### Already available:
- `flrc_tx_raw.cpp` (rp2040-flrc-tx-raw env) — current TX, 1377 kbps
- `flrc_rx_raw.cpp` (rp2040-flrc-rx-raw env) — current RX, 0% loss
- `scripts/coordinated_tx_rx_test.py` — test harness

### Needs writing:
- TX firmware variant with configurable power (serial command)
- TX firmware variant with configurable packet size (serial command)
- LoRa mode firmware (both TX and RX)
- RSSI readback firmware (if LR2021 supports it)

### Configurable firmware approach:
Instead of reflashing for each parameter, write ONE firmware that accepts
serial commands to change power, packet size, and frequency at runtime.
This saves enormous time during testing.

Commands:
- `POWER 12` — set TX power to +12 dBm
- `PKTLEN 64` — set packet size to 64 bytes
- `FREQ 2422` — set frequency to 2422 MHz
- `COUNT 500` — send 500 packets
- `RUN` — start transmission

This is the highest-value firmware to write before range testing.

---

## SAFETY

- 2.4 GHz at +12 dBm (16 mW) — completely safe, no RF exposure concern
- Outdoor testing: bring water, sunscreen, charged boards
- USB cables: bring spares (CDC disconnects are common)
- Bring laptop with full battery for outdoor sessions
- Keep boards in anti-static bags when not testing

## SUCCESS CRITERIA

| Milestone | Target |
|-----------|--------|
| Baseline confirmed | 0% loss at 1m |
| Max FLRC range (known) | Distance where loss >10% |
| Max LoRa range (known) | Distance where loss >10% |
| Power vs range curve | At least 4 data points |
| Packet size vs range curve | At least 4 data points |
| Optimal antenna identified | Best antenna at 50m |
| Decision: FLRC vs LoRa for flight | Based on data |
