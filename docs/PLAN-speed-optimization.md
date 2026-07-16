# FLRC Throughput Optimization Plan — Breaking the 1391 kbps Ceiling

**Date:** 2026-07-16
**Status:** ACTIVE — Phase 0 (ESP32) built, Phase 1 (LA) pending hardware
**Repo:** balloon-fresh
**Depends on:** ESP32-C3 firmware (built), logic analyzer (pending connection)
**Blocks:** Nothing — runs in parallel with range testing

---

## 1. Objective

Maximize throughput on LR2021 FLRC link beyond the current 1391 kbps RP2040 ceiling.

Theoretical maximum: 2540 kbps (air-time limited at 2600 kbps FLRC bitrate, 255B payload).

---

## 2. Current State (2026-07-16)

### Verified Results
| Metric | Value |
|--------|-------|
| Throughput | 1391 kbps |
| TX packets | 1000/1000 TX_DONE |
| RX packets | 1018 received (0% loss) |
| End-to-end | Fully functional RF link |
| Platform | RP2040 Pico + Arduino SPI |

### Timing Breakdown (Real Hardware Data)
Source: `flrc_timing_profiler.cpp` on F242D, 100-packet run

| Operation | Avg µs | % of Total | Bytes |
|-----------|--------|------------|-------|
| CLR_IRQ | 14.3 | 1.0% | 6 |
| WRITE_FIFO | 517.3 | 35.3% | 257 |
| SET_TX | 13.8 | 0.9% | 5 |
| TX_DONE_WAIT | 919.1 | 62.7% | 0 |
| **TOTAL** | **1466.8** | **100%** | — |

### Per-Byte SPI Analysis
| Measurement | Time | Per-Byte |
|-------------|------|----------|
| 10 bytes contiguous | 22 µs | 2.20 µs/byte |
| 255 bytes contiguous | 517 µs | 2.03 µs/byte |
| 10 separate transactions | 54 µs | 5.40 µs/byte |

---

## 3. Bottleneck Analysis

### 3.1 TX_DONE_WAIT — 919 µs (62.7%) — NOT REDUCIBLE
- RF air time: 803 µs (2088 bits / 2.6 Mbps)
- Chip processing overhead: 116 µs (SET_TX → actual RF start)
- This is the LR2021 chip's internal latency. No software can reduce it.
- Only way to reduce: lower bitrate (more air time, worse) or smaller payload (fewer bits).

### 3.2 WRITE_FIFO — 517 µs (35.3%) — PRIMARY OPTIMIZATION TARGET
- 257 bytes at 2.03 µs/byte via Arduino `transfer()`
- At 12 MHz SPI, each byte should take 0.67 µs (8 bits / 12 MHz)
- Overhead: 1.36 µs/byte = 68% overhead from Arduino function call + transaction layer
- **Theoretical floor: 172 µs** (257 × 0.67 µs, true 12 MHz batch)
- **At 20 MHz: 103 µs** (257 × 0.4 µs)
- Potential savings: 345–414 µs per packet → throughput gain of 350–550 kbps

### 3.3 CLR_IRQ + SET_TX — 28 µs (1.9%) — MINOR
- Could save ~14 µs by batching commands or skipping CLR_IRQ

### 3.4 Theoretical Bounds
| Scenario | FIFO time | Total/packet | Throughput |
|----------|-----------|--------------|------------|
| Current (Arduino) | 517 µs | 1467 µs | 1391 kbps |
| Optimized SPI (12 MHz batch) | 172 µs | 1119 µs | 1823 kbps |
| Optimized SPI (20 MHz batch) | 103 µs | 1050 µs | 1943 kbps |
| Full pipeline (SPI overlaps air time) | 0 µs | 919 µs | 2219 kbps |
| Air time only | — | 803 µs | 2540 kbps |

---

## 4. Failed Approaches — DO NOT RETRY

| Approach | Result | Root Cause | Documented |
|----------|--------|------------|------------|
| PIO TX v1/v2 | Crashes CDC, hangs TX loop | PIO steals SPI peripheral, CDC USB stops | `flrc_pio_tx_v2.cpp` |
| PIO TX v3 (deferred print) | RF output but wrong seq numbers | Still crashes CDC, partial packets | `flrc_pio_tx_v3.cpp` |
| DMA batch transfer | No RF output | LR2021 BUSY timing incompatible with RP2040 DMA | `flrc_raw_tx_batch.cpp` |
| Dual-core RX | Cannot parallelize | RP2040 has ONE SPI bus, both cores share it | Platform analysis |
| Runtime SPI freq change | Breaks radio permanently | `spi_deinit()+spi_init()` tears down SPI, LR2021 never re-syncs | SPI sweep doc |
| Pico SDK `spi_write_blocking` | No improvement | Same peripheral, same speed as Arduino | Timing profiler |

---

## 5. Remaining Approaches (Ordered by Priority)

### 5.1 ESP32-C3 Hardware SPI DMA — HIGHEST PRIORITY
**Status:** Built, NOT YET TESTED. Firmware at `firmware/esp32-c3-flrc/main/main.cpp`.

- ESP32-C3 `spi_master` driver uses hardware DMA for batch transfers
- `spi_device_polling_transmit()` sends entire 257-byte buffer in one transaction
- 20 MHz SPI clock (ESP32 can actually achieve this, RP2040 caps at ~12 MHz)
- If this works: FIFO write drops from 517 µs to ~100 µs
- Expected throughput: ~1900–2000 kbps

**Test plan:**
1. Flash ESP32-C3 TX firmware to a board with LR2021 wired
2. Keep RP2040 8332 as RX
3. Run `coordinated_tx_rx_test.py` with ESP32 on TX port
4. Compare TX_DONE timing and RX packet count

**Risk:** ESP32 DMA might have same BUSY timing issue as RP2040. But ESP32's SPI hardware is completely different (dedicated DMA controller, no shared peripheral).

### 5.2 Logic Analyzer Waveform Capture — HIGH PRIORITY
**Status:** Script ready (`scripts/capture_spi_timing.sh`), LA hardware NOT connected.

- Capture exact CS/SCK/MOSI timing of working Arduino `transfer()`
- Identify: CS setup/hold time, inter-byte gap, SCK frequency
- Compare with PIO/DMA waveforms to find what breaks
- Use captured timing to write a correct PIO program

**Setup:**
- Connect logic analyzer probes to TX board (F242D): GP2–GP7 + GND
- Run timing profiler (`rp2040-timing-profiler` env) which toggles GP14 as scope trigger
- Capture with sigrok-cli at 24+ MHz sample rate

### 5.3 Command Batching — MEDIUM PRIORITY, LOW EFFORT
Merge CLR_IRQ + WRITE_FIFO + SET_TX into fewer SPI transactions.

Current: 3 separate transactions (3× CS toggle = ~15 µs overhead)
Proposed: 1 transaction for CLR_IRQ + SET_TX (concatenate command bytes)
Savings: ~10–14 µs/packet

### 5.4 Preamble Reduction — MEDIUM PRIORITY
Reduce preamble from 8 to 4 symbols.

Savings: ~30 µs air time per packet (reduces TX_DONE_WAIT from 919 to ~889 µs)
Risk: RX may fail to sync at longer distances or with interference

### 5.5 Skip Per-Packet CLR_IRQ — LOW PRIORITY
Clear IRQ once at start, then rely on IRQ pin edge detection.

Savings: 14 µs/packet
Risk: IRQ flag accumulation may cause false TX_DONE detection

### 5.6 Interrupt-Driven TX_DONE — LOW PRIORITY FOR THROUGHPUT
Replace IRQ pin polling with GPIO interrupt.

Does NOT improve throughput (still must wait 919 µs for air time).
Does reduce CPU usage (can do other work during TX_DONE_WAIT).
Useful for mesh relay where CPU must handle routing during TX.

### 5.7 Cyclone IV FPGA as SPI Master — RESEARCH, LOW PRIORITY
Use the Altera Cyclone IV FPGA board as a pure hardware SPI master.

- 50 MHz onboard oscillator → zero software overhead
- Deterministic hardware SPI at any frequency
- Would reveal the LR2021's TRUE maximum throughput
- Requires Quartus II toolchain setup (USB Blaster available)
- ~50 lines of Verilog for minimal SPI master

**Purpose:** diagnostic only. If FPGA achieves 2540 kbps but ESP32 can't, we know the bottleneck is the MCU's SPI implementation, not the radio chip.

---

## 6. Expected Results

| Approach | Expected Throughput | Confidence | Effort | Dependencies |
|----------|---------------------|------------|--------|--------------|
| ESP32 DMA | 1900–2000 kbps | Medium | Low (built) | Flash + test |
| LA → PIO fix | 1800–1900 kbps | Low-Medium | High | LA connected |
| Command batching | 1405 kbps | High | Low | None |
| Preamble 8→4 | 1410 kbps | Medium | Low | None |
| Skip CLR_IRQ | 1405 kbps | High | Low | None |
| FPGA bench | 2200–2540 kbps | Low | Very High | Quartus setup |

---

## 7. Decision Tree

```
START: Flash + test ESP32-C3 firmware
│
├── ESP32 DMA works? 
│   ├── YES → DONE. Use ESP32. Throughput ~2000 kbps.
│   │         Document, commit, proceed to range test with new firmware.
│   │
│   └── NO → Connect logic analyzer to RP2040
│             │
│             ├── LA shows timing issue?
│             │   ├── YES → Write corrected PIO program
│             │   │         ├── PIO works? → DONE. ~1900 kbps.
│             │   │         └── PIO fails → FPGA bench test
│             │   │           ├── FPGA achieves 2540 kbps? → Bottleneck = RP2040 SPI
│             │   │           └── FPGA also limited → Bottleneck = LR2021 chip
│             │   │
│             │   └── NO (waveform looks correct) → 
│             │       Problem is elsewhere. Investigate BUSY/IRQ timing.
│             │
│             └── LA not available → Apply minor optimizations:
│                   Command batching + preamble reduction + skip CLR_IRQ
│                   Expected: ~1410 kbps (marginal gain)
│                   Accept 1391 kbps as RP2040 ceiling, move to ESP32 permanently.
```

---

## 8. Firmware Status

### RP2040 Environments (platformio.ini)
| Env | Source | Status |
|-----|--------|--------|
| `rp2040-raw-tx` | `flrc_raw_tx.cpp` | VERIFIED (1391 kbps) |
| `rp2040-raw-rx` | `flrc_raw_rx.cpp` | VERIFIED (1018 RX, 0% loss) |
| `rp2040-raw-tx-20mhz` | same, 20MHz SPI | UNTESTED |
| `rp2040-raw-tx-batch` | `flrc_raw_tx_batch.cpp` | FAILED (no RF) |
| `rp2040-raw-tx-pipe` | pipelined variant | FAILED |
| `rp2040-pio-tx-v3` | `flrc_pio_tx_v3.cpp` | FAILED (partial RX, CDC crash) |
| `rp2040-timing-profiler` | `flrc_timing_profiler.cpp` | VERIFIED (timing data captured) |

### ESP32-C3 Firmware
| File | Status |
|------|--------|
| `firmware/esp32-c3-flrc/main/main.cpp` | BUILT OK, NOT TESTED |
| `firmware/esp32-c3-flrc/CMakeLists.txt` | OK |
| `firmware/esp32-c3-flrc/sdkconfig.defaults` | TX mode default |

Build: `source ~/esp/esp-idf/export.sh && cd firmware/esp32-c3-flrc && idf.py build`

---

## 9. Logic Analyzer Setup

### Hardware Connection
Connect logic analyzer probes to TX board (F242D, ACM0):

| LA Channel | RP2040 Pin | Signal |
|------------|------------|--------|
| CH0 | GP2 (pin 4) | SCK |
| CH1 | GP3 (pin 5) | MOSI |
| CH2 | GP4 (pin 6) | MISO |
| CH3 | GP5 (pin 7) | CS (NSS) |
| CH4 | GP6 (pin 9) | BUSY |
| CH5 | GP7 (pin 10) | IRQ (DIO9) |
| GND | Any GND | Ground |

Optional: CH6 to GP14 (pin 19) for scope trigger from timing profiler.

### Capture Command
```bash
# 6-channel capture at 24 MHz, 2M samples
sigrok-cli --driver=saleae-logic8 --config samplerate=24MHz --samples 2000000 \
  -P spi:cs=D3:mosi=D1:miso=D2:sck=D0 \
  -A spi=hex -o capture.csv

# Or interactive:
pulseview
```

### What to Look For
1. **CS setup time:** Falling edge of CS to first SCK edge — LR2021 needs minimum setup
2. **Inter-byte gap:** Time between last SCK edge of byte N and first SCK edge of byte N+1
3. **CS hold time:** Last SCK edge to rising edge of CS
4. **SCK frequency:** Measure actual clock (should be ~12 MHz, not 16 MHz)
5. **BUSY behavior:** When does BUSY go HIGH relative to CS/SCK?
6. **Compare working vs broken:** Capture Arduino transfer() first, then PIO TX, diff the waveforms

---

## 10. Parallelism with Range Test Track

This track focuses on **throughput** (kbps). The range test track focuses on **coverage** (meters).

- Both use the same RP2040 boards — coordinate flashing
- Speed track may produce new firmware that range track can re-test
- If ESP32 DMA works, range tests should re-run on ESP32 to compare range at higher bitrate

**No conflict:** Speed tests are bench-only (30 cm). Range tests are at distance. Can alternate.

---

## 11. Links

- [Timing Profile Data](flrc-timing-profile-2026-07-16.md)
- [Platform Analysis](flrc-platform-analysis-2026-07-16.md)
- [FLRC Final Summary](flrc-final-summary-2026-07-16.md)
- [Range Test Plan](PLAN-range-tests.md)
- [AGENTS.md](../AGENTS.md) — full pin maps, build commands, inventory
