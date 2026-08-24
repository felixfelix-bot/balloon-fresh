# HANDOVER — FLRC Speed Optimization Track

> **Paste this into a new context window / Signal group as the opening prompt.**

---

## You Are

You are an AI assistant (Hermes Agent) continuing work on the **balloon-fresh** project. Your track: **FLRC throughput optimization**. You break the 1391 kbps ceiling.

**WORKTREE:** `~/worktrees/balloon-speed-tests/` (branch: `speed-optimization`)
**All work goes in this worktree. Do NOT touch ~/repos/balloon-fresh/ — that's the main branch, another agent owns it.**
**Start here:** Read `docs/HANDOVER-speed-tests.md` and `docs/PLAN-speed-optimization.md` inside the worktree.

---

## What the Project Is

ESP32-C3 + NiceRF LR2021 (Semtech) pico balloon tracker + mesh internet transport. Solar/supercap powered. Target weight <14g. Using 2.4 GHz FLRC mode for high-speed data.

Full details: `AGENTS.md` in repo root.

---

## Current State (2026-07-16)

- **Throughput ceiling:** 1391 kbps on RP2040 (Arduino SPI)
- **Theoretical max:** 2540 kbps (air-time limited)
- **Bottleneck:** WRITE_FIFO takes 517 µs (35% of packet time) due to Arduino `transfer()` overhead
- **TX_DONE_WAIT:** 919 µs (63%) — RF air time, NOT reducible

### Timing Breakdown (Real Hardware Data)
| Operation | µs | % |
|-----------|-----|---|
| CLR_IRQ | 14 | 1% |
| WRITE_FIFO | 517 | 35% |
| SET_TX | 14 | 1% |
| TX_DONE_WAIT | 919 | 63% |
| **Total** | **1467** | **100%** |

### Per-Byte SPI
- Contiguous: 2.03 µs/byte (68% overhead over theoretical 0.67 µs)
- With CS toggle: 5.40 µs/byte

---

## What This Track Does

Find a way to send SPI data to the LR2021 faster:

1. **ESP32-C3 DMA test** (HIGHEST PRIORITY) — firmware built, not yet tested
2. **Logic analyzer capture** — pending LA hardware connection
3. **PIO fix** — after LA shows us what's wrong
4. **Minor optimizations** — command batching, preamble reduction

Full decision tree: `docs/PLAN-speed-optimization.md` Section 7.

---

## Hardware Setup

### RP2040 Boards
| Board | Serial | Role | Port |
|-------|--------|------|------|
| F242D | E663B035977F242D | TX | /dev/ttyACM0 |
| 8332 | E663B035973B8332 | RX | /dev/ttyACM3 |

### ESP32-C3 Boards
| Port | Board | Note |
|------|-------|------|
| /dev/ttyACM1 | ESP32-C3 #1 (MAC ...FB:18) | Has LR2021 wired? |
| /dev/ttyACM2 | ESP32-C3 #2 (MAC ...21:00) | Has LR2021 wired? |

### Logic Analyzer
- sigrok-cli installed and ready
- Capture script: `scripts/capture_spi_timing.sh`
- **NOT YET CONNECTED** — needs physical probe attachment

---

## Quick Start — First 3 Steps

### Step 1: Test ESP32-C3 DMA (HIGHEST IMPACT)
```bash
# Build already done. Flash to ESP32-C3 with LR2021 connected:
cd ~/repos/balloon-fresh/firmware/esp32-c3-flrc
source ~/esp/esp-idf/export.sh
idf.py -p /dev/ttyACM1 flash monitor

# ESP32 starts in TX mode, sends 1000 packets after 2s delay
# Use RP2040 8332 as RX to receive
```

If ESP32 TX_DONE count = 1000 and RX receives packets → DMA works, breakthrough achieved.

### Step 2: If ESP32 works — measure throughput
```bash
# Flash RP2040 RX
cd ~/repos/balloon-fresh/firmware/rp2040
pio run -e rp2040-raw-rx -t upload --upload-port /dev/ttyACM3

# Run coordinated test (ESP32 on ACM1 as TX, RP2040 on ACM3 as RX)
python3 scripts/coordinated_tx_rx_test.py
```

### Step 3: If ESP32 fails — set up logic analyzer
Connect LA probes to RP2040 TX board (F242D):
- CH0: GP2 (SCK), CH1: GP3 (MOSI), CH2: GP4 (MISO)
- CH3: GP5 (CS), CH4: GP6 (BUSY), CH5: GP7 (IRQ)

```bash
# Flash timing profiler
cd ~/repos/balloon-fresh/firmware/rp2040
pio run -e rp2040-timing-profiler -t upload --upload-port /dev/ttyACM0

# Capture waveform
sigrok-cli --driver=saleae-logic8 --config samplerate=24MHz --samples 2000000 \
  -P spi:cs=D3:mosi=D1:miso=D2:sck=D0 \
  -A spi=hex -o capture.csv
```

---

## Failed Approaches — DO NOT RETRY

| Approach | Why it failed |
|-----------|---------------|
| PIO TX v1/v2/v3 | Crashes USB CDC, hangs TX loop |
| DMA batch transfer | LR2021 BUSY timing incompatible with RP2040 DMA |
| Dual-core RX | RP2040 has ONE SPI bus, can't parallelize |
| Runtime SPI freq change | `spi_deinit()+spi_init()` breaks radio permanently |
| Pico SDK `spi_write_blocking` | Same speed as Arduino, no improvement |

---

## ESP32-C3 Firmware Details

**Location:** `firmware/esp32-c3-flrc/main/main.cpp`
**Build:** `source ~/esp/esp-idf/export.sh && cd firmware/esp32-c3-flrc && idf.py build`
**Status:** BUILT OK. Uses `spi_device_polling_transmit()` at 20 MHz.

Key difference from RP2040: ESP32's `spi_master` driver uses hardware DMA for the entire transfer buffer. If the LR2021 accepts it, FIFO write drops from 517 µs to ~100 µs.

**Pin mapping (ESP32-C3 Mini V1):**
```
GPIO6  = SCK
GPIO2  = MISO
GPIO7  = MOSI
GPIO10 = NSS (CS)
GPIO4  = BUSY
GPIO5  = DIO9 (IRQ)
GPIO3  = RST
GPIO8  = LED (active LOW)
```

---

## What the Other Track Is Doing

**Range test track** (separate Signal group) is working on:
- Distance/bitrate/payload sweeps with current firmware
- Environmental testing (walls, antennas, orientation)

**Board sharing:** Both tracks use the same RP2040 boards. Do NOT flash simultaneously. Coordinate access.

If speed track produces faster firmware, notify range track to re-test range at new bitrate.

---

## Key Documents

| Document | Purpose |
|----------|---------|
| `docs/PLAN-speed-optimization.md` | **YOUR PRIMARY PLAN** — approaches, decision tree, expected results |
| `docs/PLAN-range-tests.md` | What the other track is doing |
| `docs/flrc-timing-profile-2026-07-16.md` | Real timing data from hardware |
| `docs/flrc-platform-analysis-2026-07-16.md` | Why approaches failed, bottleneck analysis |
| `docs/flrc-final-summary-2026-07-16.md` | Overall progress summary |
| `AGENTS.md` | Full project context, pin maps, inventory |
| `docs/breadboard-wiring-guide.md` | How boards are wired |

---

## Theoretical Bounds

| Scenario | FIFO time | Total/packet | Throughput |
|----------|-----------|--------------|------------|
| Current (Arduino) | 517 µs | 1467 µs | 1391 kbps |
| ESP32 DMA @ 20 MHz | ~100 µs | ~1050 µs | ~1940 kbps |
| Absolute ceiling | 0 µs | 919 µs | 2219 kbps |
| Air time only | — | 803 µs | 2540 kbps |
