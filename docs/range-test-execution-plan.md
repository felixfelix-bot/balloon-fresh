# Comprehensive Range Test Plan — Execution Strategy

**Date:** 2026-07-16
**Track:** Range Testing
**Status:** PLANNING — ready for execution after configurable firmware

---

## 1. TEST SETUP ARCHITECTURE

### The Core Problem

Current harness requires one laptop connected to BOTH boards via USB.
USB practical limit is 3m passive, 5m with active cables. Range testing
goes to 100m+. Something has to change.

### Option A: Two Laptops (RECOMMENDED for initial sweeps)

```
[Person 1]                    [Person 2]
Laptop 1                      Laptop 2
  |                             |
  USB                           USB
  |                             |
  TX Board                    RX Board
  (battery optional)          (battery optional)
```

- TX side: Laptop runs a script that sends commands and captures TX_DONE stats
- RX side: Laptop captures all RX output, packet counts, RSSI
- Coordination: Signal via phone/walkie-talkie ("TX starting in 3...2...1...")
- Distance: Laser distance measure or GPS for precision

**Pros:** Full real-time visibility, can adjust params on the fly, proven setup
**Cons:** Need two people, two laptops

### Option B: Autonomous Boards (RECOMMENDED for data collection runs)

```
[Person 1 with laptop]
  |
  Configure TX + RX via serial, then disconnect
  |
  TX Board (battery)              RX Board (battery)
  Runs pre-programmed test        Logs results to flash
  LED blinks during TX            LED blinks on RX
```

After the run, reconnect RX to laptop, dump flash log.

**Pros:** One person, no laptop at far end, real-world battery operation
**Cons:** No real-time feedback, must retrieve and dump logs, can't adjust mid-test
**This is the mode that tests real flight conditions.**

### Option C: ESP32-C3 with WiFi Results (ADVANCED — future)

```
TX Board (RP2040 or ESP32)       RX Board (ESP32-C3)
  Battery powered                  Battery powered
                                   WiFi → MQTT/HTTP → phone/laptop
                                   Real-time RSSI + packet stats
```

ESP32-C3 has WiFi. RX board could serve a web page or send MQTT with
live results. Phone connects to ESP32 AP mode.

**Pros:** Real-time data with one person, no laptop at RX end
**Cons:** WiFi at 2.4 GHz may interfere with FLRC at 2.4 GHz. Must use 5 GHz WiFi or
ensure FLRC frequency is far from WiFi channel. Needs ESP32 firmware development.

---

## 2. DATA COLLECTION — WHAT TO CAPTURE

### Per-Packet Data (RX Side)

Every received packet should log:
- Sequence number (already implemented)
- Timestamp (millis)
- **RSSI in dBm** — available via radio_get_rssi() reading register 0x0AAB
- **SNR** — if LR2021 supports it (check GetPacketStatus register 0x03)
- Payload integrity (CRC pass/fail)

### Per-Test-Point Data

Each test configuration (distance, power, pktsize, etc.) records:

```
RANGE_TEST,
  date=YYYY-MM-DD,
  time=HH:MM:SS,
  test_id=N,
  distance_m=X,           # measured distance
  distance_method=GPS|laser|paced,  # how distance was measured
  power_dbm=Y,
  pkt_size=Z,
  mode=FLRC2600|FLRC1300|FLRC650|FLRC325|LoRaSF5|LoRaSF7|LoRaSF12,
  freq_mhz=F,
  antenna_tx=trace|wire61mm|pcb_yagi,
  antenna_rx=trace|wire61mm|pcb_yagi,
  orientation_tx=vertical|horizontal|rotating,
  orientation_rx=vertical|horizontal|rotating,
  height_tx_m=H,          # antenna height above ground
  height_rx_m=H,
  environment=indoor|outdoor_LOS|outdoor_obstructed|parking_lot|field,
  obstacles=none|trees|wall|building|metal,
  weather=clear|cloudy|rain,
  wifi_channel_scan=ch1,ch6,ch11,  # nearby WiFi channels
  packets_sent=N,
  packets_rx=M,
  loss_pct=P,
  rssi_min=X,             # weakest packet received
  rssi_max=X,             # strongest packet
  rssi_avg=X,             # mean RSSI
  rssi_stddev=X,          # RSSI variation
  throughput_kbps=K,
  notes=free_text
```

### Environmental Context

- **WiFi scan:** Run `iwlist scan` at each test location before testing
- **Temperature:** If sensor available (RP2040 has internal temp sensor on ADC4)
- **Battery voltage:** Log VSYS voltage to detect brownouts (ADC2 on GP28)

---

## 3. LOGGING AND DATA STORAGE

### RP2040 Flash Logging (BUILT-IN, NO EXTRA HARDWARE)

RP2040 Pico has 2MB flash. Firmware uses ~100KB. ~1.8MB available.

**Implementation:**
- Reserve last 64KB of flash (8 pages) for log storage
- Each log entry: fixed 128-byte struct (test config + results)
- Can store ~14,000 entries or ~500 test-point results with raw packet data
- Commands: `DUMP` (read all to serial), `CLEAR` (erase log), `LOGSTAT` (show usage)

**Write cycle concern:** RP2040 flash supports ~100K erase cycles per sector.
At 64KB (8 sectors), even writing 1 test/sector = 800 tests before wear.
Use wear leveling if doing thousands of tests. For our purposes: fine.

### UART Output (ALREADY WIRED)

The boards already have Serial1 on GP12 (TX) and GP13 (RX).
Currently used as ESP32 UART bridge. Can connect:
- USB-to-UART adapter for laptop-less logging
- ESP32-C3 as WiFi bridge to relay data
- GPS module for position logging

### SD Card (OPTIONAL — adds hardware)

If we want unlimited storage, a microSD module on SPI (but SPI is used
by radio). Would need second SPI bus (spi1) or bit-banged SPI.
NOT RECOMMENDED — adds complexity, flash logging is sufficient.

---

## 4. GPS — WORTH IT?

### For Range Testing: YES, MODERATELY USEFUL

**Value:**
- Precise distance measurement (GPS accuracy: 3-5m with NEO-6M, 1-2m with NEO-M8N)
- Better than pacing (±10% error) or estimation
- Logs exact coordinates for reproducibility

**Limitations:**
- Cold start: 30s-2min for first fix
- Needs clear sky view (doesn't work well indoors or under trees)
- 3-5m accuracy is borderline for short distances (10m test ± 3m GPS error)
- For 100m+ tests: GPS is great. For 10m tests: laser tape is better.

**Recommendation:** Use laser distance measure for <50m. GPS for >50m and flight tests.
A $3 GT-U7 or NEO-6M module can connect to RP2040 GP0/GP1 (free UART pins).
For range testing specifically, GPS is a "nice to have" not a "must have."

### For Flight Tests: MANDATORY

GPS is required for real balloon flights regardless. The range testing
GPS firmware work directly feeds into the flight tracker. So building
GPS support now is not wasted effort.

**GPS Module Options (inventory check needed):**
- GT-U7 (~$3, NEO-6M clone, UART 9600 baud)
- NEO-M8N (~$10, better accuracy, faster fix, UART 9600/38400 baud)
- ATGM336H (~$3, Chinese, BeiDou+GPS dual mode)

**RP2040 Wiring (free pins):**
```
GPS TX  → GP1 (RP2040 UART0 RX)  [or GP13 if UART1 free]
GPS RX  → GP0 (RP2040 UART0 TX)  [or GP12]
GPS VCC → 3.3V
GPS GND → GND
GPS PPS → GP9 (optional, for timing)
```

---

## 5. ESP32-C3 + LR2021 — SHOULD WE TEST IT?

### Short Answer: YES, BUT FOR DIFFERENT REASONS

The radio range depends on the LR2021 chip, antenna, and environment — NOT the MCU
driving it. The RP2040 and ESP32-C3 both just send SPI commands to the same radio.
Range should be identical.

**BUT there are important reasons to test ESP32 anyway:**

1. **Flight hardware is ESP32-C3, not RP2040.** The pico balloon tracker uses
   ESP32-C3 as MCU. We need to verify the radio works on the actual flight platform.

2. **SPI implementation differs.** ESP32 uses spi_master with hardware DMA. RP2040
   uses Arduino per-byte transfer. Different SPI timing could theoretically affect
   radio init or TX timing, though unlikely to change range.

3. **ESP32 has WiFi for data relay.** The RX board could serve real-time results
   over WiFi AP mode, eliminating need for laptop at RX end during range tests.

4. **ESP32 firmware already exists** (built by speed track, untested on hardware).
   Testing it during range testing validates two things at once.

### How To Test

Use ESP32-C3 on one end (TX or RX), RP2040 on the other. Run same baseline test
at 1m. If results match (0% loss, similar throughput), ESP32 is validated.

```
Test Matrix:
  A) RP2040 TX → RP2040 RX  (baseline, already proven)
  B) ESP32 TX  → RP2040 RX  (validate ESP32 TX path)
  C) RP2040 TX → ESP32 RX   (validate ESP32 RX path)
  D) ESP32 TX  → ESP32 RX   (full ESP32 link)
```

Only test A→D needs to be done once at 1m. If all pass, use whichever platform
is more convenient for range testing. ESP32-C3 with WiFi AP mode for real-time
data at the far end is the killer feature.

### ESP32 WiFi Interference Concern

ESP32-C3 WiFi operates at 2.4 GHz — same band as FLRC. If using WiFi for data
relay while testing FLRC, must ensure:
- WiFi on channel 1 (2412 MHz) while FLRC on 2440+ MHz, OR
- WiFi on channel 11 (2462 MHz) while FLRC on <2440 MHz, OR
- Turn off WiFi during FLRC TX bursts, transmit results between bursts

This is a test artifact we should measure, not assume.

---

## 6. CONFIGURABLE FIRMWARE DESIGN

### The Key Enabler

Instead of reflashing for every test parameter, write ONE firmware that accepts
serial commands. This is the single highest-value piece of work before outdoor testing.

### TX Firmware Commands

```
POWER 12        → Set TX power (0-12.5 dBm)
PKTLEN 64       → Set payload size (1-255 bytes)
FREQ 2440       → Set frequency (2400-2480 MHz)
COUNT 500       → Set number of packets to transmit
MODE FLRC2600   → Set modulation: FLRC2600, FLRC1300, FLRC650, FLRC325
DELAY 10        → Set inter-packet delay in ms (0=maximum rate)
RUN             → Start transmission with current parameters
STOP            → Abort current transmission
STATUS          → Report current configuration
LOGSTART        → Begin logging results to flash
LOGSTOP         → Stop logging
LOGDUMP         → Dump all logged data to serial
LOGCLEAR        → Erase flash log
HELP            → List all commands
```

### RX Firmware Commands

```
RUN             → Enter RX mode, start counting
STOP            → Exit RX mode, report summary
RSSI ON         → Enable per-packet RSSI logging
RSSI OFF        → Disable RSSI logging (faster)
STATUS          → Report current statistics (live count, loss, RSSI)
LOGSTART        → Begin logging to flash
LOGDUMP         → Dump flash log
LOGCLEAR        → Clear flash log
CLEAR           → Reset packet counters
MODE FLRC2600   → Match TX modulation
FREQ 2440       → Match TX frequency
```

### Autonomous Operation Protocol

1. Connect board to laptop, configure via serial
2. Send `AUTOSTART` command — board enters autonomous mode
3. Disconnect USB, connect battery
4. Board flashes LED 3x = "ready, waiting for trigger"
5. Press BOOTSEL button (or connect a pin to GND) = start test
6. LED solid during TX/RX, blinks per 100 packets
7. LED flashes 5x = test complete
8. Reconnect to laptop, `LOGDUMP` to retrieve results

---

## 7. EXECUTION PLAN — SESSION BY SESSION

### Session 0: Firmware Development (INDOOR, ~2 hours)

**Goal:** Build the configurable firmware and flash logging

1. Write `flrc_config_tx.cpp` — configurable TX with serial commands
2. Write `flrc_config_rx.cpp` — configurable RX with RSSI logging + flash storage
3. Flash both boards, test all commands at 1m
4. Verify RSSI readback works (radio_get_rssi at 1m should read ~-20 to -30 dBm)
5. Verify flash logging: run test, dump, verify data integrity
6. Commit and push

### Session 1: Baseline + First Distance Points (OUTDOOR, ~2 hours)

**Setup:** Two laptops, two people, laser distance measure

1. Indoor baseline: 1m, verify 0% loss and RSSI reading
2. Move outside, parking lot or open field
3. Distance sweep at +12 dBm, 255-byte packets, FLRC 2600:
   - 5m, 10m, 25m, 50m
4. At each distance: 1000-packet burst, record loss + RSSI
5. WiFi scan at test location (`iwlist scan` or phone WiFi analyzer)
6. Commit results

### Session 2: Extended Distance + Power Sweep (OUTDOOR, ~2 hours)

1. Continue distance sweep: 75m, 100m, 150m, 200m
2. At 50m (or wherever loss becomes measurable):
   - Power sweep: 0, 3, 6, 9, 12, 12.5 dBm
   - Record loss + RSSI at each power level
3. Find the "edge" — distance where loss crosses 1%, 5%, 10%, 50%
4. Commit results

### Session 3: Packet Size + Modulation (OUTDOOR, ~2 hours)

1. At 50m, sweep packet sizes: 16, 32, 64, 128, 255 bytes
2. At 100m, test FLRC 1300/650/325 kbps (lower bitrate = better sensitivity)
3. At 100m, test LoRa modes if firmware ready:
   - SF5 BW1250 (fastest LoRa)
   - SF7 BW312 (medium)
   - SF12 BW312 (max range)
4. Compare: FLRC 2600 at 100m vs FLRC 650 at 100m vs LoRa SF7 at 100m
5. Commit results

### Session 4: Antenna + Frequency + ESP32 (OUTDOOR, ~2 hours)

1. At 50m, test antenna configurations:
   - PCB trace (module built-in) vs wire dipole (61mm)
   - Both vertical (reference)
   - TX vertical, RX horizontal (polarization mismatch)
   - Rotating RX (simulate balloon spin)
2. At 10m, frequency sweep: 2400, 2412, 2422, 2440, 2462, 2480
   - Correlate with WiFi channel scan
3. ESP32-C3 validation: ESP32 TX → RP2040 RX at 1m, compare baseline
4. Commit results

---

## 8. DATA ANALYSIS

### Key Plots To Generate

1. **Distance vs Packet Loss** — the primary range curve
   - X axis: distance (m), Y axis: loss (%)
   - One curve per TX power level

2. **Distance vs RSSI** — signal strength decay
   - X axis: distance (m), Y axis: RSSI (dBm)
   - Should follow inverse-square law (−20 dB/decade in free space)

3. **TX Power vs Range at Fixed Loss** — how much power buys how much range
   - X axis: TX power (dBm), Y axis: distance where loss = 5% (m)

4. **Packet Size vs Loss at Fixed Distance** — does smaller = more reliable?
   - X axis: packet size (bytes), Y axis: loss (%)

5. **Modulation Comparison** — FLRC vs LoRa at same distance
   - Bar chart: loss % for each mode at 100m

6. **Frequency vs Loss** — WiFi interference impact
   - X axis: frequency (MHz), Y axis: loss (%)
   - Annotate with nearby WiFi channels

7. **Antenna Polarization Impact** — vertical vs horizontal vs rotating
   - Bar chart: loss % for each orientation at 50m

### Link Budget Validation

Compare measured RSSI vs theoretical:

```
RSSI_theoretical = TX_power + TX_antenna_gain - FSPL - RX_antenna_gain

FSPL(dB) = 20*log10(d) + 20*log10(f_MHz) + 32.44

At 2440 MHz:
  10m:  FSPL = 40.2 dB
  50m:  FSPL = 54.2 dB
  100m: FSPL = 60.2 dB
  500m: FSPL = 74.2 dB
```

If measured RSSI matches theory → free space propagation confirmed.
If RSSI is lower → multipath, obstruction, or antenna inefficiency.

---

## 9. HARDWARE SHOPPING LIST

### Already Have
- 2x RP2040 + LR2021 boards (proven)
- 2x ESP32-C3 Mini V1 (speed track using these)
- USB cables
- Laptop(s)

### Needed For Range Testing

| Item | Purpose | Priority | Cost |
|------|---------|----------|------|
| Laser distance measure (30m+) | Precise distance | HIGH | $15-30 |
| USB power banks (2x small) | Battery operation | HIGH | $10 each |
| Wire dipole antennas (2x, 61mm) | Better range than PCB trace | HIGH | $1 (DIY) |
| Phone with WiFi analyzer app | WiFi interference mapping | MEDIUM | $0 (have phone) |
| GPS module (GT-U7 or NEO-6M) | Distance logging | LOW | $3-5 |
| Walkie-talkies or phones | TX/RX coordination | LOW | $0 (have phones) |

### Antenna Construction

Wire dipole for 2440 MHz:
- Half-wavelength = c / (2f) = 3e8 / (2 * 2.44e9) = 61.5 mm
- Each element: ~30mm (quarter wave)
- Use solid copper wire (20-22 AWG), solder to U.FL or SMA pigtail
- Orientation: vertical for omnidirectional

---

## 10. RISK MITIGATION

| Risk | Mitigation |
|------|------------|
| Port swap after BOOTSEL | Always re-discover with udevadm |
| USB cable disconnect outdoors | Bring 3+ spare cables, tape connections |
| Battery dies mid-test | Log to flash continuously, check voltage before each run |
| WiFi interference varies | Scan WiFi before AND after each test point |
| Weather changes | Test within 2h window, note conditions |
| Board damage outdoors | Anti-static bags, handle carefully |
| 1200 baud BOOTSEL trigger | Never use 1200 baud, be careful with serial tools |
| Two agents flash same board | ALWAYS use balloon-board-lock.py mutex |

---

## 11. COMMIT AND DATA POLICY

After every outdoor session:
```bash
cd ~/worktrees/track-range-testing
git add docs/range-test-results-*.md
git commit -m "test: range test session N — [description]"
git push github track/range-testing
git push origin track/range-testing
```

Raw data (CSV lines) goes in `docs/range-test-results-YYYY-MM-DD.md`.
Analysis plots go in `docs/plots/` as PNG.
Analysis summary goes in `docs/range-test-analysis-YYYY-MM-DD.md`.

**No data is real until committed and pushed.**
