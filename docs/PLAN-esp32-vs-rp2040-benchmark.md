# BENCHMARK PLAN: ESP32-C3 vs RP2040 — LR2021 Throughput

**Created:** 2026-07-30
**Author:** balloon-speed-tests sub-manager
**Status:** READY — awaiting ESP32 hardware

## OBJECTIVE

Determine which MCU (ESP32-C3 vs RP2040) achieves higher sustained throughput
with the LR2021 radio in FLRC mode. This decision determines which MCU Felix
solders to the F33 PA board for production balloon trackers.

## RP2040 BASELINE (ALREADY CAPTURED)

Data is version-controlled in the repo. No re-capture needed.

| Metric | Value | Source |
|--------|-------|--------|
| SPI clock (actual) | 10.40 MHz | LA measurement |
| SPI clock (requested) | 20 MHz | platformio.ini |
| Clock utilization | 52% | RP2040 divider limit |
| Throughput (255B) | 1,760 kbps | bench-rp2040.sr |
| Throughput (32B) | 1,192 kbps | sweep-32.sr |
| Bus duty cycle | 18.3% | — |
| Inter-packet gap | 320 us | Air time (BUSY during TX) |
| Packets per 41.7ms | 107 | — |
| SPI cmds per packet | 3 (CLEAR_IRQ + WRITE_FIFO + SET_TX) | — |

Captures: `captures/bench-rp2040.sr`, `captures/sweep-{32,64,128,255}.sr`
Analysis: `docs/rp2040-baseline-results.md`, `docs/spi-timing-analysis.md`

**Key finding:** RP2040 is near-optimal. 320us gaps are air time (radio physics),
not firmware overhead. 10.40 MHz SPI is the RP2040 clock divider ceiling.

## ESP32-C3 HYPOTHESIS

ESP32-C3 `spi_master` driver with hardware DMA should achieve 20 MHz SPI clock
(RP2040 only hit 10.4 MHz). If true:
- SPI transfer time per packet drops ~50%
- But air time (320us) is fixed by radio physics
- Expected throughput: ~2,000-2,400 kbps (modest improvement, not 2x)

## METRICS TO CAPTURE

For each MCU × payload size:

| Metric | How to measure |
|--------|---------------|
| SPI clock (actual) | LA: measure SCK period |
| Effective throughput (kbps) | payload_bytes × 8 / total_time |
| Packet loss % | goodput script: seq gaps / expected count |
| Per-packet SPI time (CS-low) | LA: decode CS pulses |
| Inter-packet gap (us) | LA: time between CS-low edges |
| Bus duty cycle (%) | LA: active_time / total_time |
| RSSI at receiver | goodput script (if RX firmware reports) |

## TEST MATRIX

Each cell: 2 runs for variance check. 10-second goodput measurement per run.

| Payload | RP2040 Run 1 | RP2040 Run 2 | ESP32 Run 1 | ESP32 Run 2 |
|---------|-------------|-------------|------------|------------|
| 32 B    | 1192 kbps (baseline) | — | TBD | TBD |
| 64 B    | TBD (sweep-64.sr) | — | TBD | TBD |
| 128 B   | TBD (sweep-128.sr) | — | TBD | TBD |
| 255 B   | 1760 kbps (baseline) | — | TBD | TBD |

## PROCEDURE

### Phase 1: ESP32 LA Capture (SPI timing)

```bash
# 1. Ensure ESP32 cont-TX firmware is selected in menuconfig
cd firmware/esp32-c3-flrc
source ~/esp/esp-idf/export.sh
idf.py menuconfig
  # → Component config → FLRC Continuous TX → enable
  # → Payload size → 255 bytes
idf.py build

# 2. Flash to ESP32 board
idf.py -p /dev/ttyACM0 flash

# 3. Capture via logic analyzer
cd ~/worktrees/balloon-speed-tests
make capture-esp32 DURATION=1 OUTPUT=captures/bench-esp32.sr

# 4. Decode SPI
make decode-esp32 FILE=captures/bench-esp32.sr
```

### Phase 2: ESP32 Goodput (packet-level)

```bash
# TX board: ESP32 with cont-TX firmware
# RX board: ESP32 with RX firmware (main.cpp default mode)
python3 scripts/measure_goodput.py \
    --port /dev/ttyACM1 \
    --duration 10 \
    --payload-size 255
```

### Phase 3: Payload Sweep

Repeat Phase 1-2 for 32/64/128/255 byte payloads:
```bash
# For each payload size, rebuild with menuconfig, reflash, recapture
make capture-esp32 DURATION=1 OUTPUT=captures/sweep-esp32-32.sr
make capture-esp32 DURATION=1 OUTPUT=captures/sweep-esp32-64.sr
make capture-esp32 DURATION=1 OUTPUT=captures/sweep-esp32-128.sr
make capture-esp32 DURATION=1 OUTPUT=captures/sweep-esp32-255.sr
```

### Phase 4: Analysis + Comparison

Write results to `docs/esp32-vs-rp2040-results.md`:
- Side-by-side table for each metric × payload size
- Conclusion: which MCU wins, by how much
- Decision recommendation for F33 PA board

## DECISION CRITERIA

| ESP32 SPI Clock | Verdict | Action |
|----------------|---------|--------|
| > 15 MHz stable | ESP32 wins | Solder LR2021+F33 PA to ESP32-C3 |
| 12-15 MHz | Marginal | Weight other factors (power, size, complexity) |
| < 12 MHz or unstable | RP2040 stays | RP2040 already near-optimal at 10.4 MHz |

**Critical insight:** Even at 2x SPI clock, throughput gain is bounded by
radio air time (320us per packet at 2600 kbps air rate). SPI optimization
only reduces the 217us SPI portion, not the 320us air portion. Maximum
theoretical improvement: ~30-40%, not 2x.

## HARDWARE REQUIREMENTS

- ESP32-C3 Mini V1 dev board (×2 for TX+RX goodput test)
- NiceRF LoRa2021 module soldered to ESP32
- Logic analyzer (Saleae/fx2lafw, 8-channel, ≥24 MHz sample rate)
- Serial USB connection for UART stats output
- Board mutex lock (tools/balloon-board-lock.py) for shared board access

## SOFTWARE REQUIREMENTS

- ESP-IDF v5.4.1 (source ~/esp/esp-idf/export.sh)
- sigrok-cli with fx2lafw driver
- Python 3 + pyserial (for goodput script)
- BoardSerial wrapper (tools/board-serial.py)
