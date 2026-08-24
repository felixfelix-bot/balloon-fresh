# SPI Timing Comparison Status — ESP32-C3 vs RP2040 for LR2021

**Date:** 2026-08-05
**Status:** GAP ANALYSIS — RP2040 baseline complete, C3 capture pending

---

## Executive Summary

The RP2040 SPI timing baseline is fully captured and analyzed. The ESP32-C3 has
working firmware and a complete benchmark plan, but **no logic analyzer capture
has been performed**. The comparison cannot be completed until C3 captures are
taken with the logic analyzer.

---

## 1. What Exists for RP2040 (COMPLETE)

### Firmware
- `firmware/rp2040/src/flrc_spi_timing_diag.cpp` — Self-timing diagnostic that
  measures per-byte vs batch vs single-batch SPI transfers using RP2040's cycle
  counter (`time_us_32()`). Tests 3 transfer modes, 100 iterations each, reports
  ns/byte and speedup ratios. Includes debug trigger pin (GP14) for external
  scope/LA synchronization.
- `firmware/rp2040/build_pio2/dma_chain_tx.uf2` — Built continuous-TX firmware
  (81,920 bytes, dated Aug 1).
- `firmware/rp2040/sweep-tx-latest.uf2` — Payload sweep firmware (32/64/128/255B).
- RP2040 cont-tx firmware: 255-byte payload, FLRC 2600 kbps air rate, 3-command
  SPI pattern (CLEAR_IRQ → WRITE_TX_FIFO → SET_TX).

### Logic Analyzer Captures
All in `captures/` directory:
| File | Description | Size |
|------|-------------|------|
| `bench-rp2040.sr` | Official baseline capture (1s, 24 MHz) | 10,538 bytes |
| `sweep-32.sr` | 32-byte payload sweep | 7,973 bytes |
| `sweep-64.sr` | 64-byte payload sweep | 8,216 bytes |
| `sweep-128.sr` | 128-byte payload sweep | 9,107 bytes |
| `sweep-255.sr` | 255-byte payload sweep | 11,068 bytes |

### Analysis Documents
- `docs/spi-timing-analysis.md` — Full RP2040 timing analysis with optimization
  attempts (batched SPI failed, manual inline SPI worse). Documents root cause:
  320µs gaps are air time, not firmware overhead.
- `docs/rp2040-baseline-results.md` — Official benchmark reference with per-packet
  command breakdown and bottleneck analysis.

### RP2040 Baseline Results
| Metric | Value |
|--------|-------|
| SPI clock (actual) | 10.40 MHz (requested 20 MHz — 52% delivery) |
| SCK period | 96 ns |
| Transactions in 41.7ms | 107 |
| Avg CS-low duration | 72.4 µs |
| Avg inter-packet gap | 320.4 µs (mostly air time) |
| Bus duty cycle | 18.3% |
| **Effective throughput** | **1,760 kbps** |
| Active SPI throughput | 9,634 kbps |
| % of PHY max (2600 kbps) | 67.7% |

Per-packet SPI breakdown: CLEAR_IRQ (6.4µs) + WRITE_TX_FIFO (205.1µs) + SET_TX
(5.6µs) = 217.1µs total SPI time.

### Capture Tooling
- `scripts/capture_spi_timing.sh` — sigrok-cli capture script. Detects logic
  analyzer (fx2lafw/saleae/etc), captures at 24 MHz (2x oversampling), exports
  to CSV, runs quick SCK frequency + CS assertion count analysis. Channel map:
  D0=CS, D1=SCK, D2=MOSI, D3=MISO, D4=BUSY, D5=IRQ.
- `Makefile` target `debug-esp32` — One-command workflow: build C3 firmware
  with CONTINUOUS_TX → flash → auto-start TX → capture with sigrok.

---

## 2. What Exists for ESP32-C3 (PARTIAL — no captures)

### Firmware (WORKING)
- `firmware/esp32-c3-flrc/main/main.cpp` — Complete C3 FLRC raw SPI throughput
  test firmware. Has `CONTINUOUS_TX` CMake option for infinite TX loop (same
  3-command SPI pattern as RP2040). Configured for 20 MHz SPI, manual CS control
  (`spics_io_num = -1`), SPI2_HOST with DMA.
- `firmware/esp32-c3-flrc/build/esp32-c3-flrc.bin` — Built firmware binary
  (203,744 bytes, dated Jul 16). **NOTE: built WITHOUT CONTINUOUS_TX flag.**
  A rebuild with `-DCONTINUOUS_TX=1` is required for LA benchmark.
- `firmware/esp32-c3-flrc/CMakeLists.txt` — Has `option(CONTINUOUS_TX ...)`.
- Proven C3 performance (from code comments): **1,733 kbps, 1000/1000 packets
  at 20 MHz SPI** — but this is software-reported throughput, not LA-measured.

### Tracker Firmware (relay mode — different code path)
- `tracker/firmware/components/lr2021_transport/` — Production LR2021 transport
  layer for the tracker. `EspHalLr2021Radio` class uses identical SPI patterns
  (manual CS, 20 MHz, batched TX FIFO writes). This is the relay-mode radio
  driver, NOT a timing diagnostic.
- `tracker/firmware/main/EspHalC3.h` — RadioLib HAL adapter. Uses 2 MHz SPI
  clock (conservative — `devcfg.clock_speed_hz = 2000000`). This is a DIFFERENT
  SPI configuration than the benchmark firmware (20 MHz). The HAL is for
  RadioLib compatibility, not for throughput testing.
- No SPI timing instrumentation exists in tracker/firmware/.

### C3 Pin Mapping (from la-wiring-guide.md)
| Signal | ESP32-C3 GPIO |
|--------|---------------|
| CS (NSS) | GPIO10 |
| SCK | GPIO6 |
| MOSI | GPIO7 |
| MISO | GPIO2 |
| BUSY | GPIO4 |
| IRQ (DIO9) | GPIO5 |
| RST | GPIO3 |

### What's MISSING for C3
1. **No logic analyzer captures** — `captures/` has zero C3/ESP32 files.
2. **No LA-measured SPI clock** — C3 claims 20 MHz, but actual delivered clock
   is unverified. RP2040 requested 20 MHz but only got 10.4 MHz (divider issue).
3. **No LA-measured throughput** — The 1,733 kbps figure is software-reported
   via `esp_timer_get_time()`, not externally measured.
4. **No bus duty cycle measurement** — No external capture of CS-low timing.
5. **No inter-packet gap measurement** — Air time vs firmware overhead split
   is unknown for C3.
6. **CONTINUOUS_TX build not flashed** — Existing build lacks the flag. Need
   `idf.py -DCONTINUOUS_TX=1 build` + flash to a C3 board.

---

## 3. Logic Analyzer Comparison Plan

### Benchmark Plan (exists: `docs/plan-esp32-vs-rp2040-benchmark.md`)
7-task plan, status AWAITING APPROVAL as of 2026-07-30:

| Task | Description | Status |
|------|-------------|--------|
| 1 | ESP32-C3 CONTINUOUS_TX firmware | ✅ Code exists, needs rebuild with flag |
| 2 | Make targets for LA capture | ✅ `make debug-esp32` exists in Makefile |
| 3 | Capture RP2040 baseline | ✅ Done (`captures/bench-rp2040.sr`) |
| 4 | Capture ESP32-C3 #1 | ❌ Not done |
| 5 | Capture ESP32-C3 #2 | ❌ Not done |
| 6 | Analyze + document results | ❌ Blocked on Tasks 4-5 |
| 7 | MCU decision (>15% = switch) | ❌ Blocked on Task 6 |

### Comparison Metrics (identical methodology for both)
- SPI clock frequency (actual, measured from SCK edges)
- SPI transfer time per packet (CS-low duration)
- Inter-packet gap (air time + firmware overhead)
- Bus duty cycle (% time CS is low)
- Effective throughput (kbps)
- Packets per second

### Decision Threshold
- ESP32-C3 >15% faster than RP2040 (1,760 kbps baseline): switch to C3 for 2W board
- Within 15%: stay on RP2040 (dual-core advantage outweighs marginal gain)

---

## 4. What's Blocking

### Hardware
- **No logic analyzer connected.** `lsusb` shows no fx2lafw/Saleae/sigrok device.
  The captures in `captures/` were taken previously (Jul 30) but the LA hardware
  is not currently plugged in. The fx2lafw driver IS installed (sigrok-cli lists
  it as supported), so when the hardware is connected, captures can proceed.
- **ESP32-C3 board connectivity unknown.** Need to verify an ESP32-C3 with
  LR2021 is connected and functional before flashing CONTINUOUS_TX firmware.
- **LA probe rewiring required** — Probes are currently mapped to RP2040 pins.
  Must move 7 probes to C3 GPIO pins (documented in la-wiring-guide.md, ~5 min).

### Software
- **CONTINUOUS_TX rebuild needed** — Existing C3 binary was built Jul 16 without
  the flag. Must rebuild with `idf.py -DCONTINUOUS_TX=1 build`.
- **No analyze_spi.py script** — The benchmark plan references `analyze_spi.py`
  for automated analysis, but this script was not found in the repo. The capture
  script (`capture_spi_timing.sh`) has basic CSV analysis built in, but a
  dedicated comparison analyzer doesn't exist yet.

### Not Blocking
- sigrok-cli: ✅ installed at `/usr/bin/sigrok-cli`
- pulseview: ✅ installed at `/usr/bin/pulseview`
- fx2lafw driver: ✅ available in sigrok
- C3 firmware source code: ✅ complete with CONTINUOUS_TX support
- Makefile targets: ✅ `make debug-esp32` exists
- RP2040 baseline data: ✅ complete and analyzed

---

## 5. Recommended Next Steps

### Step 1: Connect Hardware (5 min)
1. Plug in logic analyzer (USB)
2. Verify: `lsusb | grep -i fx2` — should show Cypress FX2 device
3. Connect ESP32-C3 + LR2021 board to USB
4. Verify: `ls /dev/ttyACM* /dev/ttyUSB*` — identify C3 port (VID 303a)

### Step 2: Rewire LA Probes (5 min)
Move probes from RP2040 to ESP32-C3 per la-wiring-guide.md:
```
D0→GPIO10(CS)  D1→GPIO6(SCK)  D2→GPIO7(MOSI)  D3→GPIO2(MISO)
D4→GPIO4(BUSY)  D5→GPIO5(IRQ)  D6→GPIO3(RST)  GND→GND
```

### Step 3: Build + Flash C3 CONTINUOUS_TX (10 min)
```bash
cd ~/repos/balloon-fresh
source ~/esp/esp-idf/export.sh
cd firmware/esp32-c3-flrc
idf.py -DCONTINUOUS_TX=1 build
idf.py -p /dev/ttyUSB0 flash
# Verify: serial monitor shows "CONT_TX START" and incrementing counters
```

### Step 4: Capture C3 SPI Timing (5 min)
```bash
cd ~/repos/balloon-fresh
make debug-esp32 PORT=/dev/ttyUSB0 DURATION=1 OUTPUT=captures/bench-esp32-1.sr
# OR manually:
sigrok-cli --driver=fx2lafw \
  --channels=D0=CS,D1=SCK,D2=MOSI,D3=MISO,D4=BUSY,D5=IRQ \
  --config samplerate=24000000 \
  --output-file=captures/bench-esp32-1.sr \
  --time 1s
```

### Step 5: Analyze + Compare (15 min)
1. Open both captures in PulseView or use sigrok-cli
2. Measure for C3: SCK frequency, CS-low duration, inter-packet gap, bus duty
3. Create comparison table:
   | Metric | RP2040 | ESP32-C3 | Δ |
   |--------|--------|----------|---|
   | SPI clock | 10.40 MHz | ? | |
   | Throughput | 1,760 kbps | ? | |
   | Bus duty | 18.3% | ? | |
   | Inter-pkt gap | 320 µs | ? | |
4. Write `docs/spi-timing-comparison-results.md`
5. Decision: >15% improvement → switch; ≤15% → stay RP2040

### Step 6: Commit + Push
```bash
git add docs/SPI-TIMING-COMPARISON-STATUS.md docs/spi-timing-comparison-results.md captures/bench-esp32-*.sr
git commit -m "docs: SPI timing comparison — C3 vs RP2040 empirical results"
git push github autonomous/mesh-baseline
```

---

## 6. Key Observations

### SPI Clock Delivery (the critical unknown)
RP2040 requested 20 MHz but delivered only 10.40 MHz (52%) due to clock divider
rounding. ESP32-C3's GDMA-SPI peripheral is expected to deliver closer to the
requested 20 MHz. If C3 actually achieves 20 MHz SPI:
- SPI transfer time would halve: ~108µs vs 217µs
- Theoretical throughput ceiling: ~2,438 kbps (94% of PHY max)
- vs RP2040's 1,760 kbps = potential **38% improvement** → would exceed the
  15% threshold for MCU switch

### Theoretical Ceiling Analysis (from mcu-assessment)
```
Air time (fixed): 255 × 8 / 2600 kbps = 784µs per packet
Theoretical max: 255 × 8 / 784µs = 2,602 kbps

RP2040 current: 1,760 kbps = 67.7% of max
RP2040 with 20MHz SPI: ~2,438 kbps = 93.7% of max
ESP32-C3 with 20MHz SPI: ~2,438 kbps = 93.7% of max (if clock delivers)
```

### C3 HAL Discrepancy
The tracker firmware's `EspHalC3.h` (RadioLib HAL) uses **2 MHz** SPI, while the
benchmark firmware uses **20 MHz**. The production `EspHalLr2021Radio` transport
correctly uses 20 MHz with manual CS. Any throughput comparison must use the
benchmark firmware (20 MHz), not the tracker HAL.

---

## File Inventory

| File | Platform | Purpose | Status |
|------|----------|---------|--------|
| `docs/spi-timing-analysis.md` | RP2040 | Timing analysis + optimization | ✅ Complete |
| `docs/rp2040-baseline-results.md` | RP2040 | Official benchmark reference | ✅ Complete |
| `docs/mcu-assessment-rp2040-vs-esp32.md` | Both | Hardware comparison + theory | ✅ Complete |
| `docs/plan-esp32-vs-rp2040-benchmark.md` | Both | 7-task benchmark plan | ✅ Exists, Tasks 4-7 pending |
| `docs/la-wiring-guide.md` | Both | LA probe wiring for both MCUs | ✅ Complete |
| `docs/logic-analyzer-wiring-diagram.png` | Both | Visual wiring guide | ✅ Complete |
| `scripts/capture_spi_timing.sh` | Both | sigrok capture script | ✅ Complete |
| `firmware/rp2040/src/flrc_spi_timing_diag.cpp` | RP2040 | Self-timing diagnostic | ✅ Complete |
| `firmware/rp2040/build_pio2/dma_chain_tx.uf2` | RP2040 | Cont-TX firmware | ✅ Built |
| `firmware/esp32-c3-flrc/main/main.cpp` | C3 | Cont-TX firmware (needs flag) | ⚠️ Needs rebuild |
| `firmware/esp32-c3-flrc/build/esp32-c3-flrc.bin` | C3 | Built binary (no CONT_TX) | ⚠️ Stale build |
| `Makefile` (debug-esp32 target) | C3 | One-command workflow | ✅ Ready |
| `captures/bench-rp2040.sr` | RP2040 | Baseline LA capture | ✅ Complete |
| `captures/bench-esp32-*.sr` | C3 | C3 LA capture | ❌ Does not exist |
| `docs/spi-timing-comparison-results.md` | Both | Comparison results | ❌ Not yet created |