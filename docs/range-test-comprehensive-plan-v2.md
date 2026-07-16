# Comprehensive Range Testing Plan (2026-07-17)

## PURPOSE

Systematically characterize the LR2021 FLRC radio link across all parameters
affecting range, reliability, and real-world performance. This data informs
antenna design, power budget, flight planning, and mesh network topology.

---

## PART 1: TEST SETUP ARCHITECTURE

### Do I Need a Computer on Both Ends?

**No.** The current TX firmware auto-starts transmission on power-up. A USB
battery pack is sufficient to run TX autonomously — no laptop needed at the TX
end for the default 1000-packet burst.

**Recommended setup: One laptop at RX, battery-powered TX.**

```
                 [USB Battery Pack]
                        |
                  [TX Board + LR2021]
                        |
                   (wire antenna)
                        |
                    ~ ~ AIR ~ ~
                        |
                   (wire antenna)
                        |
                  [RX Board + LR2021]
                        |
                   [USB Cable]
                        |
                   [Laptop]
                  (serial capture)
```

The laptop at RX:
1. Powers the RX board
2. Sends "RUN" command to start listening
3. Captures serial output with packet counts, loss %, throughput
4. Records all data

The TX board:
1. Powered by any USB power source (battery pack, wall adapter, car USB)
2. Auto-starts 1000-packet burst 3 seconds after power-on
3. No serial connection needed (but available if laptop is present)

### To What Extent Can This Be Done Without a Computer?

**Phase 1 (now): One laptop required.** The RX board must be connected to a
computer to read serial output and record results.

**Phase 2 (upgrade): Fully autonomous logging.** Write RX firmware that stores
results in RP2040 flash memory or outputs via UART to an ESP32 relay. Then both
boards run off batteries and results are read after the test. This requires
firmware development (see FIRMWARE section below).

**Phase 3 (flight-like): ESP32-C3 autonomous.** The ESP32-C3 can host a WiFi
AP or connect to a phone hotspot. Results displayed on phone browser. No laptop
at all. This is the ultimate goal but requires the ESP32-C3+LR2021 link to be
verified first.

### Can We Cache / Log Data?

Three logging tiers, in order of implementation priority:

**Tier 1: Serial capture (CURRENT — ready now)**
- RX firmware outputs structured results over USB serial
- Laptop captures with `cat /dev/ttyACMX > results.txt` or the test harness script
- Already working, already proven

**Tier 2: UART relay + SD/flash (requires firmware work)**
- RX firmware outputs results over UART (GP12/GP13) to an ESP32
- ESP32 logs to SD card or SPIFFS flash
- Both boards battery-powered, no laptop during test
- Read SD card after test

**Tier 3: WiFi telemetry (requires ESP32-C3+LR2021 verification)**
- ESP32-C3+LR2021 as RX, connects to phone hotspot
- Results POSTed to a simple HTTP endpoint or displayed on phone
- Real-time monitoring on phone screen
- GPS coordinates attached automatically

### Would GPS on One End Help?

**YES — for three specific scenarios:**

1. **Static tests (moderate value):** GPS gives precise distance between TX and
   RX positions. More accurate than pace-counting or estimation. Also records
   elevation (height above sea level), useful for elevated tests.

2. **Moving tests (high value):** Walk/drive while measuring. GPS logs speed,
   position, time. Without GPS, moving tests are nearly impossible to quantify
   (you don't know distance at each moment).

3. **Reproducibility (high value):** GPS coordinates allow anyone to return to
   the exact same test location and reproduce results. Critical for scientific
   validity.

**Implementation:**
- Phone GPS is sufficient for static tests (standalone GPS app, record position
  at each test point, note coordinates in data)
- Dedicated GPS module (NEO-6M or similar, ~$3, connects to ESP32 UART) would
  enable automated distance logging for moving tests
- GPS module is already planned for the tracker payload

**Recommendation:** Start with phone GPS for static tests. Add dedicated GPS
when we reach the moving/mobile test phase.

### Would It Make Sense to Test with ESP32-C3 + LR2021?

**YES — absolutely. Three reasons:**

1. **It is the actual flight platform.** The balloon tracker uses ESP32-C3, not
   RP2040. Range data from RP2040 may not perfectly represent flight performance
   due to different SPI characteristics, RF layout, ground plane, etc.

2. **Isolates MCU effects from radio effects.** If we test both RP2040+LR2021
   and ESP32-C3+LR2021 at the same distance/power/frequency, any difference
   reveals how much the host MCU and PCB layout affect range. This is valuable
   engineering data.

3. **ESP32-C3 enables autonomous operation.** WiFi for wireless data logging,
   GPS for position, lower power consumption. The ESP32-C3 is the path to
   field-deployable range testing.

**BUT:** The ESP32-C3+LR2021 firmware (firmware/esp32-c3-flrc/) is BUILT but
NEVER TESTED on hardware. We need to verify it works at bench distance first.

**Plan:** After RP2040 baseline range data is collected, test ESP32-C3+LR2021
at the same distances for direct comparison. This becomes Phase 6.

---

## PART 2: DATA COLLECTION — WHAT TO CAPTURE

### Per-Test-Point Data Record

Every single test point records ALL of the following:

**RF Parameters (controlled):**
| Field | Example | Source |
|-------|---------|--------|
| distance_m | 50 | Measured (tape/GPS) |
| power_dbm | 12 | Firmware config |
| pkt_size | 255 | Firmware config |
| mode | FLRC2600 | Firmware config |
| freq_mhz | 2440 | Firmware config |
| antenna_tx | wire_dipole_61mm | Physical |
| antenna_rx | wire_dipole_61mm | Physical |
| orientation_tx | vertical | Physical |
| orientation_rx | vertical | Physical |

**Results (measured):**
| Field | Example | Source |
|-------|---------|--------|
| packets_sent | 1000 | TX firmware (via DEADBEEF marker) |
| packets_rx | 998 | RX firmware count |
| loss_pct | 0.2 | Calculated |
| throughput_kbps | 1377 | RX firmware |
| rssi_dbm | -65 | LR2021 register 0x0AAB |
| per_sequence | "1,2,3,5,6,8,9..." | RX firmware (which packets lost) |

**Environmental (contextual):**
| Field | Example | Source |
|-------|---------|--------|
| environment | outdoor_LOS | Observer |
| obstacles | none | Observer |
| temp_c | 24 | RP2040 internal temp sensor (ADC ch4) |
| wifi_channels_busy | "1,6,11" | `iwlist scan` on laptop |
| timestamp | 2026-07-17T14:30:00Z | Laptop clock |
| gps_lat | 32.1234 | Phone GPS (if available) |
| gps_lon | -110.9876 | Phone GPS (if available) |
| gps_alt_m | 730 | Phone GPS (if available) |
| tx_height_m | 1.2 | Measured |
| rx_height_m | 1.2 | Measured |
| notes | parking_lot_pavement | Observer |

### RSSI Readback (NEW — needs firmware addition)

The LR2021 supports RSSI readback via register 0x0AAB:
```c
// Read RSSI from LR2021
// Register address: 0x0AAB
// Returns signed int8, RSSI = value / -2.0 dBm
uint8_t rssi_raw;
read_reg16(0x0AAB, &rssi_raw, 1);
float rssi_dbm = (float)(int8_t)rssi_raw / -2.0f;
```

This already exists in `firmware/rp2040/src/radio.cpp` (radio_get_rssi function).
We need to integrate it into the RX firmware and log per-packet RSSI.

RSSI gives us:
- Signal strength at each distance → propagation model
- Signal-to-noise estimation (compare to baseline noise floor)
- Packet loss correlation with RSSI threshold
- Antenna orientation effect quantification

### Packet Loss Pattern Analysis (NEW — needs firmware addition)

Currently the RX firmware counts total received and unique packets. We should
also log the SEQUENCE NUMBERS of received packets. This reveals:
- Random losses (individual packets dropped) — noise/interference
- Burst losses (consecutive packets lost) — fades, obstructions
- Periodic losses (every Nth packet lost) — timing/concurrency issue
- Beginning/end losses — TX/RX startup synchronization

**Implementation:** Store received sequence numbers in a bitmap or log first
100 sequence numbers, then log gaps.

---

## PART 3: FIRMWARE NEEDED

### Priority 1: Configurable Range Test TX (flrc_range_tx.cpp)

New firmware based on flrc_raw_tx.cpp that accepts serial commands for runtime
parameter changes. Also auto-starts with last-known configuration on power-up.

**Serial commands:**
```
POWER 12        Set TX power (0, 3, 6, 9, 12, 12.5 dBm)
PKTLEN 127      Set packet size (16-255 bytes)
FREQ 2422       Set frequency (2400-2500 MHz)
COUNT 500       Set packet count
INTERVAL 0      Set inter-packet delay (0=fastest, ms)
MODE FLRC2600    Set modulation mode (FLRC2600/1300/650/325, LORA_SF5_BW1250, etc.)
RUN             Start transmission burst
STATUS          Print current configuration
```

**Auto-start behavior:**
- On power-up: wait 5 seconds (let user position board), then auto-transmit
  with current (or default) configuration
- LED blink pattern indicates: ready (slow blink), transmitting (fast blink),
  done (solid on)

**Key design:**
- Store last configuration in RP2040 flash (survives power cycle)
- After burst completes, print structured results: "TX_RESULT,sent=1000,elapsed_ms=1493"
- Accept new parameters via serial between bursts

### Priority 2: Enhanced Range Test RX (flrc_range_rx.cpp)

New firmware based on flrc_raw_rx.cpp with additions:

**New features:**
- RSSI readback per packet (register 0x0AAB)
- Packet sequence logging (first 50 + all gaps)
- Temperature readback (RP2040 ADC channel 4)
- Auto-restart RX after burst received (wait for next RUN command)
- Structured CSV output for easy parsing

**Output format per received packet:**
```
PKT,seq=42,rssi=-67,temp=24.3
```

**End-of-burst summary:**
```
RX_RESULT,rx=998,unique=998,lost=2,total=1000,loss_pct=0.2,rssi_avg=-67,rssi_min=-72,rssi_max=-58,throughput_kbps=1377,temp=24.3,elapsed_ms=1493
```

### Priority 3: Autonomous Logging Mode (Phase 2)

If we reach the phase where both boards run off batteries:
- RX stores results in RP2040 flash (last 100 test results)
- TX auto-starts, auto-repeats with configurable delay between bursts
- Read results later by connecting RX to laptop and sending "DUMP" command

### Priority 4: LoRa Mode Firmware

For the modulation comparison phase, we need firmware that can switch between
FLRC and LoRa modes. This requires different radio init sequences:

| Mode | Bitrate | Sensitivity | Range (expected) |
|------|---------|-------------|-----------------|
| FLRC 2600 | 2600 kbps | ~-95 dBm | Short (bench-100m) |
| FLRC 1300 | 1300 kbps | ~-98 dBm | Medium |
| FLRC 650 | 650 kbps | ~-101 dBm | Medium-far |
| FLRC 325 | 325 kbps | ~-104 dBm | Far |
| LoRa SF5 BW1250 | ~122 kbps | ~-107 dBm | Far |
| LoRa SF7 BW312 | ~0.9 kbps | ~-120 dBm | Very far |
| LoRa SF12 BW312 | ~0.02 kbps | ~-135 dBm | Maximum |

Note: LoRa modes require different packet params, sync word, and modulation
register settings. RadioLib supports both modes, so we can use RadioLib init
for LoRa mode and raw SPI for the hot loop.

---

## PART 4: TEST EXECUTION PLAN

### Session 1: Baseline Verification + Initial Distance (2 hours)

**Setup:** One laptop at RX, USB battery at TX, bench → 10m

1. **Flash configurable TX** to F242D (serial E663B035977F242D)
2. **Flash enhanced RX** to 8332 (serial E663B035973B8332)
3. **Bench test (0.5m):** Confirm 0% loss, verify RSSI readback works
4. **1m test:** Record baseline RSSI, confirm 0% loss
5. **5m test:** Record RSSI, packet loss
6. **10m test (outdoor LOS):** Record RSSI, packet loss
7. Record all data in standard format
8. Commit and push results

**Deliverable:** Confirmed baseline + first distance data points

### Session 2: Distance Sweep (2-3 hours, outdoor)

**Setup:** One laptop at RX, battery TX, tape measure or GPS

Test matrix at each distance (1000 packets per test):

| Distance | Config | Expected |
|----------|--------|----------|
| 10m | FLRC2600, 255B, +12dBm | 0% loss |
| 25m | FLRC2600, 255B, +12dBm | 0-1% loss |
| 50m | FLRC2600, 255B, +12dBm | 0-5% loss |
| 100m | FLRC2600, 255B, +12dBm | 5-50% loss? |
| 200m | FLRC2600, 255B, +12dBm | High loss? |

**At each distance:**
1. Position TX (waist height, antenna vertical, battery powered)
2. Walk to RX position with laptop
3. Record GPS coordinates (phone)
4. Send "RUN" to RX, trigger TX
5. Capture results (serial output)
6. Record environmental notes (obstacles, WiFi, weather)
7. Move to next distance

**Deliverable:** Distance vs packet loss curve + RSSI vs distance curve

### Session 3: Power + Packet Size Sweep (1-2 hours, outdoor)

Fix distance at the point where we see 5-10% loss (from Session 2 data).

**Power sweep (at fixed distance):**
| Power | Packets | Expected |
|-------|---------|----------|
| 0 dBm | 1000 | Higher loss |
| +3 dBm | 1000 | Moderate loss |
| +6 dBm | 1000 | Lower loss |
| +9 dBm | 1000 | Low loss |
| +12 dBm | 1000 | Lowest loss |
| +12.5 dBm | 1000 | Marginally better |

**Packet size sweep (at fixed distance, +12 dBm):**
| Size | Packets | Expected |
|------|---------|----------|
| 16 bytes | 1000 | Lowest loss (shortest air time) |
| 32 bytes | 1000 | Low loss |
| 64 bytes | 1000 | Low-moderate loss |
| 128 bytes | 1000 | Moderate loss |
| 255 bytes | 1000 | Highest loss |

**Deliverable:** Power vs range curve + packet size vs loss curve

### Session 4: Modulation Comparison (2-3 hours, outdoor)

Fix distance at 100m (or wherever FLRC2600 shows significant loss).

| Mode | Packets | Time | Expected Range |
|------|---------|------|----------------|
| FLRC 2600 | 1000 | ~2s | Baseline |
| FLRC 1300 | 1000 | ~4s | 1.4x further |
| FLRC 650 | 1000 | ~8s | 2x further |
| FLRC 325 | 1000 | ~16s | 2.8x further |
| LoRa SF5 BW1250 | 100 | ~30s | 3-5x further |
| LoRa SF7 BW312 | 100 | ~15min | 10x+ further |
| LoRa SF12 BW312 | 10 | ~15min | Maximum |

Note: LoRa modes are MUCH slower. Send fewer packets.

**Deliverable:** FLRC vs LoRa range comparison → mode selection for flight

### Session 5: Antenna + Frequency (1-2 hours, outdoor)

**Antenna sweep at 50m:**
| TX Antenna | RX Antenna | Orientation | Expected |
|------------|-----------|-------------|----------|
| PCB trace | PCB trace | Both vertical | Baseline |
| Wire dipole | Wire dipole | Both vertical | Better |
| Wire dipole | Wire dipole | TX vert, RX horiz | Polarization loss |
| Wire dipole | Wire dipole | TX vert, RX rotating | Balloon simulation |

**Frequency sweep at 10m:**
| Frequency | WiFi Channel | Expected |
|-----------|-------------|----------|
| 2400 MHz | Ch1 edge | Some interference |
| 2412 MHz | Ch1 center | High interference |
| 2422 MHz | Ch3 | Moderate |
| 2440 MHz | Ch9 | Low interference |
| 2462 MHz | Ch11 center | High interference |
| 2480 MHz | Ch14 edge | Low interference |

Before frequency tests: `iwlist scan` to map local WiFi landscape.

**Deliverable:** Antenna comparison + frequency interference map

### Session 6: ESP32-C3 Platform Comparison (2-3 hours)

After RP2040 baseline data is complete:

1. **Verify ESP32-C3+LR2021 link at bench** (0.5m, confirm packets received)
2. **Repeat key distance tests with ESP32-C3 as TX** (10m, 50m, 100m)
3. **Compare RSSI between platforms** at same distance/power
4. **If ESP32-C3 has WiFi logging:** test autonomous operation (phone-only)

**Deliverable:** RP2040 vs ESP32-C3 range comparison

### Session 7: Mobile + Flight Simulation (future)

Requires GPS module and moving platform:
- Walking test (5 km/h) with GPS distance logging
- Driving test (30 km/h)
- Elevated test (second floor / roof)
- Rotating antenna (slow rotation, balloon spin simulation)

---

## PART 5: PHYSICAL SETUP GUIDE

### What to Bring (Per Outdoor Session)

**Electronics:**
- 2x RP2040+LR2021 boards (TX and RX)
- 1x USB battery pack (5000mAh+ for TX)
- 1x USB cable for RX → laptop
- 1x USB cable for TX → battery (or use battery's built-in cable)
- 2x wire dipole antennas (λ/2 = 61mm at 2440 MHz, 20AWG solid core wire)
- Spare USB cables (CDC disconnects happen)

**Measurement:**
- 1x Laptop (full battery, ~3h runtime)
- 1x Phone (GPS, WiFi scan, timer)
- 1x Tape measure (30m+) or laser distance meter

**Documentation:**
- Notebook or phone notes app
- Anti-static bags for transport
- Clipboard or hard surface for laptop

### Antenna Construction

Wire dipole for 2440 MHz:
- λ = c/f = 3×10⁸ / 2.44×10⁹ = 123mm
- λ/2 = 61.5mm per element
- Two 61.5mm pieces of 20AWG solid copper wire
- Solder one to signal pin, one to ground, 180° apart
- Vertical orientation = element pointing up/down

### Physical Positioning Rules

1. **TX height:** 1.2m (waist height) on non-conductive stand or held
2. **RX height:** 1.2m (waist height), laptop on ground or held
3. **Antenna clearance:** >30cm from metal objects, body, laptop chassis
4. **Body positioning:** Operator stands behind board, not between TX and RX
5. **Orientation:** Both antennas vertical unless testing polarization

---

## PART 6: DATA ANALYSIS

### Propagation Model

From RSSI vs distance data, fit to log-distance path loss model:

```
RSSI(d) = RSSI(d0) - 10*n*log10(d/d0) - Xσ
```

Where:
- d0 = reference distance (1m)
- n = path loss exponent (2=free space, 2.7-3.5=typical outdoor)
- Xσ = shadow fading (Gaussian random variable)

This model predicts range at any power level and any packet loss threshold.

### Key Decision Criteria

| Question | Answer comes from | Threshold |
|----------|-------------------|-----------|
| Max FLRC2600 range? | Distance sweep | Loss > 10% |
| Best power for 100m? | Power sweep | Loss < 5% |
| Best packet size? | Size sweep | Best throughput at acceptable loss |
| FLRC vs LoRa? | Modulation comparison | Range at acceptable throughput |
| Is ESP32-C3 equivalent? | Platform comparison | < 3dB RSSI difference |
| Best antenna? | Antenna sweep | Lowest loss at fixed distance |
| Clearest frequency? | Frequency sweep | Lowest loss + lowest RSSI variance |

---

## APPENDIX: LR2021 RSSI REFERENCE

RSSI readback via register 0x0AAB (from radio.cpp):
```c
uint8_t rssi_raw;
read_reg16(0x0AAB, &rssi_raw, 1);
float rssi_dbm = (float)(int8_t)rssi_raw / -2.0f;
// Example: rssi_raw=0xC2 (=-62) → rssi_dbm = -62/-2 = -31 dBm? No...
// Actually: (int8_t)0xC2 = -62, then / -2.0 = +31 → wrong sign
// Correct interpretation: rssi_dbm = -(int8_t)rssi_raw / 2.0
// So 0xC2 = -62, → -62/2 = -31 dBm
// Need to verify exact formula against datasheet
```

**IMPORTANT:** RSSI formula needs verification on hardware before relying on
absolute values. Relative trends (more negative = weaker signal) are reliable
even if absolute calibration is off.
